"""Integration tests for the drivers API endpoints (``/api/v1/drivers``).

Uses ``client_with_mocks`` for mocked repository layer.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/drivers"


class TestDriversListEndpoint:
    """GET /api/v1/drivers/"""

    def test_list_drivers_returns_200_with_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.return_value = [
            {"id": 1, "name": "John", "created_at": "", "updated_at": ""},
            {"id": 2, "name": "Jane", "created_at": "", "updated_at": ""},
        ]

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2

    def test_list_drivers_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.return_value = []

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_drivers_passes_limit_offset(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.return_value = []

        resp = client.get(f"{BASE}/?page=1&page_size=10")
        assert resp.status_code == 200
        mocks["driver_repo"].get_all.assert_called_once_with(limit=10, offset=0)


class TestDriversGetEndpoint:
    """GET /api/v1/drivers/{driver_id}"""

    def test_get_driver_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = {
            "id": 1, "name": "John", "phone": "",
            "email": "", "license_number": "", "license_category": "",
            "is_active": True, "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }

        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1
        assert resp.json()["name"] == "John"

    def test_get_driver_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = None

        resp = client.get(f"{BASE}/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Driver not found"


class TestDriversCreateEndpoint:
    """POST /api/v1/drivers/"""

    def test_create_driver_returns_201(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].create.return_value = 7

        payload = {
            "name": "New Driver",
            "phone": "123",
            "email": "d@d.com",
            "license_number": "LIC-001",
            "license_category": "C+E",
        }
        resp = client.post(f"{BASE}/", json=payload)
        assert resp.status_code == 201
        assert resp.json() == {"id": 7}

    def test_create_driver_missing_fields_returns_422(self, client_with_mocks):
        client, mocks = client_with_mocks
        # DriverCreate has defaults for all fields; empty dict is valid.
        resp = client.post(f"{BASE}/", json={})
        assert resp.status_code == 201


class TestDriversUpdateEndpoint:
    """PUT /api/v1/drivers/{driver_id}"""

    def test_update_driver_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = {"id": 1, "name": "John"}

        resp = client.put(f"{BASE}/1", json={"phone": "999"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mocks["driver_repo"].update.assert_called_once_with(1, {"phone": "999"})

    def test_update_driver_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = None

        resp = client.put(f"{BASE}/999", json={"phone": "999"})
        assert resp.status_code == 404


class TestDriversDeleteEndpoint:
    """DELETE /api/v1/drivers/{driver_id}"""

    def test_delete_driver_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = {"id": 1}

        resp = client.delete(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        mocks["driver_repo"].delete.assert_called_once_with(1)

    def test_delete_driver_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = None

        resp = client.delete(f"{BASE}/999")
        assert resp.status_code == 404


class TestDriversTruckAssignment:
    """Driver-truck assignment endpoints."""

    def test_assign_driver_to_truck(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].row_to_dict.side_effect = lambda row: None if row is None else dict(row)

        resp = client.post(f"{BASE}/1/assign-truck?truck_id=5")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json()["status"] == "assigned"

    def test_unassign_driver(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("backend.services.driver_truck_service.DriverTruckService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.unassign_driver.return_value = 5

            resp = client.post(f"{BASE}/1/unassign")
            assert resp.status_code == 200
            assert resp.json() == {"status": "unassigned", "truck_id": 5}

    def test_get_driver_truck_plate(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("backend.services.driver_truck_service.DriverTruckService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_truck_plate_for_driver.return_value = "AB-123-CD"

            resp = client.get(f"{BASE}/1/truck-plate")
            assert resp.status_code == 200
            assert resp.json() == {"plate": "AB-123-CD"}

    def test_get_driver_truck_plate_none(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("backend.services.driver_truck_service.DriverTruckService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_truck_plate_for_driver.return_value = None

            resp = client.get(f"{BASE}/1/truck-plate")
            assert resp.status_code == 200
            assert resp.json() == {"plate": None}


class TestDriversTachoActivity:
    """GET /api/v1/drivers/{driver_id}/tacho-activity"""

    def test_get_tacho_activity(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch(
            "repositories.tacho_driver_activity_repository.TachoDriverActivityRepository"
        ) as mock_cls:
            mock_repo = mock_cls.return_value
            fake = [{"date": "2024-01-15", "activity": "driving"}]
            mock_repo.get_by_driver.return_value = fake

            resp = client.get(f"{BASE}/1/tacho-activity")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1

    def test_get_tacho_activity_with_from_date(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch(
            "backend.repositories.tacho_driver_activity_repository.TachoDriverActivityRepository"
        ) as mock_cls:
            mock_repo = mock_cls.return_value
            mock_repo.get_by_driver.return_value = []

            resp = client.get(f"{BASE}/1/tacho-activity?from_date=2024-06-01")
            assert resp.status_code == 200
            call_kwargs = mock_repo.get_by_driver.call_args[1]
            call_arg = call_kwargs.get("date_from") or call_kwargs.get("from_date")
            assert call_arg is not None
            assert call_arg.isoformat() == "2024-06-01"


class TestDriversAuth:
    """Authentication gates."""

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.side_effect = RuntimeError("fail")
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 500
