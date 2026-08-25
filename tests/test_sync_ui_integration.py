"""Tests for the offline-first sync UI integration (Phase 4b).

Covers:
- SyncEngine wiring: constructing the engine with a fake ApiClient + temp DB
  works; start()/stop() don't crash.
- Status indicator updates on sync_status_changed (SyncStatusLabel + engine
  signal wiring).
- Conflict journal dialog: list_unresolved shows recorded conflicts;
  mark_resolved works.
- Keep-local / Take-server logic: take-server applies server_payload to the
  local row + marks resolved.
- main.py wiring: setup_sync() builds the engine and wires it to a window
  without crashing (offline-safe).
"""
from __future__ import annotations

import os
import tempfile

import pytest

from database.db_manager import DatabaseManager
from services.sync_conflict_service import SyncConflictService
from services.sync_engine import SyncEngine
from services.sync_outbox_service import SyncOutboxService
from services.sync_pull_service import SyncPullService


class FakeApiClient:
    """Stub ApiClient with canned push/pull responses (same contract as
    ``tests/test_sync_engine.py``)."""

    def __init__(self, online=True, push_handler=None, pull_responses=None):
        self.online = online
        self.push_handler = push_handler
        self.pull_responses = pull_responses or {}
        self.push_calls = []
        self.pull_calls = []

    def is_online(self):
        return self.online

    def post(self, path, json=None):
        self.push_calls.append((path, json))
        if self.push_handler is not None:
            return self.push_handler((json or {}).get("items") or [])
        return {"results": []}

    def get(self, path, params=None):
        self.pull_calls.append((path, params))
        entity = (params or {}).get("entity")
        return {
            "records": self.pull_responses.get(entity, []),
            "next_after_id": 0,
            "has_more": False,
        }


@pytest.fixture
def db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def db(db_path):
    _db = DatabaseManager(db_path)
    yield _db
    try:
        _db.close()
    except Exception:
        pass


def _make_engine(db, fake, interval_seconds=60):
    outbox = SyncOutboxService(db)
    pull = SyncPullService(db, fake)
    return SyncEngine(db, fake, outbox, pull, interval_seconds=interval_seconds)


def _insert_client(db, name="Local Client"):
    cur = db.conn.execute(
        "INSERT INTO clients (name, created_at, updated_at) "
        "VALUES (?, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')",
        (name,),
    )
    db.conn.commit()
    return cur.lastrowid


def _record_id_map(db, entity_type, local_id, server_id):
    db.conn.execute(
        "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
        "VALUES (?, ?, ?, '2026-08-01T00:00:00Z')",
        (entity_type, local_id, server_id),
    )
    db.conn.commit()


# ── SyncEngine wiring ──────────────────────────────────────────────────────


class TestSyncEngineWiring:
    def test_engine_constructs_and_start_stop(self, db):
        fake = FakeApiClient(online=False)
        engine = _make_engine(db, fake)
        engine.start()
        engine.stop()
        assert True

    def test_engine_offline_cycle_emits_status(self, db):
        fake = FakeApiClient(online=False)
        engine = _make_engine(db, fake)
        statuses = []
        engine.sync_status_changed.connect(statuses.append)
        engine.sync_once()
        assert statuses == ["syncing", "offline"]


# ── Status indicator ───────────────────────────────────────────────────────


class TestStatusIndicator:
    def test_sync_status_text_mapping(self):
        from ui.widgets.sync_status import sync_status_text

        assert sync_status_text("offline") == "Sync: offline"
        assert sync_status_text("syncing") == "Sync: syncing…"
        assert sync_status_text("idle") == "Sync: up to date"
        assert sync_status_text("conflicts", 3) == "Sync: 3 conflicts"

    def test_sync_status_text_error(self):
        """S2: a failed cycle must render as 'Sync: error', not 'up to date'."""
        from ui.widgets.sync_status import resolve_status, sync_status_text

        assert sync_status_text("error") == "Sync: error"
        # Error wins over a stale conflict count.
        assert sync_status_text("error", 3) == "Sync: error"
        assert resolve_status("error", 3) == "error"
        assert resolve_status("error", 0) == "error"

    def test_resolve_status_prioritizes_conflicts(self):
        from ui.widgets.sync_status import resolve_status

        assert resolve_status("offline", 5) == "offline"
        assert resolve_status("idle", 3) == "conflicts"
        assert resolve_status("idle", 0) == "idle"
        assert resolve_status("syncing", 0) == "syncing"

    def test_label_updates_on_sync_status_changed(self, db, qapp):
        from ui.widgets.sync_status import SyncStatusLabel

        fake = FakeApiClient(online=False)
        engine = _make_engine(db, fake)
        label = SyncStatusLabel()
        engine.sync_status_changed.connect(label.update_status)
        engine.sync_finished.connect(
            lambda s: label.update_status(s.get("status"), s.get("conflicts", 0))
        )
        engine.sync_once()
        assert label.text() == "Sync: offline"

    def test_label_shows_conflict_count(self, qapp):
        from ui.widgets.sync_status import SyncStatusLabel

        label = SyncStatusLabel()
        label.update_status("conflicts", 4)
        assert label.text() == "Sync: 4 conflicts"


# ── Conflict journal dialog ────────────────────────────────────────────────


class TestConflictDialog:
    def test_list_unresolved_shows_recorded_conflicts(self, db, qapp):
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record(
            "client", 1, server_id=100,
            local_payload={"id": 1, "name": "Local"},
            server_payload={"id": 100, "name": "Server"},
        )
        dlg = SyncConflictDialog(conflict_service=conflict_service)
        assert dlg._conflicts[0]["id"] == conflict_id
        assert dlg._table.rowCount() == 1
        assert dlg._table.item(0, 0).text() == "client"

    def test_mark_resolved_removes_from_list(self, db, qapp):
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record("client", 1, server_id=100)
        dlg = SyncConflictDialog(conflict_service=conflict_service)
        assert dlg._table.rowCount() == 1
        dlg._keep_local(conflict_id)
        assert dlg._table.rowCount() == 0
        assert conflict_service.list_unresolved() == []

    def test_take_server_applies_payload_and_marks_resolved(self, db, qapp):
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        local_id = _insert_client(db, "Local Client")
        _record_id_map(db, "client", local_id, 100)
        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record(
            "client", local_id, server_id=100,
            local_payload={"id": local_id, "name": "Local Client"},
            server_payload={
                "id": 100, "name": "Server Client",
                "created_at": "2026-08-01T00:00:00Z",
                "updated_at": "2026-08-02T00:00:00Z",
            },
        )
        fake = FakeApiClient(online=False)
        pull = SyncPullService(db, fake)
        outbox = SyncOutboxService(db)
        dlg = SyncConflictDialog(
            conflict_service=conflict_service,
            pull_service=pull,
            outbox_service=outbox,
        )
        dlg._take_server(conflict_id)

        row = dict(db.conn.execute(
            "SELECT * FROM clients WHERE id = ?", (local_id,)
        ).fetchone())
        assert row["name"] == "Server Client"
        assert conflict_service.list_unresolved() == []
        # The pending outbox op for the row is cleared (nothing left to push).
        pending = db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_outbox WHERE synced_at IS NULL"
        ).fetchone()["n"]
        assert pending == 0

    def test_keep_local_requests_resync(self, db, qapp):
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record("client", 1, server_id=100)
        requested = []

        class FakeEngine:
            def request_sync(self):
                requested.append(True)

        dlg = SyncConflictDialog(
            conflict_service=conflict_service,
            engine=FakeEngine(),
        )
        dlg._keep_local(conflict_id)
        assert requested == [True]
        assert conflict_service.list_unresolved() == []

    def test_record_dedups_same_row(self, db):
        """R3a: recording the same (entity_type, local_id) twice yields one
        unresolved journal row (the engine re-pushes every cycle)."""
        conflict_service = SyncConflictService(db)
        first = conflict_service.record(
            "client", 1, server_id=100,
            local_payload={"id": 1, "name": "Local"},
            server_payload={"id": 100, "name": "Server"},
        )
        second = conflict_service.record(
            "client", 1, server_id=100,
            local_payload={"id": 1, "name": "Local"},
            server_payload={"id": 100, "name": "Server"},
        )
        assert second == first
        unresolved = conflict_service.list_unresolved()
        assert len(unresolved) == 1
        assert unresolved[0]["id"] == first

    def test_record_allows_distinct_rows(self, db):
        """R3a: dedup is per (entity_type, local_id) — different rows still
        journal separately, and a resolved conflict can be re-recorded."""
        conflict_service = SyncConflictService(db)
        c1 = conflict_service.record("client", 1, server_id=100)
        c2 = conflict_service.record("client", 2, server_id=200)
        assert c1 != c2
        assert len(conflict_service.list_unresolved()) == 2
        conflict_service.mark_resolved(c1)
        # Same row re-conflicts after resolution → new journal row allowed.
        c3 = conflict_service.record("client", 1, server_id=100)
        assert c3 != c1
        assert len(conflict_service.list_unresolved()) == 2

    def test_keep_local_restamps_updated_at(self, db, qapp):
        """R3b: keep-local re-stamps the local row's updated_at so the pending
        outbox op re-pushes with a fresh base and wins (no infinite loop)."""
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        local_id = _insert_client(db, "Local Client")
        # Pin an old updated_at (suppress the stamping trigger while we set it).
        db.conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '1')"
        )
        db.conn.execute(
            "UPDATE clients SET updated_at = '2026-08-01T00:00:00Z' WHERE id = ?",
            (local_id,),
        )
        db.conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '0')"
        )
        db.conn.commit()

        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record("client", local_id, server_id=100)
        requested = []

        class FakeEngine:
            def request_sync(self):
                requested.append(True)

        dlg = SyncConflictDialog(
            conflict_service=conflict_service,
            engine=FakeEngine(),
        )
        dlg._keep_local(conflict_id)

        row = dict(db.conn.execute(
            "SELECT * FROM clients WHERE id = ?", (local_id,)
        ).fetchone())
        assert row["updated_at"] != "2026-08-01T00:00:00Z"
        assert conflict_service.list_unresolved() == []
        assert requested == [True]

    def test_keep_local_hard_delete_bumps_frozen_payload(self, db, qapp):
        """R3b residual: for a HARD-deleted row (no row to re-stamp) the
        frozen DELETE payload's updated_at is bumped so the DELETE re-pushes
        with a fresh base and wins instead of looping forever."""
        import json as _json

        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        # Deliberately HARD-delete the expense (expenses has deleted_at now,
        # but a real hard delete is still possible — e.g. out-of-band purge)
        # so the frozen DELETE payload bump path is exercised.
        cur = db.conn.execute(
            "INSERT INTO expenses (date, category, description, amount, "
            "created_at, updated_at) "
            "VALUES ('2026-08-01', 'fuel', 'diesel', 100.0, "
            "'2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')"
        )
        db.conn.commit()
        expense_id = cur.lastrowid

        # Hard-delete → outbox DELETE op with frozen payload_json.
        db.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        db.conn.commit()

        delete_rows = [
            dict(r) for r in db.conn.execute(
                "SELECT * FROM sync_outbox "
                "WHERE entity_type = 'expense' AND local_id = ? AND op = 'DELETE'",
                (expense_id,),
            ).fetchall()
        ]
        assert len(delete_rows) == 1
        delete_row = delete_rows[0]
        payload = _json.loads(delete_row["payload_json"])
        # Pin the frozen payload to a known old updated_at so the bump is
        # deterministic (seconds-precision timestamps could otherwise collide).
        payload["updated_at"] = "2026-08-01T00:00:00Z"
        db.conn.execute(
            "UPDATE sync_outbox SET payload_json = ? WHERE id = ?",
            (_json.dumps(payload), delete_row["id"]),
        )
        db.conn.commit()

        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record("expense", expense_id, server_id=500)
        requested = []

        class FakeEngine:
            def request_sync(self):
                requested.append(True)

        dlg = SyncConflictDialog(
            conflict_service=conflict_service,
            outbox_service=SyncOutboxService(db),
            engine=FakeEngine(),
        )
        dlg._keep_local(conflict_id)

        updated = dict(db.conn.execute(
            "SELECT * FROM sync_outbox WHERE id = ?", (delete_row["id"],)
        ).fetchone())
        new_payload = _json.loads(updated["payload_json"])
        assert new_payload["updated_at"] != "2026-08-01T00:00:00Z"
        assert conflict_service.list_unresolved() == []
        assert requested == [True]

    def test_keep_local_row_gone_no_pending_op(self, db, qapp):
        """R3b residual: row gone and no pending DELETE op → nothing to
        re-push; the conflict is simply marked resolved without crashing."""
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record("client", 999, server_id=100)
        requested = []

        class FakeEngine:
            def request_sync(self):
                requested.append(True)

        dlg = SyncConflictDialog(
            conflict_service=conflict_service,
            outbox_service=SyncOutboxService(db),
            engine=FakeEngine(),
        )
        dlg._keep_local(conflict_id)

        assert conflict_service.list_unresolved() == []
        assert requested == [True]

    def test_take_server_with_missing_payload_leaves_conflict(self, db, qapp, monkeypatch):
        """S1: no server_payload → nothing applied → conflict stays unresolved
        and the pending outbox op is NOT cleared."""
        from ui.dialogs import sync_conflict_dialog
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        monkeypatch.setattr(
            sync_conflict_dialog.QMessageBox, "warning", lambda *a, **k: None
        )
        local_id = _insert_client(db, "Local Client")
        _record_id_map(db, "client", local_id, 100)
        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record(
            "client", local_id, server_id=100,
            local_payload={"id": local_id, "name": "Local Client"},
            server_payload=None,
        )
        fake = FakeApiClient(online=False)
        pull = SyncPullService(db, fake)
        outbox = SyncOutboxService(db)
        dlg = SyncConflictDialog(
            conflict_service=conflict_service,
            pull_service=pull,
            outbox_service=outbox,
        )
        dlg._take_server(conflict_id)

        assert len(conflict_service.list_unresolved()) == 1
        pending = db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_outbox WHERE synced_at IS NULL"
        ).fetchone()["n"]
        assert pending == 1

    def test_take_server_gates_on_apply_result(self, db, qapp, monkeypatch):
        """S1: when apply_server_row returns False, the conflict is NOT marked
        resolved and the outbox op is NOT cleared."""
        from ui.dialogs import sync_conflict_dialog
        from ui.dialogs.sync_conflict_dialog import SyncConflictDialog

        monkeypatch.setattr(
            sync_conflict_dialog.QMessageBox, "warning", lambda *a, **k: None
        )
        local_id = _insert_client(db, "Local Client")
        _record_id_map(db, "client", local_id, 100)
        conflict_service = SyncConflictService(db)
        conflict_id = conflict_service.record(
            "client", local_id, server_id=100,
            local_payload={"id": local_id, "name": "Local Client"},
            server_payload={"id": 100, "name": "Server Client"},
        )
        outbox = SyncOutboxService(db)

        class FailingPull:
            def apply_server_row(self, entity_type, server_row):
                return False

        dlg = SyncConflictDialog(
            conflict_service=conflict_service,
            pull_service=FailingPull(),
            outbox_service=outbox,
        )
        dlg._take_server(conflict_id)

        assert len(conflict_service.list_unresolved()) == 1
        pending = db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_outbox WHERE synced_at IS NULL"
        ).fetchone()["n"]
        assert pending == 1


# ── main.py wiring ─────────────────────────────────────────────────────────


class TestSetupSync:
    def test_setup_sync_wires_engine(self, db):
        from main import setup_sync

        class FakeWindow:
            def __init__(self):
                self.calls = []

            def setup_sync_ui(self, engine, **kwargs):
                self.calls.append(("setup_sync_ui", engine, kwargs))

        fake = FakeApiClient(online=False)
        window = FakeWindow()
        engine = setup_sync(db, window, api_client=fake)
        assert engine is not None
        assert window.calls[0][0] == "setup_sync_ui"
        assert window.calls[0][2]["outbox"] is not None
        assert window.calls[0][2]["pull"] is not None
        assert window.calls[0][2]["conflict_service"] is not None
        engine.stop()  # never started — safe no-op

    def test_setup_sync_skips_when_api_client_construction_fails(self, db, monkeypatch):
        from main import setup_sync

        import client.api_client

        def boom(*args, **kwargs):
            raise RuntimeError("no API config")

        monkeypatch.setattr(client.api_client, "ApiClient", boom)

        class FakeWindow:
            def setup_sync_ui(self, engine, **kwargs):
                pass

        window = FakeWindow()
        engine = setup_sync(db, window, api_client=None)
        assert engine is None  # app continues local-only

    def test_setup_sync_accepts_none_window(self, db):
        from main import setup_sync

        fake = FakeApiClient(online=False)
        engine = setup_sync(db, None, api_client=fake)
        assert engine is not None
        engine.stop()

    def test_setup_sync_hydrated_auth_sets_initial_user(self, db):
        """Phase F: boot WITH a hydrated session — the engine's initial
        per-user cursor namespace must be the auth-derived user id (non-zero),
        set at construction (login happens before setup_sync in run_app)."""
        from main import setup_sync

        import client.auth_manager as auth_mgr

        class FakeAuth:
            def __init__(self, uid):
                self._uid = uid

            @property
            def user_id(self):
                return self._uid

            def clear_token(self):
                pass

        fake = FakeApiClient(online=False)
        auth_mgr.clear_auth()
        engine = None
        try:
            # Hydrate FIRST (as run_app does via hydrate_from_storage), then
            # construct the engine through the real setup_sync path.
            auth_mgr.set_auth(FakeAuth(4242))
            engine = setup_sync(db, None, api_client=fake)
            assert engine is not None
            assert engine._worker._user_id == 4242, (
                f"initial engine user not wired from hydrated auth: "
                f"{engine._worker._user_id}"
            )
            # The freshly-wired engine also forces a full refresh for the user.
            assert engine._worker._force_full_sync is True
        finally:
            auth_mgr.clear_auth()
            if engine is not None:
                engine.stop()

    def test_setup_sync_attaches_auth_to_api_client(self, db):
        """The sync ApiClient must carry the logged-in user's Bearer token —
        without it the server 401s every push/pull (regression: the desktop
        entry point never attached auth, unlike main_remote)."""
        from main import setup_sync

        import client.auth_manager as auth_mgr

        class FakeAuth:
            def __init__(self, uid):
                self._uid = uid

            @property
            def user_id(self):
                return self._uid

            def clear_token(self):
                pass

        class RecordingClient(FakeApiClient):
            def __init__(self):
                super().__init__(online=False)
                self.auth_updates = []

            def update_auth(self, auth):
                self.auth_updates.append(auth)

        fake = RecordingClient()
        auth_mgr.clear_auth()
        engine = None
        try:
            auth_mgr.set_auth(FakeAuth(7))
            engine = setup_sync(db, None, api_client=fake)
            assert engine is not None
            # Attached at construction (initial session)…
            assert fake.auth_updates[-1].user_id == 7
            # …and kept in lockstep on in-app login/logout.
            auth_mgr.set_auth(FakeAuth(8))
            assert fake.auth_updates[-1].user_id == 8
            auth_mgr.clear_auth()
            assert fake.auth_updates[-1] is None
        finally:
            auth_mgr.clear_auth()
            if engine is not None:
                engine.stop()

    def test_setup_sync_wires_engine_user_to_auth_state(self, db):
        """Phase F: setup_sync locks the engine's per-user cursor namespace to
        the auth state — initial user at construction, and reactive updates on
        login/logout (each switch forces a full refresh)."""
        from main import setup_sync

        import client.auth_manager as auth_mgr

        class FakeAuth:
            def __init__(self, uid):
                self._uid = uid

            @property
            def user_id(self):
                return self._uid

            def clear_token(self):
                pass

        window = None
        fake = FakeApiClient(online=False)
        auth_mgr.clear_auth()
        engine = None
        try:
            engine = setup_sync(db, window, api_client=fake)
            assert engine is not None
            # No session at boot → engine user stays 0 (single-user namespace).
            assert engine._worker._user_id == 0

            # A login lands (in-app) → the engine switches + forces a refresh.
            auth_mgr.set_auth(FakeAuth(42))
            assert engine._worker._user_id == 42
            assert engine._worker._force_full_sync is True, (
                "login switch did not force a full refresh"
            )

            # Logout → back to the single-user namespace + full refresh.
            auth_mgr.clear_auth()
            assert engine._worker._user_id == 0
            assert engine._worker._force_full_sync is True
        finally:
            auth_mgr.clear_auth()
            if engine is not None:
                engine.stop()