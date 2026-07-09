from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from backend.dependencies import get_trip_service
from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow


class TestLoadTrips:
    """Load tests for /api/v1/trips/ endpoints."""

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
        svc.get_filtered.return_value = []
        svc.get_by_id.return_value = {"id": 1, "status": "planned", "created_at": "2026-07-09T00:00:00"}
        svc.add.return_value = 1
        svc.update.return_value = None
        svc.delete.return_value = None
        app.dependency_overrides[get_trip_service] = lambda: svc

        yield TestClient(app)

        app.dependency_overrides.clear()

    # ── test 1: list trips concurrency ────────────────────────────────────

    def test_list_trips_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/trips/")

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"list_trips success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 2: get trip by id concurrency ────────────────────────────────

    def test_get_trip_by_id_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/trips/1")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"get_trip_by_id success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 3: create trip concurrency ───────────────────────────────────

    def test_create_trip_concurrency(self, client):
        payload = {"title": "test trip", "client_name": "Acme", "status": "planned"}

        def make_request():
            return client.post("/api/v1/trips/", json=payload)

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.95, f"create_trip success_rate={success_rate:.3f} < 0.95 at n={n}"

    # ── test 4: update trip concurrency ───────────────────────────────────

    def test_update_trip_concurrency(self, client):
        payload = {"status": "completed"}

        def make_request():
            return client.put("/api/v1/trips/1", json=payload)

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.95, f"update_trip success_rate={success_rate:.3f} < 0.95 at n={n}"

    # ── test 5: delete trip concurrency ───────────────────────────────────

    def test_delete_trip_concurrency(self, client):
        def make_request():
            return client.delete("/api/v1/trips/1")

        for n in [1, 10]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.90, f"delete_trip success_rate={success_rate:.3f} < 0.90 at n={n}"

    # ── test 6: check conflicts concurrency ───────────────────────────────

    def test_check_conflicts_concurrency(self, client):
        payload = {"pickup_date": "2026-07-10", "truck_id": 1}

        def make_request():
            return client.post("/api/v1/trips/conflicts/check", json=payload)

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"check_conflicts success_rate={success_rate:.3f} < 0.99 at n={n}"
