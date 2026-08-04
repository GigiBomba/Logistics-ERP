"""Idempotency middleware — prevents duplicate processing of POST/PATCH requests.

Uses Redis as the primary backend (for multi-worker deployments) with an
in-memory dict fallback.
"""
import hashlib
import json
import logging
import os
import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio

logger = logging.getLogger(__name__)

# Simple in-memory store with TTL (fallback for when Redis is unavailable)
_idempotency_store: dict[str, tuple[float, int, str, str]] = {}  # key → (expiry, status, content_type, body)
_store_lock = asyncio.Lock()
_IDEMPOTENCY_TTL = 86400  # 24 hours

# Per-key serialization locks.  Concurrent requests that carry the SAME
# ``Idempotency-Key`` are serialized on this lock so exactly ONE request
# executes the underlying mutation while the others replay the cached
# response.  Different keys never block each other.  Locks are pruned
# together with their store entry by ``cleanup_expired_entries()``.
_key_locks: dict[str, asyncio.Lock] = {}


# ---------------------------------------------------------------------------
# Redis-backed store (primary)
# ---------------------------------------------------------------------------
class RedisIdempotencyStore:
    """Redis-backed idempotency store for multi-worker deployments.

    Stores response tuples ``(status_code, content_type, body)`` as JSON
    under keys prefixed with ``idem:``.  TTL is controlled by Redis so no
    manual expiry clean-up is needed.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._ttl = _IDEMPOTENCY_TTL

    # ── public helpers ────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """Whether the underlying Redis client is connected."""
        return self._redis is not None

    def get(self, key_hash: str) -> Optional[tuple[int, str, str]]:
        """Return ``(status_code, content_type, body)`` or *None*."""
        if not self._redis:
            return None
        try:
            data = self._redis.get(f"idem:{key_hash}")
            if data:
                return tuple(json.loads(data))
        except Exception:
            pass
        return None

    def set(self, key_hash: str, status: int, content_type: str, body: str):
        """Cache a response for the configured TTL."""
        if not self._redis:
            return
        try:
            value = json.dumps([status, content_type, body])
            self._redis.setex(f"idem:{key_hash}", self._ttl, value)
        except Exception:
            pass

    def count(self) -> int:
        """Approximate number of idempotency keys currently in Redis."""
        if not self._redis:
            return 0
        try:
            return len(list(self._redis.scan_iter(match="idem:*")))
        except Exception:
            return 0

    def keys_with_ttl(self, limit: int = 100) -> list[dict]:
        """Return up to *limit* entries with remaining TTL (seconds)."""
        if not self._redis:
            return []
        result: list[dict] = []
        try:
            for key in self._redis.scan_iter(match="idem:*"):
                ttl = self._redis.ttl(key)
                if ttl > 0:
                    result.append({"hash": key[5:21] + "...", "expires_in": int(ttl)})
                    if len(result) >= limit:
                        break
        except Exception:
            pass
        return result

    def clear(self) -> int:
        """Delete **all** idempotency keys. Returns number of deleted keys."""
        if not self._redis:
            return 0
        try:
            keys = list(self._redis.scan_iter(match="idem:*"))
            if keys:
                return self._redis.delete(*keys)
            return 0
        except Exception:
            return 0


# Global Redis store instance (initialised lazily — see get_redis_store())
_redis_store: Optional[RedisIdempotencyStore] = None


def get_redis_store() -> RedisIdempotencyStore:
    """Return the singleton ``RedisIdempotencyStore``, connecting on first call."""
    global _redis_store
    if _redis_store is None:
        redis_url = os.environ.get("OPERION_REDIS_URL", "")
        redis_password = os.environ.get("OPERION_REDIS_PASSWORD", "")
        client = None
        if redis_url:
            try:
                import redis as _redis  # pylint: disable=import-outside-toplevel

                client = _redis.Redis.from_url(
                    redis_url,
                    socket_timeout=2,
                    password=redis_password or None,
                    decode_responses=True,
                )
                client.ping()
                logger.info("RedisIdempotencyStore connected at %s", redis_url)
            except Exception:
                logger.warning(
                    "Redis unavailable for idempotency store — using in-memory only."
                )
                client = None
        _redis_store = RedisIdempotencyStore(client)
    return _redis_store


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware to provide idempotency-key support for POST, PATCH, and PUT.

    Clients send: ``Idempotency-Key: <unique-key>``
    Server caches the response for 24 hours.
    Replay of the same key returns the cached response.

    The primary storage backend is **Redis** (shared across gunicorn workers).
    An in-memory dict acts as a transparent fallback when Redis is unavailable.
    """

    IDEMPOTENT_METHODS = {"POST", "PATCH", "PUT"}
    IDEMPOTENCY_HEADER = "Idempotency-Key"

    def __init__(self, app):
        super().__init__(app)
        # Obtain the shared Redis store (lazy connected on first call).
        self._redis_store = get_redis_store()

    async def dispatch(self, request: Request, call_next):
        # Only apply to write methods
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get(self.IDEMPOTENCY_HEADER)
        if not idempotency_key:
            response = await call_next(request)
            response.headers["Idempotency-Key-Supported"] = "true"
            return response

        # Hash the key to prevent storing raw keys
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Serialize concurrent requests carrying the same key within this
        # process.  Without this, two simultaneous requests with the same
        # key can both miss the store check before either one caches its
        # response — allowing the underlying mutation to run twice.
        # The lock is per-key, so requests with different keys never
        # contend.  Multi-worker deployments additionally rely on Redis
        # (see _process_with_key) for cross-process deduplication.
        lock = _key_locks.setdefault(key_hash, asyncio.Lock())
        async with lock:
            return await self._process_with_key(
                request, call_next, key_hash, idempotency_key
            )

    async def _process_with_key(
        self, request: Request, call_next, key_hash: str, idempotency_key: str
    ):
        # ── 1. Try Redis first (shared across workers) ────────────────
        if self._redis_store.available:
            # ⚠ CROSS-PROCESS RACE: this GET is followed by a SETEX below,
            # and the two are NOT atomic.  Two workers handling the same
            # Idempotency-Key concurrently can both miss here and both
            # execute the mutation.  The per-process ``_key_locks`` only
            # serialises workers within THIS process.
            #   Real fix (separate work item): an atomic ``SET NX GET``
            #   (Redis 7.0+) or a Lua script that performs the
            #   get-if-exists / set-if-absent in one round-trip.
            redis_result = self._redis_store.get(key_hash)
            if redis_result is not None:
                status, content_type, body = redis_result
                logger.info(
                    "Idempotency key replay (Redis): %s...", idempotency_key[:16]
                )
                return Response(
                    content=body,
                    status_code=status,
                    media_type=content_type,
                    headers={"Idempotency-Replayed": "true"},
                )

        # ── 2. Fall back to in-memory store ───────────────────────────
        async with _store_lock:
            if key_hash in _idempotency_store:
                expiry, status, content_type, body = _idempotency_store[key_hash]
                if time.time() < expiry:
                    logger.info(
                        "Idempotency key replay (in-memory): %s...",
                        idempotency_key[:16],
                    )
                    return Response(
                        content=body,
                        status_code=status,
                        media_type=content_type,
                        headers={"Idempotency-Replayed": "true"},
                    )
                else:
                    # Expired — clean up
                    del _idempotency_store[key_hash]

        # ── 3. First request — process normally ───────────────────────
        response = await call_next(request)

        # ── 4. Cache the response in both stores ──────────────────────
        body = ""
        if hasattr(response, "body"):
            body = response.body.decode("utf-8", errors="replace")
        content_type = response.headers.get("content-type", "application/json")

        # Store in Redis (primary)
        if self._redis_store.available:
            self._redis_store.set(key_hash, response.status_code, content_type, body)

        # Store in memory (fallback)
        async with _store_lock:
            _idempotency_store[key_hash] = (
                time.time() + _IDEMPOTENCY_TTL,
                response.status_code,
                content_type,
                body,
            )

        response.headers["Idempotency-Key-Supported"] = "true"
        return response


def cleanup_expired_entries():
    """Clean up expired idempotency entries from the in-memory store.

    Call periodically (e.g. from a background task or the stats endpoint).
    Redis entries expire automatically via TTL.
    """
    now = time.time()
    expired = [
        k for k, (expiry, _, _, _) in _idempotency_store.items() if now >= expiry
    ]
    for k in expired:
        del _idempotency_store[k]
        _key_locks.pop(k, None)
