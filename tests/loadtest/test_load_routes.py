from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from tests.loadtest.conftest import run_concurrent, mock_redis_success
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


class TestLoadRoutes:
    """Load tests for /api/v1/routes/ endpoints."""

    MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(api_v1_router)
        return app

    @pytest.fixture
    def client(self, app):
        from backend.dependencies_security import get_current_user, require_dispatcher, require_admin
        from backend.dependencies import get_db

        app.dependency_overrides[get_current_user] = lambda: self.MOCK_USER
        app.dependency_overrides[require_dispatcher] = lambda: self.MOCK_USER
        app.dependency_overrides[require_admin] = lambda: self.MOCK_USER

        db = make_db()
        app.dependency_overrides[get_db] = lambda: db

        yield TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides.clear()

    # ── test 1: route calculation concurrency ─────────────────────────────

    @patch("services.route_service.RouteService.calculate_route")
    @patch("services.geocode_nominatim.geocode_place")
    def test_route_calculation_concurrency(self, mock_geocode, mock_calc_route, client):
        mock_geocode.return_value = None
        mock_calc_route.return_value = {"distance_km": 100, "duration_h": 2, "polyline": []}

        payload = {
            "points": [
                {"lat": 52.5200, "lng": 13.4050},
                {"lat": 48.8566, "lng": 2.3522},
            ],
            "profile": "truck",
        }

        def make_request():
            return client.post("/api/v1/routes/calculate", json=payload)

        for n in [1, 5, 20]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"route_calculation success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 2: list route history concurrency ────────────────────────────

    def test_list_route_history_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/routes/history")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"list_route_history success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 3: route statistics concurrency ──────────────────────────────

    def test_route_statistics_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/routes/history/statistics")

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"route_statistics success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 4: get route by id concurrency ───────────────────────────────

    def test_get_route_by_id_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/routes/history/1")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"get_route_by_id success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 5: duplicate route concurrency ───────────────────────────────

    def test_duplicate_route_concurrency(self, client):
        def make_request():
            return client.post("/api/v1/routes/history/1/duplicate")

        for n in [1, 10, 20]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"duplicate_route success_rate={success_rate:.3f} < 0.99 at n={n}"
