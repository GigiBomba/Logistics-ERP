"""Integration tests for the clients API endpoints (``/api/v1/clients``).

Uses ``client_with_mocks`` for mocked service layer.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/clients"


class TestClientsListEndpoint:
    """GET /api/v1/clients/"""

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

    def test_list_clients_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.return_value = []

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_clients_with_search(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].search_advanced.return_value = [
            {"id": 1, "name": "Acme"},
        ]

        resp = client.get(f"{BASE}/?query=acme&include_inactive=true&limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        mocks["client_service"].search_advanced.assert_called_once_with(
            "acme", include_inactive=True, limit=50,
        )

    def test_list_clients_defaults_when_no_query(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.return_value = []

        resp = client.get(f"{BASE}/?include_inactive=false")
        assert resp.status_code == 200
        mocks["client_service"].get_all.assert_called_once_with(
            include_inactive=False,
        )


class TestClientsGetEndpoint:
    """GET /api/v1/clients/{client_id}"""

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


class TestClientsCreateEndpoint:
    """POST /api/v1/clients/"""

    def test_create_client_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].create.return_value = 10

        resp = client.post(f"{BASE}/?name=NewCo", json={"email": "n@n.com"})
        assert resp.status_code == 200
        assert resp.json() == {"id": 10}
        mocks["client_service"].create.assert_called_once_with(
            name="NewCo", email="n@n.com",
        )


class TestClientsUpdateEndpoint:
    """PUT /api/v1/clients/{client_id}"""

    def test_update_client_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.put(f"{BASE}/1", json={"phone": "123"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mocks["client_service"].update.assert_called_once_with(1, phone="123")


class TestClientsDeleteEndpoint:
    """POST /api/v1/clients/{client_id}/deactivate (soft-delete)"""

    def test_deactivate_client_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/1/deactivate")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deactivated"}
        mocks["client_service"].deactivate.assert_called_once_with(1)


class TestClientsSubResources:
    """Sub-resource endpoints for clients."""

    def test_get_client_dashboard(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_client_dashboard.return_value = {
            "total_trips": 5, "revenue": 1000,
        }

        resp = client.get(f"{BASE}/1/dashboard")
        assert resp.status_code == 200
        assert resp.json()["total_trips"] == 5

    def test_get_client_trips(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_client_trips.return_value = [
            {"id": 10, "status": "completed"},
        ]

        resp = client.get(f"{BASE}/1/trips?limit=10&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1

    def test_get_client_invoices(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_client_invoices.return_value = [
            {"id": 1, "amount": 500.0},
        ]

        resp = client.get(f"{BASE}/1/invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_get_client_trip_count(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_trip_count.return_value = 42

        resp = client.get(f"{BASE}/1/trip-count")
        assert resp.status_code == 200
        assert resp.json() == {"count": 42}

    def test_get_client_contacts(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_contacts.return_value = [
            {"id": 1, "name": "Alice"},
        ]

        resp = client.get(f"{BASE}/1/contacts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_add_client_contact(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].add_contact.return_value = 7

        resp = client.post(f"{BASE}/1/contacts", json={"name": "Bob"})
        assert resp.status_code == 201
        assert resp.json() == {"id": 7}

    def test_get_client_tags(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_tags.return_value = ["vip", "fleet"]

        resp = client.get(f"{BASE}/1/tags")
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["vip", "fleet"]

    def test_add_client_tag(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/1/tags", json={"tag": "vip"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "tag_added"}

    def test_get_payment_summary(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake = {"total_paid": 10000.0, "total_due": 2500.0}
        mocks["client_service"].get_payment_summary.return_value = fake

        resp = client.get(f"{BASE}/1/payment-summary")
        assert resp.status_code == 200
        assert resp.json() == fake

    def test_get_client_revenue_history(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake = [{"month": "2024-01", "revenue": 5000.0}]
        mocks["client_service"].get_client_revenue_history.return_value = fake

        resp = client.get(f"{BASE}/1/revenue-history")
        assert resp.status_code == 200
        assert resp.json() == fake


class TestClientsAuth:
    """Authentication gates."""

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.side_effect = RuntimeError("fail")
        with pytest.raises(RuntimeError, match="fail"):
            client.get(f"{BASE}/")
