"""API Key authentication middleware.

Authenticates requests via one of two mechanisms:

1. **Legacy global key** — the ``OPERION_API_KEY`` env var.
   If set, it acts as a super-key that grants access to everything.

2. **Per-partner API keys** — stored in the ``api_keys`` table
   (SHA-256 hashed). These support per-partner scoping, expiry,
   rotation, and usage tracking.

If *neither* mechanism is available and no API key is provided,
requests are allowed through in non-production environments for
backward compatibility (open API mode).

In production (``OPERION_ENV=production``), the middleware **raises**
at startup if no global API key is configured — the API will not start.

Used as an ASGI middleware in ``backend/main.py``.

Usage::

    export OPERION_API_KEY=my-secret-key-123
    python -m uvicorn backend.main:app
"""

import hmac
import json
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.errors import ErrorCode
from config import Config

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate ``X-API-Key`` header against global or per-partner keys."""

    def __init__(self, app):
        super().__init__(app)
        self._api_key = Config.API_KEY
        self._enabled = bool(self._api_key)

        if not self._api_key:
            env = os.environ.get("OPERION_ENV", "development")
            if env == "production":
                raise RuntimeError(
                    "OPERION_API_KEY is not set — the API key middleware cannot "
                    "start in production. Set OPERION_API_KEY in your environment."
                )
            logger.critical(
                "OPERION_API_KEY is not set — API key middleware is DISABLED. "
                "All requests are accepted without API key validation."
            )

    # ── Public-path prefixes exempt from auth ──────────────────────────
    # These are public website endpoints — the marketing/SPA frontend
    # (src/api/endpoints.ts) calls them WITHOUT an X-API-Key header, so
    # they must be exempt from API-key enforcement in production.
    # Admin/ops/subscriptions/licenses/organizations/fleet stay protected.
    SKIP_PREFIXES = (
        "/docs", "/redoc", "/openapi.json", "/api/v1/health",
        "/api/v1/auth", "/api/v1/registration", "/api/v1/route-demo",
        "/api/v1/waitlist",
        # ── Public forms (bot-protected via Turnstile) ─────────────────
        "/api/v1/contact",
        "/api/v1/newsletter",
        # ── Public pricing (website pricing page, no auth) ─────────────
        "/api/v1/subscriptions/plans",
        # ── Public marketing read endpoints (see src/api/endpoints.ts) ──
        "/api/v1/blog/posts",
        "/api/v1/blog/categories",
        "/api/v1/blog/authors",
        "/api/v1/changelog",
        "/api/v1/roadmap",
        "/api/v1/status",
        "/api/v1/tutorials",
        "/api/v1/developers",
        "/api/v1/security",
        "/api/v1/announcements",
        "/api/v1/integrations",
        "/api/v1/customer-stories",
        "/api/v1/careers",
        "/api/v1/press",
        "/api/v1/partners",
        "/api/v1/search",
    )

    @staticmethod
    def _is_public_path(path: str) -> bool:
        return path.startswith(AuthMiddleware.SKIP_PREFIXES)

    # ------------------------------------------------------------------
    #  DB access — lazily import to avoid circular dependency at startup
    # ------------------------------------------------------------------
    _db = None

    def _get_db(self):
        if self._db is None:
            from backend.dependencies import init_db
            AuthMiddleware._db = init_db()
        return self._db

    async def dispatch(self, request: Request, call_next):
        # ── CORS preflight — pass through immediately ───────────────────
        if request.method == "OPTIONS":
            return await call_next(request)

        # ── Skip public paths ──────────────────────────────────────────
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # ── Skip requests authenticated with a Bearer JWT ──────────────
        # The website SPA authenticates with Bearer tokens only (no
        # X-API-Key). Route-level dependencies (get_current_user /
        # require_dispatcher / require_admin) enforce the JWT, so passing
        # Bearer requests through here is safe. X-API-Key enforcement
        # remains for partner integrations (no Bearer token).
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            # No key provided — allow through only in non-production
            # when no global key is configured (backward compat).
            if not self._enabled:
                return await call_next(request)
            logger.warning(
                "API key auth failed: reason=%s client_ip=%s path=%s",
                "missing",
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "API key required", "error_code": ErrorCode.INVALID_API_KEY.value},
            )

        # ── 1. Check legacy global key (fast path) ─────────────────────
        if self._enabled and hmac.compare_digest(api_key, self._api_key):
            return await call_next(request)

        # ── 2. Check per-partner keys ──────────────────────────────────
        from repositories.api_key_repository import ApiKeyRepository

        repo = ApiKeyRepository(self._get_db())
        key_data = repo.validate_key(api_key)
        if key_data is not None:
            request.state.api_key_partner = key_data.get("partner")
            try:
                request.state.api_key_scopes = json.loads(key_data.get("scopes", "[]"))
            except (json.JSONDecodeError, TypeError):
                request.state.api_key_scopes = []
            return await call_next(request)

        # ── 3. Neither matched — reject ────────────────────────────────
        logger.warning(
            "API key auth failed: reason=%s client_ip=%s path=%s",
            "invalid",
            request.client.host if request.client else "unknown",
            request.url.path,
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid API key", "error_code": ErrorCode.INVALID_API_KEY.value},
        )
