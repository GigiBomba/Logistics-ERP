"""Tests for Trans.eu webhook endpoint handler.

Covers: payload parsing, company extraction, event routing.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from tests.test_helpers import InMemoryDB


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def sample_webhook_payload():
    return {
        "id": "87795",
        "event_name": "freights.proposal_request.accepted",
        "occurred_at": "2026-01-25T11:41:11+00:00",
        "data": {"price": 560.20, "author_id": "12665-1"},
    }


class TestTransEuWebhookParsing:
    def test_payload_has_required_fields(self, sample_webhook_payload):
        assert "id" in sample_webhook_payload
        assert "event_name" in sample_webhook_payload
        assert "occurred_at" in sample_webhook_payload
        # data is optional in Trans.eu spec but often present
        assert isinstance(sample_webhook_payload.get("id"), str)

    def test_event_name_prefix_routing(self, sample_webhook_payload):
        name = sample_webhook_payload["event_name"]
        assert name.startswith("freights."), f"Unexpected prefix: {name}"


@pytest.mark.parametrize("event_id,event_name,expected", [
    ("1", "freights.freight.create", "freight"),
    ("2", "freight_orders.order.delivery_was_confirmed", "order"),
    ("3", "transports.transport.devices_set_changed", "transport"),
    ("4", "time_slot_management.announcement.created", "dock"),
    ("5", "something.else.altogether", "unknown"),
])
def test_event_routing_from_ingestion(event_id, event_name, expected):
    """Verify WebhookIngestionService.route_event categorizes correctly."""
    from services.trans_eu.webhook_ingestion import WebhookIngestionService
    service = WebhookIngestionService(None)
    assert service.route_event(event_name) == expected


class TestCompanyExtraction:
    def test_extract_from_event_id_via_freight_table(self, db):
        """_extract_company_from_trans_eu_event finds company from freight_offers."""
        db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_freight_offers (
            id TEXT, company_id INTEGER, user_id INTEGER,
            trans_eu_freight_id INTEGER, origin TEXT, destination TEXT,
            created_at TEXT, updated_at TEXT
        )""")
        db.conn.execute("INSERT INTO trans_eu_freight_offers VALUES ('f1',1,1,87795,'X','Y','now','now')")
        db.conn.commit()

        from backend.api.v1.webhooks import _extract_company_from_trans_eu_event
        result = _extract_company_from_trans_eu_event({"id": "87795"}, db)
        assert result == 1

    def test_extract_from_data_freight_id(self, db):
        db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_freight_offers (
            id TEXT, company_id INTEGER, user_id INTEGER,
            trans_eu_freight_id INTEGER, origin TEXT, destination TEXT,
            created_at TEXT, updated_at TEXT
        )""")
        db.conn.execute("INSERT INTO trans_eu_freight_offers VALUES ('f1',1,1,99999,'X','Y','now','now')")
        db.conn.commit()

        from backend.api.v1.webhooks import _extract_company_from_trans_eu_event
        payload = {"data": {"freight_id": 99999}}
        result = _extract_company_from_trans_eu_event(payload, db)
        assert result == 1

    def test_no_match_returns_none(self, db):
        from backend.api.v1.webhooks import _extract_company_from_trans_eu_event
        result = _extract_company_from_trans_eu_event({"id": "999999"}, db)
        assert result is None


class _SharedConnDB:
    """In-memory SQLite DB whose single connection is shared across threads.

    TestClient executes the ASGI app in a worker thread, but
    ``DatabaseManager.conn`` is thread-local — a second thread would get a
    fresh, empty in-memory database.  A single ``check_same_thread=False``
    connection keeps the tables visible to both the test body and the route.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @staticmethod
    def row_to_dict(row):
        return dict(row) if row else None

    @staticmethod
    def rows_to_dicts(rows):
        return [dict(r) for r in rows] if rows else []

    def execute(self, query, params=()):
        return self.conn.execute(query, params)


class TestTransEuWebhookEndpoint:
    """POST /api/v1/webhooks/trans-eu/{company_id} — dedicated Trans.eu receiver."""

    BASE = "/api/v1/webhooks/trans-eu"

    def _make_db_with_tables(self):
        conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_freight_offers (
            id TEXT PRIMARY KEY, company_id INTEGER, user_id INTEGER,
            trans_eu_freight_id INTEGER, status TEXT DEFAULT 'draft',
            publication_status TEXT, origin TEXT, destination TEXT,
            created_at TEXT, updated_at TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_webhook_events (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            company_id INTEGER, trans_eu_event_id TEXT UNIQUE,
            event_name TEXT, occurred_at TEXT, payload TEXT,
            status TEXT DEFAULT 'received', processed_at TEXT,
            error_message TEXT, created_at TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_webhook_events_failed (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            company_id INTEGER, trans_eu_event_id TEXT,
            event_name TEXT, payload TEXT, error_message TEXT,
            error_type TEXT, attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 10, next_retry_at TEXT,
            status TEXT DEFAULT 'pending', created_at TEXT
        )""")
        conn.commit()
        return _SharedConnDB(conn)

    def _payload(self, event_name, event_id, freight_id):
        return {
            "id": event_id,
            "event_name": event_name,
            "occurred_at": "2026-01-25T11:41:11+00:00",
            "data": {"freight_id": freight_id},
        }

    def test_freight_event_updates_freight_offer(self, app):
        """POST /trans-eu/{company_id} processes a freight event end-to-end."""
        from backend.dependencies import get_db

        db = self._make_db_with_tables()
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, user_id, trans_eu_freight_id, status, origin, destination, created_at, updated_at) "
            "VALUES ('f-r1', 1, 1, 900, 'draft', 'Krakow', 'Berlin', ?, ?)",
            (now, now),
        )
        db.conn.commit()
        app.dependency_overrides[get_db] = lambda: db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs:
            gs.return_value = ""  # no secret configured — skip check
            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/1",
                json=self._payload("freights.publication.activated", "evt-r1", 900),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processed"
        assert data["company_id"] == 1
        assert data["event_id"] == "evt-r1"
        assert data["category"] == "freight"

        freight = db.conn.execute(
            "SELECT status, publication_status FROM trans_eu_freight_offers"
            " WHERE trans_eu_freight_id = 900"
        ).fetchone()
        assert freight[0] == "published"
        assert freight[1] == "active"

        app.dependency_overrides.clear()

    def test_invalid_secret_rejected(self, app):
        """A mismatched ?secret= query param returns 403."""
        from backend.dependencies import get_db

        db = self._make_db_with_tables()
        app.dependency_overrides[get_db] = lambda: db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs:
            gs.return_value = "real-secret"
            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/1?secret=wrong",
                json=self._payload("freights.freight.create", "evt-r2", 901),
            )

        assert resp.status_code == 403
        assert "secret" in resp.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_valid_secret_accepted(self, app):
        """A matching ?secret= query param is accepted."""
        from backend.dependencies import get_db

        db = self._make_db_with_tables()
        app.dependency_overrides[get_db] = lambda: db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs:
            gs.return_value = "real-secret"
            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/1?secret=real-secret",
                json=self._payload("freights.freight.create", "evt-r3", 902),
            )

        assert resp.status_code == 200
        assert resp.json()["status"] in ("processed", "skipped")

        app.dependency_overrides.clear()

    def test_invalid_json_returns_400(self, app):
        """Non-JSON body yields 400."""
        from backend.dependencies import get_db

        db = self._make_db_with_tables()
        app.dependency_overrides[get_db] = lambda: db

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs:
            gs.return_value = ""
            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/1",
                content=b"this is not json",
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

        app.dependency_overrides.clear()

    def test_always_acknowledges_processing_failures(self, app):
        """A failing sync still returns 200 — the event goes to the DLQ."""
        from backend.dependencies import get_db

        db = self._make_db_with_tables()
        app.dependency_overrides[get_db] = lambda: db

        from services.trans_eu.sync_service import FreightSyncService
        from unittest.mock import AsyncMock

        with patch("backend.api.v1.webhooks._get_webhook_secret") as gs, \
             patch.object(
                 FreightSyncService,
                 "process_freight_event",
                 new=AsyncMock(side_effect=RuntimeError("route boom")),
             ):
            gs.return_value = ""
            client = TestClient(app)
            resp = client.post(
                f"{self.BASE}/1",
                json=self._payload("freights.freight.update", "evt-r4", 903),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"

        dlq = db.conn.execute(
            "SELECT trans_eu_event_id, error_type FROM trans_eu_webhook_events_failed"
        ).fetchone()
        assert dlq is not None
        assert dlq[0] == "evt-r4"
        assert dlq[1] == "processing"

        app.dependency_overrides.clear()
