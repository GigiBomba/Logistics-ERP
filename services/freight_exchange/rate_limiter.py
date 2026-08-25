"""Redis-backed token bucket rate limiter for Trans.eu API calls.

Trans.eu limits:
  - Token endpoints: 5 RPS
  - API endpoints: 15 RPS

Per-(company_id, provider_id) sliding-window buckets stored in Redis.
Keys auto-expire after 2 seconds for automatic cleanup.
"""
from __future__ import annotations

import logging
import asyncio
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_PREFIX = "rate_limit:freight:"


class RateLimitExceededError(Exception):
    """Raised when the rate limiter denies a request."""
    def __init__(self, company_id: int, provider_id: str, endpoint_type: str):
        super().__init__(
            f"Rate limit exceeded for provider '{provider_id}' (company {company_id}) "
            f"on {endpoint_type} endpoint."
        )


_UNSET = object()


class FreightRateLimiter:
    """Token bucket rate limiter backed by Redis sorted-set sliding windows.

    Two buckets per (company_id, provider_id):
      - API calls: 15 per second
      - Token calls: 5 per second

    Usage::

        limiter = FreightRateLimiter()
        if not await limiter.acquire_api(company_id=1, provider_id="trans_eu"):
            raise RateLimitExceededError(1, "trans_eu", "api")
        # make API call...
    """

    def __init__(self, redis_client=_UNSET):
        """If redis_client is None, runs in degraded mode (no Redis, all requests allowed).
        If not passed, uses the global RedisCache singleton.
        Explicitly passing None means degraded mode."""
        if redis_client is _UNSET:
            # Lazy + guarded: backend.cache only exists on the server; the
            # packaged desktop build ships no backend package.  Missing
            # backend == no Redis == degraded mode (unlimited).
            try:
                from backend.cache import get_cache
                cache = get_cache()
            except ImportError:
                cache = None
            self._redis = (
                cache._redis if cache is not None and hasattr(cache, "_redis") and cache._enabled else None
            )
        else:
            self._redis = redis_client

    def _api_key(self, company_id: int, provider_id: str) -> str:
        return f"{REDIS_PREFIX}{company_id}:{provider_id}:api"

    def _token_key(self, company_id: int, provider_id: str) -> str:
        return f"{REDIS_PREFIX}{company_id}:{provider_id}:token"

    async def acquire_api(self, company_id: int, provider_id: str) -> bool:
        """Try to acquire 1 token from the API bucket (15 RPS)."""
        return self._acquire(self._api_key(company_id, provider_id), 15)

    async def acquire_token(self, company_id: int, provider_id: str) -> bool:
        """Try to acquire 1 token from the token bucket (5 RPS)."""
        return self._acquire(self._token_key(company_id, provider_id), 5)

    def _acquire(self, key: str, max_per_second: int) -> bool:
        """Sliding window: count requests in the last second. True if allowed.

        Uses Redis sorted sets (ZSET) with timestamp scores.
        Members older than 1 second are removed before counting.
        """
        if self._redis is None:
            return True  # no Redis — allow all (degraded mode)

        now = time.time()
        window_start = now - 1.0

        # Remove entries older than the window
        self._redis.zremrangebyscore(key, 0, window_start)

        # Count current entries
        count = self._redis.zcard(key)
        if count is not None and count >= max_per_second:
            logger.debug("Rate limit hit for key=%s (count=%d, max=%d)", key, count, max_per_second)
            return False

        # Record this request with a unique score (timestamp + sub-millisecond)
        member = f"{now}:{random.randint(0, 999999)}"
        self._redis.zadd(key, {member: now})
        self._redis.expire(key, 2)  # auto-cleanup after 2 seconds
        return True

    async def acquire_api_with_wait(
        self, company_id: int, provider_id: str, timeout_ms: int = 200
    ) -> bool:
        """Try to acquire, with brief wait + jitter if unavailable.

        Returns True if a token was acquired within the timeout.
        """
        if await self.acquire_api(company_id, provider_id):
            return True

        # Wait with jitter before retrying
        await asyncio.sleep(random.uniform(0.01, 0.05))

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            if self._acquire(self._api_key(company_id, provider_id), 15):
                return True
            await asyncio.sleep(0.02)

        logger.warning(
            "Rate limit wait timed out for company=%d provider=%s after %dms",
            company_id, provider_id, timeout_ms,
        )
        return False

    def get_status(self, company_id: int, provider_id: str) -> dict:
        """Return current rate limit status for monitoring."""
        if self._redis is None:
            return {"api": "unknown", "token": "unknown", "reason": "redis_unavailable"}

        api_key = self._api_key(company_id, provider_id)
        token_key = self._token_key(company_id, provider_id)

        now = time.time()
        self._redis.zremrangebyscore(api_key, 0, now - 1.0)
        self._redis.zremrangebyscore(token_key, 0, now - 1.0)

        api_count = self._redis.zcard(api_key) or 0
        token_count = self._redis.zcard(token_key) or 0

        return {
            "api": {"current_rps": api_count, "max_rps": 15, "available": 15 - api_count},
            "token": {"current_rps": token_count, "max_rps": 5, "available": 5 - token_count},
        }
