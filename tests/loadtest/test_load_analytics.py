from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from backend.dependencies import get_analytics_service
from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow


class TestLoadAnalytics:
    """Load tests for /api/v1/analytics/ endpoints."""

    MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(api_v1_router)
        return app

    @pytest.fixture
    def client(self, app):
        app.dependency_overrides[get_current_user] = lambda: self.MOCK_USER
        app.dependency_overrides[require_dispatcher] = lambda: self.MOCK_USER
        app.dependency_overrides[require_admin] = lambda: self.MOCK_USER

        svc = MagicMock()
        svc.get_financial.return_value = {"revenue": 100000}
        svc.get_data.return_value = {"total_trips": 500}
        svc.get_monthly_financial.return_value = []
        svc.get_cost_breakdown.return_value = {}
        svc.get_trip_status_distribution.return_value = {}
        svc.get_monthly_trip_volume.return_value = {}
        svc.get_revenue_by_country.return_value = {}
        svc.get_revenue_quarterly.return_value = {}
        svc.get_invoice_aging.return_value = []
        svc.get_revenue_by_client.return_value = {}
        svc.get_client_analytics.return_value = {}
        svc.get_client_growth.return_value = {}
        svc.get_client_retention.return_value = {}
        svc.get_revenue_concentration.return_value = {}
        svc.get_fleet.return_value = {}
        svc.get_truck_utilization.return_value = {}
        svc.get_route_profitability.return_value = {}
        svc.get_profit_per_km_by_country.return_value = {}
        svc.get_profit_vs_distance.return_value = []
        svc.get_driver.return_value = {}
        svc.get_driver_comparison.return_value = {}
        svc.get_driver_profit_per_km.return_value = {}
        svc.get_driver_tacho_violations.return_value = []
        svc.get_driver_monthly_activity.return_value = {}
        svc.get_document.return_value = {}
        svc.get_document_upload_trend.return_value = {}
        svc.get_maintenance_alerts.return_value = []
        svc.invalidate.return_value = None
        app.dependency_overrides[get_analytics_service] = lambda: svc

        yield TestClient(app)

        app.dependency_overrides.clear()

    ANALYTICS_ENDPOINTS = [
        "/api/v1/analytics/financial",
        "/api/v1/analytics/financial/monthly",
        "/api/v1/analytics/financial/cost-breakdown",
        "/api/v1/analytics/financial/trip-status",
        "/api/v1/analytics/financial/trip-volume",
        "/api/v1/analytics/financial/by-country",
        "/api/v1/analytics/financial/quarterly",
        "/api/v1/analytics/financial/invoice-aging",
        "/api/v1/analytics/revenue-by-client",
        "/api/v1/analytics/client",
        "/api/v1/analytics/client/growth",
        "/api/v1/analytics/client/retention",
        "/api/v1/analytics/client/concentration",
        "/api/v1/analytics/fleet",
        "/api/v1/analytics/fleet/utilization",
        "/api/v1/analytics/route/profitability",
        "/api/v1/analytics/route/by-country",
        "/api/v1/analytics/route/profit-vs-distance",
        "/api/v1/analytics/driver",
        "/api/v1/analytics/driver/comparison",
        "/api/v1/analytics/driver/profit-per-km",
        "/api/v1/analytics/driver/violations",
        "/api/v1/analytics/driver/monthly-activity",
        "/api/v1/analytics/document",
        "/api/v1/analytics/document/upload-trend",
        "/api/v1/analytics/maintenance/alerts",
    ]

    # ── test 1: financial analytics concurrency ───────────────────────────

    def test_financial_analytics_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/analytics/financial")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"financial_analytics success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 2: overview analytics concurrency ────────────────────────────

    def test_overview_analytics_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/analytics/overview")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"overview_analytics success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 3: multiple analytics endpoints concurrently ─────────────────

    def test_multiple_analytics_endpoints_concurrently(self, client):
        endpoints = [
            "/api/v1/analytics/financial",
            "/api/v1/analytics/overview",
            "/api/v1/analytics/client",
            "/api/v1/analytics/fleet",
            "/api/v1/analytics/route/profitability",
            "/api/v1/analytics/document",
        ]

        def make_request(endpoint: str):
            return client.get(endpoint)

        for n in [1, 5, 20]:
            results, timings, errors, elapsed = run_concurrent(make_request, n, endpoints[n % len(endpoints)])
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"multiple_endpoints success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 4: analytics cache invalidation under load ───────────────────

    def test_analytics_cache_invalidation_under_load(self, client):
        import threading

        results = {"get": [], "post": []}

        def getter():
            resp = client.get("/api/v1/analytics/financial")
            results["get"].append(resp)
            return resp

        def invalidator():
            resp = client.post("/api/v1/analytics/invalidate")
            results["post"].append(resp)
            return resp

        for _ in range(10):
            t1 = threading.Thread(target=getter)
            t2 = threading.Thread(target=invalidator)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        success_rate_get = len(results["get"]) / 10
        success_rate_post = len(results["post"]) / 10
        assert success_rate_get >= 0.99, f"cache invalidation GET success_rate={success_rate_get:.3f}"
        assert success_rate_post >= 0.99, f"cache invalidation POST success_rate={success_rate_post:.3f}"
