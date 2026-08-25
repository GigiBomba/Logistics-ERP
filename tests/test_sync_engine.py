"""Tests for the offline-first sync ENGINE (Phase 4a).

Covers ``SyncEngine``:
- offline → status "offline", no push/pull calls
- online + pending outbox → push with translated FKs, items marked synced,
  server_id recorded in sync_id_map
- UPDATE-with-deleted_at → converted to op=DELETE (R4)
- conflict result → journaled in sync_conflicts, not marked synced
- gone result → outbox row dropped + sync_id_map entry cleared (P4)
- pull skips rows with pending outbox ops (P2)
- full cycle: push then pull, summary emitted
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from database.db_manager import DatabaseManager
from services.sync_engine import SyncEngine
from services.sync_outbox_service import SyncOutboxService
from services.sync_pull_service import SyncPullService


class FakeApiClient:
    """Stub ApiClient with canned push/pull responses.

    ``push_handler`` is a callable ``(items) -> {"results": [...]}`` so each
    test controls the per-item statuses.  ``pull_responses`` maps entity_type
    → list of record dicts (single page, no pagination).
    """

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


def _make_engine(db, fake, interval_seconds=60, device_id=None):
    outbox = SyncOutboxService(db)
    pull = SyncPullService(db, fake)
    return SyncEngine(
        db, fake, outbox, pull,
        interval_seconds=interval_seconds, device_id=device_id,
    )


def _outbox_rows(db):
    return [
        dict(r)
        for r in db.conn.execute("SELECT * FROM sync_outbox ORDER BY id").fetchall()
    ]


def _id_map_rows(db):
    return [
        dict(r)
        for r in db.conn.execute("SELECT * FROM sync_id_map ORDER BY id").fetchall()
    ]


def _insert_trip(db, truck_number="AB-01", status="Planned"):
    cur = db.conn.execute(
        "INSERT INTO trips (truck_number, driver_name, client_name, status) "
        "VALUES (?, 'John', 'ACME', ?)",
        (truck_number, status),
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


def _ok_handler(server_id=500):
    """Push handler that returns status 'ok' for every item."""
    def handler(items):
        return {
            "results": [
                {"local_id": it["local_id"], "server_id": server_id, "status": "ok"}
                for it in items
            ]
        }
    return handler


# ── Offline ───────────────────────────────────────────────────────────────


class TestOffline:
    def test_offline_emits_status_and_skips_network(self, db):
        fake = FakeApiClient(online=False)
        engine = _make_engine(db, fake)
        statuses = []
        summaries = []
        engine.sync_status_changed.connect(statuses.append)
        engine.sync_finished.connect(summaries.append)

        engine.sync_once()

        assert statuses == ["syncing", "offline"]
        assert fake.push_calls == []
        assert fake.pull_calls == []
        assert len(summaries) == 1
        assert summaries[0]["status"] == "offline"


class TestUnauthenticated:
    """A client with no auth token (logged out / cleared session) must skip
    the cycle quietly — the server 401s every sync request without a JWT, so
    erroring every interval would just spam the journal."""

    def test_cycle_skipped_when_client_has_no_auth(self, db):
        fake = FakeApiClient(online=True)
        fake._auth = None  # logged-out ApiClient (update_auth(None))
        engine = _make_engine(db, fake)
        statuses = []
        summaries = []
        engine.sync_status_changed.connect(statuses.append)
        engine.sync_finished.connect(summaries.append)

        engine.sync_once()

        assert statuses == ["syncing", "offline"]
        assert fake.push_calls == []
        assert fake.pull_calls == []
        assert len(summaries) == 1
        assert summaries[0]["status"] == "offline"

    def test_cycle_skipped_when_token_is_none(self, db):
        fake = FakeApiClient(online=True)
        fake._auth = type("Auth", (), {"token": None})()
        engine = _make_engine(db, fake)
        statuses = []
        engine.sync_status_changed.connect(statuses.append)

        engine.sync_once()

        assert statuses == ["syncing", "offline"]
        assert fake.push_calls == []
        assert fake.pull_calls == []

    def test_cycle_runs_when_client_has_token(self, db):
        fake = FakeApiClient(online=True)
        fake._auth = type("Auth", (), {"token": "valid"})()
        engine = _make_engine(db, fake)
        statuses = []
        engine.sync_status_changed.connect(statuses.append)

        engine.sync_once()

        assert statuses == ["syncing", "idle"]
        assert fake.push_calls == []
        assert fake.pull_calls != []  # the pull lane actually ran


# ── Push ──────────────────────────────────────────────────────────────────


class TestPush:
    def test_push_marks_synced_and_records_id_map(self, db):
        trip_id = _insert_trip(db)
        fake = FakeApiClient(push_handler=_ok_handler(server_id=500))
        engine = _make_engine(db, fake)

        engine.sync_once()

        # Push called once with the trip item
        assert len(fake.push_calls) == 1
        path, body = fake.push_calls[0]
        assert path == "/api/v1/sync/push"
        item = body["items"][0]
        assert item["entity_type"] == "trip"
        assert item["op"] == "INSERT"
        assert item["local_id"] == trip_id
        assert item["base_updated_at"] is None

        # Outbox drained
        assert all(r["synced_at"] is not None for r in _outbox_rows(db))

        # sync_id_map populated (local → server)
        by_local = db.conn.execute(
            "SELECT server_id FROM sync_id_map "
            "WHERE entity_type = 'trip' AND local_id = ?",
            (trip_id,),
        ).fetchone()
        assert by_local is not None and by_local["server_id"] == 500

    def test_push_translates_fk_ids(self, db):
        """P1: local FK ids are translated to server ids before sending."""
        truck_id = db.conn.execute(
            "INSERT INTO trucks (plate_number, updated_at) "
            "VALUES ('AB-01', '2026-08-01T00:00:00Z')"
        ).lastrowid
        db.conn.commit()
        _record_id_map(db, "truck", truck_id, 777)
        trip_id = _insert_trip(db)
        db.conn.execute(
            "UPDATE trips SET truck_id = ? WHERE id = ?", (truck_id, trip_id)
        )
        db.conn.commit()

        captured = {}
        def handler(items):
            captured["items"] = items
            return _ok_handler()(items)
        fake = FakeApiClient(push_handler=handler)
        engine = _make_engine(db, fake)

        engine.sync_once()

        # The trip payload must carry the SERVER truck id (777), not the local one
        trip_item = next(it for it in captured["items"] if it["entity_type"] == "trip")
        assert trip_item["payload"]["truck_id"] == 777

    def test_update_with_deleted_at_converted_to_delete(self, db):
        """R4: an UPDATE whose row is soft-deleted locally is sent as DELETE."""
        trip_id = _insert_trip(db)
        db.conn.execute(
            "UPDATE trips SET deleted_at = '2026-08-10T00:00:00Z' WHERE id = ?",
            (trip_id,),
        )
        db.conn.commit()

        captured = {}
        def handler(items):
            captured["items"] = items
            return _ok_handler()(items)
        fake = FakeApiClient(push_handler=handler)
        engine = _make_engine(db, fake)

        engine.sync_once()

        ops = [it["op"] for it in captured["items"]]
        assert ops == ["INSERT", "DELETE"]
        del_item = captured["items"][1]
        assert del_item["payload"].get("deleted_at") is not None
        # The converted DELETE carries the row's updated_at as base
        assert del_item["base_updated_at"] == del_item["payload"].get("updated_at")


# ── Conflict ──────────────────────────────────────────────────────────────


class TestConflict:
    def test_conflict_journaled_and_not_marked_synced(self, db):
        trip_id = _insert_trip(db)
        fake = FakeApiClient(push_handler=lambda items: {
            "results": [
                {
                    "local_id": it["local_id"],
                    "server_id": 500,
                    "status": "conflict",
                    "server_row": {
                        "id": 500, "status": "Server Status",
                        "updated_at": "2026-08-02T00:00:00Z",
                    },
                }
                for it in items
            ]
        })
        engine = _make_engine(db, fake)
        statuses = []
        engine.sync_status_changed.connect(statuses.append)

        engine.sync_once()

        # Not marked synced → still pending
        pending = _outbox_rows(db)
        assert len(pending) == 1
        assert pending[0]["synced_at"] is None

        # Journaled
        conflicts = db.conn.execute("SELECT * FROM sync_conflicts").fetchall()
        assert len(conflicts) == 1
        c = dict(conflicts[0])
        assert c["entity_type"] == "trip"
        assert c["local_id"] == trip_id
        assert c["server_id"] == 500
        assert c["resolved"] == 0
        local_payload = json.loads(c["local_payload"])
        assert local_payload["id"] == trip_id
        server_payload = json.loads(c["server_payload"])
        assert server_payload["status"] == "Server Status"

        # Status "conflicts" emitted
        assert "conflicts" in statuses


# ── Gone ──────────────────────────────────────────────────────────────────


class TestGone:
    def test_gone_drops_outbox_and_id_map(self, db):
        """P4: 'gone' drops the outbox row AND the stale id-map entry."""
        trip_id = _insert_trip(db)
        _record_id_map(db, "trip", trip_id, 500)
        fake = FakeApiClient(push_handler=lambda items: {
            "results": [
                {"local_id": it["local_id"], "server_id": 500, "status": "gone"}
                for it in items
            ]
        })
        engine = _make_engine(db, fake)

        engine.sync_once()

        # Outbox row dropped (marked synced)
        assert all(r["synced_at"] is not None for r in _outbox_rows(db))
        # id map entry cleared
        assert _id_map_rows(db) == []


# ── Pull skip (P2) ────────────────────────────────────────────────────────


class TestPullSkip:
    def test_pull_skips_rows_with_pending_outbox_ops(self, db):
        """P2: a row with a pending outbox op is not clobbered by the pull."""
        client_id = db.conn.execute(
            "INSERT INTO clients (name, created_at, updated_at) "
            "VALUES ('Local Edit', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')"
        ).lastrowid
        db.conn.commit()
        _record_id_map(db, "client", client_id, 100)

        # The push for the INSERT fails → the outbox row stays pending
        def handler(items):
            return {
                "results": [
                    {"local_id": it["local_id"], "status": "error", "error": "boom"}
                    for it in items
                ]
            }
        fake = FakeApiClient(
            push_handler=handler,
            pull_responses={
                "client": [
                    {"id": 100, "name": "Server Name",
                     "created_at": "2026-08-01T00:00:00Z",
                     "updated_at": "2026-08-02T00:00:00Z"},
                ],
            },
        )
        engine = _make_engine(db, fake)

        engine.sync_once()

        # The local row must NOT be clobbered by the server version
        row = dict(db.conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone())
        assert row["name"] == "Local Edit"


# ── Full cycle ────────────────────────────────────────────────────────────


class TestFullCycle:
    def test_full_cycle_push_then_pull_with_summary(self, db):
        trip_id = _insert_trip(db)
        fake = FakeApiClient(
            push_handler=_ok_handler(server_id=500),
            pull_responses={
                "truck": [
                    {"id": 900, "plate_number": "AB-99",
                     "created_at": "2026-08-01T00:00:00Z",
                     "updated_at": "2026-08-01T00:00:00Z"},
                ],
            },
        )
        engine = _make_engine(db, fake)
        summaries = []
        engine.sync_finished.connect(summaries.append)

        engine.sync_once()

        # Push happened
        assert len(fake.push_calls) == 1
        # Pull happened
        assert any(c[0] == "/api/v1/sync/pull" for c in fake.pull_calls)
        # Local truck created from pull
        assert db.conn.execute("SELECT COUNT(*) AS n FROM trucks").fetchone()["n"] == 1

        # Summary emitted
        assert len(summaries) == 1
        s = summaries[0]
        assert s["pushed"] == 1
        assert s["pulled"] == 1
        assert s["conflicts"] == 0
        assert s["errors"] == 0
        assert s["gone"] == 0
        assert s["status"] == "idle"


# ── R1: ApiClient public post() ───────────────────────────────────────────


class TestApiClientPublicPost:
    def test_api_client_has_public_post(self):
        """R1: the real ApiClient must expose a public ``post`` so the sync
        engine's push lane works (previously only ``_post`` existed)."""
        from client.api_client import ApiClient

        assert callable(getattr(ApiClient, "post", None))

    def test_api_client_post_wraps_post(self):
        """R1: the public ``post`` delegates to ``_post`` with ``json_data``."""
        from client.api_client import ApiClient

        client = ApiClient.__new__(ApiClient)  # skip __init__ (needs config)
        calls = []

        def fake_post(path, json_data=None, files=None, data=None):
            calls.append((path, json_data))
            return {"results": []}

        client._post = fake_post
        result = client.post("/api/v1/sync/push", json={"items": [{"x": 1}]})
        assert calls == [("/api/v1/sync/push", {"items": [{"x": 1}]})]
        assert result == {"results": []}


# ── R2: connectivity re-probe ─────────────────────────────────────────────


class TestReconnect:
    def test_engine_reprobes_connectivity_each_cycle(self, db):
        """R2: the engine resets the cached ``_online`` flag each cycle so a
        booted-offline app re-probes and recovers when the server returns."""
        class FlakyApiClient(FakeApiClient):
            """Mimics the real ApiClient's caching is_online() behavior."""

            def __init__(self):
                super().__init__()
                self._online = None
                self._probe_results = [False, True]
                self._probe_index = 0

            def is_online(self):
                if self._online is None:
                    self._online = self._probe_results[self._probe_index]
                    self._probe_index += 1
                return self._online

        trip_id = _insert_trip(db)
        fake = FlakyApiClient()
        fake.push_handler = _ok_handler(server_id=500)
        engine = _make_engine(db, fake)

        # First cycle: probe → False → offline, no push
        engine.sync_once()
        assert fake.push_calls == []

        # Second cycle: engine resets _online → probe → True → push happens
        engine.sync_once()
        assert len(fake.push_calls) == 1


# ── R4: shutdown abort ────────────────────────────────────────────────────


class TestStop:
    def test_stop_aborts_long_cycle(self, db):
        """R4: stop() during a long cycle returns promptly and the worker
        thread finishes (no 5s ceiling, no destroyed-while-running crash)."""
        import threading
        import time

        class BlockingApiClient(FakeApiClient):
            def __init__(self):
                super().__init__()
                self.release = threading.Event()
                self.entered = threading.Event()

            def is_online(self):
                return True

            def post(self, path, json=None):
                self.entered.set()
                self.release.wait(timeout=2)  # simulate a slow network call
                return {"results": []}

        _insert_trip(db)
        fake = BlockingApiClient()
        engine = _make_engine(db, fake)
        engine.start()
        assert fake.entered.wait(timeout=5), "worker never entered the blocking post"
        start = time.monotonic()
        engine.stop()
        elapsed = time.monotonic() - start
        assert elapsed < 10, f"stop() took too long: {elapsed:.1f}s"
        assert not engine._thread.isRunning()


# ── S3: gone-after-clear wedge ────────────────────────────────────────────


class TestS3NoMappingWedge:
    def test_update_without_mapping_sent_as_insert(self, db):
        """S3: an UPDATE with no sync_id_map entry is sent as INSERT so the
        server's R6 path re-creates + re-maps (avoids the gone-after-clear
        wedge where the server rejects the UPDATE with 'no mapping' forever)."""
        trip_id = _insert_trip(db)
        # Simulate a prior 'gone' result: the mapping was cleared.
        assert _id_map_rows(db) == []
        # Edit the row → outbox UPDATE (after the INSERT)
        db.conn.execute(
            "UPDATE trips SET status = 'In Transit' WHERE id = ?", (trip_id,)
        )
        db.conn.commit()

        captured = {}
        def handler(items):
            captured["items"] = items
            return _ok_handler()(items)
        fake = FakeApiClient(push_handler=handler)
        engine = _make_engine(db, fake)

        engine.sync_once()

        ops = [it["op"] for it in captured["items"]]
        # The INSERT stays INSERT; the UPDATE (no mapping) becomes INSERT
        assert ops == ["INSERT", "INSERT"]


# ── R4 should-fix: pull pagination stop check ─────────────────────────────


class TestPullStopCheck:
    def test_pull_entity_stops_between_pages(self, db):
        """R4 should-fix: pull_entity checks should_stop between pages so a
        long paginated pull aborts promptly on shutdown (no infinite loop)."""
        class InfinitePager(FakeApiClient):
            """Always reports has_more — would loop forever without the stop check."""

            def get(self, path, params=None):
                self.pull_calls.append((path, params))
                after_id = (params or {}).get("after_id", 0)
                return {
                    "records": [
                        {"id": after_id + 1, "name": f"C{after_id + 1}",
                         "created_at": "2026-08-01T00:00:00Z",
                         "updated_at": "2026-08-01T00:00:00Z"},
                    ],
                    "next_after_id": after_id + 1,
                    "has_more": True,
                }

        fake = InfinitePager()
        pull = SyncPullService(db, fake, page_size=1)
        checks = []

        def should_stop():
            checks.append(True)
            return len(checks) > 1  # allow the first page, stop before the second

        count = pull.pull_entity("client", should_stop=should_stop)

        # Only one page fetched, then the stop check broke the loop
        assert len(fake.pull_calls) == 1
        assert count == 1
        assert len(checks) == 2  # checked before page 1 and before page 2

    def test_pull_all_stops_between_entities(self, db):
        """R4 should-fix: pull_all checks should_stop between entities too."""
        fake = FakeApiClient(pull_responses={
            "client": [
                {"id": 1, "name": "C1", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        pull = SyncPullService(db, fake)
        checks = []

        def should_stop():
            # pull_all checks before each entity AND pull_entity checks before
            # each page — allow the first entity's page, stop before the next.
            checks.append(True)
            return len(checks) > 2

        count = pull.pull_all(should_stop=should_stop)

        # Only the first entity (client) was pulled
        assert count == 1
        entities_pulled = {c[1].get("entity") for c in fake.pull_calls}
        assert entities_pulled == {"client"}

    def test_engine_stop_during_pull(self, db):
        """R4 should-fix: stop() during a long pull returns promptly — the
        pull loop checks the stop flag between pages."""
        import threading
        import time

        class BlockingPager(FakeApiClient):
            def __init__(self):
                super().__init__()
                self.entered = threading.Event()
                self.release = threading.Event()

            def get(self, path, params=None):
                self.entered.set()
                self.release.wait(timeout=2)  # simulate a slow pull page
                return {"records": [], "next_after_id": 0, "has_more": False}

        fake = BlockingPager()
        engine = _make_engine(db, fake)
        engine.start()
        assert fake.entered.wait(timeout=5), "worker never entered the pull"
        start = time.monotonic()
        engine.stop()
        elapsed = time.monotonic() - start
        assert elapsed < 10, f"stop() took too long: {elapsed:.1f}s"
        assert not engine._thread.isRunning()


# ── Phase A: device_id ────────────────────────────────────────────────────


class TestDeviceId:
    def test_engine_sends_device_id_in_push_and_pull(self, db):
        """The engine includes device_id in every push body and pull param."""
        trip_id = _insert_trip(db)
        fake = FakeApiClient(push_handler=_ok_handler(server_id=500))
        engine = _make_engine(db, fake, device_id="test-device-1")

        engine.sync_once()

        # Push body carries device_id
        assert len(fake.push_calls) == 1
        _, body = fake.push_calls[0]
        assert body["device_id"] == "test-device-1"

        # Pull params carry device_id
        assert fake.pull_calls
        for _, params in fake.pull_calls:
            assert params.get("device_id") == "test-device-1"

    def test_device_identity_stable_across_engine_instances(self, db):
        """Same DB → same device_id across engine instances (persisted)."""
        fake1 = FakeApiClient(push_handler=_ok_handler())
        engine1 = _make_engine(db, fake1)
        device1 = engine1._device_id
        assert device1

        fake2 = FakeApiClient(push_handler=_ok_handler())
        engine2 = _make_engine(db, fake2)
        assert engine2._device_id == device1

        # Persisted in sync_meta
        row = db.conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'device_id'"
        ).fetchone()
        assert row is not None and row["value"] == device1

    def test_injected_device_id_is_used(self, db):
        """An explicitly injected device_id is used (not regenerated)."""
        fake = FakeApiClient(push_handler=_ok_handler())
        engine = _make_engine(db, fake, device_id="injected-device")
        assert engine._device_id == "injected-device"