"""Tests for the offline-first sync push endpoint (Phase 2).

Covers ``POST /api/v1/sync/push``:
- INSERT creates a row + ``sync_server_map`` entry (exactly-once)
- INSERT retry (same local_id) updates the mapped row, no duplicate
- UPDATE with stale ``base_updated_at`` → conflict + server_row
- UPDATE with fresh ``base_updated_at`` → applied
- DELETE soft-deletes the mapped row (idempotent when unmapped)
- Unsupported entity type → error status
- company_id isolation between users
- Pull stub returns company-scoped rows with id > after_id

Pattern follows ``tests/contracts/test_driver_trip_overview_schema.py``:
real endpoint logic, mocked identity, real file-backed SQLite DB.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.main import create_app
from database.db_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Fresh file-backed SQLite database with the full app schema."""
    db = DatabaseManager(str(tmp_path / "sync.db"))
    for cid in range(0, 101):
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (?, ?, 'starter')",
            (cid, f"Company-{cid}"),
        )
    db.conn.commit()
    yield db
    db.close()


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


# ── INSERT ────────────────────────────────────────────────────────────────


class TestPushInsert:
    def test_insert_creates_row_and_mapping(self, db, tmp_path):
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9001,
                "payload": {"name": "Sync Client", "email": "sync@client.com"},
                "base_updated_at": None,
            }
        ])
        assert result["results"][0]["status"] == "ok"
        server_id = result["results"][0]["server_id"]
        assert server_id is not None and server_id > 0

        # Row exists with company_id stamped from JWT
        row = db.conn.execute(
            "SELECT * FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row is not None
        assert row["name"] == "Sync Client"
        assert row["company_id"] == 1

        # Mapping recorded
        mapping = db.conn.execute(
            "SELECT server_id FROM sync_server_map "
            "WHERE company_id = 1 AND entity_type = 'client' AND local_id = 9001"
        ).fetchone()
        assert mapping is not None and mapping["server_id"] == server_id

    def test_insert_retry_does_not_duplicate(self, db):
        """Replaying the same local_id must update, not duplicate."""
        client = _make_client(db)
        item = {
            "entity_type": "client",
            "op": "INSERT",
            "local_id": 9002,
            "payload": {"name": "Retry Client"},
            "base_updated_at": None,
        }
        first = _push(client, [item])
        server_id = first["results"][0]["server_id"]

        # Replay the same INSERT (network drop scenario)
        second = _push(client, [item])
        assert second["results"][0]["status"] == "ok"
        assert second["results"][0]["server_id"] == server_id

        # Exactly one row with that name
        rows = db.conn.execute(
            "SELECT COUNT(*) AS n FROM clients WHERE name = 'Retry Client'"
        ).fetchone()
        assert rows["n"] == 1

    def test_insert_trip_with_fk_fields(self, db):
        """Trip insert round-trips FK fields through the repository."""
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "trip",
                "op": "INSERT",
                "local_id": 9100,
                "payload": {
                    "client_name": "Trip Client",
                    "loading_country": "RO",
                    "delivery_country": "DE",
                    "status": "planned",
                },
                "base_updated_at": None,
            }
        ])
        assert result["results"][0]["status"] == "ok"
        server_id = result["results"][0]["server_id"]
        row = db.conn.execute(
            "SELECT * FROM trips WHERE id = ?", (server_id,)
        ).fetchone()
        assert row is not None
        assert row["loading_country"] == "RO"


# ── UPDATE + conflict ─────────────────────────────────────────────────────


class TestPushUpdate:
    def _seed(self, db, client):
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9200,
                "payload": {"name": "Update Client"},
                "base_updated_at": None,
            }
        ])
        return result["results"][0]["server_id"]

    def test_update_applied_with_fresh_base(self, db):
        client = _make_client(db)
        server_id = self._seed(db, client)
        # Use the server row's actual updated_at as base (client saw this state)
        row = db.conn.execute(
            "SELECT updated_at FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        base = row["updated_at"]
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "UPDATE",
                "local_id": 9200,
                "payload": {"name": "Updated Name"},
                "base_updated_at": base,
            }
        ])
        assert result["results"][0]["status"] == "ok"
        row = db.conn.execute(
            "SELECT name FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row["name"] == "Updated Name"

    def test_update_stale_base_conflicts(self, db):
        client = _make_client(db)
        server_id = self._seed(db, client)
        # Server row's updated_at is now (2026); client claims base 2000 → stale
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "UPDATE",
                "local_id": 9200,
                "payload": {"name": "Stale Write"},
                "base_updated_at": "2000-01-01T00:00:00Z",
            }
        ])
        res = result["results"][0]
        assert res["status"] == "conflict"
        assert res["server_row"] is not None
        # The stale write must NOT have been applied
        row = db.conn.execute(
            "SELECT name FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row["name"] == "Update Client"

    def test_update_without_mapping_errors(self, db):
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "UPDATE",
                "local_id": 99999,
                "payload": {"name": "No Mapping"},
                "base_updated_at": None,
            }
        ])
        assert result["results"][0]["status"] == "error"


# ── DELETE ────────────────────────────────────────────────────────────────


class TestPushDelete:
    def test_delete_soft_deletes_mapped_row(self, db):
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9300,
                "payload": {"name": "Delete Me"},
                "base_updated_at": None,
            }
        ])
        server_id = result["results"][0]["server_id"]

        del_result = _push(client, [
            {
                "entity_type": "client",
                "op": "DELETE",
                "local_id": 9300,
                "payload": {},
                "base_updated_at": None,
            }
        ])
        assert del_result["results"][0]["status"] == "ok"
        row = db.conn.execute(
            "SELECT deleted_at FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row is not None and row["deleted_at"] is not None

    def test_delete_unmapped_is_idempotent(self, db):
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "DELETE",
                "local_id": 99998,
                "payload": {},
                "base_updated_at": None,
            }
        ])
        assert result["results"][0]["status"] == "ok"


# ── Edge cases ────────────────────────────────────────────────────────────


class TestPushEdgeCases:
    def test_unsupported_entity_type(self, db):
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "route_history_v2",
                "op": "INSERT",
                "local_id": 1,
                "payload": {},
                "base_updated_at": None,
            }
        ])
        assert result["results"][0]["status"] == "error"
        assert "unsupported" in result["results"][0]["error"]

    def test_company_isolation(self, db):
        """Company 2's push must not be visible to company 1's pull."""
        client1 = _make_client(db, company_id=1)
        client2 = _make_client(db, company_id=2)
        _push(client2, [
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9400,
                "payload": {"name": "Company2 Client"},
                "base_updated_at": None,
            }
        ])
        pull = client1.get("/api/v1/sync/pull?entity=client&device_id=device-A&after_id=0&limit=500")
        assert pull.status_code == 200
        records = pull.json()["records"]
        assert all(r.get("company_id") == 1 for r in records)
        assert all(r.get("name") != "Company2 Client" for r in records)

    def test_one_bad_item_does_not_abort_batch(self, db):
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "bogus_entity",
                "op": "INSERT",
                "local_id": 1,
                "payload": {},
                "base_updated_at": None,
            },
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9500,
                "payload": {"name": "Good Client"},
                "base_updated_at": None,
            },
        ])
        statuses = [r["status"] for r in result["results"]]
        assert statuses == ["error", "ok"]


# ── Pull stub ─────────────────────────────────────────────────────────────


class TestPullStub:
    def test_pull_returns_company_scoped_rows(self, db):
        client = _make_client(db)
        _push(client, [
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9600,
                "payload": {"name": "Pull Client"},
                "base_updated_at": None,
            }
        ])
        pull = client.get("/api/v1/sync/pull?entity=client&device_id=device-A&after_id=0&limit=500")
        assert pull.status_code == 200
        body = pull.json()
        assert body["has_more"] is False
        assert any(r["name"] == "Pull Client" for r in body["records"])

    def test_pull_unknown_entity_empty(self, db):
        client = _make_client(db)
        pull = client.get("/api/v1/sync/pull?entity=nope&device_id=device-A&after_id=0&limit=500")
        assert pull.status_code == 200
        # Phase E: the response carries the delta ``cursor`` (empty for an
        # unknown entity / full refresh with no rows).
        assert pull.json() == {
            "records": [], "next_after_id": 0, "has_more": False, "cursor": "",
        }


# ── R4 hardening ──────────────────────────────────────────────────────────


class TestR4Hardening:
    def test_delete_with_stale_base_conflicts(self, db):
        """DELETE with a stale base_updated_at must conflict, not delete."""
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9700,
                "payload": {"name": "Delete Conflict"},
                "base_updated_at": None,
            }
        ])
        server_id = result["results"][0]["server_id"]

        del_result = _push(client, [
            {
                "entity_type": "client",
                "op": "DELETE",
                "local_id": 9700,
                "payload": {},
                "base_updated_at": "2000-01-01T00:00:00Z",
            }
        ])
        res = del_result["results"][0]
        assert res["status"] == "conflict"
        assert res["server_row"] is not None
        # The delete must NOT have been applied
        row = db.conn.execute(
            "SELECT deleted_at FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row is not None and row["deleted_at"] is None

    def test_insert_retry_skips_conflict_check(self, db):
        """INSERT-retry is the same logical op — a stale base must NOT conflict."""
        client = _make_client(db)
        item = {
            "entity_type": "client",
            "op": "INSERT",
            "local_id": 9701,
            "payload": {"name": "Retry No Conflict"},
            "base_updated_at": "2000-01-01T00:00:00Z",
        }
        first = _push(client, [item])
        server_id = first["results"][0]["server_id"]

        # Replay with a stale base — the retry is the same logical op, so it
        # must NOT conflict (the desktop clock may be stale vs the server).
        second = _push(client, [item])
        res = second["results"][0]
        assert res["status"] == "ok"
        assert res["server_id"] == server_id

    def test_expense_delete_soft_deletes_and_hard_deleted_returns_gone(self, db):
        """Phase B: expenses has deleted_at → DELETE soft-deletes (row stays).
        A later UPDATE for a HARD-deleted (out-of-band purged) row still
        returns status 'gone' so the desktop lane drops the outbox row."""
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "expense",
                "op": "INSERT",
                "local_id": 9702,
                "payload": {"category": "Fuel", "amount": 100.0},
                "base_updated_at": None,
            }
        ])
        server_id = result["results"][0]["server_id"]

        # Phase B: expenses now has deleted_at → DELETE soft-deletes.
        del_result = _push(client, [
            {
                "entity_type": "expense",
                "op": "DELETE",
                "local_id": 9702,
                "payload": {},
                "base_updated_at": None,
            }
        ])
        assert del_result["results"][0]["status"] == "ok"
        row = db.conn.execute(
            "SELECT deleted_at FROM expenses WHERE id = ?", (server_id,)
        ).fetchone()
        assert row is not None and row["deleted_at"] is not None

        # Simulate an out-of-band HARD delete (admin purge) — the row is now
        # truly gone, so a later UPDATE must return "gone".
        db.conn.execute("DELETE FROM expenses WHERE id = ?", (server_id,))
        db.conn.commit()
        upd_result = _push(client, [
            {
                "entity_type": "expense",
                "op": "UPDATE",
                "local_id": 9702,
                "payload": {"amount": 200.0},
                "base_updated_at": None,
            }
        ])
        res = upd_result["results"][0]
        assert res["status"] == "gone"


# ── R6 / R7 remediation ───────────────────────────────────────────────


class TestR6R7Remediation:
    def test_insert_retry_on_gone_row_recreates_and_remaps(self, db):
        """R6: if the mapped server row was hard-deleted out-of-band, an
        INSERT-retry must re-create the row and re-map (fresh server_id),
        returning status 'ok' — NOT 'gone' (which would drop the local row)."""
        client = _make_client(db)
        item = {
            "entity_type": "client",
            "op": "INSERT",
            "local_id": 9703,
            "payload": {"name": "Recreate Client"},
            "base_updated_at": None,
        }
        first = _push(client, [item])
        server_id = first["results"][0]["server_id"]

        # Hard-delete the server row out-of-band (simulating an admin purge)
        db.conn.execute("DELETE FROM clients WHERE id = ?", (server_id,))
        db.conn.commit()

        # Replay the INSERT → must re-create + re-map, not return "gone"
        second = _push(client, [item])
        res = second["results"][0]
        assert res["status"] == "ok"
        assert res["server_id"] is not None
        assert res["server_id"] != server_id

        # The mapping now points at the fresh row
        mapping = db.conn.execute(
            "SELECT server_id FROM sync_server_map "
            "WHERE company_id = 1 AND entity_type = 'client' AND local_id = 9703"
        ).fetchone()
        assert mapping is not None and mapping["server_id"] == res["server_id"]
        row = db.conn.execute(
            "SELECT * FROM clients WHERE id = ?", (res["server_id"],)
        ).fetchone()
        assert row is not None and row["name"] == "Recreate Client"

    def test_soft_delete_stamps_updated_at(self, db):
        """R7: a server soft-delete must stamp updated_at so a second device's
        stale UPDATE (base_updated_at = pre-delete value) conflicts instead of
        silently writing into a deleted row."""
        client = _make_client(db)
        result = _push(client, [
            {
                "entity_type": "client",
                "op": "INSERT",
                "local_id": 9704,
                "payload": {"name": "Delete Stamps"},
                "base_updated_at": None,
            }
        ])
        server_id = result["results"][0]["server_id"]

        # Simulate a pre-delete server state with a fixed past updated_at.
        # sync_in_progress=1 suppresses the stamping triggers so the value
        # survives the manual UPDATE (R5 guard).
        db.conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '1')"
        )
        db.conn.execute(
            "UPDATE clients SET updated_at = '2020-01-01T00:00:00Z' WHERE id = ?",
            (server_id,),
        )
        db.conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('sync_in_progress', '0')"
        )
        db.conn.commit()

        del_result = _push(client, [
            {
                "entity_type": "client",
                "op": "DELETE",
                "local_id": 9704,
                "payload": {},
                "base_updated_at": "2020-01-01T00:00:00Z",
            }
        ])
        assert del_result["results"][0]["status"] == "ok"
        row = db.conn.execute(
            "SELECT deleted_at, updated_at FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row["deleted_at"] is not None
        # The soft-delete stamped updated_at (no longer the pre-delete value)
        assert row["updated_at"] is not None
        assert row["updated_at"] != "2020-01-01T00:00:00Z"

        # A second device's UPDATE with the pre-delete base must now CONFLICT
        # (before R7 it passed the check and wrote into the deleted row).
        upd_result = _push(client, [
            {
                "entity_type": "client",
                "op": "UPDATE",
                "local_id": 9704,
                "payload": {"name": "Stale Write Into Deleted"},
                "base_updated_at": "2020-01-01T00:00:00Z",
            }
        ])
        res = upd_result["results"][0]
        assert res["status"] == "conflict"
        row = db.conn.execute(
            "SELECT name FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row["name"] == "Delete Stamps"


# ── Phase A: multi-device ─────────────────────────────────────────────────


class TestMultiDevice:
    """Two devices with colliding local ids must NOT cross-contaminate.

    Each device has its own ``sync_server_map`` namespace keyed by
    ``(company_id, device_id, entity_type, local_id)``, so device B's
    local_id=1 maps to a different server row than device A's local_id=1.
    """

    def test_two_devices_same_local_id_create_distinct_rows(self, db):
        client = _make_client(db)
        item = {
            "entity_type": "client",
            "op": "INSERT",
            "local_id": 1,
            "payload": {"name": "Device A Client"},
            "base_updated_at": None,
        }
        res_a = _push(client, [item], device_id="device-A")
        res_b = _push(client, [item], device_id="device-B")
        server_a = res_a["results"][0]["server_id"]
        server_b = res_b["results"][0]["server_id"]

        # Two distinct server rows
        assert server_a != server_b
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM clients WHERE name = 'Device A Client'"
        ).fetchone()["n"] == 2

        # Each device mapped to its own row
        map_a = db.conn.execute(
            "SELECT server_id FROM sync_server_map "
            "WHERE company_id = 1 AND device_id = 'device-A' "
            "AND entity_type = 'client' AND local_id = 1"
        ).fetchone()
        map_b = db.conn.execute(
            "SELECT server_id FROM sync_server_map "
            "WHERE company_id = 1 AND device_id = 'device-B' "
            "AND entity_type = 'client' AND local_id = 1"
        ).fetchone()
        assert map_a is not None and map_a["server_id"] == server_a
        assert map_b is not None and map_b["server_id"] == server_b

    def test_update_from_device_b_only_touches_b_row(self, db):
        client = _make_client(db)
        item = {
            "entity_type": "client",
            "op": "INSERT",
            "local_id": 1,
            "payload": {"name": "Original"},
            "base_updated_at": None,
        }
        res_a = _push(client, [item], device_id="device-A")
        res_b = _push(client, [item], device_id="device-B")
        server_a = res_a["results"][0]["server_id"]
        server_b = res_b["results"][0]["server_id"]

        # Device B updates its own row (local_id=1)
        upd = _push(client, [
            {
                "entity_type": "client",
                "op": "UPDATE",
                "local_id": 1,
                "payload": {"name": "Device B Updated"},
                "base_updated_at": None,
            }
        ], device_id="device-B")
        assert upd["results"][0]["status"] == "ok"
        assert upd["results"][0]["server_id"] == server_b

        # Device A's row is untouched
        row_a = db.conn.execute(
            "SELECT name FROM clients WHERE id = ?", (server_a,)
        ).fetchone()
        row_b = db.conn.execute(
            "SELECT name FROM clients WHERE id = ?", (server_b,)
        ).fetchone()
        assert row_a["name"] == "Original"
        assert row_b["name"] == "Device B Updated"

    def test_push_requires_device_id(self, db):
        """device_id is a required field on the push request."""
        client = _make_client(db)
        resp = client.post("/api/v1/sync/push", json={"items": []})
        assert resp.status_code == 422


# ── BLOCKER #1: legacy '' mapping adoption ─────────────────────────────────


class TestLegacyAdoption:
    """Upgraded devices must be able to UPDATE/DELETE pre-Phase-A rows.

    The Phase A migration parks old server maps under ``device_id=''``; the
    upgraded desktop never sends ``''`` again, so without adoption it could
    never touch its pre-existing rows.  ``_resolve_mapping`` adopts the
    legacy row on first use.
    """

    def _seed_legacy(self, db, name, local_id):
        server_id = db.conn.execute(
            "INSERT INTO clients (name, company_id, created_at, updated_at) "
            "VALUES (?, 1, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')",
            (name,),
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_server_map (company_id, device_id, entity_type, local_id, server_id, created_at) "
            "VALUES (1, '', 'client', ?, ?, '2026-08-01T00:00:00Z')",
            (local_id, server_id),
        )
        db.conn.commit()
        return server_id

    def test_legacy_update_adopts_mapping(self, db):
        """UPDATE from an upgraded device targets the existing server row."""
        client = _make_client(db)
        server_id = self._seed_legacy(db, "Legacy Client", 9000)

        result = _push(client, [
            {
                "entity_type": "client",
                "op": "UPDATE",
                "local_id": 9000,
                "payload": {"name": "Updated Legacy"},
                "base_updated_at": None,
            }
        ], device_id="device-upgraded")
        res = result["results"][0]
        assert res["status"] == "ok"
        assert res["server_id"] == server_id
        row = db.conn.execute(
            "SELECT name FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row["name"] == "Updated Legacy"
        # Mapping adopted to the new device
        mapping = db.conn.execute(
            "SELECT server_id FROM sync_server_map WHERE company_id=1 "
            "AND device_id='device-upgraded' AND entity_type='client' AND local_id=9000"
        ).fetchone()
        assert mapping is not None and mapping["server_id"] == server_id

    def test_legacy_delete_adopts_mapping(self, db):
        """DELETE from an upgraded device actually soft-deletes the row."""
        client = _make_client(db)
        server_id = self._seed_legacy(db, "Legacy Delete", 9001)

        result = _push(client, [
            {
                "entity_type": "client",
                "op": "DELETE",
                "local_id": 9001,
                "payload": {},
                "base_updated_at": None,
            }
        ], device_id="device-upgraded")
        res = result["results"][0]
        assert res["status"] == "ok"
        row = db.conn.execute(
            "SELECT deleted_at FROM clients WHERE id = ?", (server_id,)
        ).fetchone()
        assert row is not None and row["deleted_at"] is not None

    def test_legacy_adoption_once_second_device_gets_own_row(self, db):
        """Adoption happens once; a second device's INSERT gets its own row."""
        client = _make_client(db)
        server_id = self._seed_legacy(db, "Legacy", 9002)

        # Device A adopts the legacy mapping (INSERT-retry → updates the row)
        res_a = _push(client, [
            {
                "entity_type": "client", "op": "INSERT", "local_id": 9002,
                "payload": {"name": "A"}, "base_updated_at": None,
            }
        ], device_id="device-A")
        assert res_a["results"][0]["status"] == "ok"
        assert res_a["results"][0]["server_id"] == server_id

        # Device B's INSERT for the same local_id gets its OWN new row
        res_b = _push(client, [
            {
                "entity_type": "client", "op": "INSERT", "local_id": 9002,
                "payload": {"name": "B"}, "base_updated_at": None,
            }
        ], device_id="device-B")
        assert res_b["results"][0]["status"] == "ok"
        assert res_b["results"][0]["server_id"] != server_id


# ── Phase B: entity completeness (the 15 previously unsupported entities) ──


class TestPhaseB:
    """Push round-trips for the newly synced entities (direct-SQL paths)."""

    def _seed_client(self, client, local_id=9900, name="PhaseB Client", device_id="device-A"):
        res = _push(client, [
            {
                "entity_type": "client", "op": "INSERT", "local_id": local_id,
                "payload": {"name": name}, "base_updated_at": None,
            }
        ], device_id=device_id)
        assert res["results"][0]["status"] == "ok"
        return res["results"][0]["server_id"]

    def _seed_document(self, client, local_id=9901, device_id="device-A"):
        res = _push(client, [
            {
                "entity_type": "document", "op": "INSERT", "local_id": local_id,
                "payload": {"doc_number": "DOC-PB-1", "title": "PB Doc",
                            "file_path": "/tmp/pb.pdf", "file_name": "pb.pdf",
                            "uploaded_at": "2026-08-01T00:00:00Z"},
                "base_updated_at": None,
            }
        ], device_id=device_id)
        assert res["results"][0]["status"] == "ok"
        return res["results"][0]["server_id"]

    def test_insert_round_trip_new_entities(self, db):
        client = _make_client(db)
        server_client = self._seed_client(client)
        server_doc = self._seed_document(client)

        # client_contact (direct SQL)
        res = _push(client, [{
            "entity_type": "client_contact", "op": "INSERT", "local_id": 1,
            "payload": {"client_id": server_client, "full_name": "Contact A",
                        "contact_type": "operations"},
            "base_updated_at": None,
        }])
        assert res["results"][0]["status"] == "ok"
        cid = res["results"][0]["server_id"]
        row = db.conn.execute("SELECT * FROM client_contacts WHERE id = ?", (cid,)).fetchone()
        assert row["full_name"] == "Contact A"
        assert row["company_id"] == 1

        # client_tag (direct SQL)
        res = _push(client, [{
            "entity_type": "client_tag", "op": "INSERT", "local_id": 1,
            "payload": {"client_id": server_client, "tag": "VIP"},
            "base_updated_at": None,
        }])
        assert res["results"][0]["status"] == "ok"
        tgid = res["results"][0]["server_id"]
        row = db.conn.execute("SELECT * FROM client_tags WHERE id = ?", (tgid,)).fetchone()
        assert row["tag"] == "VIP"
        assert row["company_id"] == 1

        # tacho_import (direct SQL)
        res = _push(client, [{
            "entity_type": "tacho_import", "op": "INSERT", "local_id": 1,
            "payload": {"file_name": "f.ddd", "file_type": "ddd",
                        "file_hash": "abc123"},
            "base_updated_at": None,
        }])
        assert res["results"][0]["status"] == "ok"
        tid = res["results"][0]["server_id"]
        row = db.conn.execute("SELECT * FROM tacho_imports WHERE id = ?", (tid,)).fetchone()
        assert row["file_hash"] == "abc123"
        assert row["company_id"] == 1

        # contract (direct SQL)
        res = _push(client, [{
            "entity_type": "contract", "op": "INSERT", "local_id": 1,
            "payload": {"client_id": server_client, "contract_type": "transport"},
            "base_updated_at": None,
        }])
        assert res["results"][0]["status"] == "ok"
        ctid = res["results"][0]["server_id"]
        row = db.conn.execute("SELECT * FROM contracts WHERE id = ?", (ctid,)).fetchone()
        assert row["client_id"] == server_client
        assert row["company_id"] == 1

        # document_link (direct SQL)
        res = _push(client, [{
            "entity_type": "document_link", "op": "INSERT", "local_id": 1,
            "payload": {"document_id": server_doc, "linked_entity_type": "trip",
                        "linked_entity_id": 5},
            "base_updated_at": None,
        }])
        assert res["results"][0]["status"] == "ok"
        dli = res["results"][0]["server_id"]
        row = db.conn.execute("SELECT * FROM document_links WHERE id = ?", (dli,)).fetchone()
        assert row["document_id"] == server_doc
        assert row["company_id"] == 1

    def test_update_new_entity(self, db):
        client = _make_client(db)
        server_client = self._seed_client(client)
        res = _push(client, [{
            "entity_type": "contract", "op": "INSERT", "local_id": 1,
            "payload": {"client_id": server_client, "contract_type": "transport",
                        "status": "active"},
            "base_updated_at": None,
        }])
        ctid = res["results"][0]["server_id"]

        upd = _push(client, [{
            "entity_type": "contract", "op": "UPDATE", "local_id": 1,
            "payload": {"status": "completed"},
            "base_updated_at": None,
        }])
        assert upd["results"][0]["status"] == "ok"
        assert upd["results"][0]["server_id"] == ctid
        row = db.conn.execute(
            "SELECT status FROM contracts WHERE id = ?", (ctid,)
        ).fetchone()
        assert row["status"] == "completed"

    def test_delete_new_entity(self, db):
        client = _make_client(db)
        server_client = self._seed_client(client)
        _push(client, [{
            "entity_type": "client_tag", "op": "INSERT", "local_id": 1,
            "payload": {"client_id": server_client, "tag": "VIP"},
            "base_updated_at": None,
        }])
        del_res = _push(client, [{
            "entity_type": "client_tag", "op": "DELETE", "local_id": 1,
            "payload": {},
            "base_updated_at": None,
        }])
        assert del_res["results"][0]["status"] == "ok"
        # client_tags has no deleted_at → hard delete
        assert db.conn.execute("SELECT COUNT(*) AS n FROM client_tags").fetchone()["n"] == 0

    def test_new_entity_company_isolation(self, db):
        client1 = _make_client(db, company_id=1)
        client2 = _make_client(db, company_id=2)
        c2_client = self._seed_client(client2, local_id=9902, name="C2 Client",
                                      device_id="device-B")
        _push(client2, [{
            "entity_type": "client_contact", "op": "INSERT", "local_id": 1,
            "payload": {"client_id": c2_client, "full_name": "C2 Contact"},
            "base_updated_at": None,
        }], device_id="device-B")

        pull = client1.get(
            "/api/v1/sync/pull?entity=client_contact&device_id=device-A&after_id=0&limit=500"
        )
        assert pull.status_code == 200
        records = pull.json()["records"]
        assert all(r.get("company_id") == 1 for r in records)
        assert all(r.get("full_name") != "C2 Contact" for r in records)


# ── D1: sent_emails unique-collision dedup ────────────────────────────────


class TestSentEmailDedup:
    def test_sent_email_unique_collision_reuses_existing_row(self, db):
        """D1: a sent_emails INSERT colliding with an existing (document_id,
        recipient) row returns ok and reuses the existing row's id (the dedup
        intent), instead of erroring and retrying forever."""
        client = _make_client(db)
        res = _push(client, [{
            "entity_type": "document", "op": "INSERT", "local_id": 1,
            "payload": {"doc_number": "D1", "title": "T",
                        "file_path": "/f.pdf", "file_name": "f.pdf",
                        "uploaded_at": "2026-08-01T00:00:00Z"},
            "base_updated_at": None,
        }])
        doc_id = res["results"][0]["server_id"]
        assert res["results"][0]["status"] == "ok"

        first = _push(client, [{
            "entity_type": "sent_email", "op": "INSERT", "local_id": 1,
            "payload": {"document_id": doc_id, "recipient": "a@b.com"},
            "base_updated_at": None,
        }], device_id="device-A")
        assert first["results"][0]["status"] == "ok"
        first_id = first["results"][0]["server_id"]

        # Second device inserts the same (document_id, recipient) → dedup to
        # the existing row, not an error.
        second = _push(client, [{
            "entity_type": "sent_email", "op": "INSERT", "local_id": 1,
            "payload": {"document_id": doc_id, "recipient": "a@b.com"},
            "base_updated_at": None,
        }], device_id="device-B")
        res2 = second["results"][0]
        assert res2["status"] == "ok"
        assert res2["server_id"] == first_id
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM sent_emails"
        ).fetchone()["n"] == 1


# ── R1 (document file_path is binary-endpoint-owned) ──────────────────────


class TestDocumentFilePathNotSyncable:
    """R1: file_path must NOT be writable via the sync push payload — it is
    attacker-controlled and meaningless across machines; the binary endpoint
    owns it.  The server row gets an empty placeholder instead."""

    def test_insert_drops_file_path(self, db):
        client = _make_client(db)
        res = _push(client, [{
            "entity_type": "document", "op": "INSERT", "local_id": 9902,
            "payload": {"doc_number": "DOC-R1-1", "title": "R1 Doc",
                        "file_path": "../../../.env", "file_name": "r1.pdf",
                        "uploaded_at": "2026-08-01T00:00:00Z"},
            "base_updated_at": None,
        }])
        assert res["results"][0]["status"] == "ok"
        doc_id = res["results"][0]["server_id"]
        row = db.conn.execute(
            "SELECT file_path, file_name FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        # The pushed "../../.env" must NOT be persisted — only "".
        assert row["file_path"] == ""
        assert row["file_name"] == "r1.pdf"

    def test_update_drops_file_path(self, db):
        client = _make_client(db)
        res = _push(client, [{
            "entity_type": "document", "op": "INSERT", "local_id": 9903,
            "payload": {"doc_number": "DOC-R1-2", "title": "R1 Doc",
                        "file_name": "r1.pdf",
                        "uploaded_at": "2026-08-01T00:00:00Z"},
            "base_updated_at": None,
        }])
        doc_id = res["results"][0]["server_id"]
        # A second push (UPDATE) must not overwrite file_path either.
        base = db.conn.execute(
            "SELECT updated_at FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()["updated_at"]
        upd = _push(client, [{
            "entity_type": "document", "op": "UPDATE", "local_id": 9903,
            "payload": {"title": "R1 Doc v2",
                        "file_path": "/etc/passwd"},
            "base_updated_at": base,
        }])
        assert upd["results"][0]["status"] == "ok"
        row = db.conn.execute(
            "SELECT file_path, title FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        assert row["file_path"] == ""
        assert row["title"] == "R1 Doc v2"


# ── R4 transaction seam: atomic INSERT + mapping ──────────────────────────


class TestAtomicInsertMapping:
    """A repository-backed INSERT and its sync_server_map entry must be atomic.

    A failure between the entity INSERT and the mapping INSERT (e.g. a crash
    or an exception) must roll back BOTH — no orphan server row is left behind,
    so the next INSERT-retry cannot create a duplicate.
    """

    def test_repo_insert_rolls_back_when_mapping_fails(self, db, monkeypatch):
        import backend.api.v1.sync as sync_mod

        client = _make_client(db)

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated pre-mapping failure")

        monkeypatch.setattr(sync_mod, "_insert_mapping", _boom)

        result = _push(client, [{
            "entity_type": "client",
            "op": "INSERT",
            "local_id": 9800,
            "payload": {"name": "Atomic Client"},
            "base_updated_at": None,
        }])
        assert result["results"][0]["status"] == "error"

        # Neither the orphan server row nor the mapping may survive.
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM clients WHERE name = 'Atomic Client'"
        ).fetchone()["n"] == 0
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_server_map "
            "WHERE company_id = 1 AND entity_type = 'client' AND local_id = 9800"
        ).fetchone()["n"] == 0

    def test_repo_insert_commits_row_and_mapping_together(self, db):
        """The happy path still lands both the row and the mapping."""
        client = _make_client(db)
        result = _push(client, [{
            "entity_type": "client",
            "op": "INSERT",
            "local_id": 9801,
            "payload": {"name": "Atomic Commit Client"},
            "base_updated_at": None,
        }])
        assert result["results"][0]["status"] == "ok"
        server_id = result["results"][0]["server_id"]
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM clients WHERE id = ?", (server_id,)
        ).fetchone()["n"] == 1
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM sync_server_map "
            "WHERE company_id = 1 AND entity_type = 'client' AND local_id = 9801"
        ).fetchone()["n"] == 1