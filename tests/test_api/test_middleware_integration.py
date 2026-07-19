"""Comprehensive integration tests for API middleware chain and authentication guards.

Tests cover:
1. AuthMiddleware — X-API-Key header validation
2. RateLimitMiddleware — per-IP request throttling
3. Auth guards (require_admin, require_manager, require_dispatcher) — RBAC
4. JWT token and password utilities — create/decode/verify
5. Registration rate limiting — per-IP registration throttle
"""

import os
from datetime import timedelta
from typing import Any, Dict
from unittest.mock import MagicMock

import jwt as pyjwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.registration import (
    _check_register_rate_limit,
    _register_rate_limit,
)
from backend.dependencies_security import (
    get_current_user,
    require_admin,
    require_dispatcher,
    require_manager,
)
from backend.middleware.auth_middleware import AuthMiddleware
from backend.middleware.rate_limit_middleware import RateLimitMiddleware
from backend.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from config import Config
from tests.conftest import OPERION_TEST_JWT_SECRET as _TEST_JWT_SECRET

# ── Test constants ──────────────────────────────────────────────────
_TEST_API_KEY = "integration-test-api-key-98765"

# Reusable mock user builders
def _admin_user(**overrides: Any) -> Dict[str, Any]:
    user = {
        "id": 1,
        "email": "admin@test.com",
        "role": "admin",
        "is_admin": True,
        "company_id": 1,
        "display_name": "Admin User",
        "company_name": "Test Corp",
        "subscription_tier": "enterprise",
    }
    user.update(overrides)
    return user


def _manager_user(**overrides: Any) -> Dict[str, Any]:
    user = {
        "id": 2,
        "email": "manager@test.com",
        "role": "manager",
        "is_admin": False,
        "company_id": 1,
        "display_name": "Manager User",
        "company_name": "Test Corp",
        "subscription_tier": "enterprise",
    }
    user.update(overrides)
    return user


def _dispatcher_user(**overrides: Any) -> Dict[str, Any]:
    user = {
        "id": 3,
        "email": "dispatcher@test.com",
        "role": "dispatcher",
        "is_admin": False,
        "company_id": 1,
        "display_name": "Dispatcher User",
        "company_name": "Test Corp",
        "subscription_tier": "standard",
    }
    user.update(overrides)
    return user


def _driver_user(**overrides: Any) -> Dict[str, Any]:
    user = {
        "id": 4,
        "email": "driver@test.com",
        "role": "driver",
        "is_admin": False,
        "company_id": 1,
        "display_name": "Driver User",
        "company_name": "Test Corp",
        "subscription_tier": "standard",
    }
    user.update(overrides)
    return user


# ── Helpers ─────────────────────────────────────────────────────────

def _make_token(role: str, email: str = "test@test.com",
                expires_delta: timedelta = None) -> str:
    """Create a signed JWT with the given role/authn for testing guards."""
    return create_access_token(
        data={"sub": email, "role": role},
        expires_delta=expires_delta,
    )


def _app_with_guard(guard) -> FastAPI:
    """Return a minimal FastAPI app whose ``/protected`` route uses *guard*."""
    app = FastAPI()

    @app.get("/protected")
    async def protected_route(
        current_user: Dict[str, Any] = Depends(guard),
    ):
        return {"ok": True, "role": current_user.get("role")}

    return app


# ═════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module", autouse=True)
def _set_jwt_env():
    """Ensure the JWT secret is available for all token-related tests."""
    old = os.environ.get("OPERION_JWT_SECRET_KEY")
    os.environ["OPERION_JWT_SECRET_KEY"] = _TEST_JWT_SECRET
    yield
    if old is None:
        os.environ.pop("OPERION_JWT_SECRET_KEY", None)
    else:
        os.environ["OPERION_JWT_SECRET_KEY"] = old


# ═════════════════════════════════════════════════════════════════════
# 1. Auth Middleware Tests
# ═════════════════════════════════════════════════════════════════════

class TestAuthMiddleware:
    """AuthMiddleware — X-API-Key header validation."""

    # ── No API key configured ──────────────────────────────────────

    def test_request_without_api_key_passes_when_key_not_set(self, monkeypatch):
        """When OPERION_API_KEY is empty, requests pass through."""
        monkeypatch.setattr(Config, "API_KEY", "")
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"pong": True}

    # ── API key set → validation enforced ─────────────────────────

    def test_request_with_valid_api_key_passes(self, monkeypatch):
        """Correct X-API-Key header → request passes."""
        monkeypatch.setattr(Config, "API_KEY", _TEST_API_KEY)
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)
        resp = client.get("/ping", headers={"X-API-Key": _TEST_API_KEY})
        assert resp.status_code == 200
        assert resp.json() == {"pong": True}

    def test_request_with_invalid_api_key_returns_401(self, monkeypatch):
        """Wrong X-API-Key header → 403 (Forbidden)."""
        monkeypatch.setattr(Config, "API_KEY", _TEST_API_KEY)
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)
        resp = client.get("/ping", headers={"X-API-Key": "invalid-key"})
        assert resp.status_code == 403

    def test_request_without_api_key_returns_401_when_key_required(self, monkeypatch):
        """API key required but not sent → 401."""
        monkeypatch.setattr(Config, "API_KEY", _TEST_API_KEY)
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)
        resp = client.get("/ping")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "API key required"

    # ── Auth endpoint must be accessible ───────────────────────────

    def test_auth_endpoint_accessible_without_api_key(self, monkeypatch):
        """/api/v1/auth/token must be reachable *without* an API key.

        **Expected design**: the auth endpoint should bypass API key
        validation so that unauthenticated clients can obtain JWTs.
        If this test fails the middleware skip_prefixes tuple needs
        to include ``/api/v1/auth/token`` (or a broader prefix such
        as ``/api/v1/auth``).
        """
        monkeypatch.setattr(Config, "API_KEY", _TEST_API_KEY)
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.post("/api/v1/auth/token")
        async def login():
            return {"access_token": "mock", "token_type": "bearer"}

        client = TestClient(app)
        resp = client.post("/api/v1/auth/token")
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}. "
            "Auth endpoint should bypass API key middleware."
        )

    # ── Swagger docs are exempt ───────────────────────────────────

    def test_swagger_docs_bypass_api_key(self, monkeypatch):
        """Swagger paths (/docs, /redoc, /openapi.json) skip API key check."""
        monkeypatch.setattr(Config, "API_KEY", _TEST_API_KEY)
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/docs")
        async def swagger_docs():
            return {"swagger": True}

        @app.get("/redoc")
        async def swagger_redoc():
            return {"redoc": True}

        @app.get("/openapi.json")
        async def swagger_openapi():
            return {"openapi": True}

        client = TestClient(app)
        for path in ("/docs", "/redoc", "/openapi.json"):
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} should bypass API key auth"

    # ── CRITICAL log on disabled middleware ───────────────────────

    def test_disabled_middleware_logs_critical(self, monkeypatch, caplog):
        """A CRITICAL log is emitted when AuthMiddleware is disabled."""
        monkeypatch.setattr(Config, "API_KEY", "")
        import logging

        caplog.set_level(logging.CRITICAL)
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        # Trigger middleware initialisation by making a request
        client = TestClient(app)
        client.get("/ping")

        assert any(
            "API key middleware is DISABLED" in rec.message
            for rec in caplog.records
        ), "Expected CRITICAL log when AuthMiddleware has no API key"


# ═════════════════════════════════════════════════════════════════════
# 2. Rate Limiting Tests
# ═════════════════════════════════════════════════════════════════════

class TestRateLimitMiddleware:
    """RateLimitMiddleware — per-IP request throttling."""

    MAX_REQUESTS = 5
    WINDOW_SECONDS = 60

    # ── Under limit ────────────────────────────────────────────────

    def test_rate_limit_allows_requests_under_limit(self):
        """Requests below the limit all succeed."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=self.MAX_REQUESTS,
            window_seconds=self.WINDOW_SECONDS,
        )

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)
        for i in range(self.MAX_REQUESTS - 1):
            resp = client.get("/ping")
            assert resp.status_code == 200, f"Request {i + 1} should succeed"

    # ── Over limit ────────────────────────────────────────────────

    def test_rate_limit_blocks_requests_over_limit(self):
        """Exceeding the limit returns 429."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=self.MAX_REQUESTS,
            window_seconds=self.WINDOW_SECONDS,
        )

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)

        for _ in range(self.MAX_REQUESTS):
            client.get("/ping")

        resp = client.get("/ping")
        assert resp.status_code == 429
        data = resp.json()
        assert "Too many requests" in data["detail"]
        assert data["retry_after"] == self.WINDOW_SECONDS

    # ── Window expiry ─────────────────────────────────────────────

    def test_rate_limit_resets_after_window(self, monkeypatch):
        """After the window passes the counter resets and requests succeed."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=self.MAX_REQUESTS,
            window_seconds=60,
        )

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)

        fake_now = [1000.0]  # mutable container for closure

        # Patch time.time in the middleware's module
        import backend.middleware.rate_limit_middleware as rlm

        monkeypatch.setattr(rlm.time, "time", lambda: fake_now[0])

        # Exhaust the limit at time=1000
        for _ in range(self.MAX_REQUESTS):
            client.get("/ping")

        # Verify the next request is blocked
        resp = client.get("/ping")
        assert resp.status_code == 429

        # Advance time past the window
        fake_now[0] += 61  # window is 60 s → 61 s puts us outside

        # The request should now succeed
        resp = client.get("/ping")
        assert resp.status_code == 200

    # ── Per-IP isolation ──────────────────────────────────────────

    def test_rate_limit_per_ip_isolation(self):
        """Different client IPs have independent counters."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=3,
            window_seconds=60,
        )

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)

        # Exhaust IP A
        for _ in range(3):
            client.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"})

        resp_a = client.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp_a.status_code == 429

        # IP B is still allowed
        resp_b = client.get("/ping", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp_b.status_code == 200

    # ── X-Forwarded-For header ────────────────────────────────────

    def test_rate_limit_respects_x_forwarded_for(self):
        """The middleware reads X-Forwarded-For when present."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=2,
            window_seconds=60,
        )

        @app.get("/ping")
        async def ping():
            return {"pong": True}

        client = TestClient(app)

        # Two requests from the same proxy-forwarded IP
        client.get("/ping", headers={"X-Forwarded-For": "203.0.113.1"})
        client.get("/ping", headers={"X-Forwarded-For": "203.0.113.1"})

        # Third should be blocked
        resp = client.get("/ping", headers={"X-Forwarded-For": "203.0.113.1"})
        assert resp.status_code == 429

        # Different forwarded IP is fine
        resp2 = client.get("/ping", headers={"X-Forwarded-For": "203.0.113.2"})
        assert resp2.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# 3. Auth Guard Tests
# ═════════════════════════════════════════════════════════════════════

class TestAuthGuards:
    """RBAC guards: require_admin, require_manager, require_dispatcher."""

    # ── require_admin ─────────────────────────────────────────────

    def test_require_admin_allows_admin_user(self):
        """admin role → 200."""
        app = _app_with_guard(require_admin)
        app.dependency_overrides[get_current_user] = lambda: _admin_user()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_require_admin_blocks_dispatcher_user(self):
        """dispatcher role → 403."""
        app = _app_with_guard(require_admin)
        app.dependency_overrides[get_current_user] = lambda: _dispatcher_user()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403
        assert "Admin privileges required" in resp.json()["detail"]["detail"]

    def test_require_admin_blocks_driver_user(self):
        """driver role → 403."""
        app = _app_with_guard(require_admin)
        app.dependency_overrides[get_current_user] = lambda: _driver_user()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403

    # ── require_manager ───────────────────────────────────────────

    def test_require_manager_allows_admin_and_manager(self):
        """admin and manager roles both pass require_manager."""
        # Admin
        app = _app_with_guard(require_manager)
        app.dependency_overrides[get_current_user] = lambda: _admin_user()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

        # Manager
        app2 = _app_with_guard(require_manager)
        app2.dependency_overrides[get_current_user] = lambda: _manager_user()
        client2 = TestClient(app2)
        resp2 = client2.get("/protected")
        assert resp2.status_code == 200
        assert resp2.json()["role"] == "manager"

    def test_require_manager_blocks_driver(self):
        """driver → 403."""
        app = _app_with_guard(require_manager)
        app.dependency_overrides[get_current_user] = lambda: _driver_user()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403
        assert "Manager or admin privileges required" in resp.json()["detail"]["detail"]

    def test_require_manager_blocks_dispatcher(self):
        """dispatcher → 403."""
        app = _app_with_guard(require_manager)
        app.dependency_overrides[get_current_user] = lambda: _dispatcher_user()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403

    # ── require_dispatcher ────────────────────────────────────────

    def test_require_dispatcher_allows_all_roles(self):
        """admin, manager, and dispatcher all pass require_dispatcher."""
        for role_builder in (_admin_user, _manager_user, _dispatcher_user):
            app = _app_with_guard(require_dispatcher)
            # Wrap in lambda to prevent FastAPI from introspecting
            # the builder function's signature as a dependency.
            app.dependency_overrides[get_current_user] = lambda rb=role_builder: rb()
            client = TestClient(app)
            resp = client.get("/protected")
            assert resp.status_code == 200, f"{role_builder.__name__} should pass"
            assert resp.json()["role"] == role_builder()["role"]

    def test_require_dispatcher_blocks_driver(self):
        """driver → 403."""
        app = _app_with_guard(require_dispatcher)
        app.dependency_overrides[get_current_user] = lambda: _driver_user()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 403
        assert "Dispatcher or admin privileges required" in resp.json()["detail"]["detail"]

    def test_require_dispatcher_blocks_unauthenticated(self):
        """No Bearer token → 401 from get_current_user."""
        app = _app_with_guard(require_dispatcher)
        # Do NOT override get_current_user — the real implementation runs
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert "Not authenticated" in resp.json()["detail"]


# ═════════════════════════════════════════════════════════════════════
# 4. JWT Token & Password Tests
# ═════════════════════════════════════════════════════════════════════

class TestJWTAndPassword:
    """Unit / integration tests for backend.security utilities."""

    # ── JWT round-trip ─────────────────────────────────────────────

    def test_create_and_decode_token(self):
        """create_access_token → decode_access_token round-trip."""
        token = create_access_token(
            data={"sub": "user@test.com", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )
        payload = decode_access_token(token)
        assert payload["sub"] == "user@test.com"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_token_contains_standard_claims(self):
        """JWT payload includes sub, role, and exp."""
        token = create_access_token(
            data={"sub": "me@test.com", "role": "manager"},
            expires_delta=timedelta(hours=1),
        )
        payload = decode_access_token(token)
        assert payload["sub"] == "me@test.com"
        assert payload["role"] == "manager"
        assert isinstance(payload["exp"], int)

    # ── Expired token ─────────────────────────────────────────────

    def test_decode_expired_token_raises(self):
        """A token issued with a past expiry raises PyJWTError."""
        token = create_access_token(
            data={"sub": "user@test.com", "role": "admin"},
            expires_delta=timedelta(seconds=-1),  # expired
        )
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(token)

    # ── Invalid / tampered token ──────────────────────────────────

    def test_decode_invalid_token_raises(self):
        """Garbage token → PyJWTError."""
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token("this.is.not.a.jwt")

    def test_decode_tampered_token_raises(self):
        """Token with a modified payload → signature mismatch → PyJWTError."""
        token = create_access_token(
            data={"sub": "user@test.com", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )
        parts = token.split(".")
        tampered = parts[0] + ".aW52YWxpZHBheWxvYWQ" + "." + parts[2]
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(tampered)

    # ── Password hashing & verification ───────────────────────────

    def test_password_hash_and_verify(self):
        """hash_password creates a bcrypt hash; verify_password accepts it."""
        password = "MySecureP@ssw0rd!"
        hashed = hash_password(password)
        assert hashed.startswith("$2b$")
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        """verify_password returns False for a mismatched password."""
        password = "MySecureP@ssw0rd!"
        hashed = hash_password(password)
        assert verify_password("WrongPassword!", hashed) is False

    def test_password_hash_is_unique(self):
        """Each call produces a different salt (different hash)."""
        pw = "SamePassword"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2
        assert verify_password(pw, h1) is True
        assert verify_password(pw, h2) is True

    def test_verify_password_with_invalid_hash_returns_false(self):
        """Malformed hashes are handled gracefully (False, no crash)."""
        assert verify_password("password", "not-a-valid-hash") is False
        assert verify_password("password", "") is False


# ═════════════════════════════════════════════════════════════════════
# 5. Registration Rate Limiting Tests
# ═════════════════════════════════════════════════════════════════════

class TestRegistrationRateLimit:
    """Per-IP rate limiting on the public registration endpoint."""

    # ── Clean slate between tests ─────────────────────────────────

    @pytest.fixture(autouse=True)
    def _clear_register_cache(self):
        """Clear the in-memory registration rate-limit dict before each test."""
        _register_rate_limit.clear()
        yield

    # ── Under threshold ───────────────────────────────────────────

    def test_registration_rate_limit_allows_under_threshold(self):
        """Fewer than 3 attempts from the same IP are allowed."""
        for _ in range(2):
            _check_register_rate_limit("10.0.0.1")  # no exception

    # ── Over threshold ────────────────────────────────────────────

    def test_registration_rate_limit_blocks_after_threshold(self):
        """The 4th registration attempt from the same IP raises 429."""
        for _ in range(3):
            _check_register_rate_limit("10.0.0.1")

        with pytest.raises(Exception) as exc_info:
            _check_register_rate_limit("10.0.0.1")

        assert exc_info.value.status_code == 429
        assert "Too many registration attempts" in exc_info.value.detail

    # ── Per-IP independence ───────────────────────────────────────

    def test_registration_rate_limit_per_ip_independent(self):
        """Different IPs have independent rate-limit counters."""
        # Exhaust IP A
        for _ in range(3):
            _check_register_rate_limit("10.0.0.1")

        with pytest.raises(Exception) as exc_info:
            _check_register_rate_limit("10.0.0.1")
        assert exc_info.value.status_code == 429

        # IP B is unaffected
        _check_register_rate_limit("10.0.0.2")  # no exception

    # ── Window expiry ─────────────────────────────────────────────

    def test_registration_rate_limit_window_expiry(self, monkeypatch):
        """After the 900-second window passes the counter resets."""
        fake_now = [1000.0]

        monkeypatch.setattr(
            "backend.api.v1.registration.time.time",
            lambda: fake_now[0],
        )

        for _ in range(3):
            _check_register_rate_limit("10.0.0.1")

        # Blocked
        with pytest.raises(Exception):
            _check_register_rate_limit("10.0.0.1")

        # Advance past the 900-second window
        fake_now[0] += 901

        # Should be allowed again
        _check_register_rate_limit("10.0.0.1")  # no exception

    # ── Integration through the full app ──────────────────────────

    def test_registration_rate_limit_integration_through_app(self, monkeypatch):
        """The registration endpoint enforces per-IP rate limiting end-to-end.

        The rate-limit check runs *before* database interaction, so we mock
        the DB to accept the SELECT (email uniqueness) but fail on COMMIT.
        The rate-limit counter is incremented regardless of DB outcome.
        """
        from backend.main import create_app
        from backend.dependencies import get_db

        # Speed up the rate-limit threshold for the test
        monkeypatch.setattr(
            "backend.api.v1.registration._REGISTER_RATE_LIMIT", 2,
        )
        monkeypatch.setattr(
            "backend.api.v1.registration._REGISTER_RATE_WINDOW", 60,
        )

        app = create_app()
        mock_db = MagicMock()
        # SELECT returns no existing user → uniqueness check passes
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 1
        mock_db.conn.execute.return_value = mock_cursor
        # COMMIT raises → registration fails after rate-limit counter is bumped
        mock_db.conn.commit.side_effect = Exception("Simulated DB commit failure")
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        payload: Dict[str, str] = {
            "email": "ratelimit-int@test.com",
            "password": "Pass123!",
            "display_name": "Rate Limit Integration",
            "company_name": "RateLimit Corp",
        }

        # First request — counter goes to 1, SELECT passes, COMMIT fails → 500
        client.post("/api/v1/registration/register", json=payload)
        # Second request — counter goes to 2, same behaviour → 500
        client.post("/api/v1/registration/register", json=payload)

        # Third request — blocked by rate limit *before* any DB call → 429
        resp3 = client.post("/api/v1/registration/register", json=payload)
        assert resp3.status_code == 429
        assert "Too many registration attempts" in resp3.json()["detail"]
