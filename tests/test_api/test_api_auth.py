"""Tests for the JWT authentication endpoint.

Requires ``OPERION_ADMIN_EMAIL`` and ``OPERION_ADMIN_PASSWORD_HASH``
to be set in the environment.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.v1.auth import _failed_attempts
from backend.main import create_app
from backend.security import decode_access_token
from tests.conftest import OPERION_TEST_JWT_SECRET as _TEST_JWT_SECRET

# ── Test admin credentials (loaded from environment, never hardcoded) ──
_TEST_ADMIN_EMAIL = os.environ.get("OPERION_TEST_ADMIN_EMAIL", "bonjourlol444@gmail.com")
_TEST_ADMIN_PASSWORD = os.environ.get("OPERION_TEST_ADMIN_PASSWORD", "test-admin-password")
_TEST_ADMIN_HASH = os.environ.get("OPERION_TEST_ADMIN_HASH",
    "$2b$04$zcZO4.5yiIgHbo0advffsOPRpRh0hdHygnejWNc6tFpyIw0t1tg0y")


@pytest.fixture(scope="module", autouse=True)
def _set_env():
    """Set test environment variables before any test."""
    os.environ["OPERION_ADMIN_EMAIL"] = _TEST_ADMIN_EMAIL
    os.environ["OPERION_ADMIN_PASSWORD_HASH"] = _TEST_ADMIN_HASH
    os.environ["OPERION_JWT_SECRET_KEY"] = _TEST_JWT_SECRET
    os.environ["OPERION_ACCESS_TOKEN_EXPIRE_MINUTES"] = "480"
    yield
    # Cleanup
    for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
              "OPERION_JWT_SECRET_KEY", "OPERION_ACCESS_TOKEN_EXPIRE_MINUTES"):
        os.environ.pop(k, None)


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_lockout():
    """Clear brute-force lockout state between tests."""
    _failed_attempts.clear()


class TestAuthTokenEndpoint:
    """POST /api/v1/auth/token"""

    def test_admin_login_success(self, client):
        """Valid admin credentials return 200 with a JWT containing role=admin."""
        response = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": _TEST_ADMIN_PASSWORD,
        })
        assert response.status_code == 200
        data: dict = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Decode and verify payload
        payload = decode_access_token(data["access_token"])
        assert payload["sub"] == _TEST_ADMIN_EMAIL
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_admin_login_wrong_password(self, client):
        """Wrong password returns 401 with a generic message."""
        response = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": "WRONG_PASSWORD",
        })
        assert response.status_code == 401
        data = response.json()
        detail = data.get("detail", "")
        if isinstance(detail, dict):
            detail = detail.get("detail", str(detail))
        assert "Invalid" in detail

    def test_admin_login_unknown_email(self, client):
        """Unknown email returns 401 with a generic message (anti-enumeration)."""
        response = client.post("/api/v1/auth/token", data={
            "username": "unknown@example.com",
            "password": "somepassword",
        })
        assert response.status_code == 401
        data = response.json()
        detail = data.get("detail", "")
        if isinstance(detail, dict):
            detail = detail.get("detail", str(detail))
        assert "Invalid" in detail

    def test_admin_login_empty_password(self, client):
        """Empty password returns 422 (validation error from OAuth2 form)."""
        response = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": "",
        })
        assert response.status_code == 422

    def test_admin_login_missing_fields(self, client):
        """Missing username/password returns 422."""
        response = client.post("/api/v1/auth/token", data={})
        assert response.status_code == 422

    def test_admin_login_returns_valid_jwt(self, client):
        """The JWT can be decoded with the correct secret."""
        response = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": _TEST_ADMIN_PASSWORD,
        })
        token = response.json()["access_token"]
        payload = decode_access_token(token)
        assert payload["sub"] == _TEST_ADMIN_EMAIL
        assert payload["role"] == "admin"

    def test_public_endpoints_still_work_without_auth(self, client):
        """Existing public endpoints (e.g. health) must not require a token."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    # ── brute-force lockout ────────────────────────────────────────────────

    def test_lockout_returns_429_after_threshold(self, client):
        """5 consecutive bad passwords → 429 Too Many Requests."""
        for _ in range(5):
            client.post("/api/v1/auth/token", data={
                "username": _TEST_ADMIN_EMAIL,
                "password": "WRONG",
            })
        resp = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": "WRONG",
        })
        assert resp.status_code == 429
        detail = resp.json().get("detail", "")
        if isinstance(detail, dict):
            detail = detail.get("detail", str(detail))
        assert "Too many login attempts" in detail

    def test_lockout_resets_after_success(self, client):
        """4 failures then a successful login → 200 (lockout clears)."""
        for _ in range(4):
            client.post("/api/v1/auth/token", data={
                "username": _TEST_ADMIN_EMAIL,
                "password": "WRONG",
            })
        resp = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": _TEST_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        # Subsequent failures should be counted from zero
        resp2 = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": "WRONG",
        })
        assert resp2.status_code == 401  # not locked out

    def test_lockout_expires_after_duration(self, client, monkeypatch):
        """After lockout, advancing time beyond LOCKOUT_DURATION clears it."""
        # Reach threshold
        for _ in range(5):
            client.post("/api/v1/auth/token", data={
                "username": _TEST_ADMIN_EMAIL,
                "password": "WRONG",
            })
        resp = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": "WRONG",
        })
        assert resp.status_code == 429

        # Advance time past LOCKOUT_DURATION (900s + buffer)
        original_time = time.time
        monkeypatch.setattr(time, "time", lambda: original_time() + 1000)

        resp2 = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": _TEST_ADMIN_PASSWORD,
        })
        assert resp2.status_code == 200

    def test_lockout_clears_on_admin_success(self, client):
        """Failed attempts for an email are cleared when admin logs in."""
        for _ in range(4):
            client.post("/api/v1/auth/token", data={
                "username": _TEST_ADMIN_EMAIL,
                "password": "WRONG",
            })
        # Successful admin login clears the lockout counter
        resp = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": _TEST_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200

        # The next failure should count as attempt #1, not trigger lockout
        resp2 = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": "WRONG",
        })
        assert resp2.status_code == 401
        # Reach threshold to confirm counter really reset
        for _ in range(4):
            client.post("/api/v1/auth/token", data={
                "username": _TEST_ADMIN_EMAIL,
                "password": "WRONG",
            })
        resp3 = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": "WRONG",
        })
        assert resp3.status_code == 429


class TestAdminGatewayIndependence:
    """The admin gateway must not depend on the database."""

    def test_admin_login_no_db_required(self, client):
        """Admin login must succeed even without a users table."""
        response = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": _TEST_ADMIN_PASSWORD,
        })
        assert response.status_code == 200
        payload = decode_access_token(response.json()["access_token"])
        assert payload["role"] == "admin"
        assert payload["sub"] == _TEST_ADMIN_EMAIL
