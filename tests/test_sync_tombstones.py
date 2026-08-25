"""Tests for Phase D — hard-delete tombstones.

Covers:
- server records a tombstone when a sync-push DELETE lands (soft-delete path)
- GET /sync/pull?entity=tombstone returns the tombstones and deletes them
  (one-shot semantics)
- desktop pull_tombstones hard-deletes the local row + clears the id-map +
  drops stale pending outbox rows
- echo suppression: the tombstone-driven local DELETE creates no outbox row
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


def _push(client: TestClient, items: list[dict], device_id: str = "device-A") -> dict:
    resp = client.post(
        "/api/v1/sync/push",
        json={"items": items, "device_id": device_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _seed_trip(client: TestClient) -> int:
    res = _push(client, [{
        "entity_type": "trip", "op": "INSERT", "local_id": 1,
        "payload": {"truck_number": "B-100-XYZ", "driver_name": "D",
                    "client_name": "C", "distance_km": 100,
                    "created_at": "2026-08-01T00:00:00Z",
                    "updated_at": "2026-08-01T00:00:00Z"},
        "base_updated_at": None,
    }])
    assert res["results"][0]["status"] == "ok"
    return res["results"][0]["server_id"]


def _delete_trip(client: TestClient, trip_id: int, db) -> None:
    """DELETE a trip via the sync lane with a FRESH base_updated_at."""
    base = db.conn.execute(
        "SELECT updated_at FROM trips WHERE id = ?", (trip_id,)
    ).fetchone()["updated_at"]
    res = _push(client, [{
        "entity_type": "trip", "op": "DELETE", "local_id": 1,
        "payload": {"updated_at": base},
        "base_updated_at": base,
    }])
    assert res["results"][0]["status"] == "ok"


# ── Server: tombstone recording + one-shot pull ───────────────────────────


class TestServerTombstones:
    def test_soft_delete_push_records_tombstone(self, db):
        client = _make_client(db)
        trip_id = _seed_trip(client)

        # DELETE the trip via the sync lane (soft-delete path).
        _delete_trip(client, trip_id, db)

        # The server row is soft-deleted AND a tombstone was recorded.
        row = db.conn.execute(
            "SELECT deleted_at FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["deleted_at"] is not None
        tombstones = db.conn.execute(
            "SELECT * FROM sync_tombstones WHERE company_id = 1"
        ).fetchall()
        assert any(t["entity_type"] == "trip" and t["server_id"] == trip_id
                   for t in tombstones)

    def test_pull_tombstone_re_delivered(self, db):
        """B3: tombstones are NOT consumed on pull — the deleting device must
        not eat its own tombstone before the other devices sync.  Re-delivery
        is idempotent (desktop apply = no-op for missing rows)."""
        client = _make_client(db)
        trip_id = _seed_trip(client)
        _delete_trip(client, trip_id, db)

        # Every pull returns the tombstone...
        for _ in range(2):
            resp = client.get(
                "/api/v1/sync/pull",
                params={"entity": "tombstone", "after_id": 0, "limit": 10,
                        "device_id": "device-B"},
            )
            assert resp.status_code == 200
            records = resp.json()["records"]
            assert any(
                r["entity_type"] == "trip" and r["server_id"] == trip_id
                for r in records
            ), "tombstone was consumed by a pull (B3 regression)"

    def test_pull_tombstone_janitor_purges_old(self, db):
        """B3: the 30-day retention janitor purges stale tombstones."""
        client = _make_client(db)
        trip_id = _seed_trip(client)
        _delete_trip(client, trip_id, db)
        # Age the tombstone beyond the retention window.
        db.conn.execute(
            "UPDATE sync_tombstones SET purged_at = "
            "datetime('now', '-45 days') WHERE server_id = ?",
            (trip_id,),
        )
        db.conn.commit()
        resp = client.get(
            "/api/v1/sync/pull",
            params={"entity": "tombstone", "after_id": 0, "limit": 10,
                    "device_id": "device-B"},
        )
        assert resp.status_code == 200
        assert resp.json()["records"] == []

    def test_tombstones_are_never_since_filtered(self, db):
        """Oracle Phase D→E note: a device's delta cursor must NEVER suppress
        hard-delete propagation — tombstones come back regardless of `since`."""
        client = _make_client(db)
        trip_id = _seed_trip(client)
        _delete_trip(client, trip_id, db)

        # A since far in the future would filter out every entity row — but
        # the tombstone entity ignores `since` and still returns the tombstone.
        resp = client.get(
            "/api/v1/sync/pull",
            params={"entity": "tombstone", "since": "2999-01-01T00:00:00Z",
                    "after_id": 0, "limit": 10, "device_id": "device-B"},
        )
        assert resp.status_code == 200
        assert any(
            r["entity_type"] == "trip" and r["server_id"] == trip_id
            for r in resp.json()["records"]
        ), "tombstone was suppressed by a since param (delta pull regression)"

    def test_tombstones_are_company_scoped(self, db):
        client = _make_client(db, company_id=1)
        trip_id = _seed_trip(client)
        _delete_trip(client, trip_id, db)

        other = _make_client(db, company_id=2)
        resp = other.get(
            "/api/v1/sync/pull",
            params={"entity": "tombstone", "after_id": 0, "limit": 10,
                    "device_id": "device-D"},
        )
        assert resp.json()["records"] == []
        # Company 1 still has it (the other tenant's pull did not consume it).
        still = db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_tombstones WHERE entity_type = 'trip' "
            "AND server_id = ?",
            (trip_id,),
        ).fetchone()["n"]
        assert still == 1


# ── Desktop: tombstone apply ──────────────────────────────────────────────


class _TombstoneFake:
    def __init__(self, tombstones):
        self.tombstones = tombstones
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        entity = (params or {}).get("entity")
        if entity == "tombstone":
            return {"records": self.tombstones, "next_after_id": 0, "has_more": False}
        return {"records": [], "next_after_id": 0, "has_more": False}


class TestDesktopTombstones:
    def test_tombstone_deletes_local_row_and_clears_map(self, db):
        # Local trip + mapping + a stale pending outbox DELETE.
        local_id = db.conn.execute(
            "INSERT INTO trips (truck_number, driver_name, client_name, "
            "distance_km, created_at, updated_at, company_id) "
            "VALUES ('B-100-XYZ', 'D', 'C', 100, '2026-08-01T00:00:00Z', "
            "'2026-08-01T00:00:00Z', 1)",
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('trip', ?, 700, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.execute(
            "INSERT INTO sync_outbox (entity_type, op, local_id, created_at) "
            "VALUES ('trip', 'DELETE', ?, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()

        fake = _TombstoneFake([
            {"entity_type": "trip", "server_id": 700},
        ])
        pull = SyncPullService(db, fake)
        count = pull.pull_tombstones_standalone()

        assert count == 1
        # Local row hard-deleted.
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM trips WHERE id = ?", (local_id,)
        ).fetchone()["n"] == 0
        # Mapping cleared.
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_id_map "
            "WHERE entity_type = 'trip' AND server_id = 700"
        ).fetchone()["n"] == 0
        # Stale pending outbox row dropped (marked synced).
        outbox = SyncOutboxService(db)
        assert all(r["synced_at"] is not None for r in outbox.pending())
        # Echo suppression: the tombstone-driven DELETE created NO new outbox
        # row.  (The trip INSERT above already queued an INSERT row; the total
        # stays at 2 — no DELETE row was added.)
        rows = db.conn.execute(
            "SELECT * FROM sync_outbox WHERE entity_type = 'trip'"
        ).fetchall()
        assert len(rows) == 2
        assert all(r["synced_at"] is not None for r in rows)

    def test_tombstone_unknown_entity_skipped(self, db):
        fake = _TombstoneFake([
            {"entity_type": "widget", "server_id": 1},
        ])
        pull = SyncPullService(db, fake)
        count = pull.pull_tombstones_standalone()
        assert count == 0

    def test_tombstone_unmapped_row_noop(self, db):
        fake = _TombstoneFake([
            {"entity_type": "trip", "server_id": 9999},
        ])
        pull = SyncPullService(db, fake)
        count = pull.pull_tombstones_standalone()
        assert count == 0  # nothing was ever pulled for that server row
