"""Tests for the analytics API router (``/api/v1/analytics``)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/analytics"


class TestAnalyticsRouter:
    """Analytics endpoints — all delegate to the analytics service."""

    FAKE_FINANCIAL = {
        "total_revenue": 250000.0,
        "total_expenses": 180000.0,
        "net_profit": 70000.0,
    }

    def _set_service(self, mocks, return_value=None):
        """Configure the analytics service mock with a default return value."""
        svc = mocks["analytics_service"]
        if return_value is not None:
            svc.get_financial.return_value = return_value
        return svc

    # ── financial ──────────────────────────────────────────────────────────

    def test_get_financial_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.return_value = self.FAKE_FINANCIAL

        resp = client.get(f"{BASE}/financial")
        assert resp.status_code == 200
        assert resp.json() == self.FAKE_FINANCIAL
        svc.get_financial.assert_called_once_with(from_date=None, to_date=None)

    def test_get_financial_with_date_params(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.return_value = {}

        resp = client.get(f"{BASE}/financial?from_date=2024-01-01&to_date=2024-12-31")
        assert resp.status_code == 200
        svc.get_financial.assert_called_once_with(
            from_date="2024-01-01", to_date="2024-12-31"
        )

    # ── financial/monthly ──────────────────────────────────────────────────

    def test_get_monthly_financial_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"month": "2024-01", "revenue": 20000.0}]
        svc.get_monthly_financial.return_value = fake_data

        resp = client.get(f"{BASE}/financial/monthly?months=12")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_monthly_financial.assert_called_once_with(
            months=12, from_date=None, to_date=None
        )

    # ── financial/cost-breakdown ───────────────────────────────────────────

    def test_get_cost_breakdown_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"category": "Fuel", "amount": 50000.0}]
        svc.get_cost_breakdown.return_value = fake_data

        resp = client.get(f"{BASE}/financial/cost-breakdown")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_cost_breakdown.assert_called_once_with(
            months=12, from_date=None, to_date=None
        )

    # ── fleet ──────────────────────────────────────────────────────────────

    def test_get_fleet_analytics_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = {"total_trucks": 10, "active_trucks": 8}
        svc.get_fleet.return_value = fake_data

        resp = client.get(f"{BASE}/fleet")
        assert resp.status_code == 200
        assert resp.json() == fake_data

    # ── driver ─────────────────────────────────────────────────────────────

    def test_get_driver_analytics_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = {"total_drivers": 15, "active_drivers": 12}
        svc.get_driver.return_value = fake_data

        resp = client.get(f"{BASE}/driver")
        assert resp.status_code == 200
        assert resp.json() == fake_data

    # ── overview ───────────────────────────────────────────────────────────

    def test_get_overview_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = {"trips_count": 250, "revenue_ytd": 500000.0}
        svc.get_data.return_value = fake_data

        resp = client.get(f"{BASE}/overview")
        assert resp.status_code == 200
        assert resp.json() == fake_data

    # ── invalidate cache ───────────────────────────────────────────────────

    def test_post_invalidate_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]

        resp = client.post(f"{BASE}/invalidate")
        assert resp.status_code == 200
        assert resp.json() == {"status": "cache invalidated"}
        svc.invalidate.assert_called_once_with()

    # ── error handling ─────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.side_effect = RuntimeError("Analytics broken")

        with pytest.raises(RuntimeError, match="Analytics broken"):
            client.get(f"{BASE}/financial")

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/financial")
        assert resp.status_code == 401
