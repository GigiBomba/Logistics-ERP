"""Tests for Phase D — sequence reconciliation (invoice/CMR counters).

Covers:
- server POST /sync/sequences max-merges: a higher value bumps the counter,
  a lower value is a no-op (both invoice_number_sequences and cmr_counter)
- the engine calls reconcile_sequences after a successful push
  (fake ApiClient records the calls)
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


def _reconcile(client: TestClient, entity: str, year: int, value: int) -> dict:
    resp = client.post(
        "/api/v1/sync/sequences",
        json={"entity": entity, "year": year, "value": value},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Server: max-merge endpoint ────────────────────────────────────────────


class TestServerSequences:
    def test_invoice_higher_value_bumps(self, db):
        client = _make_client(db)
        body = _reconcile(client, "invoice", 2026, 7)
        row = db.conn.execute(
            "SELECT last_number FROM invoice_number_sequences "
            "WHERE series = 'inv_year_seq' AND year = 2026"
        ).fetchone()
        assert row["last_number"] == 7
        # B5: the response carries the POST-MERGE value (the desktop applies
        # it back so the next allocation cannot re-use a server number).
        assert body["value"] == 7

    def test_invoice_lower_value_is_noop(self, db):
        client = _make_client(db)
        _reconcile(client, "invoice", 2026, 7)
        body = _reconcile(client, "invoice", 2026, 3)  # stale desktop — must NOT decrease
        row = db.conn.execute(
            "SELECT last_number FROM invoice_number_sequences "
            "WHERE series = 'inv_year_seq' AND year = 2026"
        ).fetchone()
        assert row["last_number"] == 7
        # B5: the merged value stays at the higher server value.
        assert body["value"] == 7

    def test_cmr_higher_value_bumps_lower_is_noop(self, db):
        client = _make_client(db)
        _reconcile(client, "cmr", 2026, 12)
        row = db.conn.execute(
            "SELECT sequence_number FROM cmr_counter WHERE year = 2026"
        ).fetchone()
        assert row["sequence_number"] == 12

        body = _reconcile(client, "cmr", 2026, 4)
        row = db.conn.execute(
            "SELECT sequence_number FROM cmr_counter WHERE year = 2026"
        ).fetchone()
        assert row["sequence_number"] == 12
        assert body["value"] == 12

    def test_invalid_entity_rejected(self, db):
        client = _make_client(db)
        resp = client.post(
            "/api/v1/sync/sequences",
            json={"entity": "receipt", "year": 2026, "value": 1},
        )
        assert resp.status_code == 422


# ── Desktop: engine calls reconcile after push ────────────────────────────


class _ReconcileFake:
    def __init__(self, merged=None):
        self.online = True
        self.push_calls = []
        self.pull_calls = []
        self.reconcile_calls = []  # (entity, year, value)
        self.merged = merged or {}

    def is_online(self):
        return self.online

    def post(self, path, json=None):
        self.push_calls.append((path, json))
        return {"results": []}

    def get(self, path, params=None):
        self.pull_calls.append((path, params))
        return {"records": [], "next_after_id": 0, "has_more": False}

    def reconcile_sequences(self, entity, year, value):
        self.reconcile_calls.append((entity, year, value))
        merged = self.merged.get((entity, year))
        return {"status": "ok", "value": merged if merged is not None else value}


class TestEngineReconcile:
    def test_reconcile_after_push(self, db):
        # Seed local counters (the desktop's numbering state).
        db.conn.execute(
            "INSERT INTO cmr_counter (year, sequence_number) VALUES (2026, 5)"
        )
        db.conn.execute(
            "INSERT INTO invoice_number_sequences (series, year, last_number) "
            "VALUES ('inv_year_seq', 2026, 9)"
        )
        db.conn.commit()

        fake = _ReconcileFake()
        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, fake)
        engine = SyncEngine(db, fake, outbox, pull)
        engine.sync_once()

        calls = sorted(fake.reconcile_calls)
        assert ("cmr", 2026, 5) in calls
        assert ("invoice", 2026, 9) in calls

    def test_reconcile_converges_local_counter_to_server_max(self, db):
        """B5: the server's post-merge value is applied BACK — the local
        counter converges to the server max so the next allocation cannot
        re-use a number another device already handed out."""
        db.conn.execute(
            "INSERT INTO cmr_counter (year, sequence_number) VALUES (2026, 5)"
        )
        db.conn.execute(
            "INSERT INTO invoice_number_sequences (series, year, last_number) "
            "VALUES ('inv_year_seq', 2026, 9)"
        )
        db.conn.commit()

        # The server already allocated higher numbers (device B did).
        fake = _ReconcileFake(merged={("cmr", 2026): 42, ("invoice", 2026): 99})
        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, fake)
        engine = SyncEngine(db, fake, outbox, pull)
        engine.sync_once()

        cmr = db.conn.execute(
            "SELECT sequence_number FROM cmr_counter WHERE year = 2026"
        ).fetchone()["sequence_number"]
        assert cmr == 42, "local cmr counter did not converge to server max"
        inv = db.conn.execute(
            "SELECT last_number FROM invoice_number_sequences "
            "WHERE series = 'inv_year_seq' AND year = 2026"
        ).fetchone()["last_number"]
        assert inv == 99, "local invoice counter did not converge to server max"

    def test_reconcile_skipped_without_support(self, db):
        """A fake without reconcile_sequences must not break the cycle."""
        class Minimal:
            online = True

            def is_online(self):
                return True

            def post(self, path, json=None):
                return {"results": []}

            def get(self, path, params=None):
                return {"records": [], "next_after_id": 0, "has_more": False}

        fake = Minimal()
        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, fake)
        engine = SyncEngine(db, fake, outbox, pull)
        engine.sync_once()  # must not raise
