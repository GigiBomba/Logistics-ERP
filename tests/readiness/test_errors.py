"""Tests for the RFC 7807 error handling system.

Covers ErrorCode enum, ProblemDetail dataclass, the exception-to-error mapping,
the custom exception hierarchy, and the global FastAPI exception handler.
"""
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.errors import (
    ErrorCode,
    ProblemDetail,
    get_error_code_for_exception,
    HTTP_STATUS_TO_ERROR,
)
from services.exceptions import (
    OperionError,
    ValidationError,
    NotFoundError,
    PermissionDeniedError,
    ExternalServiceError,
    TripError,
    InvoiceError,
    DocumentError,
    OCRError,
    ExportError,
    RouteError,
    DispatchError,
)


# ===================================================================
# ErrorCode enum
# ===================================================================

class TestErrorCode:
    """5 tests for the ErrorCode str enum."""

    def test_all_error_codes_have_unique_values(self):
        """No two enum members share the same error code string."""
        values = [e.value for e in ErrorCode]
        assert len(values) == len(set(values)), f"Found {len(values) - len(set(values))} duplicate(s)"

    def test_error_codes_are_categorized(self):
        """Codes follow naming convention with recognised category prefixes."""
        known_categories = ("auth/", "resource/", "business/", "integration/")
        for code in ErrorCode:
            val = code.value
            if "/" not in val:
                # General-purpose codes have no prefix
                continue
            assert any(val.startswith(prefix) for prefix in known_categories), (
                f"{code.name}={val!r} does not start with a recognised category prefix "
                f"({known_categories})"
            )

    def test_error_code_from_string(self):
        """ErrorCode can be constructed from its string value."""
        assert ErrorCode("auth/invalid-credentials") is ErrorCode.INVALID_CREDENTIALS
        assert ErrorCode("resource/trip-not-found") is ErrorCode.TRIP_NOT_FOUND
        assert ErrorCode("business/vehicle-unavailable") is ErrorCode.VEHICLE_UNAVAILABLE
        assert ErrorCode("integration/external-api-error") is ErrorCode.EXTERNAL_API_ERROR
        assert ErrorCode("not-found") is ErrorCode.NOT_FOUND
        assert ErrorCode("unauthorized") is ErrorCode.UNAUTHORIZED

    def test_error_code_to_status(self):
        """get_error_code_for_exception returns correct (ErrorCode, status) pairs."""
        assert get_error_code_for_exception(NotFoundError()) == (ErrorCode.NOT_FOUND, 404)
        assert get_error_code_for_exception(ValidationError()) == (ErrorCode.VALIDATION_ERROR, 422)
        assert get_error_code_for_exception(PermissionDeniedError()) == (ErrorCode.FORBIDDEN, 403)
        assert get_error_code_for_exception(ExternalServiceError()) == (ErrorCode.EXTERNAL_API_ERROR, 502)
        assert get_error_code_for_exception(TripError()) == (ErrorCode.INTERNAL_ERROR, 500)
        assert get_error_code_for_exception(OperionError()) == (ErrorCode.INTERNAL_ERROR, 500)

    def test_http_status_to_error_code(self):
        """HTTP status codes map to the expected ErrorCode values."""
        assert HTTP_STATUS_TO_ERROR[400] is ErrorCode.VALIDATION_ERROR
        assert HTTP_STATUS_TO_ERROR[401] is ErrorCode.UNAUTHORIZED
        assert HTTP_STATUS_TO_ERROR[403] is ErrorCode.FORBIDDEN
        assert HTTP_STATUS_TO_ERROR[404] is ErrorCode.NOT_FOUND
        assert HTTP_STATUS_TO_ERROR[405] is ErrorCode.METHOD_NOT_ALLOWED
        assert HTTP_STATUS_TO_ERROR[409] is ErrorCode.DUPLICATE_RESOURCE
        assert HTTP_STATUS_TO_ERROR[422] is ErrorCode.VALIDATION_ERROR
        assert HTTP_STATUS_TO_ERROR[429] is ErrorCode.RATE_LIMITED
        assert HTTP_STATUS_TO_ERROR[500] is ErrorCode.INTERNAL_ERROR
        assert HTTP_STATUS_TO_ERROR[502] is ErrorCode.EXTERNAL_API_ERROR
        assert HTTP_STATUS_TO_ERROR[503] is ErrorCode.SERVICE_UNAVAILABLE


# ===================================================================
# ProblemDetail
# ===================================================================

class TestProblemDetail:
    """4 tests for the ProblemDetail dataclass."""

    def test_problem_detail_minimal(self):
        """Can create a ProblemDetail with only status and title."""
        pd = ProblemDetail(status=400, title="Bad Request")
        assert pd.status == 400
        assert pd.title == "Bad Request"
        assert pd.detail == ""
        assert pd.instance == ""
        assert pd.error_code == ""
        assert pd.errors == []

    def test_problem_detail_full(self):
        """All ProblemDetail fields are populated correctly."""
        pd = ProblemDetail(
            type="https://api.operionerp.xyz/errors/validation-error",
            title="Validation Error",
            status=422,
            detail="The 'email' field is required.",
            instance="/api/v1/clients",
            error_code="validation-error",
            errors=[{"field": "email", "message": "required"}],
        )
        assert pd.type == "https://api.operionerp.xyz/errors/validation-error"
        assert pd.title == "Validation Error"
        assert pd.status == 422
        assert pd.detail == "The 'email' field is required."
        assert pd.instance == "/api/v1/clients"
        assert pd.error_code == "validation-error"
        assert pd.errors == [{"field": "email", "message": "required"}]

    def test_problem_detail_to_dict(self):
        """Serialisation produces a valid RFC 7807 JSON dictionary."""
        # -- Full --
        pd = ProblemDetail(
            type="https://api.operionerp.xyz/errors/validation-error",
            title="Validation Error",
            status=422,
            detail="Invalid input",
            instance="/api/v1/clients",
            error_code="validation-error",
            errors=[{"field": "email", "message": "required"}],
        )
        d = pd.to_dict()
        assert d["type"] == "https://api.operionerp.xyz/errors/validation-error"
        assert d["title"] == "Validation Error"
        assert d["status"] == 422
        assert d["detail"] == "Invalid input"
        assert d["instance"] == "/api/v1/clients"
        assert d["error_code"] == "validation-error"
        assert d["errors"] == [{"field": "email", "message": "required"}]

        # -- Minimal (no error_code, no instance, no errors) --
        pd2 = ProblemDetail(status=500, title="Server Error")
        d2 = pd2.to_dict()
        assert d2["type"] == "about:blank"
        assert d2["title"] == "Server Error"
        assert d2["status"] == 500
        assert "instance" not in d2
        assert "error_code" not in d2
        assert "errors" not in d2

        # -- error_code set but type left as default "about:blank" --
        # The default type ("about:blank") is truthy, so to_dict() uses it as-is.
        pd3 = ProblemDetail(status=404, title="Not Found", error_code="not-found")
        d3 = pd3.to_dict()
        assert d3["type"] == "about:blank"
        assert d3["error_code"] == "not-found"

    def test_problem_detail_error_code_in_type(self):
        """When error_code is set AND type is empty, the type URI includes it."""
        # With explicit empty type, error_code drives the URI
        pd = ProblemDetail(status=404, title="Not Found", error_code="not-found", type="")
        d = pd.to_dict()
        assert ErrorCode.NOT_FOUND.value in d["type"]
        assert "https://api.operionerp.xyz/errors/not-found" == d["type"]
        assert d["error_code"] == "not-found"

        # Different error code
        pd2 = ProblemDetail(status=403, title="Forbidden", error_code="forbidden", type="")
        d2 = pd2.to_dict()
        assert ErrorCode.FORBIDDEN.value in d2["type"]
        assert d2["error_code"] == "forbidden"

        # When type is explicitly provided, it takes precedence
        pd3 = ProblemDetail(
            status=404, title="Not Found",
            type="https://custom.example/errors/my-error",
            error_code="not-found",
        )
        d3 = pd3.to_dict()
        assert d3["type"] == "https://custom.example/errors/my-error"
        assert d3["error_code"] == "not-found"


# ===================================================================
# Exception hierarchy
# ===================================================================

class TestExceptionHierarchy:
    """3 tests for the Operion custom exception hierarchy."""

    def test_exception_inheritance(self):
        """All custom exceptions are subclasses of OperionError."""
        for exc_cls in (
            ValidationError,
            NotFoundError,
            PermissionDeniedError,
            ExternalServiceError,
            TripError,
            InvoiceError,
            DocumentError,
            OCRError,
            ExportError,
            RouteError,
            DispatchError,
        ):
            assert issubclass(exc_cls, OperionError), (
                f"{exc_cls.__name__} does not inherit from OperionError"
            )

    def test_exception_can_be_caught_by_parent(self):
        """A bare ``except OperionError`` catches any custom exception."""
        with pytest.raises(OperionError):
            raise TripError("trip scheduling failed")

        # Also works for other subclasses
        with pytest.raises(OperionError):
            raise ExternalServiceError("api timeout")

    def test_exception_messages(self):
        """Custom exceptions preserve the message string passed at construction."""
        msg = "Resource not found"
        exc = NotFoundError(msg)
        assert str(exc) == msg
        assert exc.args[0] == msg

        msg2 = "Invalid email format"
        exc2 = ValidationError(msg2)
        assert str(exc2) == msg2

        msg3 = "Insufficient permissions"
        exc3 = PermissionDeniedError(msg3)
        assert str(exc3) == msg3


# ===================================================================
# Global exception handler (via TestClient)
# ===================================================================

@pytest.fixture
def error_test_app():
    """Build a minimal FastAPI app that uses the same global exception handler
    as the production ``backend.main`` module, without pulling in middleware
    or route dependencies."""
    app = FastAPI()

    # ── Replicate the exception handler from backend.main ──────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):  # noqa: ANN001
        from backend.middleware.correlation_middleware import get_correlation_id  # noqa: PLC0415

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

        return JSONResponse(status_code=status, content=problem.to_dict())

    # ── Test endpoints that raise specific exceptions ──────────────
    @app.get("/raise/validation")
    async def _():
        raise ValidationError("Input validation failed")

    @app.get("/raise/not-found")
    async def _():
        raise NotFoundError("Resource not found")

    @app.get("/raise/permission")
    async def _():
        raise PermissionDeniedError("Insufficient permissions")

    @app.get("/raise/external")
    async def _():
        raise ExternalServiceError("External API call failed")

    @app.get("/raise/unknown")
    async def _():
        raise RuntimeError("Something unexpected happened")

    return app


@pytest.fixture
def client(error_test_app):
    """TestClient wired to the minimal error-handling app.

    ``raise_server_exceptions=False`` is required because Starlette's
    ``ServerErrorMiddleware`` re-raises the exception *after* the
    exception-handler response has been sent; without this flag the
    original exception would propagate through the test client and
    mask the response we want to assert on.
    """
    return TestClient(error_test_app, raise_server_exceptions=False)


class TestGlobalExceptionHandler:
    """5 tests verifying the FastAPI exception handler returns correct
    HTTP status codes and RFC 7807 bodies."""

    def test_validation_error_returns_422(self, client):
        resp = client.get("/raise/validation")
        assert resp.status_code == 422
        data = resp.json()
        assert data["status"] == 422
        assert data["error_code"] == ErrorCode.VALIDATION_ERROR.value
        assert ErrorCode.VALIDATION_ERROR.value in data["type"]
        assert data["title"] == "An error occurred"
        assert data["detail"] == "Input validation failed"

    def test_not_found_returns_404(self, client):
        resp = client.get("/raise/not-found")
        assert resp.status_code == 404
        data = resp.json()
        assert data["status"] == 404
        assert data["error_code"] == ErrorCode.NOT_FOUND.value
        assert ErrorCode.NOT_FOUND.value in data["type"]
        assert data["detail"] == "Resource not found"

    def test_permission_denied_returns_403(self, client):
        resp = client.get("/raise/permission")
        assert resp.status_code == 403
        data = resp.json()
        assert data["status"] == 403
        assert data["error_code"] == ErrorCode.FORBIDDEN.value
        assert ErrorCode.FORBIDDEN.value in data["type"]
        assert data["detail"] == "Insufficient permissions"

    def test_external_service_error_returns_502(self, client):
        resp = client.get("/raise/external")
        assert resp.status_code == 502
        data = resp.json()
        assert data["status"] == 502
        assert data["error_code"] == ErrorCode.EXTERNAL_API_ERROR.value
        assert ErrorCode.EXTERNAL_API_ERROR.value in data["type"]
        assert data["detail"] == "External API call failed"

    def test_unknown_exception_returns_500(self, client):
        resp = client.get("/raise/unknown")
        assert resp.status_code == 500
        data = resp.json()
        assert data["status"] == 500
        assert data["error_code"] == ErrorCode.INTERNAL_ERROR.value
        assert ErrorCode.INTERNAL_ERROR.value in data["type"]
        assert data["detail"] == "Something unexpected happened"
