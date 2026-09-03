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
from __future__ import annotations


import hashlib
import hmac
import json
import logging
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.desktop_config import Config
from backend.errors import ErrorCode

logger = logging.getLogger(__name__)

# ── Validated-key cache (R7) ────────────────────────────────────────────
# Every authenticated request used to do a DB SELECT + last_used UPDATE.
# Validated per-partner keys are now cached in-process for a short TTL,
# keyed by the SHA-256 hash of the raw key (the ``api_keys.key_hash`` is
# globally unique — no tenant component needed).  The TTL bounds revocation
# propagation: ``ApiKeyRepository.revoke_key`` evicts the matching entries
# immediately (best-effort), otherwise a revoked key may be accepted for at
# most ``_KEY_CACHE_TTL`` seconds.
_VALIDATED_KEY_CACHE: dict[str, tuple[float, dict]] = {}  # key_hash -> (expiry_ts, data)
_KEY_CACHE_TTL = 45.0  # seconds
_KEY_CACHE_MAX_ENTRIES = 1000


def _key_cache_hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _prune_key_cache() -> None:
    """Cap the cache so a flood of unique keys can't grow it unbounded."""
    if len(_VALIDATED_KEY_CACHE) < _KEY_CACHE_MAX_ENTRIES:
        return
    now = time.time()
    expired = [k for k, (exp, _) in _VALIDATED_KEY_CACHE.items() if exp <= now]
    for k in expired:
        del _VALIDATED_KEY_CACHE[k]
    if len(_VALIDATED_KEY_CACHE) >= _KEY_CACHE_MAX_ENTRIES:
        oldest = sorted(_VALIDATED_KEY_CACHE.items(), key=lambda kv: kv[1][0])
        for k, _ in oldest[: _KEY_CACHE_MAX_ENTRIES // 4]:
            _VALIDATED_KEY_CACHE.pop(k, None)


def evict_api_key_cache_by_id(key_id: int) -> None:
    """Evict cached validation entries whose row ``id`` matches *key_id*.

    Called by ``ApiKeyRepository.revoke_key`` so a freshly revoked key stops
    being accepted on the next request.  Best-effort — a missing entry is a
    no-op and the cache TTL remains the upper revocation bound.
    """
    for cache_key in [
        k for k, (_, data) in _VALIDATED_KEY_CACHE.items()
        if data.get("id") == key_id
    ]:
        del _VALIDATED_KEY_CACHE[cache_key]


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
    SKIP_PREFIXES = (
        "/docs", "/redoc", "/openapi.json", "/api/v1/health",
        "/api/v1/auth", "/api/v1/registration", "/api/v1/route-demo",
        "/api/v1/waitlist", "/api/v1/status",
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
        from backend.repositories.api_key_repository import ApiKeyRepository

        # Short-TTL in-memory cache (R7): a validated key is served from
        # memory for up to _KEY_CACHE_TTL seconds, eliminating the DB SELECT
        # (+ throttled last_used UPDATE) on every request.  Keyed by the
        # globally-unique key hash.
        key_hash = _key_cache_hash(api_key)
        now = time.time()
        entry = _VALIDATED_KEY_CACHE.get(key_hash)
        if entry is not None and entry[0] > now:
            key_data = entry[1]
        else:
            repo = ApiKeyRepository(self._get_db())
            key_data = repo.validate_key(api_key)
            if key_data is not None:
                _prune_key_cache()
                _VALIDATED_KEY_CACHE[key_hash] = (now + _KEY_CACHE_TTL, key_data)
            else:
                _VALIDATED_KEY_CACHE.pop(key_hash, None)

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
