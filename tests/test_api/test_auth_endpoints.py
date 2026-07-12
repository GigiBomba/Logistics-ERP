"""Integration tests for the auth API endpoints (``/api/v1/auth``).

POST /token  — login
POST /logout — clear cookie
GET  /me    — current user info
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/auth"


class TestAuthTokenEndpoint:
    """POST /api/v1/auth/token"""

    def test_login_success_admin(self, app):
        """Valid admin login returns 200 with tokens (via env-var gateway)."""
        import os
        os.environ.setdefault("OPERION_JWT_SECRET_KEY",
                              "e8f9b23fbc062b8a74c4dbb9dcde99252a13f040b201a056a29df147c216298a")
        os.environ["OPERION_ADMIN_EMAIL"] = "admin@test.com"
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = \
            "$2b$12$HWGCueEet/0YiXml7OvbpevITMJdjgs9FCFLmfYuwcgKwYvtpeOCG"

        from backend.security import verify_password
        from passlib.context import CryptContext
        # Register a known valid hash for "admin123"
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        pw_hash = pwd_ctx.hash("admin123")
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = pw_hash

        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={
            "username": "admin@test.com",
            "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

        for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                  "OPERION_JWT_SECRET_KEY"):
            os.environ.pop(k, None)

    def test_login_wrong_password_returns_401(self, app):
        """Wrong password returns 401."""
        import os
        os.environ.setdefault("OPERION_JWT_SECRET_KEY",
                              "e8f9b23fbc062b8a74c4dbb9dcde99252a13f040b201a056a29df147c216298a")
        os.environ["OPERION_ADMIN_EMAIL"] = "admin@test.com"
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = "$2b$12$dummyhashdummyhashdummyhashdummyhashdummy"
        from backend.api.v1.auth import _failed_attempts
        _failed_attempts.clear()

        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={
            "username": "admin@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

        for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                  "OPERION_JWT_SECRET_KEY"):
            os.environ.pop(k, None)

    def test_login_unknown_user_returns_401(self, app):
        """Unknown user returns 401."""
        import os
        os.environ.setdefault("OPERION_JWT_SECRET_KEY",
                              "e8f9b23fbc062b8a74c4dbb9dcde99252a13f040b201a056a29df147c216298a")
        os.environ["OPERION_ADMIN_EMAIL"] = "realadmin@test.com"
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = "$2b$12$dummyhash"
        from backend.api.v1.auth import _failed_attempts
        _failed_attempts.clear()

        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={
            "username": "unknown@test.com",
            "password": "somepass",
        })
        assert resp.status_code == 401

        for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
                  "OPERION_JWT_SECRET_KEY"):
            os.environ.pop(k, None)

    def test_login_missing_fields_returns_422(self, app):
        """Missing form fields returns 422."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={})
        assert resp.status_code == 422

    def test_login_missing_password_returns_422(self, app):
        """Missing password returns 422."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/token", data={"username": "user@test.com"})
        assert resp.status_code == 422


class TestAuthLogoutEndpoint:
    """POST /api/v1/auth/logout"""

    def test_logout_clears_cookie(self, app):
        """Logout clears the refresh_token cookie."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/logout", json={"refresh_token": "some-token"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # Verify Set-Cookie header clears the cookie
        set_cookie = resp.headers.get("set-cookie", "")
        assert "refresh_token=" in set_cookie
        assert "Max-Age=0" in set_cookie or "expires=" in set_cookie

    def test_logout_without_body_still_succeeds(self, app):
        """Logout succeeds even without a refresh token."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuthMeEndpoint:
    """GET /api/v1/auth/me — requires authentication."""

    def test_me_without_token_returns_401(self, app):
        """No token returns 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/me")
        assert resp.status_code == 401

    def test_me_with_mock_token_returns_user(self, client_with_mocks):
        """Authenticated request returns user info."""
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@test.com"
        assert data["role"] == "admin"
