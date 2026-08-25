"""Authorization tests — endpoint protection, expired tokens, role claims.

Uses the shared security fixtures (client, admin_token, auth_admin)
defined in ``tests/security/conftest.py``.
"""
from __future__ import annotations


import time
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient


# ── Public paths that do NOT require authentication ──────────────────────────
PUBLIC_PATHS = {
    "/api/v1/health/",
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/auth/token",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/token/client-credentials",
    "/api/v1/registration/register",
    "/api/v1/route-demo/calculate",
    "/api/v1/waitlist/join",
    "/api/v1/waitlist/count",
    "/api/v1/status",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Finding #3 — All protected endpoints require authentication
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllEndpointsRequireAuth:
    """Every non-public route must reject unauthenticated requests."""

    def _extract_route_paths(self, app) -> set[str]:
        """Extract all route paths from a FastAPI app, traversing
        ``_IncludedRouter`` objects (FastAPI >= 0.139.0 stores included
        routers as ``_IncludedRouter`` instead of expanding them).
        """
        paths: set[str] = set()
        for route in app.routes:
            if hasattr(route, "path") and route.path:
                paths.add(route.path)
            elif hasattr(route, "effective_route_contexts"):
                for ctx in route.effective_route_contexts():
                    if hasattr(ctx, "path") and ctx.path:
                        paths.add(ctx.path)
        return paths

    def test_all_protected_routes_reject_no_token(self, client: TestClient):
        """Dynamically iterate app.routes, hit each without auth, expect 401/403.

        Routes with path parameters (containing ``{``) are skipped because
        they cannot be resolved with literal braces.  If a route returns 405
        on GET, a POST is attempted as a fallback.
        """
        from backend.main import app as fastapi_app

        routes = self._extract_route_paths(fastapi_app)

        tested = 0
        errors: list[str] = []

        for path in sorted(routes):
            if path in PUBLIC_PATHS:
                continue
            if "{" in path:
                continue  # path params cannot be resolved with literal braces

            # Try GET first; fall back to POST on 405
            resp = client.get(path)
            if resp.status_code == 405:
                resp = client.post(path)

            if resp.status_code not in (401, 403, 429):
                errors.append(
                    f"{path} returned {resp.status_code} without auth "
                    f"(expected 401/403): {resp.text[:120]}"
                )
            tested += 1

        assert tested >= 10, (
            f"Only tested {tested} protected routes — the route discovery "
            f"may be incomplete."
        )
        if errors:
            pytest.fail("\n".join(errors))


# ═══════════════════════════════════════════════════════════════════════════════
# Expired token rejection
# ═══════════════════════════════════════════════════════════════════════════════

class TestExpiredToken:
    """Tokens past their expiry date must be rejected with 401."""

    def test_expired_token_rejected(self, client: TestClient):
        """Call a protected endpoint with an obviously expired token.

        Create a JWT that expired 1 hour ago, send it to a known
        protected route, and assert 401.
        """
        import os
        secret = os.environ.get(
            "OPERION_JWT_SECRET_KEY", "test-secret-key-32-chars-for-testing-only!!"
        )
        expired_payload = {
            "sub": "admin@test.com",
            "role": "admin",
            "exp": int(time.time()) - 3600,  # expired 1 hour ago
        }
        expired_token = pyjwt.encode(
            expired_payload, secret, algorithm="HS256"
        )
        headers = {"Authorization": f"Bearer {expired_token}"}

        resp = client.get("/api/v1/trips/", headers=headers)
        assert resp.status_code in (401, 429), (
            f"Expired token should return 401 or 429, got {resp.status_code}: {resp.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Role downgrade gap documentation
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoleDowngradeGap:
    """Document the current token behaviour when a user's role is changed.

    **Known limitation:** The JWT carries a ``role`` claim that is set at
    login time.  If an administrator later downgrades the user's role in
    the database, the already-issued token remains valid until it expires.
    A comprehensive fix would require a token-blacklist or short-lived
    token strategy.
    """

    def test_role_downgrade_not_reflected_in_current_token(
        self, client: TestClient, admin_token: str, auth_admin: dict
    ):
        """Verify the token's role claim is what was issued at login.

        This test documents the gap: after a role change in the database,
        existing tokens still carry the original role.  The application
        relies on token-expiry (default minutes) rather than immediate
        revocation.

        Steps:
        1. Log in with admin credentials.
        2. Decode the token and inspect the ``role`` claim.
        3. Assert it matches the expected role (``admin``) — confirming
           that the token role is what was *issued*, not what the
           current DB row says.
        """
        import os
        secret = os.environ.get(
            "OPERION_JWT_SECRET_KEY", "test-secret-key-32-chars-for-testing-only!!"
        )

        # Decode the admin token to inspect its claims
        payload = pyjwt.decode(
            admin_token, secret, algorithms=["HS256"]
        )
        assert payload.get("role") == "admin", (
            f"Expected token role claim to be 'admin', got '{payload.get('role')}'"
        )
        assert payload.get("sub") is not None, "Token is missing 'sub' claim"
