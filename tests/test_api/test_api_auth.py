"""Tests for the JWT authentication endpoint.

Requires ``OPERION_ADMIN_EMAIL`` and ``OPERION_ADMIN_PASSWORD_HASH``
to be set in the environment.
"""

import os

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.security import decode_access_token

# ── Test admin credentials (must match admin.env) ──────────────────────
_TEST_ADMIN_EMAIL = "bonjourlol444@gmail.com"
_TEST_ADMIN_PASSWORD = (
    "aF!81YYU2b>zLw5eJW7sGXM7Ri6Q7,Y3:zGzd^!ddMnjxkAHkcgduf}"
    "?w9tg*]N@sg]tN)Fy0k.q843}!d2_xZpW?MkCKPUC4qA7"
)
_TEST_ADMIN_HASH = "$2b$12$HWGCueEet/0YiXml7OvbpevITMJdjgs9FCFLmfYuwcgKwYvtpeOCG"
_TEST_JWT_SECRET = "e8f9b23fbc062b8a74c4dbb9dcde99252a13f040b201a056a29df147c216298a"


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
        assert "Incorrect" in data["detail"]

    def test_admin_login_unknown_email(self, client):
        """Unknown email returns 401 with a generic message (anti-enumeration)."""
        response = client.post("/api/v1/auth/token", data={
            "username": "unknown@example.com",
            "password": "somepassword",
        })
        assert response.status_code == 401
        data = response.json()
        assert "Incorrect" in data["detail"] or "Invalid" in data["detail"]

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
