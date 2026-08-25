"""Tests for Phase E — multi-user desktop (per-user cursors).

Covers:
- two users on the same desktop DB get independent pull cursors
  (user A's delta does not suppress user B's first full sync)
- a user switch triggers a full refresh for the new user (no cursors yet)
- push works under either user (company_id from the JWT, server-side)
- single-user edge: default user_id=0 keeps one cursor namespace (today's
  behavior — no extra full refreshes)
- engine set_user / force_full_sync wiring + summary counts
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
from services.sync_engine import SyncEngine
from services.sync_outbox_service import SyncOutboxService
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


class _Fake:
    """Records pull params + push bodies; returns canned per-entity records."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.pull_calls = []
        self.push_calls = []
        self.online = True

    def is_online(self):
        return self.online

    def post(self, path, json=None):
        self.push_calls.append((path, json))
        return {"results": []}

    def get(self, path, params=None):
        params = dict(params or {})
        self.pull_calls.append((path, params))
        entity = params.get("entity")
        if entity == "tombstone":
            return {"records": [], "next_after_id": 0, "has_more": False, "cursor": ""}
        records = self.responses.get(entity, [])
        since = params.get("since")
        if since is not None:
            records = [
                r for r in records
                if r.get("updated_at") is None or str(r["updated_at"]) > since
            ]
        cursor = since or ""
        for r in records:
            ts = r.get("updated_at")
            if ts and str(ts) > cursor:
                cursor = str(ts)
        return {
            "records": records,
            "next_after_id": 0,
            "has_more": False,
            "cursor": cursor,
        }


def _client_row(server_id, name, updated_at):
    return {
        "id": server_id, "name": name, "phone": "", "email": "",
        "address": "", "vat_number": "", "is_active": 1,
        "created_at": "2026-08-01T00:00:00Z", "updated_at": updated_at,
        "company_id": 1,
    }


class TestPerUserCursors:
    def test_two_users_independent_cursors(self, db):
        """User A's stored delta must NOT suppress user B's first full sync."""
        fake = _Fake(responses={"client": [
            _client_row(1, "A", "2026-08-01T00:00:00Z"),
            _client_row(2, "B", "2026-08-05T00:00:00Z"),
        ]})
        pull = SyncPullService(db, fake)

        # User 1: first pull = full refresh, cursor stored under user 1.
        pull.set_user(1)
        pull.pull_all(device_id="device-A")
        assert db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 1 AND entity_type = 'client'"
        ).fetchone()["cursor"] == "2026-08-05T00:00:00Z"

        # User 2 (different account on the same desktop): no cursors yet →
        # their first pull is a FULL refresh too, and their cursor is stored
        # under user 2 (independent namespace).
        pull.set_user(2)
        fake.pull_calls.clear()
        pull.pull_all(device_id="device-A")
        client_calls = [p for _, p in fake.pull_calls if (p or {}).get("entity") == "client"]
        assert client_calls[0].get("since") is None, "user 2's first pull was not full"
        assert db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 2 AND entity_type = 'client'"
        ).fetchone()["cursor"] == "2026-08-05T00:00:00Z"
        # User 1's cursor is untouched.
        assert db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 1 AND entity_type = 'client'"
        ).fetchone()["cursor"] == "2026-08-05T00:00:00Z"

    def test_user_switch_triggers_full_refresh(self, db):
        fake = _Fake(responses={"client": [_client_row(1, "A", "2026-08-01T00:00:00Z")]})
        pull = SyncPullService(db, fake, user_id=1)
        pull.pull_all(device_id="device-A")  # user 1: full + cursor

        # User 1's next pull is a DELTA.
        fake.pull_calls.clear()
        pull.pull_all(device_id="device-A")
        c1 = [p for _, p in fake.pull_calls if (p or {}).get("entity") == "client"]
        assert c1[0].get("since") is not None

        # Switch to user 2 → first pull is a full refresh (no since).
        pull.set_user(2)
        fake.pull_calls.clear()
        pull.pull_all(device_id="device-A")
        c2 = [p for _, p in fake.pull_calls if (p or {}).get("entity") == "client"]
        assert c2[0].get("since") is None, "user switch did not trigger full refresh"

    def test_single_user_default_namespace(self, db):
        """Default user_id=0 keeps one cursor namespace (today's behavior —
        no extra full refreshes)."""
        fake = _Fake(responses={"client": [_client_row(1, "A", "2026-08-01T00:00:00Z")]})
        pull = SyncPullService(db, fake)  # user_id defaults to 0
        pull.pull_all(device_id="device-A")
        assert db.conn.execute(
            "SELECT cursor FROM sync_cursors WHERE user_id = 0 AND entity_type = 'client'"
        ).fetchone()["cursor"] == "2026-08-01T00:00:00Z"

        # Second pull is a delta (cursor found under user 0).
        fake.pull_calls.clear()
        pull.pull_all(device_id="device-A")
        c = [p for _, p in fake.pull_calls if (p or {}).get("entity") == "client"]
        assert c[0].get("since") is not None, "single-user second pull not a delta"


class TestEngineUserWiring:
    def test_engine_set_user_and_summary_counts(self, db):
        fake = _Fake(responses={"client": [_client_row(1, "A", "2026-08-01T00:00:00Z")]})
        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, fake, user_id=1)
        engine = SyncEngine(db, fake, outbox, pull, user_id=1)

        summaries = []
        engine.sync_finished.connect(summaries.append)
        engine.sync_once()
        assert summaries[-1]["entities_full_refresh"] >= 1

        # Second cycle: delta (cursor exists).
        engine.sync_once()
        assert summaries[-1]["entities_delta"] >= 1

        # User switch → full refresh again for the new user.
        engine.set_user(2)
        engine.sync_once()
        assert summaries[-1]["entities_full_refresh"] >= 1

    def test_set_user_forces_full_refresh_even_with_existing_cursor(self, db):
        """Phase F: set_user schedules a one-shot full refresh even when the
        target user ALREADY has a stored cursor.

        A user switch can land mid-cycle (engine started at user 0, the login
        arrives after the pull phase).  Without the forced refresh, the next
        cycle would run a DELTA against a cursor that may be partial/polluted
        — re-pulling from scratch makes the switch safe regardless of timing.
        """
        fake = _Fake(responses={"client": [_client_row(1, "A", "2026-08-01T00:00:00Z")]})
        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, fake, user_id=1)
        engine = SyncEngine(db, fake, outbox, pull, user_id=1)
        engine.sync_once()  # full refresh under user 1 + cursor stored

        # Same user "re-logs in" mid-cycle → the stored cursor exists, but
        # set_user must STILL force a full refresh (not a delta).
        engine.set_user(1)
        engine.sync_once()
        client_calls = [
            p for _, p in fake.pull_calls if (p or {}).get("entity") == "client"
        ]
        assert client_calls[-1].get("since") is None, (
            "set_user did not force a full refresh against an existing cursor"
        )

    def test_engine_force_full_sync(self, db):
        fake = _Fake(responses={"client": [_client_row(1, "A", "2026-08-01T00:00:00Z")]})
        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, fake, user_id=1)
        engine = SyncEngine(db, fake, outbox, pull, user_id=1)
        engine.sync_once()  # full + cursor

        # force_full_sync ignores the cursor for one cycle.
        engine.force_full_sync()
        engine.sync_once()
        client_calls = [p for _, p in fake.pull_calls if (p or {}).get("entity") == "client"]
        assert client_calls[-1].get("since") is None, "force_full_sync sent a delta"

        # The flag is consumed — the next cycle is a delta again.
        engine.sync_once()
        client_calls = [p for _, p in fake.pull_calls if (p or {}).get("entity") == "client"]
        assert client_calls[-1].get("since") is not None


class TestPushUnderEitherUser:
    def test_push_company_scoped_per_user(self, db):
        """The server scopes pushed rows by the JWT's company_id — the same
        local_id pushed under two different users lands in each company."""
        client1 = _make_client(db, company_id=1)
        client2 = _make_client(db, company_id=2)

        def push(client, device_id):
            resp = client.post("/api/v1/sync/push", json={"items": [{
                "entity_type": "client", "op": "INSERT", "local_id": 1,
                "payload": {"name": "X", "created_at": "2026-08-01T00:00:00Z",
                            "updated_at": "2026-08-01T00:00:00Z"},
                "base_updated_at": None,
            }], "device_id": device_id})
            assert resp.status_code == 200, resp.text
            return resp.json()["results"][0]

        r1 = push(client1, "device-A")
        r2 = push(client2, "device-B")
        assert r1["status"] == "ok" and r2["status"] == "ok"
        assert r1["server_id"] != r2["server_id"]

        rows = db.conn.execute(
            "SELECT company_id, name FROM clients WHERE name = 'X'"
        ).fetchall()
        assert {(r["company_id"]) for r in rows} == {1, 2}
