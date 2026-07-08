"""Full token lifecycle E2E tests.

Uses the shared security fixtures (client) defined in
``tests/security/conftest.py``.

Test matrix:
  1. Full lifecycle: login → access → refresh → new access → logout → reuse rejected → re-login
  2. Same access token works across multiple endpoints
  3. Multiple refresh cycles all succeed and return new tokens
  4. Manually expired access token is rejected
"""

import time
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient


from backend.api.v1.auth import _clear_lockout

# ── Test constants ─────────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin-a@test.com"
ADMIN_PW = "test-admin-pw-123"
_PROTECTED_ENDPOINTS = [
    "/api/v1/trips/",
    "/api/v1/clients/",
    "/api/v1/drivers/",
]


# ═══════════════════════════════════════════════════════════════════════════════
# TestTokenLifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenLifecycle:
    """End-to-end token lifecycle scenarios."""

    def test_full_token_lifecycle(self, client: TestClient) -> None:
        """Complete flow: login → use → refresh → use → logout → reuse rejected → re-login."""
        _clear_lockout(ADMIN_EMAIL)

        # a) Login with valid credentials
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        tokens = login_resp.json()
        access_token_1 = tokens["access_token"]
        refresh_token_1 = tokens["refresh_token"]
        assert tokens.get("token_type") == "bearer"

        # b) Use the access token to access a protected endpoint
        headers_1 = {"Authorization": f"Bearer {access_token_1}"}
        trips_resp = client.get("/api/v1/trips/", headers=headers_1)
        assert trips_resp.status_code == 200, (
            f"First access token should work, got {trips_resp.status_code}: {trips_resp.text}"
        )

        # c) Refresh with the refresh token → get NEW pair
        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_1},
        )
        assert refresh_resp.status_code == 200, (
            f"First refresh should succeed, got {refresh_resp.status_code}: {refresh_resp.text}"
        )
        tokens_2 = refresh_resp.json()
        access_token_2 = tokens_2["access_token"]
        refresh_token_2 = tokens_2["refresh_token"]
        assert "access_token" in tokens_2
        assert "refresh_token" in tokens_2
        # Verify it is indeed a new access token
        assert access_token_2 != access_token_1, (
            "Refreshed access token should be different from the original"
        )

        # d) Use NEW access token to access a protected endpoint
        headers_2 = {"Authorization": f"Bearer {access_token_2}"}
        trips_resp_2 = client.get("/api/v1/trips/", headers=headers_2)
        assert trips_resp_2.status_code == 200, (
            f"Refreshed access token should work, got {trips_resp_2.status_code}: {trips_resp_2.text}"
        )

        # e) Logout with the SECOND refresh token
        logout_resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token_2},
        )
        assert logout_resp.status_code == 200, (
            f"Logout should succeed, got {logout_resp.status_code}: {logout_resp.text}"
        )

        # f) Try to use the SECOND (now revoked) refresh token → 401
        refresh_revoked = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_2},
        )
        assert refresh_revoked.status_code == 401, (
            f"Revoked refresh token should return 401, "
            f"got {refresh_revoked.status_code}: {refresh_revoked.text}"
        )

        # g) Re-login with valid credentials → should work again
        relogin_resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert relogin_resp.status_code == 200, (
            f"Re-login should succeed, got {relogin_resp.status_code}: {relogin_resp.text}"
        )
        assert "access_token" in relogin_resp.json()
        assert "refresh_token" in relogin_resp.json()

    def test_token_works_across_multiple_endpoints(self, client: TestClient) -> None:
        """Same access token is accepted by multiple protected endpoints."""
        _clear_lockout(ADMIN_EMAIL)

        # Login once
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        access_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Use the same token on several endpoints
        for endpoint in _PROTECTED_ENDPOINTS:
            resp = client.get(endpoint, headers=headers)
            assert resp.status_code == 200, (
                f"Token should work on {endpoint}, "
                f"got {resp.status_code}: {resp.text}"
            )

    def test_multiple_refresh_cycles(self, client: TestClient) -> None:
        """Multiple refresh cycles: login → refresh → refresh again → refresh again."""
        _clear_lockout(ADMIN_EMAIL)

        # Login
        login_resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        refresh_token = login_resp.json()["refresh_token"]
        previous_access = login_resp.json()["access_token"]

        # Perform three refresh cycles
        for cycle in range(1, 4):
            resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            assert resp.status_code == 200, (
                f"Refresh cycle {cycle} should succeed, "
                f"got {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert "access_token" in body, f"Cycle {cycle} missing access_token"
            assert "refresh_token" in body, f"Cycle {cycle} missing refresh_token"
            # Verify we got a new access token (rotation)
            assert body["access_token"] != previous_access, (
                f"Cycle {cycle} should return a different access token"
            )
            # Update for next cycle
            refresh_token = body["refresh_token"]
            previous_access = body["access_token"]

    def test_expired_access_token_rejected(self, client: TestClient) -> None:
        """A manually crafted expired JWT is rejected by a protected endpoint."""
        import os

        secret = os.environ.get(
            "OPERION_JWT_SECRET_KEY", "test-secret-key-32-chars-for-testing-only!!"
        )
        expired_payload = {
            "sub": ADMIN_EMAIL,
            "role": "admin",
            "exp": int(time.time()) - 3600,  # expired 1 hour ago
        }
        expired_token = pyjwt.encode(expired_payload, secret, algorithm="HS256")
        headers = {"Authorization": f"Bearer {expired_token}"}

        resp = client.get("/api/v1/trips/", headers=headers)
        assert resp.status_code == 401, (
            f"Expired token should return 401, got {resp.status_code}: {resp.text}"
        )
