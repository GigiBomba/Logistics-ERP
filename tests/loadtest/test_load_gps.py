from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from tests.loadtest.conftest import run_concurrent
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


class TestLoadGps:
    """Load tests for /api/v1/fleet/gps/ endpoints."""

    MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(api_v1_router)
        return app

    @pytest.fixture
    def client(self, app):
        from backend.dependencies_security import get_current_user, require_dispatcher, require_admin

        app.dependency_overrides[get_current_user] = lambda: self.MOCK_USER
        app.dependency_overrides[require_dispatcher] = lambda: self.MOCK_USER
        app.dependency_overrides[require_admin] = lambda: self.MOCK_USER

        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = True
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True
            mock_cache.rpush.return_value = True
            mock_cache.delete.return_value = True
            mock_get_cache.return_value = mock_cache

            yield TestClient(app)

        app.dependency_overrides.clear()

    GPS_PING_PAYLOAD = {
        "truck_id": 1,
        "latitude": 52.5200,
        "longitude": 13.4050,
        "speed_kmh": 80.0,
        "heading": 45,
        "timestamp": "2026-07-09T12:00:00",
        "driver_id": 1,
    }

    # ── test 1: GPS single ping concurrency ───────────────────────────────

    def test_gps_single_ping_concurrency(self, client):
        def make_request():
            return client.post("/api/v1/fleet/gps/ingest", json=self.GPS_PING_PAYLOAD)

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"gps_single_ping success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 2: GPS batch ping concurrency ────────────────────────────────

    def test_gps_batch_ping_concurrency(self, client):
        batch_payload = [self.GPS_PING_PAYLOAD.copy() for _ in range(10)]

        def make_request():
            return client.post("/api/v1/fleet/gps/batch", json=batch_payload)

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"gps_batch_ping success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 3: GPS live position concurrency ─────────────────────────────

    def test_gps_live_position_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/fleet/gps/live/1")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            # GET /live may 404 if no data; treat 404 as a valid response in load context
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"gps_live_position success_rate={success_rate:.3f} < 0.99 at n={n}"
