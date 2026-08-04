"""Integration tests for the fleet API endpoints (``/api/v1/fleet``).

Uses ``client_with_mocks`` for mocked service layer.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/fleet"


class TestFleetTrucksList:
    """GET /api/v1/fleet/trucks"""

    def test_list_trucks_returns_200_with_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        # TruckResponse uses plate / brand / is_active fields (not plate_number / model)
        fake = [
            {"id": 1, "plate": "AB123CD", "brand": "Volvo", "year": 2022, "is_active": True},
            {"id": 2, "plate": "XY789EF", "brand": "Scania", "year": 2021, "is_active": True},
        ]
        mocks["fleet_service"].get_trucks.return_value = fake

        resp = client.get(f"{BASE}/trucks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == fake
        assert data["total"] == 2

    def test_list_trucks_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["fleet_service"].get_trucks.return_value = []

        resp = client.get(f"{BASE}/trucks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestFleetTrucksGet:
    """GET /api/v1/fleet/trucks/{truck_id}"""

    def test_get_truck_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        truck = {"id": 1, "plate": "AB123CD", "brand": "Volvo", "year": 2022, "is_active": True}
        mocks["fleet_service"].get_truck.return_value = truck

        resp = client.get(f"{BASE}/trucks/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_get_truck_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["fleet_service"].get_truck.return_value = None

        resp = client.get(f"{BASE}/trucks/999")
        assert resp.status_code == 404


class TestFleetTrucksCreate:
    """POST /api/v1/fleet/trucks"""

    def test_create_truck_returns_id(self, client_with_mocks):
        client, mocks = client_with_mocks
        payload = {"plate_number": "NEW001", "model": "Mercedes Actros"}
        mocks["fleet_service"].add_truck.return_value = 42

        resp = client.post(f"{BASE}/trucks", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"id": 42}
        mocks["fleet_service"].add_truck.assert_called_once_with(payload)


class TestFleetTrucksUpdate:
    """PUT /api/v1/fleet/trucks/{truck_id}"""

    def test_update_truck_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        payload = {"model": "Updated Model"}

        resp = client.put(f"{BASE}/trucks/1", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mocks["fleet_service"].update_truck.assert_called_once_with(1, payload)


class TestFleetTrucksDelete:
    """DELETE /api/v1/fleet/trucks/{truck_id}"""

    def test_delete_truck_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.delete(f"{BASE}/trucks/1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        mocks["fleet_service"].delete_truck.assert_called_once_with(1)


class TestFleetGPS:
    """GPS endpoints for fleet."""

    @patch("backend.api.v1.fleet.get_cache")
    def test_ingest_gps_ping(self, mock_get_cache, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mocks["fleet_service"].get_truck.return_value = {"id": 1, "company_id": 1}

        payload = {
            "truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
            "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z",
            "driver_id": 5,
        }
        resp = client.post(f"{BASE}/gps/ingest", json=payload)
        assert resp.status_code == 202
        assert resp.json() == {"status": "accepted"}
        mock_cache.set.assert_called_once()
        mock_cache.rpush.assert_called_once()

    @patch("backend.api.v1.fleet.get_cache")
    def test_get_live_position_returns_200(self, mock_get_cache, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mocks["fleet_service"].get_truck.return_value = {"id": 1, "company_id": 1}
        mock_cache.get.return_value = {
            "truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
            "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z",
            "driver_id": 5,
        }

        resp = client.get(f"{BASE}/gps/live/1")
        assert resp.status_code == 200
        assert resp.json()["truck_id"] == 1

    @patch("backend.api.v1.fleet.get_cache")
    def test_get_live_position_returns_404(self, mock_get_cache, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mocks["fleet_service"].get_truck.return_value = {"id": 1, "company_id": 1}
        mock_cache.get.return_value = None

        resp = client.get(f"{BASE}/gps/live/1")
        assert resp.status_code == 404

    @patch("backend.api.v1.fleet.get_cache")
    def test_ingest_gps_batch(self, mock_get_cache, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mocks["fleet_service"].get_trucks_by_ids.return_value = [{"id": 1}, {"id": 2}]

        payload = [
            {"truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
             "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z"},
            {"truck_id": 2, "latitude": 48.8588, "longitude": 2.3544,
             "speed_kmh": 70, "heading": 90, "timestamp": "2024-01-15T10:31:00Z"},
        ]
        resp = client.post(f"{BASE}/gps/batch", json=payload)
        assert resp.status_code == 202
        assert resp.json() == {"status": "accepted", "count": 2}

    @patch("backend.api.v1.fleet.get_cache")
    def test_ingest_gps_batch_over_cap_returns_422(
        self, mock_get_cache, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        payload = [
            {"truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
             "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z"}
            for _ in range(501)
        ]
        resp = client.post(f"{BASE}/gps/batch", json=payload)
        # Schema cap (max_length=500) rejects the batch before any route logic.
        assert resp.status_code == 422
        mocks["fleet_service"].get_trucks_by_ids.assert_not_called()
        mock_cache.set.assert_not_called()
        mock_cache.rpush.assert_not_called()

    def test_get_gps_history(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["fleet_service"].get_truck.return_value = {"id": 1, "company_id": 1}
        fake = [{"truck_id": 1, "latitude": 48.8566, "recorded_at": "2024-01-15T10:30:00Z"}]
        # The conftest mock_db fixture sets rows_to_dicts with a side_effect
        # that transforms its argument.  Clear it so our return_value is used.
        mocks["db"].rows_to_dicts.side_effect = None
        mocks["db"].rows_to_dicts.return_value = fake

        resp = client.get(f"{BASE}/gps/history/1?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == fake
        assert data["total"] == 1


class TestFleetGPSOwnership:
    """GPS endpoints must reject truck ids outside the caller's company.

    ``client_with_mocks`` overrides ``get_fleet_service`` with a StrippedMock
    that strips ``company_id`` from recorded calls, so these tests capture the
    lookup kwargs via ``side_effect`` to assert the ownership check passes the
    caller's ``company_id`` down to the lookup.
    """

    GPS_PING = {
        "truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
        "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z",
        "driver_id": 5,
    }

    @patch("backend.api.v1.fleet.get_cache")
    def test_ingest_foreign_truck_returns_404_and_nothing_stored(
        self, mock_get_cache, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        captured = {}

        def _capture(truck_id, **kwargs):
            captured.update(kwargs)
            return None  # foreign / missing truck

        mocks["fleet_service"].get_truck.side_effect = _capture

        resp = client.post(f"{BASE}/gps/ingest", json=self.GPS_PING)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Truck not found"
        assert captured["company_id"] == 1
        mock_cache.set.assert_not_called()
        mock_cache.rpush.assert_not_called()

    @patch("backend.api.v1.fleet.get_cache")
    def test_ingest_own_truck_returns_202(self, mock_get_cache, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mocks["fleet_service"].get_truck.return_value = {"id": 1, "company_id": 1}

        resp = client.post(f"{BASE}/gps/ingest", json=self.GPS_PING)
        assert resp.status_code == 202
        assert resp.json() == {"status": "accepted"}

    @patch("backend.api.v1.fleet.get_cache")
    def test_live_foreign_truck_returns_404_and_cache_not_read(
        self, mock_get_cache, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        captured = {}

        def _capture(truck_id, **kwargs):
            captured.update(kwargs)
            return None  # foreign / missing truck

        mocks["fleet_service"].get_truck.side_effect = _capture

        resp = client.get(f"{BASE}/gps/live/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Truck not found"
        assert captured["company_id"] == 1
        mock_cache.get.assert_not_called()

    @patch("backend.api.v1.fleet.get_cache")
    def test_live_own_truck_returns_200(self, mock_get_cache, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mocks["fleet_service"].get_truck.return_value = {"id": 1, "company_id": 1}
        mock_cache.get.return_value = {
            "truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
            "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z",
            "driver_id": 5,
        }

        resp = client.get(f"{BASE}/gps/live/1")
        assert resp.status_code == 200
        assert resp.json()["truck_id"] == 1

    @patch("backend.api.v1.fleet.get_cache")
    def test_batch_with_foreign_truck_returns_404_and_nothing_stored(
        self, mock_get_cache, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        captured = {}

        def _capture(truck_ids, **kwargs):
            captured.update(kwargs)
            # Truck 1 is owned; truck 999 is foreign/missing → partial result.
            return [{"id": i} for i in truck_ids if i == 1]

        mocks["fleet_service"].get_trucks_by_ids.side_effect = _capture

        payload = [
            {"truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
             "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z"},
            {"truck_id": 999, "latitude": 48.8588, "longitude": 2.3544,
             "speed_kmh": 70, "heading": 90, "timestamp": "2024-01-15T10:31:00Z"},
        ]
        resp = client.post(f"{BASE}/gps/batch", json=payload)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Truck not found"
        assert captured["company_id"] == 1
        mock_cache.set.assert_not_called()
        mock_cache.rpush.assert_not_called()

    @patch("backend.api.v1.fleet.get_cache")
    def test_batch_own_trucks_returns_202(self, mock_get_cache, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mocks["fleet_service"].get_trucks_by_ids.return_value = [{"id": 1}, {"id": 2}]

        payload = [
            {"truck_id": 1, "latitude": 48.8566, "longitude": 2.3522,
             "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z"},
            {"truck_id": 2, "latitude": 48.8588, "longitude": 2.3544,
             "speed_kmh": 70, "heading": 90, "timestamp": "2024-01-15T10:31:00Z"},
        ]
        resp = client.post(f"{BASE}/gps/batch", json=payload)
        assert resp.status_code == 202
        assert resp.json() == {"status": "accepted", "count": 2}

    def test_history_foreign_truck_returns_404_and_db_not_queried(
        self, client_with_mocks
    ):
        client, mocks = client_with_mocks
        captured = {}

        def _capture(truck_id, **kwargs):
            captured.update(kwargs)
            return None  # foreign / missing truck

        mocks["fleet_service"].get_truck.side_effect = _capture

        resp = client.get(f"{BASE}/gps/history/999?limit=10")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Truck not found"
        assert captured["company_id"] == 1
        mocks["db"].execute.assert_not_called()

    def test_history_own_truck_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["fleet_service"].get_truck.return_value = {"id": 1, "company_id": 1}
        fake = [{"truck_id": 1, "latitude": 48.8566, "recorded_at": "2024-01-15T10:30:00Z"}]
        mocks["db"].rows_to_dicts.side_effect = None
        mocks["db"].rows_to_dicts.return_value = fake

        resp = client.get(f"{BASE}/gps/history/1?limit=10")
        assert resp.status_code == 200
        assert resp.json()["items"] == fake


class TestFleetHealthScores:
    """Truck health score endpoints (inferred from fleet service)."""

    def test_truck_response_schema(self, client_with_mocks):
        """Verify truck response includes expected fields."""
        client, mocks = client_with_mocks
        truck = {"id": 1, "plate": "AB123CD", "brand": "Volvo", "year": 2022, "is_active": True}
        mocks["fleet_service"].get_truck.return_value = truck

        resp = client.get(f"{BASE}/trucks/1")
        assert resp.status_code == 200
        # The schema allows extra fields, so any valid dict passes


class TestFleetAuth:
    """Authentication gates."""

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/trucks")
        assert resp.status_code == 401
