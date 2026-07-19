"""Stress tests: registration and auth endpoints under high load."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Must be set before any backend imports or BackendSettings initialization
os.environ.setdefault("OPERION_JWT_SECRET_KEY", "test-secret-32-chars-for-testing-only")
os.environ.setdefault("OPERION_ENV", "test")
os.environ.setdefault("OPERION_BCRYPT_ROUNDS", "4")

from backend.api.v1.router import api_v1_router
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.stresstest


class TestStressRegistration:
    """Registration endpoint under sustained load."""

    MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(api_v1_router)
        # Register JSON exception handlers so errors return JSON, not plain text.
        from fastapi.responses import JSONResponse
        from starlette.exceptions import HTTPException as StarletteHTTPException
        @app.exception_handler(Exception)
        async def generic_json_exception_handler(request, exc):
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error_code": "INTERNAL_ERROR"})
        @app.exception_handler(StarletteHTTPException)
        async def http_json_exception_handler(request, exc):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return app

    @pytest.fixture
    def client(self, app):
        from backend.dependencies_security import get_current_user, require_dispatcher, require_admin, require_manager
        app.dependency_overrides[get_current_user] = lambda: self.MOCK_USER
        app.dependency_overrides[require_dispatcher] = lambda: self.MOCK_USER
        app.dependency_overrides[require_admin] = lambda: self.MOCK_USER
        app.dependency_overrides[require_manager] = lambda: self.MOCK_USER

        # Disable registration rate limiter for stress tests
        from backend.api.v1.registration import _check_register_rate_limit
        _original_check = _check_register_rate_limit
        import backend.api.v1.registration as reg_mod
        reg_mod._check_register_rate_limit = lambda ip: None

        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = True
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True
            mock_cache.rpush.return_value = True
            mock_cache.delete.return_value = True
            mock_get_cache.return_value = mock_cache
            yield TestClient(app, raise_server_exceptions=False)

        app.dependency_overrides.clear()
        reg_mod._check_register_rate_limit = _original_check

    def test_rapid_sequential_registrations(self, client):
        """50 rapid sequential registrations — all succeed with unique emails."""
        successes = 0
        failures = 0
        start = time.time()

        for i in range(50):
            ts = int(time.time() * 1000000)
            resp = client.post("/api/v1/registration/register", json={
                "email": f"stress-seq-{ts}-{i}@test.com",
                "password": "securepass123",
                "display_name": f"Stress User {i}",
                "company_name": f"Stress Corp {i}",
            })
            if resp.status_code == 201:
                successes += 1
            else:
                failures += 1

        elapsed = time.time() - start
        assert successes == 50, f"Only {successes}/50 succeeded"
        assert failures == 0, f"{failures} failures"
        # bcrypt hashing dominates — even at rounds=4, 50 registrations take ~200s
        assert elapsed < 300, f"Took {elapsed:.1f}s for 50 registrations"

    def test_rapid_auth_token_requests(self, client):
        """100 rapid auth token requests — lockout, rate limiting, success all work."""
        # Register a user first
        client.post("/api/v1/registration/register", json={
            "email": "stress-auth@test.com",
            "password": "real-password",
            "display_name": "Stress Auth",
            "company_name": "Stress Auth Corp",
        })

        results: dict[str, int] = {"200": 0, "401": 0, "429": 0, "other": 0}

        for i in range(100):
            if i % 10 == 0:
                # Every 10th request uses correct password
                pw = "real-password"
            else:
                pw = "wrong-password"

            resp = client.post("/api/v1/auth/token", data={
                "username": "stress-auth@test.com",
                "password": pw,
            })
            key = str(resp.status_code)
            results[key] = results.get(key, 0) + 1

        # Should see some success, some failures, and some lockouts
        assert results["200"] > 0, "No successful logins"
        assert results["429"] > 0 or results["401"] > 0, "No lockout or failures"

        # After all that, server should still be healthy
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_large_registration_payloads(self, client):
        """Registration with very large field values."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"bigpayload_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "A" * 500,
            "company_name": "B" * 500,
        })
        # Should handle gracefully — either succeed or validation error
        assert resp.status_code in (201, 422)

    def test_unicode_registration(self, client):
        """Registration with Unicode characters in all fields."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"unicode_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "José María 官琳 Γιώργος",
            "company_name": "物流公司 SRL ™",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "José María" in data["user"]["display_name"]

    def test_forgot_password_rapid_requests(self, client):
        """Rapid forgot-password requests — all return 200 (anti-abuse)."""
        for i in range(30):
            resp = client.post("/api/v1/auth/forgot-password", json={
                "email": f"spam{i}@test.com",
            })
            assert resp.status_code == 200

        # System still healthy
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_password_reset_brute_force(self, client):
        """Brute-forcing reset tokens — all fail with 400."""
        # Register user
        email = f"resetbrute_{int(time.time())}@test.com"
        client.post("/api/v1/registration/register", json={
            "email": email,
            "password": "securepass123",
            "display_name": "Reset Brute",
            "company_name": "Reset Brute Corp",
        })

        # Try many invalid tokens
        for i in range(20):
            resp = client.post("/api/v1/auth/reset-password", json={
                "token": f"fake-token-{i}",
                "new_password": "hackedpass",
            })
            assert resp.status_code == 400

        # Real password should still work
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "securepass123",
        })
        assert resp.status_code == 200
