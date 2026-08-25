"""Tests for Phase E — cursor-based delta pull.

Covers:
- server since-filter: only rows with updated_at > since (+ NULL updated_at
  rows, which are always returned) come back; soft-deleted rows stamped with
  updated_at > since are included; company scope holds; cursor response field
- desktop cursor store/read/update in the sync_cursors table
- delta pull only fetches changed rows after the first full sync
- fallback to a full refresh when the delta request fails
"""
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.main import create_app
from database.db_manager import DatabaseManager
from services.sync_pull_service import SyncPullService


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
    for cid in range(0, 101):
        _db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (?, ?, 'starter')",
            (cid, f"Company-{cid}"),
        )
    _db.conn.commit()
    yield _db
    try:
        _db.close()
    except Exception:
        pass


def _make_client(db: DatabaseManager, company_id: int = 1) -> TestClient:
    app = create_app()

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    async def _mock_user() -> Dict[str, Any]:
        return {
            "id": 1,
            "email": "sync@test.com",
            "role": "admin",
            "is_admin": True,
            "company_id": company_id,
        }

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app)


def _seed_trip(db, truck_number, updated_at, company_id=1, deleted_at=None):
    # Suppress the updated_at stamping triggers so the seeded timestamps
    # survive (they would otherwise be overwritten with "now" on INSERT).
    db.conn.execute(
        "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '1')"
    )
    cur = db.conn.execute(
        "INSERT INTO trips (truck_number, driver_name, client_name, distance_km, "
        "created_at, updated_at, company_id, deleted_at) "
        "VALUES (?, 'D', 'C', 100, '2026-08-01T00:00:00Z', ?, ?, ?)",
        (truck_number, updated_at, company_id, deleted_at),
    )
    db.conn.execute(
        "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '0')"
    )
    db.conn.commit()
    return cur.lastrowid


def _pull(client, entity, since=None, since_id=0, after_id=0, limit=500, device_id="device-A"):
    params = {"entity": entity, "after_id": after_id, "limit": limit, "device_id": device_id}
    if since is not None:
        params["since"] = since
        params["since_id"] = since_id
    resp = client.get("/api/v1/sync/pull", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Server: since-filter ──────────────────────────────────────────────────


class TestServerSinceFilter:
    def test_since_returns_only_newer_rows(self, db):
        client = _make_client(db)
        _seed_trip(db, "OLD-1", "2026-08-01T00:00:00Z")
        _seed_trip(db, "NEW-1", "2026-08-10T00:00:00Z")
        _seed_trip(db, "NEW-2", "2026-08-12T00:00:00Z")
        # NULL updated_at (legacy row, never stamped) must ALWAYS come back.
        _seed_trip(db, "NULL-1", None)

        body = _pull(client, "trip", since="2026-08-05T00:00:00Z")
        trucks = {r["truck_number"] for r in body["records"]}
        assert trucks == {"NEW-1", "NEW-2", "NULL-1"}
        assert body["cursor"] == "2026-08-12T00:00:00Z"

        # A since past everything → only NULL rows (self-healing).
        body2 = _pull(client, "trip", since="2026-09-01T00:00:00Z")
        assert {r["truck_number"] for r in body2["records"]} == {"NULL-1"}
        # Cursor does not go backwards.
        assert body2["cursor"] == "2026-09-01T00:00:00Z"

    def test_since_includes_soft_deleted_rows(self, db):
        """Soft-deleted rows stamped with updated_at > since must NOT be
        filtered out (the delta must propagate deletions)."""
        client = _make_client(db)
        _seed_trip(db, "ACTIVE", "2026-08-01T00:00:00Z")
        _seed_trip(
            db, "GONE", "2026-08-11T00:00:00Z",
            deleted_at="2026-08-11T00:00:00Z",
        )

        body = _pull(client, "trip", since="2026-08-05T00:00:00Z")
        trucks = {r["truck_number"] for r in body["records"]}
        assert trucks == {"GONE"}, f"soft-deleted delta row missing: {trucks}"

    def test_since_is_company_scoped(self, db):
        client1 = _make_client(db, company_id=1)
        client2 = _make_client(db, company_id=2)
        _seed_trip(db, "C1-NEW", "2026-08-10T00:00:00Z", company_id=1)
        _seed_trip(db, "C2-OLD", "2026-08-01T00:00:00Z", company_id=2)
        _seed_trip(db, "C2-NEW", "2026-08-11T00:00:00Z", company_id=2)

        body1 = _pull(client1, "trip", since="2026-08-05T00:00:00Z")
        assert {r["truck_number"] for r in body1["records"]} == {"C1-NEW"}
        body2 = _pull(client2, "trip", since="2026-08-05T00:00:00Z")
        assert {r["truck_number"] for r in body2["records"]} == {"C2-NEW"}

    def test_no_since_is_full_refresh_backward_compat(self, db):
        client = _make_client(db)
        _seed_trip(db, "A", "2026-08-01T00:00:00Z")
        _seed_trip(db, "B", "2026-08-02T00:00:00Z")
        body = _pull(client, "trip")
        assert {r["truck_number"] for r in body["records"]} == {"A", "B"}
        assert body["cursor"] == "2026-08-02T00:00:00Z"

    def test_same_second_tiebreak(self, db):
        """R1: rows stamped at EXACTLY the cursor second with id > since_id
        must be fetched; rows with id <= since_id (already seen) are skipped."""
        client = _make_client(db)
        since = "2026-08-10T00:00:00Z"
        # ids 1..4 — two AT the cursor second, two before it.
        _seed_trip(db, "OLD-1", "2026-08-01T00:00:00Z")
        _seed_trip(db, "OLD-2", "2026-08-09T00:00:00Z")
        _seed_trip(db, "TIE-3", since)
        _seed_trip(db, "TIE-4", since)

        # since_id=2 → the two same-second rows (ids 3, 4) come back, the
        # pre-cursor rows (ids 1, 2) do not.
        body = _pull(client, "trip", since=since, since_id=2)
        trucks = {r["truck_number"] for r in body["records"]}
        assert trucks == {"TIE-3", "TIE-4"}, f"tiebreak wrong: {trucks}"

        # since_id=3 → only the same-second row with the HIGHER id comes back.
        body2 = _pull(client, "trip", since=since, since_id=3)
        assert {r["truck_number"] for r in body2["records"]} == {"TIE-4"}

        # since_id=4 → no same-second row is left (all seen).
        body3 = _pull(client, "trip", since=since, since_id=4)
        assert {r["truck_number"] for r in body3["records"]} == set()


# ── Desktop: cursor store / read / delta ──────────────────────────────────


class _DeltaFake:
    """Mimics the pull endpoint: full or since-filtered records + cursor."""

    def __init__(self, responses=None, fail_delta_once=False):
        self.responses = responses or {}   # entity → [record dicts]
        self.calls = []
        self.fail_delta_once = fail_delta_once
        self._delta_failures = 0

    def get(self, path, params=None):
        params = dict(params or {})
        self.calls.append((path, params))
        entity = params.get("entity")
        if entity == "tombstone":
            return {"records": [], "next_after_id": 0, "has_more": False, "cursor": ""}
        since = params.get("since")
        if since is not None and self.fail_delta_once and self._delta_failures == 0:
            self._delta_failures += 1
            raise RuntimeError("simulated delta failure")
        after_id = params.get("after_id", 0)
        limit = params.get("limit", 500)
        records = sorted(
            (r for r in self.responses.get(entity, []) if r["id"] > after_id),
            key=lambda r: r["id"],
        )
        if since is not None:
            since_id = params.get("since_id", 0)
            records = [
                r for r in records
                if r.get("updated_at") is None
                or str(r["updated_at"]) > since
                or (str(r["updated_at"]) == since and r["id"] > since_id)
            ]
        page = records[:limit]
        cursor = since or ""
        for r in page:
            ts = r.get("updated_at")
            if ts and str(ts) > cursor:
                cursor = str(ts)
        return {
            "records": page,
            "next_after_id": max((r["id"] for r in page), default=after_id),
            "has_more": len(page) >= limit,
            "cursor": cursor,
        }


def _client_row(server_id, name, updated_at, deleted_at=None):
    row = {
        "id": server_id, "name": name, "phone": "", "email": "",
        "address": "", "vat_number": "", "is_active": 1,
        "created_at": "2026-08-01T00:00:00Z", "updated_at": updated_at,
        "company_id": 1,
    }
    if deleted_at is not None:
        row["deleted_at"] = deleted_at
    return row


class TestDesktopCursors:
    def test_first_pull_full_then_delta(self, db):
        """First pull is a full refresh + stores a cursor; the second pull
        sends since and only fetches rows newer than the cursor."""
        fake = _DeltaFake(responses={"client": [
            _client_row(1, "A", "2026-08-01T00:00:00Z"),
            _client_row(2, "B", "2026-08-05T00:00:00Z"),
        ]})
        pull = SyncPullService(db, fake, user_id=7)

        count = pull.pull_entity("client", device_id="device-A")
        assert count == 2
        # Full refresh: no since param on the first call.
        first_params = [p for _, p in fake.calls if (p or {}).get("entity") == "client"]
        assert first_params[0].get("since") is None

        # Cursor stored under user 7.
        row = db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 7 AND entity_type = 'client'"
        ).fetchone()
        assert row is not None and row["cursor"] == "2026-08-05T00:00:00Z"

        # Second pull: only rows changed after the cursor.
        fake.calls.clear()
        count2 = pull.pull_entity("client", device_id="device-A")
        since_params = [p for _, p in fake.calls if (p or {}).get("entity") == "client"]
        assert since_params[0].get("since") == "2026-08-05T00:00:00Z"
        assert count2 == 0  # nothing newer → no rows fetched

    def test_delta_only_fetches_changed_rows(self, db):
        fake = _DeltaFake(responses={"client": [
            _client_row(1, "A", "2026-08-01T00:00:00Z"),
            _client_row(2, "B", "2026-08-05T00:00:00Z"),
        ]})
        pull = SyncPullService(db, fake)
        pull.pull_entity("client", device_id="device-A")

        # Row A changes; row B stays.
        fake.responses["client"] = [
            _client_row(1, "A", "2026-08-20T00:00:00Z"),
            _client_row(2, "B", "2026-08-05T00:00:00Z"),
        ]
        fake.calls.clear()
        count = pull.pull_entity("client", device_id="device-A")
        assert count == 1
        # Only the changed row was fetched.
        fetched = [p for _, p in fake.calls if (p or {}).get("entity") == "client"]
        assert fetched[0].get("since") == "2026-08-05T00:00:00Z"

    def test_fallback_to_full_refresh_on_delta_error(self, db):
        """A failing delta request falls back to a full refresh (schema change
        / clock skew) and re-derives + stores the cursor."""
        fake = _DeltaFake(
            responses={"client": [
                _client_row(1, "A", "2026-08-01T00:00:00Z"),
                _client_row(2, "B", "2026-08-05T00:00:00Z"),
            ]},
            fail_delta_once=True,
        )
        pull = SyncPullService(db, fake)
        # Store a cursor first so the second pull attempts a delta.
        pull.pull_entity("client", device_id="device-A")

        fake.calls.clear()
        fake.responses["client"] = [
            _client_row(1, "A", "2026-08-01T00:00:00Z"),
            _client_row(2, "B", "2026-08-05T00:00:00Z"),
            _client_row(3, "C", "2026-08-09T00:00:00Z"),
        ]
        count = pull.pull_entity("client", device_id="device-A")
        assert count == 3  # A, B re-upserted; C inserted (full refresh re-applies)
        calls = [p for _, p in fake.calls if (p or {}).get("entity") == "client"]
        # First attempt had since, then fell back to full refresh (no since).
        assert calls[0].get("since") is not None
        assert calls[-1].get("since") is None
        # Cursor re-derived from the full results.
        row = db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 0 AND entity_type = 'client'"
        ).fetchone()
        assert row["cursor"] == "2026-08-09T00:00:00Z"

    def test_delta_sends_since_id_tiebreak(self, db):
        """R1: the delta resends the stored last_id as since_id so a row
        stamped at exactly the cursor second is not permanently missed."""
        fake = _DeltaFake(responses={"client": [
            _client_row(1, "A", "2026-08-01T00:00:00Z"),
            _client_row(2, "B", "2026-08-05T00:00:00Z"),
        ]})
        pull = SyncPullService(db, fake, user_id=7)
        pull.pull_entity("client", device_id="device-A")
        # last_id stored = max id seen (2).
        row = db.conn.execute(
            "SELECT cursor, last_id FROM sync_cursors "
            "WHERE user_id = 7 AND entity_type = 'client'"
        ).fetchone()
        assert row["last_id"] == 2

        fake.calls.clear()
        pull.pull_entity("client", device_id="device-A")
        since_params = [p for _, p in fake.calls if (p or {}).get("entity") == "client"]
        assert since_params[0].get("since") == "2026-08-05T00:00:00Z"
        assert since_params[0].get("since_id") == 2, "since_id tiebreak not sent"

    def test_same_second_delta_fetches_new_rows(self, db):
        """R1: rows stamped at the cursor second with a higher id than the
        stored last_id are re-fetched on the next delta."""
        fake = _DeltaFake(responses={"client": [
            _client_row(1, "A", "2026-08-01T00:00:00Z"),
            _client_row(2, "B", "2026-08-05T00:00:00Z"),
        ]})
        pull = SyncPullService(db, fake, user_id=7)
        pull.pull_entity("client", device_id="device-A")  # cursor=08-05, last_id=2

        # Device B stamps TWO rows at exactly the cursor second: ids 3 and 4.
        fake.responses["client"].extend([
            _client_row(3, "C", "2026-08-05T00:00:00Z"),
            _client_row(4, "D", "2026-08-05T00:00:00Z"),
        ])
        fake.calls.clear()
        count = pull.pull_entity("client", device_id="device-A")
        # Both same-second rows come back (id > since_id=2).
        assert count == 2, f"same-second rows missed: {count}"
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM clients WHERE name IN ('C', 'D')"
        ).fetchone()["n"] == 2

    def test_stop_abort_does_not_store_cursor(self, db):
        """R2: a mid-pagination abort (should_stop) must NOT persist the
        cursor — the un-pulled tail would be stranded.  The next cycle redoes
        a full refresh for the entity."""
        records = [_client_row(i, f"C{i}", "2026-08-01T00:00:00Z") for i in range(1, 601)]
        fake = _DeltaFake(responses={"client": records})
        pull = SyncPullService(db, fake, user_id=3)

        checks = [0]
        def should_stop():
            # Allow the first page, then stop at the next pagination check.
            checks[0] += 1
            return checks[0] > 1

        count = pull.pull_entity("client", should_stop=should_stop, device_id="device-A")
        assert count == 500  # first page applied
        # Cursor NOT stored (the tail ids 501..600 was never pulled).
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_cursors "
            "WHERE user_id = 3 AND entity_type = 'client'"
        ).fetchone()["n"] == 0

        # Next pull is a FULL refresh (no since) and catches the tail.
        fake.calls.clear()
        pull2 = SyncPullService(db, fake, user_id=3)
        count2 = pull2.pull_entity("client", device_id="device-A")
        since_params = [p for _, p in fake.calls if (p or {}).get("entity") == "client"]
        assert since_params[0].get("since") is None, "aborted entity not full-refreshed"
        assert count2 == 600  # full refresh re-upserts everything
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM clients"
        ).fetchone()["n"] == 600

    def test_cursor_not_advanced_when_apply_fails(self, db):
        """A record that raises during apply must not advance the cursor —
        the next cycle re-pulls from the old watermark."""
        fake = _DeltaFake(responses={"client": [
            _client_row(1, "A", "2026-08-01T00:00:00Z"),
        ]})
        pull = SyncPullService(db, fake)
        pull.pull_entity("client", device_id="device-A")
        assert db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 0 AND entity_type = 'client'"
        ).fetchone()["cursor"] == "2026-08-01T00:00:00Z"

        # Break the upsert: make the local table reject the row via a bad
        # record with an un-writable column set (raises inside _upsert_record).
        fake.responses["client"] = [_client_row(2, "B", "2026-08-10T00:00:00Z")]
        orig = SyncPullService._upsert_record

        def boom(self, entity_type, server_row, skip_local_ids=None):
            raise RuntimeError("apply exploded")

        SyncPullService._upsert_record = boom
        try:
            pull.pull_entity("client", device_id="device-A")
        finally:
            SyncPullService._upsert_record = orig

        # Cursor NOT advanced past the failed row.
        row = db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 0 AND entity_type = 'client'"
        ).fetchone()
        assert row["cursor"] == "2026-08-01T00:00:00Z"

    def test_force_full_sync_ignores_cursor(self, db):
        fake = _DeltaFake(responses={"client": [_client_row(1, "A", "2026-08-01T00:00:00Z")]})
        pull = SyncPullService(db, fake)
        pull.pull_entity("client", device_id="device-A")  # store cursor

        fake.calls.clear()
        count = pull.pull_all(force_full_sync=True, device_id="device-A")
        client_calls = [p for _, p in fake.calls if (p or {}).get("entity") == "client"]
        assert client_calls[0].get("since") is None, "force_full_sync sent a delta"
        assert count == 1  # re-applied the row (upsert by mapping)
