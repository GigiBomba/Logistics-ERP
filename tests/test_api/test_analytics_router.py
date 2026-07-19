"""Tests for the analytics API router (``/api/v1/analytics``)."""
from __future__ import annotations

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
        data = resp.json()
        assert data["total_revenue"] == 250000.0
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
        data = resp.json()
        assert "data" in data
        assert "total" in data
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
        data = resp.json()
        assert "fuel_cost" in data
        assert "total_cost" in data
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
        data = resp.json()
        assert isinstance(data, list)

    # ── driver ─────────────────────────────────────────────────────────────

    def test_get_driver_analytics_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = {"total_drivers": 15, "active_drivers": 12}
        svc.get_driver.return_value = fake_data

        resp = client.get(f"{BASE}/driver")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    # ── overview ───────────────────────────────────────────────────────────

    def test_get_overview_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = {"trips_count": 250, "revenue_ytd": 500000.0}
        svc.get_data.return_value = fake_data

        resp = client.get(f"{BASE}/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "financial" in data
        assert "active_trips" in data

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

        resp = client.get(f"{BASE}/financial")
        assert resp.status_code == 500

    # ── financial/trip-status ──────────────────────────────────────────────

    def test_get_trip_status_distribution(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"status": "completed", "count": 50}]
        svc.get_trip_status_distribution.return_value = fake_data

        resp = client.get(f"{BASE}/financial/trip-status")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_trip_status_distribution.assert_called_once_with(
            from_date=None, to_date=None
        )

    def test_get_trip_status_distribution_with_dates(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_trip_status_distribution.return_value = []

        resp = client.get(
            f"{BASE}/financial/trip-status?from_date=2024-01-01&to_date=2024-06-30"
        )
        assert resp.status_code == 200
        svc.get_trip_status_distribution.assert_called_once_with(
            from_date="2024-01-01", to_date="2024-06-30"
        )

    # ── financial/trip-volume ──────────────────────────────────────────────

    def test_get_monthly_trip_volume(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"month": "2024-01", "trips": 120}]
        svc.get_monthly_trip_volume.return_value = fake_data

        resp = client.get(f"{BASE}/financial/trip-volume")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        svc.get_monthly_trip_volume.assert_called_once_with(
            months=12, from_date=None, to_date=None
        )

    # ── financial/by-country ───────────────────────────────────────────────

    def test_get_revenue_by_country(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"country": "FR", "revenue": 50000.0}]
        svc.get_revenue_by_country.return_value = fake_data

        resp = client.get(f"{BASE}/financial/by-country")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_revenue_by_country.assert_called_once_with(
            from_date=None, to_date=None
        )

    # ── financial/quarterly ────────────────────────────────────────────────

    def test_get_revenue_quarterly(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"quarter": "2024-Q1", "revenue": 150000.0}]
        svc.get_revenue_quarterly.return_value = fake_data

        resp = client.get(f"{BASE}/financial/quarterly")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        svc.get_revenue_quarterly.assert_called_once_with(
            quarters=8, from_date=None, to_date=None
        )

    # ── financial/invoice-aging ────────────────────────────────────────────

    def test_get_invoice_aging(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"bucket": "0-30", "amount": 25000.0}]
        svc.get_invoice_aging.return_value = fake_data

        resp = client.get(f"{BASE}/financial/invoice-aging")
        assert resp.status_code == 200
        data = resp.json()
        # response_model=dict, so raw dict returned
        assert isinstance(data, dict)
        svc.get_invoice_aging.assert_called_once_with()

    # ── revenue-by-client ──────────────────────────────────────────────────

    def test_get_revenue_by_client(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"client": "Acme", "revenue": 80000.0}]
        svc.get_revenue_by_client.return_value = fake_data

        resp = client.get(f"{BASE}/revenue-by-client")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total_revenue" in data
        svc.get_revenue_by_client.assert_called_once_with(
            from_date=None, to_date=None
        )

    # ── client ─────────────────────────────────────────────────────────────

    def test_get_client_analytics(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = {"total_clients": 25, "active_clients": 20}
        svc.get_client_analytics.return_value = fake_data

        resp = client.get(f"{BASE}/client")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total_revenue" in data
        svc.get_client_analytics.assert_called_once_with(
            from_date=None, to_date=None
        )

    def test_get_client_growth(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"month": "2024-01", "new_clients": 3}]
        svc.get_client_growth.return_value = fake_data

        resp = client.get(f"{BASE}/client/growth")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_client_growth.assert_called_once_with(
            months=12, from_date=None, to_date=None
        )

    def test_get_client_retention(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"retention_rate": 0.85}]
        svc.get_client_retention.return_value = fake_data

        resp = client.get(f"{BASE}/client/retention")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_client_retention.assert_called_once_with()

    def test_get_revenue_concentration(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"client": "Acme", "share": 0.4}]
        svc.get_revenue_concentration.return_value = fake_data

        resp = client.get(f"{BASE}/client/concentration")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_revenue_concentration.assert_called_once_with()

    # ── fleet/utilization ──────────────────────────────────────────────────

    def test_get_truck_utilization(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"truck_id": 1, "utilization_pct": 75.0}]
        svc.get_truck_utilization.return_value = fake_data

        resp = client.get(f"{BASE}/fleet/utilization")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_truck_utilization.assert_called_once_with()

    # ── route ──────────────────────────────────────────────────────────────

    def test_get_route_profitability(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"route": "Paris-Lyon", "profit": 1200.0}]
        svc.get_route_profitability.return_value = fake_data

        resp = client.get(f"{BASE}/route/profitability")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_route_profitability.assert_called_once_with(
            from_date=None, to_date=None
        )

    def test_get_profit_per_km_by_country(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"country": "DE", "profit_per_km": 1.25}]
        svc.get_profit_per_km_by_country.return_value = fake_data

        resp = client.get(f"{BASE}/route/by-country")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_profit_per_km_by_country.assert_called_once_with()

    def test_get_profit_vs_distance(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"distance_km": 500, "profit": 800.0}]
        svc.get_profit_vs_distance.return_value = fake_data

        resp = client.get(f"{BASE}/route/profit-vs-distance")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_profit_vs_distance.assert_called_once_with(limit=100)

    # ── driver sub-endpoints ───────────────────────────────────────────────

    def test_get_driver_comparison(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"driver": "John", "revenue": 30000.0}]
        svc.get_driver_comparison.return_value = fake_data

        resp = client.get(f"{BASE}/driver/comparison")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_driver_comparison.assert_called_once_with(
            from_date=None, to_date=None
        )

    def test_get_driver_profit_per_km(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"driver": "Jane", "profit_per_km": 0.95}]
        svc.get_driver_profit_per_km.return_value = fake_data

        resp = client.get(f"{BASE}/driver/profit-per-km")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_driver_profit_per_km.assert_called_once_with()

    def test_get_driver_tacho_violations(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"driver": "John", "violations": 3}]
        svc.get_driver_tacho_violations.return_value = fake_data

        resp = client.get(f"{BASE}/driver/violations")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_driver_tacho_violations.assert_called_once_with()

    def test_get_driver_monthly_activity(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"month": "2024-01", "hours": 160}]
        svc.get_driver_monthly_activity.return_value = fake_data

        resp = client.get(f"{BASE}/driver/monthly-activity")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_driver_monthly_activity.assert_called_once_with(
            months=12, from_date=None, to_date=None
        )

    # ── document ───────────────────────────────────────────────────────────

    def test_get_document_analytics(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = {"total_docs": 500, "by_category": {}}
        svc.get_document.return_value = fake_data

        resp = client.get(f"{BASE}/document")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_document.assert_called_once_with()

    def test_get_document_upload_trend(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"month": "2024-01", "uploads": 30}]
        svc.get_document_upload_trend.return_value = fake_data

        resp = client.get(f"{BASE}/document/upload-trend")
        assert resp.status_code == 200
        assert resp.json() == fake_data
        svc.get_document_upload_trend.assert_called_once_with(months=12)

    # ── maintenance ────────────────────────────────────────────────────────

    def test_get_maintenance_alerts(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake_data = [{"truck_id": 3, "alert": "Oil change due"}]
        svc.get_maintenance_alerts.return_value = fake_data

        resp = client.get(f"{BASE}/maintenance/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        svc.get_maintenance_alerts.assert_called_once_with()

    # ── error propagation ──────────────────────────────────────────────────

    def test_analytics_error_propagation(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_trip_status_distribution.side_effect = RuntimeError("Service failure")

        resp = client.get(f"{BASE}/financial/trip-status")
        assert resp.status_code == 500

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/financial")
        assert resp.status_code == 401
