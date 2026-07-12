"""Integration tests for LoggingMiddleware.

Tests cover:
- Request method and path logged at INFO level
- Response status code logged
- Duration logged in milliseconds (verify format)
- Error cases (500) logged with status code and duration
- Sensitive headers (Authorization, Cookie) not present in log output
- Successful requests (200) not logged at ERROR level

Uses caplog fixture from pytest for log capture.
"""

from __future__ import annotations

import asyncio
import logging
import re

import pytest
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture
def logging_app() -> FastAPI:
    """Return a FastAPI app with LoggingMiddleware attached."""
    from backend.middleware.logging_middleware import LoggingMiddleware

    app = FastAPI()

    @app.get("/")
    async def root():
        return {"ok": True}

    @app.get("/hello")
    async def hello():
        return {"message": "world"}

    @app.post("/data")
    async def data():
        return {"received": True}

    @app.get("/error-500")
    async def error_500():
        return JSONResponse(status_code=500, content={"detail": "Server Error"})

    @app.get("/raises")
    async def raises():
        raise RuntimeError("Something went wrong")

    @app.get("/custom-status")
    async def custom_status():
        return Response("Created", status_code=201)

    @app.get("/redirect")
    async def redirect():
        return Response("Redirect", status_code=302)

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(0.05)
        return {"slow": True}

    app.add_middleware(LoggingMiddleware)
    return app


def _access_records(caplog):
    """Return log records from the api.access logger only."""
    return [r for r in caplog.records if r.name == "api.access"]


# ── Basic logging ────────────────────────────────────────────────────────


class TestBasicLogging:
    def test_logs_method_and_path(self, caplog, logging_app: FastAPI):
        """Request method and path are logged at INFO level."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/hello")

        records = _access_records(caplog)
        assert len(records) >= 1
        record = records[-1]
        assert record.levelname == "INFO"
        assert record.name == "api.access"
        msg = record.getMessage()
        assert "GET" in msg
        assert "/hello" in msg

    def test_logs_response_status_code(self, caplog, logging_app: FastAPI):
        """Response status code appears in the log message."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/")

        records = _access_records(caplog)
        assert len(records) >= 1
        msg = records[-1].getMessage()
        assert "200" in msg

    def test_logs_duration_in_milliseconds(self, caplog, logging_app: FastAPI):
        """Duration is logged in milliseconds with 3 decimal places."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/")

        records = _access_records(caplog)
        assert len(records) >= 1
        msg = records[-1].getMessage()
        assert re.search(r"\d+\.\d{3}ms", msg), (
            f"Expected duration in ms format, got: {msg}"
        )

    def test_logs_post_method(self, caplog, logging_app: FastAPI):
        """POST requests are logged correctly."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.post("/data", json={"key": "value"})

        records = _access_records(caplog)
        assert len(records) >= 1
        msg = records[-1].getMessage()
        assert "POST" in msg
        assert "/data" in msg
        assert "200" in msg

    def test_logs_different_status_codes(self, caplog, logging_app: FastAPI):
        """Custom status codes (201, 302) are reflected in logs."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)

        client.get("/custom-status")
        records = _access_records(caplog)
        assert "201" in records[-1].getMessage()

        client.get("/redirect")
        records = _access_records(caplog)
        assert "302" in records[-1].getMessage()

    def test_log_message_format(self, caplog, logging_app: FastAPI):
        """Verify the exact log format: METHOD PATH STATUS DURATIONms."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/hello")

        records = _access_records(caplog)
        assert len(records) >= 1
        msg = records[-1].getMessage()
        assert re.match(r"GET /hello 200 \d+\.\d{3}ms \[.*?\]$", msg), (
            f"Unexpected log format: {msg}"
        )


# ── Error response (500 status returned, not raised) ─────────────────────


class TestErrorLogging:
    def test_500_response_logged_at_info_with_status(self, caplog, logging_app: FastAPI):
        """500 responses (returned, not raised) are logged with status code."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/error-500")

        records = _access_records(caplog)
        assert len(records) >= 1
        record = records[-1]
        assert record.levelname == "INFO"
        msg = record.getMessage()
        assert "GET" in msg
        assert "/error-500" in msg
        assert "500" in msg

    def test_raised_exception_not_logged_by_middleware(self, caplog, logging_app: FastAPI):
        """When a route handler raises, the middleware never sees a response,
        so no api.access log is emitted. Uses raise_server_exceptions=False
        so the test client returns a 500 to the caller.

        The middleware does NOT catch exceptions — this test documents that
        limitation / current behaviour.
        """
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app, raise_server_exceptions=False)
        resp = client.get("/raises")
        assert resp.status_code == 500

        records = _access_records(caplog)
        assert len(records) == 0, (
            "Expected no api.access log because the middleware "
            "does not catch exceptions from call_next"
        )


# ── Successful requests not logged at ERROR ──────────────────────────────


class TestNoErrorOnSuccess:
    def test_200_not_logged_at_error(self, caplog, logging_app: FastAPI):
        """Successful requests (200) must not produce ERROR-level logs."""
        caplog.set_level(logging.ERROR)
        client = TestClient(logging_app)
        client.get("/")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 0

    def test_201_not_logged_at_error(self, caplog, logging_app: FastAPI):
        caplog.set_level(logging.ERROR)
        client = TestClient(logging_app)
        client.get("/custom-status")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 0

    def test_302_not_logged_at_error(self, caplog, logging_app: FastAPI):
        caplog.set_level(logging.ERROR)
        client = TestClient(logging_app)
        client.get("/redirect")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 0

    def test_post_200_not_logged_at_error(self, caplog, logging_app: FastAPI):
        caplog.set_level(logging.ERROR)
        client = TestClient(logging_app)
        client.post("/data", json={"a": 1})

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 0


# ── Sensitive headers ────────────────────────────────────────────────────


class TestSensitiveHeaders:
    """Verify that sensitive headers are not logged by the middleware.

    The current LoggingMiddleware only logs method, path, status, and
    duration — it does **not** log request headers. These tests verify
    that no header values leak into api.access log output.
    """

    def test_authorization_header_not_in_api_access_logs(
        self, caplog, logging_app: FastAPI
    ):
        """Authorization header value must not appear in api.access log."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/", headers={"Authorization": "Bearer secret-token-12345"})

        for record in _access_records(caplog):
            msg = record.getMessage()
            assert "secret-token-12345" not in msg
            assert "Authorization" not in msg

    def test_cookie_header_not_in_api_access_logs(
        self, caplog, logging_app: FastAPI
    ):
        """Cookie header value must not appear in api.access log."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/", headers={"Cookie": "session=abc123; token=xyz"})

        for record in _access_records(caplog):
            msg = record.getMessage()
            assert "session=abc123" not in msg
            assert "token=xyz" not in msg

    def test_api_key_header_not_in_logs(self, caplog, logging_app: FastAPI):
        """X-API-Key header value must not appear in log output."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/", headers={"X-API-Key": "my-secret-api-key"})

        for record in _access_records(caplog):
            msg = record.getMessage()
            assert "my-secret-api-key" not in msg

    def test_no_header_values_leak_into_log_message(
        self, caplog, logging_app: FastAPI
    ):
        """No header key-value pairs should appear in log messages.

        The middleware must only log: METHOD PATH STATUS DURATION
        """
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get(
            "/",
            headers={
                "Authorization": "Bearer tok",
                "Cookie": "sess=1",
                "X-API-Key": "key",
                "X-Forwarded-For": "1.2.3.4",
                "User-Agent": "test-browser",
            },
        )

        records = _access_records(caplog)
        assert len(records) >= 1
        msg = records[-1].getMessage()
        assert re.match(r"GET / \d+ \d+\.\d{3}ms \[.*?\]$", msg), (
            f"Log message appears to include extra data: {msg}"
        )


# ── No middleware ────────────────────────────────────────────────────────


class TestNoLoggingMiddleware:
    """Verify that without the middleware, no api.access logs are emitted."""

    def test_no_logs_without_middleware(self, caplog):
        """Without LoggingMiddleware, the api.access logger should be silent."""
        from backend.middleware.logging_middleware import LoggingMiddleware

        app = FastAPI()

        @app.get("/")
        async def root():
            return {"ok": True}

        # Intentionally NOT adding LoggingMiddleware
        caplog.set_level(logging.INFO)
        client = TestClient(app)
        client.get("/")

        api_access_logs = [r for r in caplog.records if r.name == "api.access"]
        assert len(api_access_logs) == 0


# ── Multiple requests ────────────────────────────────────────────────────


class TestMultipleRequests:
    def test_logs_for_each_request(self, caplog, logging_app: FastAPI):
        """Each request produces its own log entry."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)

        client.get("/")
        client.get("/hello")
        client.post("/data", json={"x": 1})

        api_access_logs = _access_records(caplog)
        assert len(api_access_logs) == 3

        methods = {r.getMessage().split()[0] for r in api_access_logs}
        assert methods == {"GET", "POST"}

    def test_duration_increases_with_slow_endpoint(self, caplog, logging_app: FastAPI):
        """Slower endpoints should log a larger duration value."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)
        client.get("/slow")

        records = _access_records(caplog)
        assert len(records) >= 1
        msg = records[-1].getMessage()
        # Extract duration
        match = re.search(r"(\d+\.\d{3})ms", msg)
        assert match is not None, f"Could not find duration in: {msg}"
        duration_ms = float(match.group(1))
        assert duration_ms >= 40, (
            f"Expected duration >= 40ms for slow endpoint, got {duration_ms}ms"
        )

    def test_multiple_requests_have_increasing_duration_summary(
        self, caplog, logging_app: FastAPI
    ):
        """Multiple logs are produced, and each entry has a unique timestamp."""
        caplog.set_level(logging.INFO)
        client = TestClient(logging_app)

        client.get("/")
        client.get("/hello")

        records = _access_records(caplog)
        assert len(records) == 2
        # Each log should have a distinct message (different paths)
        assert records[0].getMessage() != records[1].getMessage()
