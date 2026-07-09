"""Stress tests: GPS ingest endpoints under high concurrency."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow


class TestStressGpsIngest:
    """Stress tests for /api/v1/fleet/gps/ batch and single ingest."""

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

    GPS_PING = {
        "truck_id": 1,
        "latitude": 52.5200,
        "longitude": 13.4050,
        "speed_kmh": 80.0,
        "heading": 45,
        "timestamp": "2026-07-09T12:00:00",
        "driver_id": 1,
    }

    # ── test 1: GPS batch flood 10k pings (500 threads × 20 pings/batch) ──

    def test_gps_batch_flood_10k_pings(self, client):
        """500 threads sending 20 pings each via POST /api/v1/fleet/gps/batch — verify no crashes."""
        batch_payload = [self.GPS_PING.copy() for _ in range(20)]

        def send_batch():
            resp = client.post("/api/v1/fleet/gps/batch", json=batch_payload)
            return resp.status_code

        results, timings, errors, elapsed = run_concurrent(send_batch, 500)
        # Allow some 202s and a handful of transient 429s/503s, but no 500s
        failures = [r for r in results if r in (500,)]
        assert len(failures) == 0, (
            f"gps_batch_flood_10k_pings produced {len(failures)} server errors "
            f"(success={len([r for r in results if r == 202])}/500)"
        )

    # ── test 2: GPS single ping 1000 concurrent ─────────────────────────

    def test_gps_single_ping_1000_concurrent(self, client):
        """1000 threads sending 1 ping each — verify no 500s."""
        def send_ping():
            resp = client.post("/api/v1/fleet/gps/ingest", json=self.GPS_PING)
            return resp.status_code

        results, timings, errors, elapsed = run_concurrent(send_ping, 1000)
        failures = [r for r in results if r in (500,)]
        assert len(failures) == 0, (
            f"gps_single_ping_1000_concurrent produced {len(failures)} server errors"
        )

    # ── test 3: GPS live position during ingest flood ────────────────────

    def test_gps_live_position_during_ingest_flood(self, client):
        """200 readers + 200 writers concurrently — verify no crashes."""
        def writer():
            return client.post("/api/v1/fleet/gps/ingest", json=self.GPS_PING).status_code

        def reader():
            return client.get("/api/v1/fleet/gps/live/1").status_code

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        import time

        results = []
        errors = []
        lock = threading.Lock()

        def run_writers():
            code = writer()
            with lock:
                results.append(("write", code))

        def run_readers():
            code = reader()
            with lock:
                results.append(("read", code))

        with ThreadPoolExecutor(max_workers=400) as pool:
            futs = []
            for _ in range(200):
                futs.append(pool.submit(run_readers))
            for _ in range(200):
                futs.append(pool.submit(run_writers))
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(e)

        server_errors = [(kind, code) for kind, code in results if code in (500,)]
        assert len(server_errors) == 0, (
            f"gps_live_position_during_ingest_flood produced {len(server_errors)} server errors"
        )
