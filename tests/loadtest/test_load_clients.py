from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from backend.dependencies import get_client_service
from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow


class TestLoadClients:
    """Load tests for /api/v1/clients/ endpoints."""

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
        svc.get_all.return_value = []
        svc.search_advanced.return_value = []
        svc.get_by_id.return_value = {
            "id": 1, "name": "Acme Corp", "is_active": True,
            "email": "acme@test.com", "phone": "+1234567890",
        }
        svc.create.return_value = 1
        svc.get_client_dashboard.return_value = {
            "total_trips": 10, "total_revenue": 50000,
            "outstanding_invoices": 2,
        }
        app.dependency_overrides[get_client_service] = lambda: svc

        yield TestClient(app)

        app.dependency_overrides.clear()

    # ── test 1: list clients / search concurrency ─────────────────────────

    def test_list_clients_search_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/clients/")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"list_clients success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 2: create client concurrency ─────────────────────────────────

    def test_create_client_concurrency(self, client):
        payload = {"email": "new@test.com", "phone": "+1111111111"}

        def make_request():
            return client.post("/api/v1/clients/?name=NewClient", json=payload)

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.95, f"create_client success_rate={success_rate:.3f} < 0.95 at n={n}"

    # ── test 3: client dashboard concurrency ──────────────────────────────

    def test_client_dashboard_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/clients/1/dashboard")

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"client_dashboard success_rate={success_rate:.3f} < 0.99 at n={n}"
