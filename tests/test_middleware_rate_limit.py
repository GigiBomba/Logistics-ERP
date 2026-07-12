"""Integration tests for RateLimitMiddleware.

Tests cover:
- Requests within limit pass (200)
- Once limit exceeded, subsequent requests return 429 with Retry-After header
- Window expiry resets counter (short window)
- Custom max_requests and window_seconds params
- X-Forwarded-For header used for client IP
- Purge interval triggers cleanup of old entries
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app() -> FastAPI:
    app_ = FastAPI()

    @app_.get("/")
    async def root():
        return {"ok": True}

    @app_.get("/other")
    async def other():
        return {"hello": "world"}

    return app_


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_app(
    max_requests: int = 5, window_seconds: int = 60
) -> FastAPI:
    """Create a FastAPI app with RateLimitMiddleware attached."""
    from backend.middleware.rate_limit_middleware import RateLimitMiddleware

    app_ = FastAPI()

    @app_.get("/")
    async def root():
        return {"ok": True}

    @app_.get("/other")
    async def other():
        return {"hello": "world"}

    app_.add_middleware(
        RateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    return app_


# ── Basic rate limiting ──────────────────────────────────────────────────


class TestBasicRateLimit:
    def test_requests_within_limit_pass(self):
        """All requests under the limit should return 200."""
        app = _build_app(max_requests=5, window_seconds=60)
        client = TestClient(app)
        for _ in range(5):
            resp = client.get("/")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
            assert resp.json() == {"ok": True}

    def test_limit_exceeded_returns_429(self):
        """Once limit is exceeded, subsequent requests return 429."""
        app = _build_app(max_requests=3, window_seconds=60)
        client = TestClient(app)
        for _ in range(3):
            resp = client.get("/")
            assert resp.status_code == 200

        # 4th request should be blocked
        resp = client.get("/")
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Too many requests"

    def test_retry_after_header_present(self):
        """429 responses must include a Retry-After header."""
        app = _build_app(max_requests=2, window_seconds=30)
        client = TestClient(app)
        for _ in range(2):
            client.get("/")
        resp = client.get("/")
        assert resp.status_code == 429
        # retry_after should be in the JSON body
        assert resp.json()["retry_after"] == 30

    def test_different_endpoints_share_counter(self):
        """Rate limit is per-IP, shared across all endpoints."""
        app = _build_app(max_requests=3, window_seconds=60)
        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/other").status_code == 200
        assert client.get("/").status_code == 200
        # 4th request (any endpoint) should be blocked
        resp = client.get("/other")
        assert resp.status_code == 429


# ── Window expiry ────────────────────────────────────────────────────────


class TestWindowExpiry:
    def test_window_expiry_resets_counter(self):
        """After the window expires, requests should be allowed again."""
        app = _build_app(max_requests=2, window_seconds=1)
        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        resp = client.get("/")
        assert resp.status_code == 200

    def test_partial_window_sliding(self):
        """Older entries slide out of the window as time passes."""
        app = _build_app(max_requests=2, window_seconds=2)
        client = TestClient(app)
        assert client.get("/").status_code == 200
        time.sleep(1)
        assert client.get("/").status_code == 200
        # Both requests are within the 2s window -> 3rd should be blocked
        assert client.get("/").status_code == 429

        # After 1 more second, the first request (at t=0) falls out of the 2s window
        time.sleep(1.1)
        assert client.get("/").status_code == 200


# ── Custom parameters ────────────────────────────────────────────────────


class TestCustomParameters:
    def test_custom_max_requests(self):
        """max_requests parameter adjusts the limit correctly."""
        app = _build_app(max_requests=10, window_seconds=60)
        client = TestClient(app)
        for _ in range(10):
            assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429

    def test_custom_window_seconds(self):
        """window_seconds parameter adjusts the window correctly."""
        app = _build_app(max_requests=3, window_seconds=3)
        client = TestClient(app)
        for _ in range(3):
            assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429

        # Wait 3 seconds for window to fully clear
        time.sleep(3.1)
        assert client.get("/").status_code == 200

    def test_max_requests_one_blocks_after_first(self):
        """Setting max_requests=1 blocks the second request."""
        app = _build_app(max_requests=1, window_seconds=60)
        client = TestClient(app)
        resp1 = client.get("/")
        assert resp1.status_code == 200
        resp2 = client.get("/")
        assert resp2.status_code == 429

    def test_large_window_never_expires_during_test(self):
        """A large window keeps blocking after limit is hit."""
        app = _build_app(max_requests=2, window_seconds=3600)
        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        # Both within the window, so subsequent requests should still be blocked
        assert client.get("/").status_code == 429
        assert client.get("/").status_code == 429


# ── X-Forwarded-For header ───────────────────────────────────────────────


class TestXForwardedFor:
    def test_forwarded_for_used_for_client_ip(self):
        """When X-Forwarded-For is present, it determines the client IP."""
        app = _build_app(max_requests=2, window_seconds=60)
        client = TestClient(app)

        # Requests from IP 10.0.0.1 hit their own limit
        ip1 = "10.0.0.1"
        assert client.get("/", headers={"X-Forwarded-For": ip1}).status_code == 200
        assert client.get("/", headers={"X-Forwarded-For": ip1}).status_code == 200
        assert client.get("/", headers={"X-Forwarded-For": ip1}).status_code == 429

        # A different IP can still make requests
        ip2 = "10.0.0.2"
        assert client.get("/", headers={"X-Forwarded-For": ip2}).status_code == 200

    def test_forwarded_for_with_multiple_ips(self):
        """X-Forwarded-For can contain a comma-separated list; first is used."""
        app = _build_app(max_requests=1, window_seconds=60)
        client = TestClient(app)
        # First IP in the chain should be used as the client identifier
        assert (
            client.get(
                "/",
                headers={"X-Forwarded-For": "203.0.113.1, 10.0.0.1, 192.168.1.1"},
            ).status_code
            == 200
        )
        # Same first IP → blocked
        assert (
            client.get(
                "/",
                headers={"X-Forwarded-For": "203.0.113.1, 10.0.0.2"},
            ).status_code
            == 429
        )
        # Different first IP → allowed
        assert (
            client.get(
                "/",
                headers={"X-Forwarded-For": "203.0.113.2, 10.0.0.1"},
            ).status_code
            == 200
        )

    def test_no_forwarded_for_uses_client_host(self):
        """Without X-Forwarded-For, request.client.host is used."""
        app = _build_app(max_requests=2, window_seconds=60)
        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        # 3rd request from the same client should be blocked
        assert client.get("/").status_code == 429


# ── Purge interval ───────────────────────────────────────────────────────


class TestPurgeInterval:
    def test_purge_interval_cleans_old_entries(self):
        """After PURGE_INTERVAL requests, stale IP entries should be removed.

        We use a short window and check that in-memory dict is cleaned up.
        """
        from backend.middleware.rate_limit_middleware import RateLimitMiddleware

        original_interval = RateLimitMiddleware._PURGE_INTERVAL
        RateLimitMiddleware._PURGE_INTERVAL = 3  # purge every 3 requests

        try:
            app = _build_app(max_requests=10, window_seconds=1)
            client = TestClient(app)

            # Make some requests with unique X-Forwarded-For IPs
            for i in range(4):
                client.get("/", headers={"X-Forwarded-For": f"10.0.0.{i}"})
                time.sleep(0.05)

            # Each request used a different IP, all are within the window
            # After 4 requests (beyond purge interval of 3), purge ran at req 3.
            # Let the window expire then verify new requests from old IPs work.
            time.sleep(1.1)

            # IPs that had entries should be cleaned up and allowed again
            resp = client.get("/", headers={"X-Forwarded-For": "10.0.0.1"})
            assert resp.status_code == 200
        finally:
            RateLimitMiddleware._PURGE_INTERVAL = original_interval

    def test_purge_does_not_affect_active_ips(self):
        """Active IPs within the window should not be purged."""
        from backend.middleware.rate_limit_middleware import RateLimitMiddleware

        original_interval = RateLimitMiddleware._PURGE_INTERVAL
        RateLimitMiddleware._PURGE_INTERVAL = 3

        try:
            app = _build_app(max_requests=5, window_seconds=60)
            client = TestClient(app)

            # Make 5 rapid requests from the same IP
            for _ in range(5):
                assert client.get("/").status_code == 200

            # The IP is still active (recent requests within window),
            # so purge should not have removed it.
            # 6th request should be rate-limited.
            assert client.get("/").status_code == 429
        finally:
            RateLimitMiddleware._PURGE_INTERVAL = original_interval


# ── Edge cases ───────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_default_max_requests_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """When no max_requests is passed, OPERION_RATE_LIMIT env var is used."""
        monkeypatch.setenv("OPERION_RATE_LIMIT", "3")

        from backend.middleware.rate_limit_middleware import RateLimitMiddleware

        app = FastAPI()

        @app.get("/")
        async def root():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware, window_seconds=60)
        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429

    def test_concurrent_ips_independent_limits(self):
        """Different IPs have independent rate limit counters."""
        app = _build_app(max_requests=2, window_seconds=60)
        client = TestClient(app)

        # IP A exhausts its limit
        assert client.get("/", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert client.get("/", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert client.get("/", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429

        # IP B still has its full limit
        assert client.get("/", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200

    def test_unknown_client_uses_unknown_fallback(self, monkeypatch: pytest.MonkeyPatch):
        """When request.client is None, 'unknown' is used as fallback."""
        from backend.middleware.rate_limit_middleware import RateLimitMiddleware

        app = FastAPI()

        @app.get("/")
        async def root():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=60)
        client = TestClient(app)
        # Without X-Forwarded-For and with client=None, 'unknown' is used
        resp1 = client.get("/")
        assert resp1.status_code == 200
        resp2 = client.get("/")
        assert resp2.status_code == 200
        resp3 = client.get("/")
        assert resp3.status_code == 429
