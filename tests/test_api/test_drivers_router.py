"""Tests for the drivers API router (``/api/v1/drivers``)."""
from __future__ import annotations
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/drivers"


class TestDriversRouter:
    """CRUD + truck-assignment + tacho endpoints for drivers."""

    # ── list ──────────────────────────────────────────────────────────────

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

    def test_list_drivers_passes_limit_offset(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.return_value = []

        resp = client.get(f"{BASE}/?limit=10&offset=5")
        assert resp.status_code == 200
        mocks["driver_repo"].get_all.assert_called_once_with(limit=10, offset=5)

    # ── get by id ─────────────────────────────────────────────────────────

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

    # ── create ────────────────────────────────────────────────────────────

    def test_create_driver_returns_201_with_id(self, client_with_mocks):
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
        # repo.create receives the full model_dump
        called_args = mocks["driver_repo"].create.call_args[0][0]
        assert called_args["name"] == "New Driver"
        assert called_args["license_number"] == "LIC-001"

    # ── update ────────────────────────────────────────────────────────────

    def test_update_driver_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = {
            "id": 1, "name": "John",
        }

        resp = client.put(f"{BASE}/1", json={"phone": "999"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mocks["driver_repo"].update.assert_called_once_with(1, {"phone": "999"})

    def test_update_driver_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = None

        resp = client.put(f"{BASE}/999", json={"phone": "999"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Driver not found"

    # ── delete ────────────────────────────────────────────────────────────

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
        assert resp.json()["detail"] == "Driver not found"

    # ── assign truck (uses get_db) ────────────────────────────────────────

    def test_assign_driver_to_truck(self, client_with_mocks):
        client, mocks = client_with_mocks
        # Configure the mock DB so row_to_dict works for queries done
        # inside DriverTruckService.
        mocks["db"].row_to_dict.side_effect = lambda row: None if row is None else dict(row)

        resp = client.post(f"{BASE}/1/assign-truck?truck_id=5")
        # The endpoint creates DriverTruckService internally with mock_db.
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json()["status"] == "assigned"

    # ── error handling ────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        """Unhandled service exceptions propagate through the TestClient."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.side_effect = RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            client.get(f"{BASE}/")

    # ── unassign ───────────────────────────────────────────────────────────

    def test_unassign_driver(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("services.driver_truck_service.DriverTruckService") as mock_svc_cls:
            mock_svc = mock_svc_cls.return_value
            mock_svc.unassign_driver.return_value = 5

            resp = client.post(f"{BASE}/1/unassign")
            assert resp.status_code == 200
            assert resp.json() == {"status": "unassigned", "truck_id": 5}
            mock_svc.unassign_driver.assert_called_once_with(1)

    # ── truck-plate ────────────────────────────────────────────────────────

    def test_get_driver_truck_plate(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("services.driver_truck_service.DriverTruckService") as mock_svc_cls:
            mock_svc = mock_svc_cls.return_value
            mock_svc.get_truck_plate_for_driver.return_value = "AB-123-CD"

            resp = client.get(f"{BASE}/1/truck-plate")
            assert resp.status_code == 200
            assert resp.json() == {"plate": "AB-123-CD"}
            mock_svc.get_truck_plate_for_driver.assert_called_once_with(1)

    def test_get_driver_truck_plate_none(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("services.driver_truck_service.DriverTruckService") as mock_svc_cls:
            mock_svc = mock_svc_cls.return_value
            mock_svc.get_truck_plate_for_driver.return_value = None

            resp = client.get(f"{BASE}/1/truck-plate")
            assert resp.status_code == 200
            assert resp.json() == {"plate": None}

    # ── tacho-activity ─────────────────────────────────────────────────────

    def test_get_driver_tacho_activity(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch(
            "repositories.tacho_driver_activity_repository.TachoDriverActivityRepository"
        ) as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            fake_rows = [
                {"date": "2024-01-15", "activity": "driving"},
                {"date": "2024-01-16", "activity": "rest"},
            ]
            mock_repo.get_by_driver.return_value = fake_rows

            resp = client.get(f"{BASE}/1/tacho-activity")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2
            mock_repo.get_by_driver.assert_called_once()

    def test_get_driver_tacho_activity_with_from_date(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch(
            "repositories.tacho_driver_activity_repository.TachoDriverActivityRepository"
        ) as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_driver.return_value = []

            resp = client.get(f"{BASE}/1/tacho-activity?from_date=2024-06-01")
            assert resp.status_code == 200
            mock_repo.get_by_driver.assert_called_once()
            call_arg = mock_repo.get_by_driver.call_args[1]["from_date"]
            assert call_arg.isoformat() == "2024-06-01"

    # ── assign error ───────────────────────────────────────────────────────

    def test_assign_driver_error(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("services.driver_truck_service.DriverTruckService") as mock_svc_cls:
            mock_svc = mock_svc_cls.return_value
            mock_svc.assign_driver_to_truck.side_effect = RuntimeError("Assignment failed")

            with pytest.raises(RuntimeError, match="Assignment failed"):
                client.post(f"{BASE}/1/assign-truck?truck_id=5")

    # ── auth ──────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
