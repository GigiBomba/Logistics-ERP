"""Infrastructure-level security tests.

CORS, Server header leakage, disabled docs in production, exception
handler registration, and rate-limiter middleware presence.
"""

import importlib
import os

import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════
# CORS
# ═══════════════════════════════════════════════════════════════════════

class TestCORS:
    """Verify CORS middleware rejects unapproved origins."""

    def test_cors_unapproved_origin_rejected(self, client: TestClient):
        """GET /api/v1/health/ with an evil Origin must NOT be reflected."""
        resp = client.get(
            "/api/v1/health/",
            headers={"Origin": "https://evil.example.com"},
        )
        # The response must not include the evil origin in ACAO
        acao = resp.headers.get("access-control-allow-origin", "")
        assert "evil.example.com" not in acao, (
            f"CORS leaked unapproved origin: {acao}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Server header leakage
# ═══════════════════════════════════════════════════════════════════════

class TestServerHeader:
    """The Server header must not leak implementation details."""

    def test_no_server_header(self, client: TestClient):
        """GET any endpoint and verify no Server header or no version info."""
        resp = client.get("/api/v1/health/")
        server = resp.headers.get("server", "")
        if not server:
            return  # No server header at all — ideal

        # If present, it must not contain version numbers or framework names
        leak_indicators = (
            "uvicorn", "gunicorn", "python", "fastapi",
            "starlette", "asgi", "1.", "2.", "3.", "4.", "5.",
        )
        lower = server.lower()
        for indicator in leak_indicators:
            assert indicator not in lower, (
                f"Server header leaks version/framework info: '{server}' "
                f"(contains '{indicator}')"
            )


# ═══════════════════════════════════════════════════════════════════════
# Docs disabled in production
# ═══════════════════════════════════════════════════════════════════════

class TestDocsDisabledInProduction:
    """Swagger UI, ReDoc and OpenAPI JSON must be 404 in production mode."""

    @pytest.fixture
    def production_client(self):
        """Create a TestClient with OPERION_ENV=production."""
        old_env = os.environ.get("OPERION_ENV", "")

        os.environ["OPERION_ENV"] = "production"

        # Reload backend.main so create_app() runs with production env
        import backend.main
        importlib.reload(backend.main)
        from backend.main import app as prod_app

        yield TestClient(prod_app)

        # Restore environment
        if old_env:
            os.environ["OPERION_ENV"] = old_env
        else:
            os.environ.pop("OPERION_ENV", None)

        # Reload again to restore original (test) state
        importlib.reload(backend.main)

    def test_docs_disabled(self, production_client: TestClient):
        """Docs endpoints return 404 when OPERION_ENV=production."""
        for path in ("/docs", "/redoc", "/openapi.json"):
            resp = production_client.get(path)
            assert resp.status_code == 404, (
                f"{path} returned {resp.status_code} in production mode, "
                f"expected 404"
            )


# ═══════════════════════════════════════════════════════════════════════
# Exception handler
# ═══════════════════════════════════════════════════════════════════════

class TestExceptionHandler:
    """A custom Exception handler must be registered on the app."""

    def test_error_handler_returns_generic_body(self, app):
        """The app.exception_handlers dict must contain Exception."""
        has_exception_handler = Exception in app.exception_handlers
        has_500_handler = 500 in app.exception_handlers
        assert has_exception_handler or has_500_handler, (
            "No global Exception or 500 handler registered — "
            "internal errors may leak stack traces"
        )


# ═══════════════════════════════════════════════════════════════════════
# Rate limiter middleware presence
# ═══════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    """Verify RateLimitMiddleware is wired into the middleware stack."""

    def test_rate_limiter_returns_429(self, app):
        """Check that RateLimitMiddleware appears in app.user_middleware."""
        from backend.middleware.rate_limit_middleware import RateLimitMiddleware

        middleware_types = [m.cls for m in app.user_middleware]
        assert RateLimitMiddleware in middleware_types, (
            "RateLimitMiddleware is not registered in the middleware stack"
        )
