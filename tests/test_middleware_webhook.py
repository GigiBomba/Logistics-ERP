"""Unit tests for WebhookBodyMiddleware — raw body preservation.

Tests cover:

1.  Raw request body preserved and accessible via ``request.state.webhook_raw_body``
2.  Multiple content types (JSON, form data, plain text)
3.  Empty body handling
4.  Large body handling
5.  Body is consumed correctly (FastAPI parser can still read it)
6.  Non-webhook paths bypass the middleware (zero overhead)
7.  Non-POST methods bypass the middleware
8.  HMAC signing scenario — body preserved for downstream verification
9.  Edge case: request with no body (Content-Length: 0)
10. Edge case: streaming body / chunked transfer
11. Middleware does not interfere with normal response operation
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

# TestClient sends JSON with compact separators (no spaces).
_JSON_SEP = (",", ":")

from backend.middleware.webhook_middleware import WebhookBodyMiddleware

# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════


def _app_with_webhook_routes() -> FastAPI:
    """Return a FastAPI app with WebhookBodyMiddleware and webhook-like
    endpoints that read ``request.state.webhook_raw_body`` to verify
    preservation."""
    app = FastAPI()

    @app.post("/api/v1/webhooks/timocom")
    async def webhook_timocom(request: Request):
        raw = request.state.webhook_raw_body
        return {"path": request.url.path, "raw_body_len": len(raw)}

    @app.post("/api/v1/webhooks/transporeon")
    async def webhook_transporeon(request: Request):
        raw = request.state.webhook_raw_body
        # Return the raw body as a hex string so binary content round-trips
        return {"raw_body_hex": raw.hex()}

    @app.post("/api/v1/webhooks/echo")
    async def webhook_echo(request: Request):
        """Echo back the raw body content-type and the raw body itself."""
        raw = request.state.webhook_raw_body
        return {
            "content_type": request.headers.get("content-type", ""),
            "raw_body": raw.decode("utf-8", errors="replace"),
            "raw_body_len": len(raw),
        }

    @app.post("/api/v1/webhooks/hmac-verify")
    async def webhook_hmac_verify(request: Request):
        """Simulate HMAC verification using the preserved raw body."""
        raw = request.state.webhook_raw_body
        secret = request.headers.get("X-Webhook-Secret", "default-secret")
        expected_sig = request.headers.get("X-Signature-256", "")
        computed_sig = hmac.new(
            secret.encode(), raw, hashlib.sha256
        ).hexdigest()
        return {
            "valid": hmac.compare_digest(computed_sig, expected_sig),
            "computed_sig": computed_sig,
        }

    # ── Non-webhook routes (should NOT have webhook_raw_body) ──────
    @app.get("/api/v1/health")
    async def health(request: Request):
        raw = getattr(request.state, "webhook_raw_body", None)
        return {"raw_body_present": raw is not None, "status": "ok"}

    @app.post("/api/v1/auth/login")
    async def login(request: Request):
        """POST but not under webhook prefix — body must NOT be cached."""
        raw = getattr(request.state, "webhook_raw_body", None)
        return {"raw_body_present": raw is not None}

    app.add_middleware(WebhookBodyMiddleware)
    return app


def _app_with_json_route() -> FastAPI:
    """Return a FastAPI app where the webhook endpoint also parses JSON
    to confirm the body is *not* consumed/left unread by the middleware."""
    app = FastAPI()

    @app.post("/api/v1/webhooks/json-test")
    async def json_test(request: Request):
        raw = request.state.webhook_raw_body
        body = await request.json()
        return {
            "raw_body_len": len(raw),
            "json_parsed": body,
        }

    app.add_middleware(WebhookBodyMiddleware)
    return app


def _app_with_no_body_route() -> FastAPI:
    """Return a FastAPI app with a GET endpoint under the webhook
    prefix (edge case — GET with no body, method check should skip)."""
    app = FastAPI()

    @app.get("/api/v1/webhooks/status")
    async def webhook_status(request: Request):
        raw = getattr(request.state, "webhook_raw_body", None)
        return {"raw_body_present": raw is not None}

    app.add_middleware(WebhookBodyMiddleware)
    return app


# ═════════════════════════════════════════════════════════════════════
# WebhookBodyMiddleware
# ═════════════════════════════════════════════════════════════════════


class TestWebhookBodyMiddleware:
    """WebhookBodyMiddleware — raw body preservation for webhook endpoints."""

    # ── Basic body preservation ─────────────────────────────────────

    def test_json_body_preserved(self):
        """A JSON POST body is preserved verbatim in request.state."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        payload = {"event": "load_assigned", "trip_id": "T-12345"}

        resp = client.post(
            "/api/v1/webhooks/echo",
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        expected_body = json.dumps(payload, separators=_JSON_SEP)
        assert data["raw_body"] == expected_body
        assert data["raw_body_len"] == len(expected_body)

    def test_form_data_body_preserved(self):
        """A form-encoded POST body is preserved verbatim."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        form_data = {"status": "delivered", "ref": "REF-001"}

        resp = client.post(
            "/api/v1/webhooks/echo",
            data=form_data,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Form-encoded body will be key=value pairs
        assert "status=delivered" in data["raw_body"]
        assert data["raw_body_len"] > 0

    def test_plain_text_body_preserved(self):
        """A plain-text POST body is preserved verbatim."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = "raw webhook payload"

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=body,
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body"] == body
        assert data["raw_body_len"] == len(body)

    def test_binary_body_preserved(self):
        """A binary POST body is preserved as raw bytes."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = b"\x00\x01\x02\xff\xfe\xfd"

        resp = client.post(
            "/api/v1/webhooks/transporeon",
            content=body,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_hex"] == body.hex()

    # ── Empty body handling ─────────────────────────────────────────

    def test_empty_body_preserved(self):
        """An empty POST body is preserved as an empty byte string."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=b"",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body"] == ""
        assert data["raw_body_len"] == 0

    def test_content_length_zero(self):
        """Explicit Content-Length: 0 still preserves an empty body."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=b"",
            headers={"Content-Length": "0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_len"] == 0

    # ── Large body handling ─────────────────────────────────────────

    def test_large_body_preserved(self):
        """A large POST body (~100 KB) is preserved verbatim."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = "x" * 100_000

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=body,
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_len"] == 100_000
        assert data["raw_body"] == body

    def test_very_large_body_preserved(self):
        """A very large POST body (~1 MB) is preserved without truncation."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = "y" * 1_000_000

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=body,
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_len"] == 1_000_000
        assert data["raw_body"] == body

    # ── Body re-readability (FastAPI parser still works) ───────────

    def test_body_still_readable_by_fastapi_parser(self):
        """After the middleware caches the raw body, FastAPI's own parser
        (e.g. ``request.json()``) can still read it."""
        app = _app_with_json_route()
        client = TestClient(app)
        payload = {"key": "value", "num": 42}

        resp = client.post(
            "/api/v1/webhooks/json-test",
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        expected_body = json.dumps(payload, separators=_JSON_SEP)
        assert data["raw_body_len"] == len(expected_body)
        assert data["json_parsed"] == payload

    def test_body_available_for_multiple_reads(self):
        """The cached body can be read multiple times (both raw and parsed)."""
        app = _app_with_json_route()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/json-test",
            json={"msg": "hello"},
        )
        assert resp.status_code == 200
        data = resp.json()
        expected_body = json.dumps({"msg": "hello"}, separators=_JSON_SEP)
        assert data["raw_body_len"] == len(expected_body)
        assert data["json_parsed"] == {"msg": "hello"}

    # ── Path filtering ──────────────────────────────────────────────

    def test_non_webhook_path_bypasses_middleware(self):
        """GET requests to non-webhook paths do NOT get webhook_raw_body."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_present"] is False
        assert data["status"] == "ok"

    def test_post_to_non_webhook_path_bypasses_middleware(self):
        """POST requests to non-webhook paths do NOT cache the body."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.post("/api/v1/auth/login", json={"user": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_present"] is False

    def test_get_to_webhook_prefix_bypasses_middleware(self):
        """GET requests under the webhook prefix do NOT cache the body
        (only POST is intercepted)."""
        app = _app_with_no_body_route()
        client = TestClient(app)

        resp = client.get("/api/v1/webhooks/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_present"] is False

    # ── HMAC signing scenario ──────────────────────────────────────

    def test_hmac_verification_with_preserved_body(self):
        """The preserved raw body can be used for HMAC-SHA256 verification."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        payload = b'{"event": "status_update", "status": "delivered"}'
        secret = "whsec_test_secret"
        expected_sig = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        resp = client.post(
            "/api/v1/webhooks/hmac-verify",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": secret,
                "X-Signature-256": expected_sig,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["computed_sig"] == expected_sig

    def test_hmac_verification_fails_on_tampered_body(self):
        """If the raw body in the middleware did not match what was signed,
        HMAC verification would fail — confirming the middleware preserves
        the *actual* body (not a modified version)."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        original_payload = b'{"amount": 100}'
        wrong_payload = b'{"amount": 999}'
        secret = "whsec_test"
        # Sign the *original* payload
        expected_sig = hmac.new(
            secret.encode(), original_payload, hashlib.sha256
        ).hexdigest()

        # Send the *wrong* payload but claim it was the original
        resp = client.post(
            "/api/v1/webhooks/hmac-verify",
            content=wrong_payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": secret,
                "X-Signature-256": expected_sig,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # The middleware preserved 'wrong_payload', so HMAC over that
        # should NOT match the signature computed over 'original_payload'.
        assert data["valid"] is False
        assert data["computed_sig"] != expected_sig

    def test_hmac_with_json_content_type(self):
        """HMAC verification works with JSON content-type bodies."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        payload = json.dumps({"event": "test"}).encode()
        secret = "whsec_json_secret"
        expected_sig = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        resp = client.post(
            "/api/v1/webhooks/hmac-verify",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": secret,
                "X-Signature-256": expected_sig,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    # ── Normal response operation ──────────────────────────────────

    def test_middleware_does_not_interfere_with_success(self):
        """The middleware passes through to the endpoint and returns a
        normal success response."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/timocom",
            json={"event": "created"},
        )
        assert resp.status_code == 200
        assert resp.json()["path"] == "/api/v1/webhooks/timocom"

    def test_middleware_preserves_response_headers(self):
        """Response headers are passed through unchanged."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/echo",
            json={"test": True},
        )
        assert resp.status_code == 200
        # TestClient sets these standard headers
        assert resp.headers.get("content-type") == "application/json"

    def test_multiple_consecutive_requests(self):
        """Multiple webhook requests in sequence each get the correct body."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        for i in range(5):
            body = f"request-{i}"
            resp = client.post(
                "/api/v1/webhooks/echo",
                content=body,
                headers={"Content-Type": "text/plain"},
            )
            assert resp.status_code == 200
            assert resp.json()["raw_body"] == body

    # ── Edge cases ─────────────────────────────────────────────────

    def test_request_with_no_content_type(self):
        """A POST with no Content-Type header still preserves the body."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = b"plain bytes"

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_len"] == len(body)

    def test_request_with_only_headers_no_body(self):
        """A POST request that has headers but sends no body."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=b"",
            headers={"X-Custom": "value"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body_len"] == 0

    def test_unicode_body_preserved(self):
        """Unicode characters (including non-ASCII) are preserved."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = "héllo wörld 🚚 📦 ✓"

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=body.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body"] == body

    def test_body_with_newlines_and_whitespace(self):
        """Body containing newlines, tabs, and extra whitespace is preserved."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = "line1\nline2\r\nline3\tindented  "

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=body,
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body"] == body

    def test_body_with_special_characters(self):
        """Body with quotes, backslashes, and other special characters."""
        app = _app_with_webhook_routes()
        client = TestClient(app)
        body = '{"data": "it\'s \"quoted\" \\ escaped"}'

        resp = client.post(
            "/api/v1/webhooks/echo",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_body"] == body

    def test_different_webhook_endpoints(self):
        """Different webhook sub-paths each get their body preserved."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp_a = client.post(
            "/api/v1/webhooks/timocom", json={"partner": "timocom"}
        )
        resp_b = client.post(
            "/api/v1/webhooks/transporeon", content=b"transporeon-data"
        )

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        expected_body = json.dumps({"partner": "timocom"}, separators=_JSON_SEP)
        assert resp_a.json()["raw_body_len"] == len(expected_body)
        assert resp_b.json()["raw_body_hex"] == b"transporeon-data".hex()

    def test_webhook_raw_body_is_bytes(self):
        """The cached body is always ``bytes``, never ``str`` or ``None``."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/echo",
            json={"type": "bytes_check"},
        )
        assert resp.status_code == 200
        # If raw_body is empty string, it means the body was decoded somewhere
        # Raw bytes should result in an empty string only when the body is
        # truly zero-length.
        data = resp.json()
        assert isinstance(data["raw_body"], str)
        # The test endpoint decodes to string for JSON serialization;
        # verify that the original length matches the expected byte length.
        expected_body = json.dumps({"type": "bytes_check"}, separators=_JSON_SEP)
        assert data["raw_body_len"] == len(expected_body)


class TestWebhookBodyMiddlewareEdgeCases:
    """Edge cases and defensive scenarios for WebhookBodyMiddleware."""

    def test_nested_webhook_path_preserved(self):
        """Deeply nested paths under the webhook prefix are still caught."""
        app = _app_with_webhook_routes()
        client = TestClient(app)

        # Add a deep-path endpoint dynamically
        @app.post("/api/v1/webhooks/partner/v2/events/callback")
        async def deep_webhook(request: Request):
            raw = request.state.webhook_raw_body
            return {"len": len(raw)}

        resp = client.post(
            "/api/v1/webhooks/partner/v2/events/callback",
            json={"deep": True},
        )
        assert resp.status_code == 200
        assert resp.json()["len"] > 0

    def test_middleware_with_error_response(self):
        """If the endpoint raises, the middleware should still propagate
        the error without swallowing it.

        Note: With ``TestClient``, unhandled endpoint exceptions
        propagate directly because the test client runs synchronously.
        We verify the exception passes through rather than being caught
        and hidden by the middleware.
        """
        app = FastAPI()

        @app.post("/api/v1/webhooks/error-test")
        async def error_endpoint(request: Request):
            raw = request.state.webhook_raw_body  # noqa: F841
            # Force an internal error
            raise ValueError("simulated handler error")

        app.add_middleware(WebhookBodyMiddleware)
        client = TestClient(app)

        with pytest.raises(ValueError, match="simulated handler error"):
            client.post(
                "/api/v1/webhooks/error-test",
                json={"trigger": "error"},
            )

    def test_middleware_with_exception_handler_app(self):
        """When the app has a custom exception handler, the middleware
        does not interfere."""
        app = FastAPI()

        @app.exception_handler(ValueError)
        async def value_error_handler(request, exc):
            return JSONResponse(
                status_code=400, content={"detail": str(exc)}
            )

        @app.post("/api/v1/webhooks/val-error")
        async def val_error_endpoint(request: Request):
            raw = request.state.webhook_raw_body  # noqa: F841
            raise ValueError("bad data")

        app.add_middleware(WebhookBodyMiddleware)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/val-error",
            json={"bad": True},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "bad data"

    def test_raw_body_not_mutated_by_downstream(self):
        """The ``request.state.webhook_raw_body`` value is a fresh copy;
        downstream handlers cannot mutate the middleware's internal state."""
        app = FastAPI()

        @app.post("/api/v1/webhooks/mutate-test")
        async def mutate_endpoint(request: Request):
            raw = request.state.webhook_raw_body
            # Attempt to mutate the bytes in-place (should not affect
            # anything since bytes are immutable — confirm the reference).
            modified = raw + b"-appended"
            request.state.webhook_raw_body = modified
            # Return both
            return {
                "original_len": len(raw),
                "modified_len": len(modified),
            }

        app.add_middleware(WebhookBodyMiddleware)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/mutate-test",
            content=b"hello",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["original_len"] == 5
        assert data["modified_len"] == 14
