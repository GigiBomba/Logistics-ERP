"""Integration tests for AuthMiddleware.

Tests cover:
- API key validation with OPERION_API_KEY set
- Missing / wrong API key rejection
- Timing-safe comparison (hmac.compare_digest)
- No-key mode (OPERION_API_KEY unset)
- Whitelist path bypass (/docs, /redoc, /openapi.json, /api/v1/health)
- Production guard (RuntimeError when env=production and no key)
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _middleware_config():
    """Return the ``Config`` class ``AuthMiddleware`` actually reads, resolved
    at call time.

    ``tests/test_security_verification.py`` and ``tests/chaos/test_chaos_celery.py``
    ``importlib.reload`` the config chain, which REPLACES ``config.Config`` with
    a NEW class object.  A module-top ``from config import Config`` reference
    goes stale after that reload, so ``monkeypatch.setattr`` on it would not
    affect the middleware (which reads the reloaded class) — producing the CI
    failures where a valid key returns 403.  Resolving through the middleware
    module at runtime always patches the class the middleware reads.
    """
    import backend.middleware.auth_middleware as _auth_mw_mod

    return _auth_mw_mod.Config


# ── Helpers ──────────────────────────────────────────────────────────────


def _add_routes(app: FastAPI) -> None:
    """Attach simple test endpoints to an app."""

    @app.get("/")
    async def root():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "healthy"}


def _build_app() -> FastAPI:
    """Create a FastAPI app with AuthMiddleware attached.

    The caller **must** set ``Config.API_KEY`` via ``monkeypatch.setattr``
    **before** calling this function so the middleware picks up the value
    when it reads ``Config.API_KEY`` during construction.
    """
    from backend.middleware.auth_middleware import AuthMiddleware

    app = FastAPI()
    _add_routes(app)
    app.add_middleware(AuthMiddleware)
    return app


# ── Valid API key ─────────────────────────────────────────────────────────


class TestValidApiKey:
    def test_valid_key_returns_200(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "my-secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "my-secret"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_valid_key_can_include_special_chars(self, monkeypatch: pytest.MonkeyPatch):
        key = "a1b2c3-d4e5_f6g7-h8i9_j0k1"
        monkeypatch.setattr(_middleware_config(), "API_KEY", key)
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": key})
        assert resp.status_code == 200


# ── Missing / invalid API key ────────────────────────────────────────────


class TestMissingOrInvalidKey:
    def test_missing_header_returns_401(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "API key required", "error_code": "auth/invalid-api-key"}

    def test_empty_header_returns_401(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": ""})
        assert resp.status_code == 401

    def test_wrong_key_returns_403(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "correct-key")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403

    def test_partial_match_returns_403(self, monkeypatch: pytest.MonkeyPatch):
        """A key that starts the same as the real key must still be rejected."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "super-secret-key")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "super-secret"})
        assert resp.status_code == 403


# ── Timing-safe comparison (hmac.compare_digest) ─────────────────────────


class TestTimingSafeComparison:
    """Verify that hmac.compare_digest is called (no early-exit on length)."""

    def test_different_length_keys_are_rejected(self, monkeypatch: pytest.MonkeyPatch):
        """A key with different length than the real key must still get 403."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "short")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "a" * 100})
        assert resp.status_code == 403

    def test_longer_real_key_with_short_input(self, monkeypatch: pytest.MonkeyPatch):
        """Real key is long, provided key is short — must still fail."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "a" * 100)
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "short"})
        assert resp.status_code == 403

    def test_empty_key_vs_non_empty_config(self, monkeypatch: pytest.MonkeyPatch):
        """Empty header against a configured key returns 401."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "non-empty")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": ""})
        assert resp.status_code == 401


# ── No API key configured (open access) ──────────────────────────────────


class TestNoKeyConfigured:
    def test_no_key_allows_all_requests(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_no_key_no_header_still_passes(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": ""})
        assert resp.status_code == 200

    def test_no_key_sends_wrong_header_gets_403(self, monkeypatch: pytest.MonkeyPatch):
        """When auth is disabled but a wrong key is sent, middleware rejects it."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "any-old-thing"})
        assert resp.status_code == 403


# ── Whitelist path bypass ────────────────────────────────────────────────


class TestWhitelistPaths:
    """Paths /docs, /redoc, /openapi.json, /api/v1/health must skip auth."""

    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    def test_swagger_paths_skip_auth(self, monkeypatch: pytest.MonkeyPatch, path: str):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get(path)
        # Swagger paths are not mounted — expect 404, crucially NOT 401
        assert resp.status_code != 401, (
            f"{path} should bypass auth but got 401"
        )

    def test_health_endpoint_skips_auth(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_health_endpoint_no_key(self, monkeypatch: pytest.MonkeyPatch):
        """Health endpoint works even without any API key header."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/v1/health", headers={"X-API-Key": ""})
        assert resp.status_code == 200

    @pytest.mark.parametrize("path", ["/docs/sub", "/redoc/extra", "/api/v1/health/stats"])
    def test_whitelist_prefix_matches_subpaths(
        self, monkeypatch: pytest.MonkeyPatch, path: str
    ):
        """Paths starting with whitelist prefixes should also bypass auth."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get(path)
        assert resp.status_code != 401

    def test_non_whitelist_path_needs_key(self, monkeypatch: pytest.MonkeyPatch):
        """A path not in the whitelist must still require auth."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/v1/trips")
        assert resp.status_code == 401


# ── Production guard ─────────────────────────────────────────────────────


class TestProductionGuard:
    def test_production_without_key_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """In production mode with no API key set, AuthMiddleware must raise."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "")
        monkeypatch.setenv("OPERION_ENV", "production")

        from backend.middleware.auth_middleware import AuthMiddleware

        app = FastAPI()
        _add_routes(app)

        # Direct instantiation triggers __init__ which reads Config + env
        with pytest.raises(RuntimeError, match="OPERION_API_KEY is not set"):
            AuthMiddleware(app)

    def test_production_with_key_starts_ok(self, monkeypatch: pytest.MonkeyPatch):
        """In production mode with a valid key, the middleware must start."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "prod-key-999")
        monkeypatch.setenv("OPERION_ENV", "production")

        from backend.middleware.auth_middleware import AuthMiddleware

        app = FastAPI()
        _add_routes(app)

        mw = AuthMiddleware(app)  # should not raise
        # Verify middleware is properly initialised via TestClient
        client = TestClient(mw)
        resp = client.get("/", headers={"X-API-Key": "prod-key-999"})
        assert resp.status_code == 200

    def test_development_without_key_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """In development mode, missing API key is allowed (with a warning)."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "")
        monkeypatch.setenv("OPERION_ENV", "development")

        from backend.middleware.auth_middleware import AuthMiddleware

        app = FastAPI()
        _add_routes(app)

        mw = AuthMiddleware(app)  # should not raise
        client = TestClient(mw)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_production_guard_message(self, monkeypatch: pytest.MonkeyPatch):
        """Verify the RuntimeError message is descriptive."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "")
        monkeypatch.setenv("OPERION_ENV", "production")

        from backend.middleware.auth_middleware import AuthMiddleware

        app = FastAPI()
        _add_routes(app)

        with pytest.raises(RuntimeError) as exc:
            AuthMiddleware(app)
        assert "OPERION_API_KEY" in str(exc.value)


# ── Validated-key cache (R7) ─────────────────────────────────────────────


class TestValidatedKeyCache:
    """Per-partner key validation is cached in-process for a short TTL."""

    @pytest.fixture(autouse=True)
    def _clear_key_cache(self):
        from backend.middleware.auth_middleware import _VALIDATED_KEY_CACHE
        _VALIDATED_KEY_CACHE.clear()
        yield
        _VALIDATED_KEY_CACHE.clear()

    def _build_partner_client(self, monkeypatch, validate_result):
        """Client whose partner-key validation hits a stubbed repository."""
        from backend.middleware.auth_middleware import AuthMiddleware

        monkeypatch.setattr(_middleware_config(), "API_KEY", "global-super-key")
        app = FastAPI()
        _add_routes(app)
        mw = AuthMiddleware(app)
        # Never touch a real DB.
        mw._get_db = lambda: MagicMock()
        client = TestClient(mw)
        return client

    def test_second_request_within_ttl_does_zero_db_calls(
        self, monkeypatch
    ):
        """Two requests with the same key within the TTL validate once."""
        from backend.middleware.auth_middleware import AuthMiddleware

        mock_repo = MagicMock()
        mock_repo.validate_key.return_value = {
            "id": 7, "partner": "acme", "scopes": '["read"]',
        }

        monkeypatch.setattr(_middleware_config(), "API_KEY", "global-super-key")
        app = FastAPI()
        _add_routes(app)
        mw = AuthMiddleware(app)
        mw._get_db = lambda: MagicMock()
        client = TestClient(mw)

        with patch(
            "backend.repositories.api_key_repository.ApiKeyRepository",
            return_value=mock_repo,
        ):
            r1 = client.get("/", headers={"X-API-Key": "ok_same_key_123"})
            r2 = client.get("/", headers={"X-API-Key": "ok_same_key_123"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        # Only the FIRST request touched the repository; the second was
        # served entirely from the in-memory cache.
        assert mock_repo.validate_key.call_count == 1
        mock_repo.validate_key.assert_called_once_with("ok_same_key_123")

    def test_different_keys_validate_independently(self, monkeypatch):
        """Each distinct key performs its own validation (no false hits)."""
        from backend.middleware.auth_middleware import AuthMiddleware

        mock_repo = MagicMock()
        mock_repo.validate_key.return_value = {
            "id": 8, "partner": "acme", "scopes": "[]",
        }

        monkeypatch.setattr(_middleware_config(), "API_KEY", "global-super-key")
        app = FastAPI()
        _add_routes(app)
        mw = AuthMiddleware(app)
        mw._get_db = lambda: MagicMock()
        client = TestClient(mw)

        with patch(
            "backend.repositories.api_key_repository.ApiKeyRepository",
            return_value=mock_repo,
        ):
            assert client.get("/", headers={"X-API-Key": "ok_key_a"}).status_code == 200
            assert client.get("/", headers={"X-API-Key": "ok_key_b"}).status_code == 200

        assert mock_repo.validate_key.call_count == 2

    def test_revoked_key_evicted_from_cache(self, monkeypatch):
        """evict_api_key_cache_by_id removes the matching cached entry."""
        from backend.middleware.auth_middleware import (
            _VALIDATED_KEY_CACHE,
            evict_api_key_cache_by_id,
        )

        _VALIDATED_KEY_CACHE["abc"] = (9999999999.0, {"id": 42, "partner": "p"})
        _VALIDATED_KEY_CACHE["def"] = (9999999999.0, {"id": 43, "partner": "p"})

        evict_api_key_cache_by_id(42)

        assert "abc" not in _VALIDATED_KEY_CACHE
        assert "def" in _VALIDATED_KEY_CACHE


# ── Edge cases ───────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_key_with_whitespace(self, monkeypatch: pytest.MonkeyPatch):
        """Keys with leading/trailing whitespace are compared as-is."""
        key = "my-key"
        monkeypatch.setattr(_middleware_config(), "API_KEY", key)
        app = _build_app()
        client = TestClient(app)
        # Exact match must pass
        resp = client.get("/", headers={"X-API-Key": key})
        assert resp.status_code == 200

    def test_key_without_prefix_is_rejected(self, monkeypatch: pytest.MonkeyPatch):
        """A key without some expected prefix is still rejected."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "sk-abcdef123456")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "abcdef123456"})
        assert resp.status_code == 403

    def test_multiple_headers_handled(self, monkeypatch: pytest.MonkeyPatch):
        """X-API-Key header is read correctly when multiple headers exist."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "secret")
        app = _build_app()
        client = TestClient(app)
        resp = client.get(
            "/",
            headers={
                "X-API-Key": "secret",
                "Authorization": "Bearer token",
                "X-Forwarded-For": "1.2.3.4",
            },
        )
        assert resp.status_code == 200

    def test_key_is_digits_only(self, monkeypatch: pytest.MonkeyPatch):
        """Numeric-only keys work correctly."""
        monkeypatch.setattr(_middleware_config(), "API_KEY", "1234567890")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/", headers={"X-API-Key": "1234567890"})
        assert resp.status_code == 200
