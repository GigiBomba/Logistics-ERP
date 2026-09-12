"""Idempotency middleware — prevents duplicate processing of POST/PATCH requests.

Uses Redis as the primary backend (for multi-worker deployments) with an
in-memory dict fallback.

Tenant isolation (R1): every idempotency key is scoped to the authenticated
``company_id`` derived from the request's JWT (``Authorization: Bearer``).
When a tenant cannot be derived at dispatch time (no JWT / API-key auth), the
middleware **skips** idempotency caching entirely — it never falls back to an
unscoped key.

Event-loop safety + cross-worker atomicity (R5): the request path uses a
dedicated ``redis.asyncio`` client (no blocking ``redis.Redis`` calls) and an
atomic claim (``SET key val NX EX ttl GET`` on Redis >= 7.0, Lua-script
fallback otherwise) so two workers handling the same key cannot both miss the
GET and both execute the mutation.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Simple in-memory store with TTL (fallback for when Redis is unavailable).
# Keys are FULL storage keys ``idem:{company_id}:{hash}`` so the in-memory
# bookkeeping is tenant-scoped too (R1).
_idempotency_store: dict[str, tuple[float, int, str, str]] = {}  # key → (expiry, status, content_type, body)
_store_lock = asyncio.Lock()
_IDEMPOTENCY_TTL = 86400  # 24 hours

# The atomic cross-worker claim marker is held for a SHORT period; the real
# cached response is stored afterwards with the full TTL.  If a worker dies
# mid-request the marker expires and the next retry re-executes instead of
# being stuck behind a 24h ghost.
_CLAIM_TTL = 30  # seconds — how long the in-progress marker is held
_CLAIM_WAIT_SECONDS = 5.0  # bounded poll the losing worker performs

_IN_PROGRESS_MARKER = "__in_progress__"

# Per-key serialization locks.  Concurrent requests that carry the SAME
# ``Idempotency-Key`` are serialized on this lock so exactly ONE request
# executes the underlying mutation while the others replay the cached
# response.  Different keys never block each other.  Locks are pruned
# together with their store entry by ``cleanup_expired_entries()``.
# Keyed by the FULL storage key (tenant component included — R1).
_key_locks: dict[str, asyncio.Lock] = {}

# Atomic cross-worker claim.  Redis 7.0+ supports ``SET key val NX EX ttl
# GET``; older servers get the equivalent Lua script.  Both return the prior
# value atomically (nil when this caller won the claim).
_CLAIM_LUA = """
local old = redis.call('get', KEYS[1])
if old then return old end
redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
return nil
"""


# ---------------------------------------------------------------------------
# Redis-backed store (primary)
# ---------------------------------------------------------------------------
class RedisIdempotencyStore:
    """Redis-backed idempotency store for multi-worker deployments.

    Request-path methods (``aclaim`` / ``aset``) are **async** and use a
    dedicated ``redis.asyncio`` client so the event loop is never blocked.
    Admin/introspection methods (``count`` / ``keys_with_ttl`` / ``clear``)
    stay sync and use the sync client — they are only called from the admin
    endpoints (``backend/api/v1/idempotency.py``) and keep their existing
    behaviour.
    """

    def __init__(self, redis_client=None, async_client=None):
        self._redis = redis_client  # sync client — admin introspection only
        self._async = async_client  # async client — request path
        self._ttl = _IDEMPOTENCY_TTL
        self._capability_checked = False
        self._supports_set_get = False

    # ── public helpers ────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """Whether the underlying async Redis client is available."""
        return self._async is not None

    # ── request path (async) ──────────────────────────────────────────

    async def aclaim(self, key: str) -> tuple[str, Optional[tuple[int, str, str]]]:
        """Atomically claim *key* if absent.

        Returns ``("cached", (status, content_type, body))`` when a cached
        response already exists, ``("claimed", None)`` when this caller won
        the claim, ``("in_progress", None)`` when another worker is still
        processing, or ``("unavailable", None)`` when Redis cannot be
        reached (caller falls back to the in-memory store).
        """
        if not self._async:
            return ("unavailable", None)
        try:
            old = await self._claim(key)
        except Exception:
            logger.warning("Redis idempotency claim failed — falling back to in-memory")
            return ("unavailable", None)
        if old is None:
            return ("claimed", None)
        if old == _IN_PROGRESS_MARKER:
            return await self._wait_for_result(key)
        try:
            return ("cached", tuple(json.loads(old)))
        except (json.JSONDecodeError, TypeError, ValueError):
            return ("in_progress", None)

    async def _claim(self, key: str) -> Optional[str]:
        """Perform the atomic get-if-exists / set-if-absent round-trip."""
        if not self._capability_checked:
            await self._probe_capability()
        if self._supports_set_get:
            return await self._async.set(
                key, _IN_PROGRESS_MARKER, nx=True, ex=_CLAIM_TTL, get=True,
            )
        return await self._async.eval(_CLAIM_LUA, 1, key, _IN_PROGRESS_MARKER, _CLAIM_TTL)

    async def _probe_capability(self) -> None:
        """Probe once at startup whether the server supports ``SET ... GET``.

        ``SET key value NX EX ttl GET`` (returning the previous value) was
        added in Redis 7.0.  Older servers fall back to the Lua script.
        """
        try:
            info = await self._async.info("server")
            version = str(info.get("redis_version", "0"))
            self._supports_set_get = _parse_redis_version(version) >= (7, 0, 0)
        except Exception:
            self._supports_set_get = False
        self._capability_checked = True

    async def _wait_for_result(self, key: str) -> tuple[str, Optional[tuple[int, str, str]]]:
        """The losing worker polls briefly for the winner's cached response.

        Bounded by ``_CLAIM_WAIT_SECONDS`` so this never stalls a request
        for long.  If the winner's marker expires (worker died) the claim is
        retried atomically.
        """
        deadline = time.monotonic() + _CLAIM_WAIT_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            try:
                value = await self._async.get(key)
            except Exception:
                return ("unavailable", None)
            if value is None:
                # Marker expired (winner died) — safe to reclaim.
                try:
                    old = await self._claim(key)
                except Exception:
                    return ("unavailable", None)
                if old is None:
                    return ("claimed", None)
                if old != _IN_PROGRESS_MARKER:
                    try:
                        return ("cached", tuple(json.loads(old)))
                    except (json.JSONDecodeError, TypeError, ValueError):
                        return ("in_progress", None)
            elif value != _IN_PROGRESS_MARKER:
                try:
                    return ("cached", tuple(json.loads(value)))
                except (json.JSONDecodeError, TypeError, ValueError):
                    return ("in_progress", None)
        return ("in_progress", None)

    async def aset(self, key: str, status: int, content_type: str, body: str):
        """Store the real cached response, overwriting any claim marker."""
        if not self._async:
            return
        try:
            value = json.dumps([status, content_type, body])
            await self._async.setex(key, self._ttl, value)
        except Exception:
            logger.warning("Failed to store idempotency response in Redis", exc_info=True)
            pass

    # ── admin / introspection (sync, existing behaviour) ──────────────

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
            logger.warning("Failed to introspect idempotency keys from Redis", exc_info=True)
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
    """Return the singleton ``RedisIdempotencyStore``, connecting on first call.

    Builds BOTH a sync client (admin introspection, unchanged) and an async
    ``redis.asyncio`` client (request path — never blocks the event loop).
    """
    global _redis_store
    if _redis_store is None:
        redis_url = os.environ.get("OPERION_REDIS_URL", "")
        redis_password = os.environ.get("OPERION_REDIS_PASSWORD", "")
        sync_client = None
        async_client = None
        if redis_url:
            try:
                import redis as _redis  # pylint: disable=import-outside-toplevel

                sync_client = _redis.Redis.from_url(
                    redis_url,
                    socket_timeout=2,
                    password=redis_password or None,
                    decode_responses=True,
                )
                sync_client.ping()
                async_client = _redis.asyncio.from_url(
                    redis_url,
                    socket_timeout=2,
                    password=redis_password or None,
                    decode_responses=True,
                )
                logger.info("RedisIdempotencyStore connected at %s", redis_url)
            except Exception:
                logger.warning(
                    "Redis unavailable for idempotency store — using in-memory only."
                )
                sync_client = None
                async_client = None
        _redis_store = RedisIdempotencyStore(
            redis_client=sync_client, async_client=async_client
        )
    return _redis_store


# ---------------------------------------------------------------------------
# Tenant derivation (R1)
# ---------------------------------------------------------------------------
def _parse_redis_version(version: str) -> tuple:
    """Parse a redis version string into a comparable tuple."""
    digits: list[int] = []
    for part in version.split("-")[0].split("."):
        try:
            digits.append(int(part))
        except ValueError:
            digits.append(0)
    return tuple((digits + [0, 0, 0])[:3])


def _extract_company_id(request: Request) -> Optional[int]:
    """Derive the tenant id from the request's Bearer JWT.

    Returns *None* when the tenant cannot be determined — the caller must
    then skip idempotency caching entirely (never fall back to an unscoped
    key).  Requests authenticated via ``X-API-Key`` cannot be tenant-scoped
    at middleware time (before auth has run), so they take this path.
    """
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        from backend.security import decode_access_token  # pylint: disable=import-outside-toplevel
        payload = decode_access_token(token.strip())
    except Exception:
        return None
    company_id = payload.get("company_id")
    if company_id is None:
        return None
    try:
        return int(company_id)
    except (TypeError, ValueError):
        return None


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
    Keys are tenant-scoped (``idem:{company_id}:{hash}``); requests whose
    tenant cannot be derived skip caching entirely.
    """

    IDEMPOTENT_METHODS = {"POST", "PATCH", "PUT"}
    IDEMPOTENCY_HEADER = "Idempotency-Key"

    def __init__(self, app):
        super().__init__(app)
        # Obtain the shared Redis store (lazy connected on first call).
        self._redis_store = get_redis_store()

    @staticmethod
    def _storage_key(company_id: int, key_hash: str) -> str:
        return f"idem:{company_id}:{key_hash}"

    async def dispatch(self, request: Request, call_next):
        # Only apply to write methods
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get(self.IDEMPOTENCY_HEADER)
        if not idempotency_key:
            response = await call_next(request)
            response.headers["Idempotency-Key-Supported"] = "true"
            return response

        # Tenant-scope the key (R1).  When the tenant cannot be derived the
        # middleware passes the request through WITHOUT caching — never under
        # an unscoped key.
        company_id = _extract_company_id(request)
        if company_id is None:
            response = await call_next(request)
            response.headers["Idempotency-Key-Supported"] = "true"
            return response

        # Hash the key to prevent storing raw keys
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        storage_key = self._storage_key(company_id, key_hash)

        # Serialize concurrent requests carrying the same key within this
        # process.  Without this, two simultaneous requests with the same
        # key can both miss the store check before either one caches its
        # response — allowing the underlying mutation to run twice.
        # The lock is per-key, so requests with different keys never
        # contend.  Multi-worker deployments additionally rely on the Redis
        # atomic claim (see _process_with_key) for cross-process
        # deduplication.
        lock = _key_locks.setdefault(storage_key, asyncio.Lock())
        async with lock:
            return await self._process_with_key(
                request, call_next, storage_key, idempotency_key
            )

    async def _process_with_key(
        self, request: Request, call_next, storage_key: str, idempotency_key: str
    ):
        outcome = None

        # ── 1. Try Redis first (shared across workers) ────────────────
        # The atomic claim (SET NX EX GET / Lua) replaces the racy
        # GET-followed-by-SETEX: exactly ONE worker wins the claim and
        # executes the mutation; the others replay the cached response or
        # wait briefly.  The in-process ``_key_locks`` above remains as a
        # secondary guard within this process.
        if self._redis_store.available:
            outcome, payload = await self._redis_store.aclaim(storage_key)
            if outcome == "cached":
                return self._replay(payload, idempotency_key, source="Redis")
            if outcome == "in_progress":
                cached = await self._memory_get(storage_key)
                if cached is not None:
                    return self._replay(cached, idempotency_key, source="in-memory")
                logger.info(
                    "Idempotency key already in progress (cross-worker): %s...",
                    idempotency_key[:16],
                )
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": (
                            "A request with this Idempotency-Key is already in "
                            "progress. Retry shortly."
                        ),
                        "retry_after": _CLAIM_WAIT_SECONDS,
                    },
                    headers={"Idempotency-Key-Supported": "true"},
                )

        # ── 2. Fall back to in-memory store ───────────────────────────
        # Skipped when we just won the Redis claim (we own the key).
        if outcome != "claimed":
            cached = await self._memory_get(storage_key)
            if cached is not None:
                return self._replay(cached, idempotency_key, source="in-memory")

        # ── 3. First request — process normally ───────────────────────
        response = await call_next(request)

        # ── 4. Cache the response in both stores ──────────────────────
        body = ""
        if hasattr(response, "body"):
            try:
                body = response.body.decode("utf-8", errors="replace")
            except Exception:
                body = ""
        if not body:
            # Starlette's BaseHTTPMiddleware streams responses through
            # ``call_next`` — the materialized ``.body`` is unavailable, so
            # read the stream and rebuild the response.  Replays must return
            # the real payload, not an empty body.
            chunks = [chunk async for chunk in response.body_iterator]
            raw = b"".join(chunks)
            body = raw.decode("utf-8", errors="replace")
            if raw:
                response = Response(
                    content=raw,
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type", "application/json"),
                    headers=dict(response.headers),
                )
        content_type = response.headers.get("content-type", "application/json")

        # Store in Redis (primary)
        if self._redis_store.available:
            await self._redis_store.aset(storage_key, response.status_code, content_type, body)

        # Store in memory (fallback)
        async with _store_lock:
            _idempotency_store[storage_key] = (
                time.time() + _IDEMPOTENCY_TTL,
                response.status_code,
                content_type,
                body,
            )

        response.headers["Idempotency-Key-Supported"] = "true"
        return response

    @staticmethod
    def _replay(payload, idempotency_key: str, source: str) -> Response:
        """Build a cached-response replay."""
        status, content_type, body = payload
        logger.info(
            "Idempotency key replay (%s): %s...", source, idempotency_key[:16]
        )
        return Response(
            content=body,
            status_code=status,
            media_type=content_type,
            headers={
                "Idempotency-Replayed": "true",
                "Idempotency-Key-Supported": "true",
            },
        )

    @staticmethod
    async def _memory_get(storage_key: str) -> Optional[tuple[int, str, str]]:
        """Read (and purge when expired) the in-memory entry for *storage_key*."""
        async with _store_lock:
            entry = _idempotency_store.get(storage_key)
            if entry is None:
                return None
            expiry, status, content_type, body = entry
            if time.time() < expiry:
                return (status, content_type, body)
            del _idempotency_store[storage_key]
        return None


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