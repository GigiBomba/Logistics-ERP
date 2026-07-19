"""Integration tests for the analytics API endpoints (/api/v1/analytics)."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/analytics"

class TestAnalyticsFinancial:
    """GET /api/v1/analytics/financial*"""

    def test_get_financial_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        fake = {"total_revenue": 250000.0, "total_expenses": 180000.0, "net_profit": 70000.0}
        svc.get_financial.return_value = fake
        resp = client.get(f"{BASE}/financial")
        assert resp.status_code == 200
        data = resp.json()
        # FinancialSummary adds extra fields — check subset
        assert data["total_revenue"] == 250000.0
        assert data["total_cost"] == 0.0
        svc.get_financial.assert_called_once_with(from_date=None, to_date=None)

    def test_get_financial_with_date_params(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_financial.return_value = {}
        resp = client.get(f"{BASE}/financial?from_date=2024-01-01&to_date=2024-12-31")
        assert resp.status_code == 200
        svc.get_financial.assert_called_once_with(from_date="2024-01-01", to_date="2024-12-31")

    def test_get_monthly_financial_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_monthly_financial.return_value = []
        resp = client.get(f"{BASE}/financial/monthly")
        assert resp.status_code == 200

    def test_get_cost_breakdown_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_cost_breakdown.return_value = []
        resp = client.get(f"{BASE}/financial/cost-breakdown")
        assert resp.status_code == 200

    def test_get_trip_status_distribution_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_trip_status_distribution.return_value = {}
        resp = client.get(f"{BASE}/financial/trip-status")
        assert resp.status_code == 200

    def test_get_monthly_trip_volume_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_monthly_trip_volume.return_value = []
        resp = client.get(f"{BASE}/financial/trip-volume")
        assert resp.status_code == 200

    def test_get_revenue_by_country_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_revenue_by_country.return_value = {}
        resp = client.get(f"{BASE}/financial/by-country")
        assert resp.status_code == 200

    def test_get_revenue_quarterly_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_revenue_quarterly.return_value = []
        resp = client.get(f"{BASE}/financial/quarterly")
        assert resp.status_code == 200

    def test_get_invoice_aging_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_invoice_aging.return_value = {}
        resp = client.get(f"{BASE}/financial/invoice-aging")
        assert resp.status_code == 200

class TestAnalyticsRevenueByClient:
    """GET /api/v1/analytics/revenue-by-client"""

    def test_revenue_by_client_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_revenue_by_client.return_value = []
        resp = client.get(f"{BASE}/revenue-by-client")
        assert resp.status_code == 200

class TestAnalyticsClient:
    """Client analytics endpoints."""

    def test_get_client_analytics_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_client_analytics.return_value = {}
        resp = client.get(f"{BASE}/client")
        assert resp.status_code == 200

    def test_get_client_growth_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_client_growth.return_value = {}
        resp = client.get(f"{BASE}/client/growth")
        assert resp.status_code == 200

    def test_get_client_retention_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_client_retention.return_value = {}
        resp = client.get(f"{BASE}/client/retention")
        assert resp.status_code == 200

    def test_get_revenue_concentration_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_revenue_concentration.return_value = {}
        resp = client.get(f"{BASE}/client/concentration")
        assert resp.status_code == 200

class TestAnalyticsFleet:
    """Fleet analytics endpoints."""

    def test_get_fleet_analytics_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_fleet.return_value = {}
        resp = client.get(f"{BASE}/fleet")
        assert resp.status_code == 200

    def test_get_truck_utilization_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_truck_utilization.return_value = {}
        resp = client.get(f"{BASE}/fleet/utilization")
        assert resp.status_code == 200

class TestAnalyticsRoute:
    """Route profitability analytics."""

    def test_get_route_profitability_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_route_profitability.return_value = {}
        resp = client.get(f"{BASE}/route/profitability")
        assert resp.status_code == 200

    def test_get_profit_per_km_by_country_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_profit_per_km_by_country.return_value = {}
        resp = client.get(f"{BASE}/route/by-country")
        assert resp.status_code == 200

    def test_get_profit_vs_distance_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_profit_vs_distance.return_value = []
        resp = client.get(f"{BASE}/route/profit-vs-distance")
        assert resp.status_code == 200

class TestAnalyticsDriver:
    """Driver analytics endpoints."""

    def test_get_driver_analytics_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_driver.return_value = {}
        resp = client.get(f"{BASE}/driver")
        assert resp.status_code == 200

    def test_get_driver_comparison_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_driver_comparison.return_value = {}
        resp = client.get(f"{BASE}/driver/comparison")
        assert resp.status_code == 200

    def test_get_driver_profit_per_km_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_driver_profit_per_km.return_value = {}
        resp = client.get(f"{BASE}/driver/profit-per-km")
        assert resp.status_code == 200

    def test_get_driver_tacho_violations_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_driver_tacho_violations.return_value = {}
        resp = client.get(f"{BASE}/driver/violations")
        assert resp.status_code == 200

    def test_get_driver_monthly_activity_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_driver_monthly_activity.return_value = {}
        resp = client.get(f"{BASE}/driver/monthly-activity")
        assert resp.status_code == 200

class TestAnalyticsDocument:
    """Document analytics endpoints."""

    def test_get_document_analytics_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_document.return_value = {}
        resp = client.get(f"{BASE}/document")
        assert resp.status_code == 200

    def test_get_document_upload_trend_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_document_upload_trend.return_value = {}
        resp = client.get(f"{BASE}/document/upload-trend")
        assert resp.status_code == 200

class TestAnalyticsMaintenance:
    """Maintenance analytics alerts."""

    def test_get_maintenance_alerts_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_maintenance_alerts.return_value = {}
        resp = client.get(f"{BASE}/maintenance/alerts")
        assert resp.status_code == 200

class TestAnalyticsCacheInvalidate:
    """POST /api/v1/analytics/invalidate"""

    def test_invalidate_cache_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        resp = client.post(f"{BASE}/invalidate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cache invalidated"
        svc.invalidate.assert_called_once()

class TestAnalyticsOverview:
    """GET /api/v1/analytics/overview"""

    def test_get_overview_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        svc = mocks["analytics_service"]
        svc.get_data.return_value = {"key": "value"}
        resp = client.get(f"{BASE}/overview")
        assert resp.status_code == 200
        data = resp.json()
        # AnalyticsOverview wraps the result — check basic structure
        assert "financial" in data
        assert "active_trips" in data

class TestAnalyticsAuth:
    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/financial")
        assert resp.status_code == 401