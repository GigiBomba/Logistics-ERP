"""Integration tests for the maintenance API endpoints (/api/v1/maintenance)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/maintenance"
FAKE_TRUCK_SUMMARY = [
    {"truck_id": 1, "plate_number": "AB123CD", "total_cost": 1200.50, "record_count": 3},
    {"truck_id": 2, "plate_number": "XY789EF", "total_cost": 850.00, "record_count": 2},
]
FAKE_COST_MONTHLY = [
    {"month": "2024-01", "total_cost": 3450.00},
    {"month": "2024-02", "total_cost": 2800.00},
]

class TestMaintenanceSummary:
    @patch("backend.api.v1.maintenance.FleetRepository")
    def test_get_summary_returns_200(self, mock_repo_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_maintenance_truck_summary.return_value = FAKE_TRUCK_SUMMARY
        mock_repo.get_maintenance_cost_monthly.return_value = FAKE_COST_MONTHLY
        resp = client.get(f"{BASE}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trucks"] == FAKE_TRUCK_SUMMARY
        assert data["cost_monthly"] == FAKE_COST_MONTHLY
        assert data["total_trucks"] == 2

class TestMaintenanceCostMonthly:
    @patch("backend.api.v1.maintenance.FleetRepository")
    def test_get_cost_monthly_returns_200(self, mock_repo_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_maintenance_cost_monthly.return_value = FAKE_COST_MONTHLY
        resp = client.get(f"{BASE}/cost-monthly")
        assert resp.status_code == 200
        assert resp.json() == {"data": FAKE_COST_MONTHLY}

    @patch("backend.api.v1.maintenance.FleetRepository")
    def test_get_cost_monthly_with_since(self, mock_repo_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        resp = client.get(f"{BASE}/cost-monthly?since=2024-01-01")
        assert resp.status_code == 200
        mock_repo.get_maintenance_cost_monthly.assert_called_once_with("2024-01-01", company_id=1)

class TestMaintenanceTruckSummary:
    @patch("backend.api.v1.maintenance.FleetRepository")
    def test_get_truck_summary_returns_200(self, mock_repo_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_maintenance_truck_summary.return_value = FAKE_TRUCK_SUMMARY
        resp = client.get(f"{BASE}/truck-summary")
        assert resp.status_code == 200
        assert resp.json() == {"data": FAKE_TRUCK_SUMMARY}

class TestMaintenanceCostByTruck:
    @patch("backend.api.v1.maintenance.FleetRepository")
    def test_get_cost_by_truck_monthly_returns_200(self, mock_repo_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        fake_data = [{"truck_id": 1, "month": "2024-01", "cost": 1200.0}]
        mock_repo.get_maintenance_cost_truck_monthly.return_value = fake_data
        resp = client.get(f"{BASE}/cost-by-truck-monthly")
        assert resp.status_code == 200
        assert resp.json() == {"data": fake_data}

class TestMaintenanceTopCategories:
    @patch("backend.api.v1.maintenance.FleetRepository")
    def test_get_top_categories_returns_200(self, mock_repo_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        fake_cats = [{"category": "Oil change", "total_cost": 5000.0}]
        mock_repo.get_maintenance_most_expensive_category.return_value = fake_cats
        resp = client.get(f"{BASE}/top-categories")
        assert resp.status_code == 200
        assert resp.json() == {"data": fake_cats}

class TestMaintenanceAuth:
    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/summary")
        assert resp.status_code == 401