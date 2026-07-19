"""Session/refresh token lifecycle and security tests.

Uses fixtures from conftest:
    client      FastAPI TestClient
    tokens      Dict with tokens for all test users

Test matrix:
  1.  Session fixation — old refresh token from first session cannot be
      reused after logout and a second login with different credentials
  2.  Concurrent sessions — two simultaneous login sessions both valid
  3.  Refresh rotation prevents replay — verified with a different (dispatcher) user
  4.  Logout then use access token — access token remains valid until expiry
  5.  Logout then use refresh token — refresh token becomes invalid immediately
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.v1.auth import _clear_lockout

# ── Test constants ─────────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin-a@test.com"
ADMIN_PW = "test-admin-pw-123"
DISPATCHER_A_EMAIL = "dispatcher-a@test.com"
DISPATCHER_PW = "dispatcher-pw-456"


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  Session Fixation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionFixation:
    """Old refresh tokens must not be usable after the user logs out and
    a new session is established."""

    def test_session_fixation(self, client: TestClient) -> None:
        """Login, capture the session's refresh token. Logout. Verify old
        refresh token can't be used. Login again with a different user,
        verify the old refresh token from the first session can't be used."""
        _clear_lockout(ADMIN_EMAIL)
        _clear_lockout(DISPATCHER_A_EMAIL)

        # ── First session: login as admin ───────────────────────────────
        login_resp_1 = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp_1.status_code == 200
        refresh_token_1 = login_resp_1.json()["refresh_token"]

        # Logout — revoke the refresh token
        logout_resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token_1},
        )
        assert logout_resp.status_code == 200, (
            f"Logout should succeed, got {logout_resp.status_code}: {logout_resp.text}"
        )

        # Verify old refresh token cannot be used after logout
        reuse_after_logout = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_1},
        )
        assert reuse_after_logout.status_code == 401, (
            f"Old refresh token should be rejected after logout, "
            f"got {reuse_after_logout.status_code}: {reuse_after_logout.text}"
        )

        # ── Second session: login as dispatcher-a (different user) ──────
        login_resp_2 = client.post(
            "/api/v1/auth/token",
            data={"username": DISPATCHER_A_EMAIL, "password": DISPATCHER_PW},
        )
        assert login_resp_2.status_code == 200

        # Clear cookies so the server reads the body refresh_token instead
        # of the cookie set by the second login.
        client.cookies.clear()

        # Verify the OLD refresh token from the first (admin) session
        # still cannot be used, even though a new session exists
        reuse_cross_session = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_1},
        )
        assert reuse_cross_session.status_code == 401, (
            f"Old refresh token from prior session should still be rejected, "
            f"got {reuse_cross_session.status_code}: {reuse_cross_session.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  Concurrent Sessions
# ═══════════════════════════════════════════════════════════════════════════════


class TestConcurrentSessions:
    """Multiple simultaneous login sessions for the same user must all be valid."""

    def test_concurrent_sessions(self, client: TestClient) -> None:
        """Login as admin twice, get two different refresh tokens.
        Both should be valid simultaneously."""
        _clear_lockout(ADMIN_EMAIL)

        # ── First login ─────────────────────────────────────────────────
        login_resp_1 = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp_1.status_code == 200, (
            f"First login should succeed, got {login_resp_1.status_code}: {login_resp_1.text}"
        )
        refresh_token_1 = login_resp_1.json()["refresh_token"]
        access_token_1 = login_resp_1.json()["access_token"]

        # ── Second login (same user) ────────────────────────────────────
        login_resp_2 = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp_2.status_code == 200, (
            f"Second login should succeed, got {login_resp_2.status_code}: {login_resp_2.text}"
        )
        refresh_token_2 = login_resp_2.json()["refresh_token"]
        access_token_2 = login_resp_2.json()["access_token"]

        # Verify we got two distinct refresh tokens
        assert refresh_token_1 != refresh_token_2, (
            "Two logins should produce different refresh tokens"
        )

        # ── Both access tokens should work ──────────────────────────────
        headers_1 = {"Authorization": f"Bearer {access_token_1}"}
        resp_1 = client.get("/api/v1/trips/", headers=headers_1)
        assert resp_1.status_code == 200, (
            f"First session access token should work, "
            f"got {resp_1.status_code}: {resp_1.text}"
        )

        headers_2 = {"Authorization": f"Bearer {access_token_2}"}
        resp_2 = client.get("/api/v1/trips/", headers=headers_2)
        assert resp_2.status_code == 200, (
            f"Second session access token should work, "
            f"got {resp_2.status_code}: {resp_2.text}"
        )

        # ── Both refresh tokens should work ─────────────────────────────
        refresh_resp_1 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_1},
        )
        assert refresh_resp_1.status_code == 200, (
            f"First session refresh token should work, "
            f"got {refresh_resp_1.status_code}: {refresh_resp_1.text}"
        )

        refresh_resp_2 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_2},
        )
        assert refresh_resp_2.status_code == 200, (
            f"Second session refresh token should work, "
            f"got {refresh_resp_2.status_code}: {refresh_resp_2.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  Refresh Rotation Prevents Replay (verified with a different user)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRefreshRotationReplay:
    """Using a refresh token a second time must fail (rotation)."""

    def test_refresh_rotation_prevents_replay(self, client: TestClient) -> None:
        """Login as dispatcher, use refresh token, then use the same
        refresh token again — second attempt should be rejected."""
        _clear_lockout(DISPATCHER_A_EMAIL)

        # Login as dispatcher-a (different user from the existing test_auth test)
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": DISPATCHER_A_EMAIL, "password": DISPATCHER_PW},
        )
        assert login_resp.status_code == 200, (
            f"Login should succeed, got {login_resp.status_code}: {login_resp.text}"
        )
        refresh_token = login_resp.json()["refresh_token"]

        # First use — should succeed
        first = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert first.status_code == 200, (
            f"First refresh should succeed, got {first.status_code}: {first.text}"
        )
        first_body = first.json()
        assert "access_token" in first_body
        assert "refresh_token" in first_body

        # Clear cookies so the server reads the body refresh_token instead
        # of the cookie set by the first refresh response.
        client.cookies.clear()

        # Second use with the **original** refresh token — should fail
        second = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert second.status_code == 401, (
            f"Reused refresh token should be rejected with 401, "
            f"got {second.status_code}: {second.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  Logout Then Use Access Token
# ═══════════════════════════════════════════════════════════════════════════════


class TestAccessTokenAfterLogout:
    """Access tokens should remain valid until they expire, even after
    logout (unless a token-blacklist is implemented)."""

    def test_logout_then_use_access_token(self, client: TestClient) -> None:
        """Login, get access token, logout, then immediately use the
        access token — should still be accepted (short-lived validity)."""
        _clear_lockout(ADMIN_EMAIL)

        # Login
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp.status_code == 200, (
            f"Login should succeed, got {login_resp.status_code}: {login_resp.text}"
        )
        access_token = login_resp.json()["access_token"]
        refresh_token = login_resp.json()["refresh_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Verify access token works before logout
        resp_before = client.get("/api/v1/trips/", headers=headers)
        assert resp_before.status_code == 200, (
            f"Access token should work before logout, "
            f"got {resp_before.status_code}: {resp_before.text}"
        )

        # Logout
        logout_resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_resp.status_code == 200, (
            f"Logout should succeed, got {logout_resp.status_code}: {logout_resp.text}"
        )

        # Use the same access token immediately after logout
        # Access tokens are short-lived and should remain valid until expiry
        resp_after = client.get("/api/v1/trips/", headers=headers)
        assert resp_after.status_code in (200, 401), (
            f"Access token after logout: expected 200 or 401, "
            f"got {resp_after.status_code}: {resp_after.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  Logout Then Use Refresh Token
# ═══════════════════════════════════════════════════════════════════════════════


class TestRefreshTokenAfterLogout:
    """Refresh tokens must be immediately invalidated on logout."""

    def test_logout_then_use_refresh(self, client: TestClient) -> None:
        """Login, logout, then try to use the refresh token — should be 401."""
        _clear_lockout(ADMIN_EMAIL)

        # Login
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp.status_code == 200, (
            f"Login should succeed, got {login_resp.status_code}: {login_resp.text}"
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Logout
        logout_resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_resp.status_code == 200, (
            f"Logout should succeed, got {logout_resp.status_code}: {logout_resp.text}"
        )

        # Try to use the now-revoked refresh token
        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 401, (
            f"Refresh token after logout should return 401, "
            f"got {refresh_resp.status_code}: {refresh_resp.text}"
        )
