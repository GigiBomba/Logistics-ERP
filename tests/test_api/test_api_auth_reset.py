"""Integration tests for password reset endpoints.

POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
POST /api/v1/auth/token  (DB-user login)
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.v1.auth import _reset_tokens
from backend.main import create_app
from backend.security import decode_access_token
from tests.conftest import OPERION_TEST_JWT_SECRET as _TEST_JWT_SECRET


@pytest.fixture(scope="module", autouse=True)
def _set_env():
    os.environ["OPERION_JWT_SECRET_KEY"] = _TEST_JWT_SECRET
    os.environ["OPERION_ENV"] = "test"
    yield
    for k in ("OPERION_JWT_SECRET_KEY", "OPERION_ENV"):
        os.environ.pop(k, None)


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_reset_tokens():
    """Clear in-memory reset tokens between tests."""
    _reset_tokens.clear()


def _register_user(client, email="resettest@test.com", password="originalpass"):
    """Helper: register a user and return the response data."""
    return client.post("/api/v1/registration/register", json={
        "email": email,
        "password": password,
        "display_name": "Reset Test",
        "company_name": "Reset Corp",
    })


class TestForgotPassword:
    """POST /api/v1/auth/forgot-password"""

    def test_forgot_password_returns_200_for_known_email(self, client):
        """Requesting reset for a known email returns 200 with success message."""
        _register_user(client)
        resp = client.post("/api/v1/auth/forgot-password", json={
            "email": "resettest@test.com",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_forgot_password_returns_200_for_unknown_email(self, client):
        """Requesting reset for unknown email also returns 200 (anti-enumeration)."""
        resp = client.post("/api/v1/auth/forgot-password", json={
            "email": "nonexistent@test.com",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_forgot_password_empty_email_returns_200(self, client):
        """Empty email still returns 200 (anti-enumeration)."""
        resp = client.post("/api/v1/auth/forgot-password", json={
            "email": "",
        })
        assert resp.status_code == 200

    def test_forgot_password_missing_field_returns_200(self, client):
        """Missing email field returns 200 (graceful handling)."""
        resp = client.post("/api/v1/auth/forgot-password", json={})
        assert resp.status_code == 200


class TestResetPassword:
    """POST /api/v1/auth/reset-password"""

    def test_reset_password_full_flow(self, client):
        """Full flow: register → forgot → get token → reset → login with new password."""
        email = f"fullflow_{int(time.time())}@test.com"
        _register_user(client, email=email, password="originalpass")

        # Step 1: Request reset
        client.post("/api/v1/auth/forgot-password", json={"email": email})

        # Step 2: Get the token from in-memory store (in production this comes via email)
        # Find the token for this email
        token = None
        for t, data in _reset_tokens.items():
            if data["email"] == email:
                token = t
                break
        assert token is not None, "Reset token should have been generated"

        # Step 3: Reset password
        resp = client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "newsecurepass",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Step 4: Login with new password
        resp2 = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "newsecurepass",
        })
        assert resp2.status_code == 200

        # Step 5: Old password should fail
        resp3 = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": "originalpass",
        })
        assert resp3.status_code == 401

    def test_reset_password_invalid_token_returns_400(self, client):
        """Invalid or nonexistent reset token returns 400."""
        resp = client.post("/api/v1/auth/reset-password", json={
            "token": "invalid-token-that-does-not-exist",
            "new_password": "newpass123",
        })
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower() or "expired" in resp.json()["detail"].lower()

    def test_reset_password_expired_token_returns_400(self, client, monkeypatch):
        """Expired reset token returns 400."""
        email = f"expired_{int(time.time())}@test.com"
        _register_user(client, email=email)

        client.post("/api/v1/auth/forgot-password", json={"email": email})

        # Find the token
        token = None
        for t, data in _reset_tokens.items():
            if data["email"] == email:
                token = t
                break

        # Advance time past 1 hour expiry
        original_time = time.time
        monkeypatch.setattr(time, "time", lambda: original_time() + 7200)

        resp = client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "newpass123",
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_reset_password_short_new_password_returns_400(self, client):
        """New password shorter than 6 chars returns 400."""
        resp = client.post("/api/v1/auth/reset-password", json={
            "token": "some-token",
            "new_password": "12345",
        })
        assert resp.status_code == 400

    def test_reset_password_missing_fields_returns_400(self, client):
        """Missing token or new_password returns 400."""
        resp = client.post("/api/v1/auth/reset-password", json={})
        assert resp.status_code == 400

    def test_reset_password_same_token_cannot_be_reused(self, client):
        """A reset token is single-use only."""
        email = f"singleuse_{int(time.time())}@test.com"
        _register_user(client, email=email, password="originalpass")
        client.post("/api/v1/auth/forgot-password", json={"email": email})

        token = None
        for t, data in _reset_tokens.items():
            if data["email"] == email:
                token = t
                break

        # First use succeeds
        r1 = client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "firstnewpass",
        })
        assert r1.status_code == 200

        # Second use with same token fails
        r2 = client.post("/api/v1/auth/reset-password", json={
            "token": token,
            "new_password": "secondnewpass",
        })
        assert r2.status_code == 400


class TestRefreshTokenFlow:
    """POST /api/v1/auth/refresh — token rotation."""

    def test_refresh_token_returns_new_pair(self, client):
        """A valid refresh token returns a new access + refresh token pair."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"refresh_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "Refresh Test",
            "company_name": "Refresh Corp",
        })
        refresh_token = resp.json()["refresh_token"]
        old_access = resp.json()["access_token"]

        resp2 = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != old_access
        assert data["refresh_token"] != refresh_token  # rotation

    def test_refresh_old_token_revoked_after_rotation(self, client):
        """After refresh, the old refresh token is revoked."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"revoked_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "Revoked Test",
            "company_name": "Revoked Corp",
        })
        old_refresh = resp.json()["refresh_token"]

        # Refresh once (rotates)
        client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})

        # Try using the old token again
        resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert resp2.status_code == 401

    def test_refresh_invalid_token_returns_401(self, client):
        """Invalid refresh token returns 401."""
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-refresh-token",
        })
        assert resp.status_code == 401

    def test_refresh_missing_token_returns_400(self, client):
        """Missing refresh_token in body returns 400."""
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 400


class TestLogout:
    """POST /api/v1/auth/logout"""

    def test_logout_revokes_refresh_token(self, client):
        """After logout, the refresh token is revoked."""
        resp = client.post("/api/v1/registration/register", json={
            "email": f"logout_{int(time.time())}@test.com",
            "password": "securepass123",
            "display_name": "Logout Test",
            "company_name": "Logout Corp",
        })
        refresh_token = resp.json()["refresh_token"]

        # Logout
        r1 = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        assert r1.status_code == 200

        # Try to refresh — should fail
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r2.status_code == 401

    def test_logout_without_token_still_returns_200(self, client):
        """Logout without refresh_token is still idempotent."""
        resp = client.post("/api/v1/auth/logout", json={})
        assert resp.status_code == 200


class TestDBUserLogin:
    """Login for DB-created users (not admin env-var)."""

    def test_db_user_login_success(self, client):
        """A user created via registration can login and get tokens."""
        email = f"dblogin_{int(time.time())}@test.com"
        password = "securepass123"
        client.post("/api/v1/registration/register", json={
            "email": email,
            "password": password,
            "display_name": "DB Login",
            "company_name": "DB Login Corp",
        })
        resp = client.post("/api/v1/auth/token", data={
            "username": email,
            "password": password,
        })
        assert resp.status_code == 200
        payload = decode_access_token(resp.json()["access_token"])
        assert payload["sub"] == email
        assert payload["role"] == "manager"
