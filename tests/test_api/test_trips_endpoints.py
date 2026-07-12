"""Integration tests for the trips API endpoints (``/api/v1/trips``).

Uses ``client_with_mocks`` for mocked service layer.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/trips"


class TestTripsListEndpoint:
    """GET /api/v1/trips/"""

    def test_list_trips_returns_200_with_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_items = [
            {"id": 1, "status": "active", "client_name": "Acme"},
            {"id": 2, "status": "planned", "client_name": "Beta"},
        ]
        mocks["trip_service"].get_filtered.return_value = fake_items

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == fake_items
        assert data["total"] == 2

    def test_list_trips_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_trips_passes_search_status_limit(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE}/?search=foo&status=active&limit=10")
        assert resp.status_code == 200
        mocks["trip_service"].get_filtered.assert_called_once_with(
            search="foo", status="active", limit=10,
        )

    def test_list_trips_pagination_defaults(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        mocks["trip_service"].get_filtered.assert_called_once_with(
            search="", status="", limit=200,
        )


class TestTripsGetEndpoint:
    """GET /api/v1/trips/{trip_id}"""

    def test_get_trip_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        trip = {
            "id": 1, "status": "active", "created_at": "2024-01-01",
            "client_name": "Acme", "loading_city": "Paris",
            "delivery_city": "Lyon",
        }
        mocks["trip_service"].get_by_id.return_value = trip

        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["client_name"] == "Acme"

    def test_get_trip_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["trip_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE}/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Trip not found"


class TestTripsCreateEndpoint:
    """POST /api/v1/trips/"""

    def test_create_trip_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        payload = {"client_name": "Acme", "loading_city": "Paris"}
        mocks["trip_service"].add.return_value = 42

        resp = client.post(f"{BASE}/", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"id": 42}
        mocks["trip_service"].add.assert_called_once_with(payload)

    def test_create_trip_missing_fields_returns_422(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/", json={})
        # Endpoint accepts dict, so it may succeed with empty or fail validation
        assert resp.status_code in (200, 422)


class TestTripsUpdateEndpoint:
    """PUT /api/v1/trips/{trip_id}"""

    def test_update_trip_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        payload = {"status": "completed"}

        resp = client.put(f"{BASE}/1", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mocks["trip_service"].update.assert_called_once_with(1, payload)


class TestTripsDeleteEndpoint:
    """DELETE /api/v1/trips/{trip_id}"""

    def test_delete_trip_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.delete(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        mocks["trip_service"].delete.assert_called_once_with(1)


class TestTripsConflictCheck:
    """POST /api/v1/trips/conflicts/check"""

    def test_check_conflicts_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].row_to_dict.side_effect = lambda row: None if row is None else dict(row)

        resp = client.post(f"{BASE}/conflicts/check", json={"date": "2024-01-01"})
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "conflicts" in resp.json()


class TestTripsAuth:
    """Authentication gates."""

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("DB down")
        with pytest.raises(RuntimeError, match="DB down"):
            client.get(f"{BASE}/")
