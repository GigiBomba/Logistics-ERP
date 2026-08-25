"""Tests for Phase D — route history sync (fingerprint natural-key dedup).

Covers:
- server push INSERT with an existing fingerprint → UPDATE, not a duplicate
  (natural_key config in backend/api/v1/sync.py)
- desktop pull upsert adopts a local row by fingerprint (no duplicate insert)
- soft-deleted server route propagates to the local row (deleted_at)
- server pull response excludes the geometry BLOB (JSON-safe)
- engine pushes a locally-written route (outbox capture → push)
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


def _push(client: TestClient, items: list[dict], device_id: str = "device-A") -> dict:
    resp = client.post(
        "/api/v1/sync/push",
        json={"items": items, "device_id": device_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _route_payload(fingerprint: str, seq: int = 1) -> dict:
    return {
        "route_fingerprint": fingerprint,
        "metadata_version": 1,
        "created_at": "2026-08-01T00:00:00Z",
        "last_calculated_at": f"2026-08-0{seq}T10:00:00Z",
        "calculation_count": seq,
        "stops_json": '[]',
        "geometry_encoding": "zlib-json",
        "total_distance_km": 100.5,
        "duration_min": 90.0,
        "profile": "fastest",
        "is_committed": 1,
    }


# ── Server push: fingerprint dedup ────────────────────────────────────────


class TestServerNaturalKey:
    def test_insert_with_existing_fingerprint_updates_not_duplicates(self, db):
        client = _make_client(db)
        fp = "fp-route-001"

        first = _push(client, [{
            "entity_type": "route_history", "op": "INSERT", "local_id": 1,
            "payload": _route_payload(fp, seq=1),
            "base_updated_at": None,
        }], device_id="device-A")
        server_id = first["results"][0]["server_id"]
        assert first["results"][0]["status"] == "ok"

        # Second device (different local_id, different device) pushes the SAME
        # fingerprint → must converge to the existing server row.
        second = _push(client, [{
            "entity_type": "route_history", "op": "INSERT", "local_id": 1,
            "payload": _route_payload(fp, seq=2),
            "base_updated_at": None,
        }], device_id="device-B")
        res = second["results"][0]
        assert res["status"] == "ok"
        assert res["server_id"] == server_id

        rows = db.conn.execute(
            "SELECT * FROM route_history_v2 WHERE route_fingerprint = ?", (fp,)
        ).fetchall()
        assert len(rows) == 1, "natural-key dedup failed — duplicate server row"
        assert rows[0]["calculation_count"] == 2, "payload was not applied as UPDATE"

        # Both devices' maps point at the same server row.
        maps = db.conn.execute(
            "SELECT device_id FROM sync_server_map WHERE entity_type = 'route_history' "
            "AND server_id = ?",
            (server_id,),
        ).fetchall()
        assert sorted(r["device_id"] for r in maps) == ["device-A", "device-B"]

    def test_pull_response_excludes_geometry_blob(self, db):
        """The pull response for route_history must be JSON-safe (no BLOB)."""
        client = _make_client(db)
        sid = _push(client, [{
            "entity_type": "route_history", "op": "INSERT", "local_id": 1,
            "payload": _route_payload("fp-blob-test"),
            "base_updated_at": None,
        }])["results"][0]["server_id"]

        # Seed a BLOB on the server row (as the route service would).
        db.conn.execute(
            "UPDATE route_history_v2 SET geometry_compressed = ? WHERE id = ?",
            (b"\x78\x9c\x4b\xcb\xcf\x07\x00\x02\x00\x01", sid),
        )
        db.conn.commit()

        resp = client.get(
            "/api/v1/sync/pull",
            params={"entity": "route_history", "after_id": 0, "limit": 10,
                    "device_id": "device-A"},
        )
        assert resp.status_code == 200
        records = resp.json()["records"]
        assert records
        assert "geometry_compressed" not in records[0]
        assert records[0]["route_fingerprint"] == "fp-blob-test"

    def test_conflict_response_excludes_geometry_blob(self, db):
        """B1: a conflict server_row must never serialize the geometry BLOB —
        a UnicodeDecodeError would 500 the whole push batch → retry wedge."""
        client = _make_client(db)
        sid = _push(client, [{
            "entity_type": "route_history", "op": "INSERT", "local_id": 1,
            "payload": _route_payload("fp-conflict-blob"),
            "base_updated_at": None,
        }])["results"][0]["server_id"]

        # Seed a BLOB on the server row.
        db.conn.execute(
            "UPDATE route_history_v2 SET geometry_compressed = ? WHERE id = ?",
            (b"\x78\x9c\x4b\xcb\xcf\x07\x00\x02\x00\x01", sid),
        )
        db.conn.commit()

        # Device-B INSERTs the SAME fingerprint → natural-key dedup maps it to
        # the existing row (which now carries the BLOB).
        res = _push(client, [{
            "entity_type": "route_history", "op": "INSERT", "local_id": 2,
            "payload": _route_payload("fp-conflict-blob", seq=2),
            "base_updated_at": None,
        }], device_id="device-B")
        assert res["results"][0]["status"] == "ok"
        assert res["results"][0]["server_id"] == sid

        # UPDATE with a STALE base_updated_at → conflict (server_row returned).
        resp = client.post(
            "/api/v1/sync/push",
            json={"items": [{
                "entity_type": "route_history", "op": "UPDATE", "local_id": 2,
                "payload": _route_payload("fp-conflict-blob", seq=3),
                "base_updated_at": "2020-01-01T00:00:00Z",
            }], "device_id": "device-B"},
        )
        assert resp.status_code == 200, resp.text  # must NOT 500
        result = resp.json()["results"][0]
        assert result["status"] == "conflict"
        assert "geometry_compressed" not in (result.get("server_row") or {})
        assert result["server_row"]["route_fingerprint"] == "fp-conflict-blob"


    def test_cross_company_fingerprint_collision_returns_terminal_error(self, db):
        """S2: the UNIQUE(route_fingerprint) constraint is GLOBAL — a truck-
        less route has the same fingerprint in every company.  An INSERT that
        collides with ANOTHER company's row must return a terminal error (so
        the lane drops it) instead of retrying forever."""
        fp = "fp-global-collision"
        c1 = _make_client(db, company_id=1)
        _push(c1, [{
            "entity_type": "route_history", "op": "INSERT", "local_id": 1,
            "payload": _route_payload(fp, seq=1),
            "base_updated_at": None,
        }], device_id="device-A")

        c2 = _make_client(db, company_id=2)
        res = _push(c2, [{
            "entity_type": "route_history", "op": "INSERT", "local_id": 1,
            "payload": _route_payload(fp, seq=1),
            "base_updated_at": None,
        }], device_id="device-B")
        result = res["results"][0]
        assert result["status"] == "error"
        assert "another company" in (result.get("error") or "")

        # Company 2 must NOT have a row (the collision belongs to company 1).
        n2 = db.conn.execute(
            "SELECT COUNT(*) AS n FROM route_history_v2 "
            "WHERE route_fingerprint = ? AND company_id = 2",
            (fp,),
        ).fetchone()["n"]
        assert n2 == 0


# ── Desktop pull: fingerprint adoption ────────────────────────────────────


class _PullFake:
    def __init__(self, responses):
        self.responses = responses
        self.pull_calls = []

    def get(self, path, params=None):
        self.pull_calls.append((path, params))
        entity = (params or {}).get("entity")
        return {
            "records": self.responses.get(entity, []),
            "next_after_id": 0,
            "has_more": False,
        }


class TestPullFingerprintAdoption:
    def test_pull_adopts_existing_local_row_by_fingerprint(self, db):
        """A local row with the same fingerprint is updated + mapped, not duplicated."""
        fp = "fp-pull-001"
        local_id = db.conn.execute(
            "INSERT INTO route_history_v2 (route_fingerprint, metadata_version, "
            "created_at, last_calculated_at, calculation_count, stops_json, "
            "geometry_encoding, total_distance_km, duration_min, profile, "
            "is_committed, company_id) "
            "VALUES (?, 1, '2026-08-01T00:00:00Z', '2026-08-01T09:00:00Z', 1, '[]', "
            "'zlib-json', 80.0, 60.0, 'fastest', 1, 1)",
            (fp,),
        ).lastrowid
        db.conn.commit()

        fake = _PullFake({"route_history": [
            {"id": 900, "route_fingerprint": fp, "metadata_version": 1,
             "created_at": "2026-08-01T00:00:00Z",
             "last_calculated_at": "2026-08-02T10:00:00Z", "calculation_count": 2,
             "stops_json": '[]', "geometry_encoding": "zlib-json",
             "total_distance_km": 120.0, "duration_min": 95.0, "profile": "fastest",
             "is_committed": 1, "company_id": 1,
             "updated_at": "2026-08-02T10:00:00Z", "deleted_at": None},
        ]})
        pull = SyncPullService(db, fake)
        count = pull.pull_entity("route_history", device_id="device-A")

        assert count == 1
        rows = db.conn.execute(
            "SELECT * FROM route_history_v2 WHERE route_fingerprint = ?", (fp,)
        ).fetchall()
        assert len(rows) == 1, "duplicate local row created"
        assert rows[0]["calculation_count"] == 2
        assert rows[0]["total_distance_km"] == 120.0
        # The local row is now mapped to server row 900.
        mapping = db.conn.execute(
            "SELECT local_id FROM sync_id_map "
            "WHERE entity_type = 'route_history' AND server_id = 900"
        ).fetchone()
        assert mapping is not None and mapping["local_id"] == local_id

    def test_pull_inserts_new_fingerprint(self, db):
        fp = "fp-new-001"
        fake = _PullFake({"route_history": [
            {"id": 901, "route_fingerprint": fp, "metadata_version": 1,
             "created_at": "2026-08-01T00:00:00Z",
             "last_calculated_at": "2026-08-01T10:00:00Z", "calculation_count": 1,
             "stops_json": '[]', "geometry_encoding": "zlib-json",
             "total_distance_km": 50.0, "duration_min": 40.0, "profile": "fastest",
             "is_committed": 1, "company_id": 1,
             "updated_at": "2026-08-01T10:00:00Z", "deleted_at": None},
        ]})
        pull = SyncPullService(db, fake)
        count = pull.pull_entity("route_history", device_id="device-A")

        assert count == 1
        rows = db.conn.execute(
            "SELECT * FROM route_history_v2 WHERE route_fingerprint = ?", (fp,)
        ).fetchall()
        assert len(rows) == 1
        mapping = db.conn.execute(
            "SELECT local_id FROM sync_id_map "
            "WHERE entity_type = 'route_history' AND server_id = 901"
        ).fetchone()
        assert mapping is not None

    def test_deleted_route_propagates(self, db):
        fp = "fp-deleted-001"
        db.conn.execute(
            "INSERT INTO route_history_v2 (route_fingerprint, metadata_version, "
            "created_at, last_calculated_at, calculation_count, stops_json, "
            "geometry_encoding, is_committed, company_id) "
            "VALUES (?, 1, '2026-08-01T00:00:00Z', '2026-08-01T09:00:00Z', 1, '[]', "
            "'zlib-json', 1, 1)",
            (fp,),
        )
        db.conn.commit()
        local_id = db.conn.execute(
            "SELECT id FROM route_history_v2 WHERE route_fingerprint = ?", (fp,)
        ).fetchone()["id"]
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('route_history', ?, 902, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()

        fake = _PullFake({"route_history": [
            {"id": 902, "route_fingerprint": fp, "metadata_version": 1,
             "created_at": "2026-08-01T00:00:00Z",
             "last_calculated_at": "2026-08-01T09:00:00Z", "calculation_count": 1,
             "stops_json": '[]', "geometry_encoding": "zlib-json",
             "is_committed": 1, "company_id": 1,
             "updated_at": "2026-08-03T00:00:00Z",
             "deleted_at": "2026-08-03T00:00:00Z"},
        ]})
        pull = SyncPullService(db, fake)
        count = pull.pull_entity("route_history", device_id="device-A")

        assert count == 1
        row = db.conn.execute(
            "SELECT deleted_at FROM route_history_v2 WHERE id = ?", (local_id,)
        ).fetchone()
        assert row["deleted_at"] == "2026-08-03T00:00:00Z"


# ── Engine: local route captured + pushed ─────────────────────────────────


class _EngineFake:
    def __init__(self, push_handler=None):
        self.push_handler = push_handler
        self.push_calls = []
        self.pull_calls = []
        self.online = True

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
        if entity == "tombstone":
            return {"records": [], "next_after_id": 0, "has_more": False}
        return {"records": [], "next_after_id": 0, "has_more": False}


def _ok_handler(server_id=500):
    def handler(items):
        return {"results": [
            {"local_id": it["local_id"], "server_id": server_id, "status": "ok"}
            for it in items
        ]}
    return handler


class TestEngineRoutePush:
    def test_local_route_write_is_pushed_via_outbox(self, db):
        db.conn.execute(
            "INSERT INTO route_history_v2 (route_fingerprint, metadata_version, "
            "created_at, last_calculated_at, calculation_count, stops_json, "
            "geometry_encoding, is_committed, company_id) "
            "VALUES ('fp-engine-001', 1, '2026-08-01T00:00:00Z', "
            "'2026-08-01T09:00:00Z', 1, '[]', 'zlib-json', 1, 1)",
        )
        db.conn.commit()

        outbox = SyncOutboxService(db)
        pending = [r for r in outbox.pending() if r["entity_type"] == "route_history"]
        assert pending, "route_history outbox trigger did not capture the write"

        fake = _EngineFake(push_handler=_ok_handler(server_id=510))
        pull = SyncPullService(db, fake)
        engine = SyncEngine(db, fake, outbox, pull)
        engine.sync_once()

        assert any(
            item["entity_type"] == "route_history"
            for _, body in fake.push_calls for item in body["items"]
        ), "route_history was not pushed"
        # The write is confirmed (mapping recorded).
        mapping = db.conn.execute(
            "SELECT server_id FROM sync_id_map "
            "WHERE entity_type = 'route_history' AND server_id = 510"
        ).fetchone()
        assert mapping is not None
