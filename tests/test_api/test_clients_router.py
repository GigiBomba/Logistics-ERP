"""Tests for the clients API router (``/api/v1/clients``)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/clients"


class TestClientsRouter:
    """CRUD + extra sub-resource endpoints for clients."""

    # ── list ──────────────────────────────────────────────────────────────

    def test_list_clients_returns_200_with_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.return_value = [
            {"id": 1, "name": "Acme", "email": "a@a.com"},
            {"id": 2, "name": "Beta", "email": "b@b.com"},
        ]

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2

    def test_list_clients_with_search_passes_query(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].search_advanced.return_value = [
            {"id": 1, "name": "Acme"},
        ]

        resp = client.get(f"{BASE}/?query=acme&include_inactive=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        mocks["client_service"].search_advanced.assert_called_once_with(
            "acme", include_inactive=True, limit=20,
        )

    def test_list_clients_defaults_to_all_when_no_query(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.return_value = []

        resp = client.get(f"{BASE}/?include_inactive=false")
        assert resp.status_code == 200
        mocks["client_service"].get_all.assert_called_once_with(
            include_inactive=False,
        )

    # ── get by id ─────────────────────────────────────────────────────────

    def test_get_client_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_by_id.return_value = {
            "id": 1, "name": "Acme", "is_active": True,
            "created_at": "2024-01-01",
        }

        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_get_client_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE}/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    # ── create ────────────────────────────────────────────────────────────

    def test_create_client_returns_id(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].create.return_value = 10

        resp = client.post(f"{BASE}/", json={"name": "NewCo", "email": "n@n.com"})
        assert resp.status_code == 200
        assert resp.json() == {"id": 10}
        mocks["client_service"].create.assert_called_once()
        call_kwargs = mocks["client_service"].create.call_args[1]
        assert call_kwargs["name"] == "NewCo"
        assert call_kwargs["email"] == "n@n.com"

    # ── update ────────────────────────────────────────────────────────────

    def test_update_client_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.put(f"{BASE}/1", json={"phone": "123"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mocks["client_service"].update.assert_called_once_with(1, phone="123")

    # ── dashboard / sub-resources ─────────────────────────────────────────

    def test_get_client_dashboard_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_client_dashboard.return_value = {
            "total_trips": 5, "revenue": 1000,
        }

        resp = client.get(f"{BASE}/1/dashboard")
        assert resp.status_code == 200
        assert resp.json()["total_trips"] == 5

    def test_get_client_trips_returns_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_client_trips.return_value = [
            {"id": 10, "status": "completed"},
        ]

        resp = client.get(f"{BASE}/1/trips?page_size=10&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        mocks["client_service"].get_client_trips.assert_called_once_with(
            1, limit=10, offset=0,
        )

    def test_deactivate_client_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/1/deactivate")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deactivated"}
        mocks["client_service"].deactivate.assert_called_once_with(1)

    def test_get_client_tags_returns_tags(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_tags.return_value = ["vip", "fleet"]

        resp = client.get(f"{BASE}/1/tags")
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["vip", "fleet"]
        mocks["client_service"].get_tags.assert_called_once_with(1)

    # ── error handling ────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        """Unhandled service exceptions return 500."""
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.side_effect = RuntimeError("fail")

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 500

    # ── invoices ───────────────────────────────────────────────────────────

    def test_get_client_invoices(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_items = [{"id": 1, "amount": 500.0}]
        mocks["client_service"].get_client_invoices.return_value = fake_items

        resp = client.get(f"{BASE}/1/invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        mocks["client_service"].get_client_invoices.assert_called_once_with(
            1, limit=50
        )

    def test_get_client_invoices_with_limit(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_client_invoices.return_value = []

        resp = client.get(f"{BASE}/1/invoices?page_size=5")
        assert resp.status_code == 200
        mocks["client_service"].get_client_invoices.assert_called_once_with(
            1, limit=5
        )

    # ── trip-count ─────────────────────────────────────────────────────────

    def test_get_client_trip_count(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_trip_count.return_value = 42

        resp = client.get(f"{BASE}/1/trip-count")
        assert resp.status_code == 200
        assert resp.json() == {"count": 42}
        mocks["client_service"].get_trip_count.assert_called_once_with(1)

    # ── contacts ──────────────────────────────────────────────────────────

    def test_get_client_contacts(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_contacts = [{"id": 1, "name": "Alice"}]
        mocks["client_service"].get_contacts.return_value = fake_contacts

        resp = client.get(f"{BASE}/1/contacts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        mocks["client_service"].get_contacts.assert_called_once_with(1)

    def test_add_client_contact(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].add_contact.return_value = 7

        resp = client.post(
            f"{BASE}/1/contacts",
            json={"name": "Bob", "email": "bob@test.com"},
        )
        assert resp.status_code == 201
        assert resp.json() == {"id": 7}
        mocks["client_service"].add_contact.assert_called_once()
        call_args = mocks["client_service"].add_contact.call_args
        assert call_args[0][0] == 1  # client_id
        assert call_args[1]["name"] == "Bob"
        assert call_args[1]["email"] == "bob@test.com"

    # ── tags ───────────────────────────────────────────────────────────────

    def test_add_client_tag(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/1/tags", json={"tag": "vip"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "tag_added"}
        mocks["client_service"].add_tag.assert_called_once_with(1, "vip")

    def test_add_client_tag_empty(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/1/tags", json={"tag": ""})
        assert resp.status_code == 200
        assert resp.json() == {"status": "tag_added"}
        mocks["client_service"].add_tag.assert_not_called()

    # ── payment-summary ───────────────────────────────────────────────────

    def test_get_payment_summary(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_summary = {"total_paid": 10000.0, "total_due": 2500.0}
        mocks["client_service"].get_payment_summary.return_value = fake_summary

        resp = client.get(f"{BASE}/1/payment-summary")
        assert resp.status_code == 200
        assert resp.json() == fake_summary
        mocks["client_service"].get_payment_summary.assert_called_once_with(1)

    # ── revenue-history ───────────────────────────────────────────────────

    def test_get_client_revenue_history(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_history = [{"month": "2024-01", "revenue": 5000.0}]
        mocks["client_service"].get_client_revenue_history.return_value = fake_history

        resp = client.get(f"{BASE}/1/revenue-history")
        assert resp.status_code == 200
        assert resp.json() == fake_history
        mocks["client_service"].get_client_revenue_history.assert_called_once_with(
            1, months=12
        )

    # ── auth ──────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
