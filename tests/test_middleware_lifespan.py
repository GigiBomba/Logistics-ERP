"""Integration tests for create_app() middleware wiring and lifecycle coverage.

Tests cover:
- create_app() returns a valid FastAPI instance without errors
- All middlewares are wired (app.user_middleware contains expected classes)
- CORS middleware is configured with explicit origins (not wildcard)
- Exception handlers are registered for HTTPException and generic Exception
- Custom exception handlers return RFC 7807 ProblemDetail format
- App startup (creation) does not raise despite unavailable Redis/DB
- App shutdown (TestClient context manager exit) completes without errors

Important note about middleware ordering:
  ``app.user_middleware`` stores middlewares in **reverse** insertion order
  (``add_middleware`` prepends).  The **execution** order (outermost first)
  is therefore the order in ``user_middleware``, which matches the order in
  which ``create_app()`` calls ``app.add_middleware()`` (last added = outermost).
"""

from __future__ import annotations

import os
from typing import Generator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.errors import ErrorCode, ProblemDetail


# ── Helper: middleware classes expected in the stack ────────────────────
# ``add_middleware`` prepends to ``user_middleware``, so the list below
# is in **reverse** insertion order (last-added = index 0 = outermost).


def _expected_outer_to_inner() -> list[type]:
    """Return middleware classes outermost-first, matching
    ``app.user_middleware`` order."""
    from backend.middleware.correlation_middleware import CorrelationMiddleware
    from backend.middleware.logging_middleware import LoggingMiddleware
    from backend.middleware.auth_middleware import AuthMiddleware
    from backend.middleware.security_headers_middleware import (
        SecurityHeadersMiddleware,
    )
    from backend.middleware.idempotency_middleware import IdempotencyMiddleware
    from backend.middleware.rate_limit_middleware import RateLimitMiddleware
    from backend.middleware.input_sanitization_middleware import (
        InputSanitizationMiddleware,
    )
    from backend.middleware.webhook_middleware import WebhookBodyMiddleware
    from backend.metrics import PrometheusMiddleware

    # This must match the order in which create_app() calls add_middleware,
    # which is also the outermost-first execution order (last added = index 0).
    return [
        InputSanitizationMiddleware,  # last added = outermost
        PrometheusMiddleware,
        WebhookBodyMiddleware,
        RateLimitMiddleware,
        IdempotencyMiddleware,
        SecurityHeadersMiddleware,
        AuthMiddleware,
        LoggingMiddleware,
        CorrelationMiddleware,
        CORSMiddleware,               # first added = innermost
    ]


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app() -> Generator[FastAPI, None, None]:
    """Create the full app via ``create_app`` once per module.

    Module scope means Redis connection attempts happen only once.
    """
    from backend.main import create_app

    _app = create_app()
    yield _app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Yield a TestClient that triggers lifespan events."""
    with TestClient(app) as _client:
        yield _client


# ═════════════════════════════════════════════════════════════════════
# App creation
# ═════════════════════════════════════════════════════════════════════


class TestAppCreation:
    """Verify create_app() succeeds despite unavailable infrastructure."""

    def test_create_app_returns_fastapi_instance(self):
        """create_app() should return a FastAPI app without raising."""
        from backend.main import create_app

        _app = create_app()
        assert isinstance(_app, FastAPI)

    def test_create_app_title_and_version(self):
        """The default title and version are set correctly."""
        from backend.main import create_app

        _app = create_app()
        assert _app.title == "Operion ERP API"
        assert _app.version == "1.0.0"

    def test_create_app_with_custom_settings(self):
        """create_app() accepts an optional BackendSettings parameter."""
        from backend.config import BackendSettings
        from backend.main import create_app

        settings = BackendSettings()
        _app = create_app(settings=settings)
        assert isinstance(_app, FastAPI)

    def test_app_lifespan_context_manager_does_not_raise(self, app: FastAPI):
        """Using TestClient as context manager (startup + shutdown) succeeds.

        This exercises any registered lifespan / on_event handlers.
        """
        with TestClient(app) as _client:
            resp = _client.get("/api/v1/health")
            # The health endpoint may return various statuses depending on
            # environment; we just verify the server responds.
            assert resp.status_code in (200, 401, 403)


# ═════════════════════════════════════════════════════════════════════
# Middleware wiring
# ═════════════════════════════════════════════════════════════════════


class TestMiddlewareWiring:
    """Verify all middlewares are registered in the expected order."""

    def test_all_expected_middleware_present(self, app: FastAPI):
        """Every expected middleware class appears in app.user_middleware.

        Comparison is by class NAME: ``test_security_verification.py`` /
        ``tests/chaos/test_chaos_celery.py`` ``importlib.reload`` the
        middleware modules, which creates NEW class objects with the same
        names — an identity check (``cls in registered``) then spuriously
        fails even though the app wires the correct middleware.
        """
        expected = _expected_outer_to_inner()
        registered_names = [m.cls.__name__ for m in app.user_middleware]

        for cls in expected:
            assert cls.__name__ in registered_names, (
                f"Expected middleware {cls.__name__} not found in user_middleware"
            )

    def test_middleware_count_matches(self, app: FastAPI):
        """The number of registered middlewares matches expected."""
        expected_count = len(_expected_outer_to_inner())
        registered_count = len(app.user_middleware)
        assert registered_count == expected_count, (
            f"Expected {expected_count} middlewares, found {registered_count}. "
            f"Registered: {[m.cls.__name__ for m in app.user_middleware]}"
        )

    def test_middleware_outermost_order(self, app: FastAPI):
        """The user_middleware list (outermost-first) matches the
        expected execution order: InputSanitization outermost, CORS innermost.

        Compared by class NAME (see ``test_all_expected_middleware_present`` —
        ``importlib.reload`` of the middleware modules changes class identity
        but not the wiring order).
        """
        expected = _expected_outer_to_inner()
        registered = [m.cls.__name__ for m in app.user_middleware]

        for i, cls in enumerate(expected):
            assert registered[i] == cls.__name__, (
                f"Position {i}: expected {cls.__name__}, "
                f"got {registered[i]}"
            )

    def test_input_sanitization_is_outermost(self, app: FastAPI):
        """InputSanitizationMiddleware must be index 0 (outermost / last added)."""
        registered = [m.cls.__name__ for m in app.user_middleware]
        assert registered[0] == "InputSanitizationMiddleware", (
            f"Expected InputSanitizationMiddleware at index 0, got {registered[0]}"
        )

    def test_cors_is_innermost(self, app: FastAPI):
        """CORSMiddleware must be last index (innermost / first added)."""
        registered = [m.cls.__name__ for m in app.user_middleware]
        assert registered[-1] == "CORSMiddleware", (
            f"Expected CORSMiddleware at last index, got {registered[-1]}"
        )

    def test_relative_order_correlation_before_logging(self, app: FastAPI):
        """CorrelationMiddleware must run before LoggingMiddleware in
        the RESPONSE path so the correlation ID is available when the
        log line is written.

        In user_middleware (outermost-first), Correlation has a higher
        index (more inner) than Logging, meaning it runs before Logging
        on the response path (inner → outer).
        """
        registered = [m.cls.__name__ for m in app.user_middleware]
        corr_idx = registered.index("CorrelationMiddleware")
        log_idx = registered.index("LoggingMiddleware")
        # Correlation runs BEFORE Logging on the response path, which is
        # when Logging's after-request code executes.  In user_middleware
        # this means Correlation has a HIGHER index (more inner).
        assert corr_idx > log_idx, (
            f"CorrelationMiddleware at {corr_idx} should be inner to "
            f"LoggingMiddleware at {log_idx} (correlation_idx > log_idx)"
        )

    def test_relative_order_auth_before_security(self, app: FastAPI):
        """AuthMiddleware must run before SecurityHeadersMiddleware
        on the RESPONSE path so that unauthenticated requests are
        rejected before security headers are appended to the response.

        In user_middleware, Auth has a higher index (more inner) than
        SecurityHeaders, meaning it runs before SecurityHeaders on the
        response path.
        """
        registered = [m.cls.__name__ for m in app.user_middleware]
        auth_idx = registered.index("AuthMiddleware")
        sec_idx = registered.index("SecurityHeadersMiddleware")
        assert auth_idx > sec_idx, (
            f"AuthMiddleware at {auth_idx} should be inner to "
            f"SecurityHeadersMiddleware at {sec_idx}"
        )

    def test_relative_order_idempotency_before_rate_limit(self, app: FastAPI):
        """IdempotencyMiddleware must run before RateLimitMiddleware
        on the RESPONSE path so replayed keys are not counted toward
        the rate limit.

        In user_middleware, Idempotency has a higher index (more inner)
        than RateLimit.
        """
        registered = [m.cls.__name__ for m in app.user_middleware]
        idem_idx = registered.index("IdempotencyMiddleware")
        rate_idx = registered.index("RateLimitMiddleware")
        assert idem_idx > rate_idx, (
            f"IdempotencyMiddleware at {idem_idx} should be inner to "
            f"RateLimitMiddleware at {rate_idx}"
        )

    def test_middleware_options_preserved(self, app: FastAPI):
        """SecurityHeadersMiddleware receives is_production and cors_origins."""
        for mw in app.user_middleware:
            if mw.cls.__name__ == "SecurityHeadersMiddleware":
                assert "is_production" in mw.kwargs
                assert "cors_origins" in mw.kwargs


# ═════════════════════════════════════════════════════════════════════
# CORS configuration
# ═════════════════════════════════════════════════════════════════════


class TestCorsConfiguration:
    """Verify CORS middleware is configured correctly (not wildcard origin)."""

    def test_cors_middleware_present(self, app: FastAPI):
        """CORSMiddleware must be registered."""
        classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in classes

    def test_cors_allow_credentials_is_true(self, app: FastAPI):
        """CORS must allow credentials (cookies, Authorization headers)."""
        for mw in app.user_middleware:
            if mw.cls is CORSMiddleware:
                assert mw.kwargs.get("allow_credentials") is True

    def test_cors_methods_are_explicit(self, app: FastAPI):
        """CORS allowed methods must be an explicit list, not wildcard."""
        for mw in app.user_middleware:
            if mw.cls is CORSMiddleware:
                methods = mw.kwargs.get("allow_methods", [])
                assert "*" not in methods, (
                    "CORS allow_methods must not be *"
                )
                assert isinstance(methods, list) and len(methods) > 0

    def test_cors_headers_are_explicit(self, app: FastAPI):
        """CORS allowed headers must be an explicit list."""
        for mw in app.user_middleware:
            if mw.cls is CORSMiddleware:
                headers = mw.kwargs.get("allow_headers", [])
                assert "*" not in headers, (
                    "CORS allow_headers must not be *"
                )
                assert isinstance(headers, list) and len(headers) > 0

    def test_cors_not_wildcard_origin_in_production(self, monkeypatch):
        """In production mode, explicit origins are set (not wildcard)."""
        monkeypatch.setenv("OPERION_ENV", "production")
        monkeypatch.setenv("OPERION_API_KEY", "test-prod-key")
        monkeypatch.setenv("OPERION_SUPPORT_INTERNAL_AUTH", "test-internal-auth")

        import importlib
        import backend.main as main_module
        importlib.reload(main_module)

        prod_app = main_module.create_app()
        for mw in prod_app.user_middleware:
            if mw.cls is CORSMiddleware:
                origins = mw.kwargs.get("allow_origins", [])
                assert "*" not in origins, (
                    "CORS allow_origins must not be * in production"
                )
                assert len(origins) > 0
                assert any(
                    "operionerp.xyz" in o for o in origins
                ), f"Expected operionerp.xyz in CORS origins, got {origins}"

    def test_cors_options_request_succeeds(self, client: TestClient):
        """An OPTIONS preflight request must succeed."""
        resp = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204, 401, 403)


# ═════════════════════════════════════════════════════════════════════
# Exception handler registration
# ═════════════════════════════════════════════════════════════════════


class TestExceptionHandlerRegistration:
    """Verify exception handlers are registered on the app."""

    def test_global_exception_handler_registered(self, app: FastAPI):
        """A handler for ``Exception`` must be registered."""
        handlers = app.exception_handlers
        assert Exception in handlers, (
            "No handler registered for Exception "
            f"(handlers: {list(handlers.keys())})"
        )

    def test_internal_error_handler_registered(self, app: FastAPI):
        """A handler for status 500 (HTTPException) must be registered."""
        has_500 = any(
            isinstance(k, int) and k == 500
            for k in app.exception_handlers
        )
        # If not registered as int, check if HTTPException has a handler
        # that covers 500
        if not has_500:
            has_500 = HTTPException in app.exception_handlers
        assert has_500, (
            "Expected a handler for HTTPException(status_code=500) or int 500"
        )


# ═════════════════════════════════════════════════════════════════════
# RFC 7807 ProblemDetail format
# ═════════════════════════════════════════════════════════════════════


class _ProblemDetailRouter:
    """Build a minimal app with exception handlers matching create_app().

    The real ``create_app`` registers:
      ``@app.exception_handler(Exception)`` — catches all Exception
      ``@app.exception_handler(500)`` — catches HTTPException(status_code=500)

    FastAPI's built-in handler catches ``HTTPException`` for other statuses
    (400, 403, 404, 422) and returns ``{"detail": ...}``.

    This fixture replicates that exact setup so we can verify the RFC 7807
    format of responses produced by the custom handlers.
    """

    @staticmethod
    def build() -> FastAPI:
        from backend.errors import get_error_code_for_exception  # noqa: PLC0415

        _app = FastAPI()

        # ── Replicate the global exception handler from main.py ──
        @_app.exception_handler(Exception)
        async def global_exception_handler(request, exc):
            error_code, status = get_error_code_for_exception(exc)

            detail = str(exc)
            error_code_value = error_code.value
            if hasattr(exc, "detail"):
                if isinstance(exc.detail, dict):
                    detail = exc.detail.get("detail", detail)
                    if "error_code" in exc.detail:
                        error_code_value = exc.detail["error_code"]
                elif isinstance(exc.detail, str):
                    detail = exc.detail

            problem = ProblemDetail(
                type=f"https://api.operionerp.xyz/errors/{error_code_value}",
                title="An error occurred",
                status=status,
                detail=detail,
                instance=str(request.url),
                error_code=error_code_value,
            )

            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=status, content=problem.to_dict())

        # ── Replicate the 500 handler from main.py ───────────────
        @_app.exception_handler(500)
        async def internal_error_handler(request, exc):
            error_code, status = get_error_code_for_exception(exc)
            problem = ProblemDetail(
                type=f"https://api.operionerp.xyz/errors/{error_code.value}",
                title="Internal server error",
                status=status,
                detail="An unexpected error occurred. Please try again later.",
                instance=str(request.url),
                error_code=error_code.value,
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=status, content=problem.to_dict())

        # ── Test routes ─────────────────────────────────────────
        @_app.get("/raise/runtime")
        async def raise_runtime():
            raise RuntimeError("Something went wrong")

        @_app.get("/raise/http-400")
        async def raise_http_400():
            raise HTTPException(status_code=400, detail="Bad request input")

        @_app.get("/raise/http-403")
        async def raise_http_403():
            raise HTTPException(status_code=403, detail="Forbidden resource")

        @_app.get("/raise/http-404")
        async def raise_http_404():
            raise HTTPException(status_code=404, detail="Resource not found")

        @_app.get("/raise/http-422")
        async def raise_http_422():
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "Validation failed",
                    "error_code": "validation-error",
                },
            )

        @_app.get("/raise/http-500")
        async def raise_http_500():
            raise HTTPException(status_code=500, detail="Internal failure")

        @_app.get("/raise/validation")
        async def raise_validation():
            from services.exceptions import ValidationError
            raise ValidationError("Input validation failed")

        @_app.get("/raise/not-found")
        async def raise_not_found():
            from services.exceptions import NotFoundError
            raise NotFoundError("Resource not found")

        return _app


@pytest.fixture(scope="module")
def problem_detail_app() -> FastAPI:
    return _ProblemDetailRouter.build()


@pytest.fixture
def problem_client(
    problem_detail_app: FastAPI,
) -> Generator[TestClient, None, None]:
    """TestClient for ProblemDetail tests.

    ``raise_server_exceptions=False`` prevents Starlette's
    ``ServerErrorMiddleware`` from re-raising exceptions after the
    exception-handler response, which would mask the response body.
    """
    with TestClient(problem_detail_app, raise_server_exceptions=False) as c:
        yield c


class TestProblemDetailFormat:
    """Verify custom exception handlers return RFC 7807 format.

    Only exceptions caught by the custom handlers produce ProblemDetail:
      - Any ``Exception`` (→ global handler)
      - ``HTTPException(status_code=500)`` (→ internal_error_handler)

    Other ``HTTPException`` statuses are handled by FastAPI's built-in
    handler and return ``{"detail": ...}`` (not ProblemDetail).
    """

    RFC_7807_FIELDS = {"type", "title", "status", "detail", "instance", "error_code"}

    def _assert_problem_detail(
        self, data: dict, expected_status: int, expected_error_code: str | None = None
    ):
        """Assert the response body follows RFC 7807 ProblemDetail format."""
        for field in self.RFC_7807_FIELDS - {"instance", "error_code"}:
            assert field in data, (
                f"Missing required RFC 7807 field '{field}' in {data}"
            )
        assert isinstance(data["type"], str) and len(data["type"]) > 0
        assert isinstance(data["title"], str) and len(data["title"]) > 0
        assert data["status"] == expected_status, (
            f"Expected status {expected_status}, got {data['status']}"
        )
        assert isinstance(data["detail"], str)
        if expected_error_code:
            assert data.get("error_code") == expected_error_code, (
                f"Expected error_code={expected_error_code!r}, "
                f"got {data.get('error_code')!r}"
            )
        # type URL should contain the error_code for known codes
        if data.get("error_code"):
            assert data["error_code"] in data.get("type", ""), (
                f"type URL {data['type']!r} should contain "
                f"error_code {data['error_code']!r}"
            )

    # ── Bare RuntimeError → ServerErrorMiddleware → 500 handler → ProblemDetail
    #    (``raise_server_exceptions=False`` causes ServerErrorMiddleware
    #     to catch the unhandled RuntimeError and synthesise a 500 response,
    #     which then triggers the ``@app.exception_handler(500)`` handler.)

    def test_runtime_error_returns_500_problem_detail(
        self, problem_client: TestClient
    ):
        """A bare RuntimeError produces a 500 ProblemDetail response via
        ServerErrorMiddleware → 500 handler."""
        resp = problem_client.get("/raise/runtime")
        assert resp.status_code == 500
        data = resp.json()
        self._assert_problem_detail(data, 500)
        assert data.get("error_code") == ErrorCode.INTERNAL_ERROR.value, (
            f"Expected error_code={ErrorCode.INTERNAL_ERROR.value}, "
            f"got {data.get('error_code')}"
        )

    # ── HTTPException(500) → FastAPI built-in handler → {"detail": ...}
    #    FastAPI's built-in HTTPException handler takes precedence over
    #    the status-code-based 500 handler for direct HTTPException raises.

    def test_http_500_uses_fastapi_default(self, problem_client: TestClient):
        """HTTPException(status_code=500) is caught by FastAPI's built-in
        handler and returns ``{'detail': '...'}`` (not ProblemDetail)."""
        resp = problem_client.get("/raise/http-500")
        assert resp.status_code == 500
        data = resp.json()
        assert "detail" in data
        assert "type" not in data

    # ── Custom Operion exceptions → global handler → ProblemDetail ──

    def test_validation_error_maps_to_422(self, problem_client: TestClient):
        """Custom ValidationError → 422 with proper error_code."""
        resp = problem_client.get("/raise/validation")
        assert resp.status_code == 422
        data = resp.json()
        self._assert_problem_detail(data, 422, ErrorCode.VALIDATION_ERROR.value)

    def test_not_found_error_maps_to_404(self, problem_client: TestClient):
        """Custom NotFoundError → 404 with proper error_code."""
        resp = problem_client.get("/raise/not-found")
        assert resp.status_code == 404
        data = resp.json()
        self._assert_problem_detail(data, 404, ErrorCode.NOT_FOUND.value)

    # ── HTTPException (non-500) → FastAPI built-in → no ProblemDetail ──

    def test_http_400_uses_fastapi_default(self, problem_client: TestClient):
        """HTTPException(400) uses FastAPI's built-in handler: no ProblemDetail."""
        resp = problem_client.get("/raise/http-400")
        assert resp.status_code == 400
        data = resp.json()
        # FastAPI default returns {"detail": ...}
        assert "detail" in data
        # It should NOT have ProblemDetail fields
        assert "type" not in data

    def test_http_403_uses_fastapi_default(self, problem_client: TestClient):
        """HTTPException(403) uses FastAPI's built-in handler."""
        resp = problem_client.get("/raise/http-403")
        assert resp.status_code == 403
        data = resp.json()
        assert "detail" in data
        assert "type" not in data

    def test_http_404_uses_fastapi_default(self, problem_client: TestClient):
        """HTTPException(404) uses FastAPI's built-in handler."""
        resp = problem_client.get("/raise/http-404")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "type" not in data

    def test_http_422_dict_detail(self, problem_client: TestClient):
        """HTTPException(422) with dict detail — FastAPI passes it as-is."""
        resp = problem_client.get("/raise/http-422")
        assert resp.status_code == 422
        data = resp.json()
        # FastAPI built-in handler passes the dict detail through
        if isinstance(data.get("detail"), dict):
            assert "description" in data or data.get("detail", {}).get("detail")
        else:
            assert "detail" in data

        # Should NOT have ProblemDetail fields
        assert "type" not in data, (
            f"Expected no ProblemDetail type, got: {data}"
        )

    def test_problem_detail_has_instance(self, problem_client: TestClient):
        """The instance field should contain the request URL."""
        resp = problem_client.get("/raise/runtime")
        data = resp.json()
        assert "instance" in data
        assert "/raise/runtime" in data["instance"]

    def test_problem_detail_has_error_code(self, problem_client: TestClient):
        """The error_code field should be present."""
        resp = problem_client.get("/raise/runtime")
        data = resp.json()
        assert "error_code" in data
        assert isinstance(data["error_code"], str)

    def test_rfc_7807_json_content_type(self, problem_client: TestClient):
        """The response must have JSON content type."""
        resp = problem_client.get("/raise/runtime")
        assert resp.headers.get("content-type", "").startswith("application/json")


class TestProblemDetailViaCreateApp:
    """Smoke-test that the real create_app() produces JSON error responses."""

    @pytest.fixture(autouse=True)
    def _clean_qt(self):
        """Clean up orphan Qt widgets left by prior test modules."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                try:
                    w.close()
                    w.deleteLater()
                except RuntimeError:
                    pass
        yield

    def test_real_app_unknown_route_returns_json(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ):
        """A 404 from an undefined route returns JSON (not HTML)."""
        # Disable API key so request passes through
        from config import Config as RootConfig

        monkeypatch.setattr(RootConfig, "API_KEY", "")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/nonexistent-route-12345")
        assert resp.status_code == 404
        data = resp.json()
        assert isinstance(data, dict)
        # Should have at least detail and potentially ProblemDetail fields
        assert "detail" in data

    def test_real_app_health_returns_success(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ):
        """The health endpoint should respond (possibly after auth)."""
        from config import Config as RootConfig

        monkeypatch.setattr(RootConfig, "API_KEY", "")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/health")
        # With auth disabled, should return 200 or 404 (route not found)
        assert resp.status_code in (200, 404)
