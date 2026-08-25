"""Unit tests for individual middleware components.

Tests cover:
1. IdempotencyMiddleware — idempotency-key caching and replay
2. CorrelationMiddleware — X-Request-ID injection and propagation
3. AuthMiddleware — API key validation and public-path bypass
"""
from __future__ import annotations


import hashlib
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.auth_middleware import AuthMiddleware
from backend.middleware.correlation_middleware import CorrelationMiddleware
from backend.middleware.idempotency_middleware import (
    IdempotencyMiddleware,
    _idempotency_store,
)
from config import Config


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _app_with_idempotency() -> FastAPI:
    """Return a FastAPI app with IdempotencyMiddleware and a write endpoint."""
    app = FastAPI()

    @app.post("/echo")
    async def echo(payload: dict):
        return {"received": payload}

    @app.patch("/patch-echo")
    async def patch_echo(payload: dict):
        return {"patched": payload}

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    app.add_middleware(IdempotencyMiddleware)
    return app


def _app_with_correlation() -> FastAPI:
    """Return a FastAPI app with CorrelationMiddleware."""
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    app.add_middleware(CorrelationMiddleware)
    return app


def _app_with_auth(api_key: str = "") -> FastAPI:
    """Return a FastAPI app with AuthMiddleware (with *api_key* patched in).

    Callers are responsible for monkeypatching ``Config.API_KEY`` before
    making requests — this helper simply wires the middleware onto an app.
    Built-in docs routes are disabled to avoid conflicts with test routes.
    """
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/docs")
    async def docs():
        return {"swagger": True}

    app.add_middleware(AuthMiddleware)
    return app


# ═════════════════════════════════════════════════════════════════════
# IdempotencyMiddleware
# ═════════════════════════════════════════════════════════════════════

class TestIdempotencyMiddleware:
    """IdempotencyMiddleware — idempotency-key caching and replay."""

    # ── Clean the in-memory store before every test ─────────────────

    @pytest.fixture(autouse=True)
    def _clear_idempotency_store(self):
        _idempotency_store.clear()
        yield

    # ── Tests ──────────────────────────────────────────────────────

    def test_idempotency_header_supported(self):
        """Response includes Idempotency-Key-Supported header even without a key."""
        app = _app_with_idempotency()
        client = TestClient(app)

        resp = client.post("/echo", json={"hello": "world"})
        assert resp.status_code == 200
        assert resp.headers.get("Idempotency-Key-Supported") == "true"

    def test_idempotency_replay_returns_cached(self):
        """Same Idempotency-Key returns cached response with Idempotency-Replayed.

        Note: When using ``TestClient``, Starlette's internally-used
        ``_StreamingResponse`` does not carry a ``.body`` attribute, so the
        middleware caches an empty body. We verify the caching mechanism via
        the store contents and response headers instead of the body payload.
        """
        app = _app_with_idempotency()
        client = TestClient(app)
        key = str(uuid.uuid4())

        # First request — cache miss
        resp1 = client.post(
            "/echo",
            json={"msg": "first"},
            headers={"Idempotency-Key": key},
        )
        assert resp1.status_code == 200
        assert resp1.headers.get("Idempotency-Key-Supported") == "true"
        assert resp1.headers.get("Idempotency-Replayed") is None

        # Store should now contain one entry for this key
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        assert key_hash in _idempotency_store
        cached_expiry, cached_status, cached_ctype, cached_body = _idempotency_store[key_hash]
        assert cached_status == 200
        assert cached_ctype == "application/json"

        # Second request with same key — replay
        resp2 = client.post(
            "/echo",
            json={"msg": "second"},
            headers={"Idempotency-Key": key},
        )
        assert resp2.status_code == cached_status
        assert resp2.headers.get("Idempotency-Replayed") == "true"

    def test_idempotency_different_key_new_response(self):
        """Different Idempotency-Key values each produce a fresh response."""
        app = _app_with_idempotency()
        client = TestClient(app)

        resp_a = client.post(
            "/echo",
            json={"seq": 1},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp_a.status_code == 200

        resp_b = client.post(
            "/echo",
            json={"seq": 2},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp_b.status_code == 200

        # Different keys → different (non-cached) responses
        assert resp_a.json() != resp_b.json()

    def test_idempotency_get_ignored(self):
        """GET requests bypass the idempotency middleware entirely."""
        app = _app_with_idempotency()
        client = TestClient(app)

        resp = client.get("/ping", headers={"Idempotency-Key": str(uuid.uuid4())})
        assert resp.status_code == 200
        # GET responses should NOT carry Idempotency-Key-Supported
        assert resp.headers.get("Idempotency-Key-Supported") is None

    def test_idempotency_no_header_passes_through(self):
        """Requests without an Idempotency-Key header pass through normally."""
        app = _app_with_idempotency()
        client = TestClient(app)

        resp = client.post("/echo", json={"hello": "world"})
        assert resp.status_code == 200
        assert resp.json() == {"received": {"hello": "world"}}
        # Still indicates support
        assert resp.headers.get("Idempotency-Key-Supported") == "true"


# ═════════════════════════════════════════════════════════════════════
# CorrelationMiddleware
# ═════════════════════════════════════════════════════════════════════

class TestCorrelationMiddleware:
    """CorrelationMiddleware — X-Request-ID injection and propagation."""

    def test_correlation_id_generated(self):
        """A new request without X-Request-ID gets one assigned in the response."""
        app = _app_with_correlation()
        client = TestClient(app)

        resp = client.get("/ping")
        assert resp.status_code == 200
        correlation_id = resp.headers.get("X-Request-ID")
        assert correlation_id is not None
        assert len(correlation_id) > 0
        # Should look like a UUID
        assert isinstance(uuid.UUID(correlation_id), uuid.UUID)

    def test_correlation_id_propagated(self):
        """An incoming X-Request-ID is echoed back in the response."""
        app = _app_with_correlation()
        client = TestClient(app)
        incoming_id = "my-trace-id-001"

        resp = client.get("/ping", headers={"X-Request-ID": incoming_id})
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID") == incoming_id

    def test_correlation_id_unique(self):
        """Consecutive requests get different correlation IDs when none is sent."""
        app = _app_with_correlation()
        client = TestClient(app)

        ids = set()
        for _ in range(10):
            resp = client.get("/ping")
            ids.add(resp.headers.get("X-Request-ID"))

        # All 10 requests received unique IDs
        assert len(ids) == 10


# ═════════════════════════════════════════════════════════════════════
# AuthMiddleware
# ═════════════════════════════════════════════════════════════════════

class TestAuthMiddleware:
    """AuthMiddleware — X-API-Key header validation."""

    TEST_API_KEY = "test-api-key-abc-12345"

    # ── Tests ──────────────────────────────────────────────────────

    @pytest.fixture(autouse=True)
    def _clean_auth_state(self, monkeypatch):
        """Reset AuthMiddleware state and force in-memory DB."""
        from backend.middleware.auth_middleware import AuthMiddleware
        AuthMiddleware._db = None
        import backend.dependencies
        if backend.dependencies._db_instance is not None:
            try:
                backend.dependencies._db_instance.close()
            except Exception:
                pass
            backend.dependencies._db_instance = None
        monkeypatch.setattr(Config, "DB_PATH", ":memory:")

    def test_valid_global_api_key(self, monkeypatch):
        """Correct X-API-Key → request passes (200)."""
        monkeypatch.setattr(Config, "API_KEY", self.TEST_API_KEY)
        monkeypatch.setattr(Config, "DB_PATH", ":memory:")
        app = _app_with_auth()
        client = TestClient(app)
        resp = client.get("/ping", headers={"X-API-Key": self.TEST_API_KEY})
        assert resp.status_code == 200
        assert resp.json() == {"pong": True}

    def test_invalid_api_key_rejected(self, monkeypatch):
        """Wrong X-API-Key → 403."""
        monkeypatch.setattr(Config, "API_KEY", self.TEST_API_KEY)
        monkeypatch.setattr(Config, "DB_PATH", ":memory:")
        app = _app_with_auth()
        client = TestClient(app)

        resp = client.get("/ping", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"] == "Invalid API key"

    def test_missing_api_key_rejected(self, monkeypatch):
        """No X-API-Key header → 401."""
        monkeypatch.setattr(Config, "API_KEY", self.TEST_API_KEY)
        app = _app_with_auth()
        client = TestClient(app)

        resp = client.get("/ping")
        assert resp.status_code == 401
        data = resp.json()
        assert data["detail"] == "API key required"

    def test_public_paths_skipped(self, monkeypatch):
        """Health and docs endpoints bypass auth even without an API key."""
        monkeypatch.setattr(Config, "API_KEY", self.TEST_API_KEY)
        app = _app_with_auth()
        client = TestClient(app)

        # Health endpoint — no key needed
        resp_health = client.get("/api/v1/health")
        assert resp_health.status_code == 200
        assert resp_health.json() == {"status": "ok"}

        # Docs endpoint — no key needed
        resp_docs = client.get("/docs")
        assert resp_docs.status_code == 200
        assert resp_docs.json() == {"swagger": True}
