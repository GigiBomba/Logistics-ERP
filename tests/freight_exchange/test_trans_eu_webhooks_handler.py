"""Tests for Trans.eu webhook endpoint handler.

Covers: payload parsing, company extraction, event routing.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
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
