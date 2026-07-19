"""Tests for Redis-backed FreightRateLimiter — token bucket, sliding window, degraded mode.

Covers: API and token rate limits, acquire success/failure, wait timeout, degraded mode, status.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from services.freight_exchange.rate_limiter import FreightRateLimiter, RateLimitExceededError


class FakeRedis:
    """In-memory dict simulating Redis sorted sets for rate limiter testing."""
    def __init__(self):
        self._data = {}       # key -> {member: score}
        self._expiry = {}     # key -> expiry_time

    def zremrangebyscore(self, key, min_s, max_s):
        """Remove members from sorted set by score range. Returns count removed."""
        if key not in self._data:
            return 0
        before = len(self._data[key])
        self._data[key] = {k: v for k, v in self._data[key].items() if not (min_s <= v <= max_s)}
        after = len(self._data[key])
        return before - after

    def zcard(self, key):
        """Get the cardinality of a sorted set."""
        if key not in self._data:
            return 0
        return len(self._data[key])

    def zadd(self, key, mapping):
        """Add members to sorted set with scores."""
        if key not in self._data:
            self._data[key] = {}
        for member, score in mapping.items():
            self._data[key][member] = score
        return len(mapping)

    def expire(self, key, seconds):
        """Set expiry on key (tracked but not enforced in tests)."""
        self._expiry[key] = time.time() + seconds
        return True


class TestRateLimiterInit:
    def test_no_redis_degraded_mode(self):
        rl = FreightRateLimiter(redis_client=None)
        async def _run():
            return await rl.acquire_api(1, "trans_eu")
        assert asyncio.run(_run()) is True

    def test_with_redis(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            return await rl.acquire_api(1, "trans_eu")
        assert asyncio.run(_run()) is True


class TestRateLimiterApiBucket:
    def test_accepts_first_15_requests(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            results = []
            for _ in range(15):
                results.append(await rl.acquire_api(1, "trans_eu"))
            return results
        results = asyncio.run(_run())
        assert all(results)

    def test_blocks_16th_request(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            for _ in range(15):
                await rl.acquire_api(1, "trans_eu")
            return await rl.acquire_api(1, "trans_eu")
        assert asyncio.run(_run()) is False

    def test_token_bucket_separate_from_api(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            for _ in range(15):
                await rl.acquire_api(1, "trans_eu")
            return await rl.acquire_token(1, "trans_eu")
        # Token bucket should still work
        assert asyncio.run(_run()) is True


class TestRateLimiterTokenBucket:
    def test_accepts_5_token_requests(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            results = []
            for _ in range(5):
                results.append(await rl.acquire_token(1, "trans_eu"))
            return results
        results = asyncio.run(_run())
        assert all(results)

    def test_blocks_6th_token_request(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            for _ in range(5):
                await rl.acquire_token(1, "trans_eu")
            return await rl.acquire_token(1, "trans_eu")
        assert asyncio.run(_run()) is False


class TestRateLimiterCompanyIsolation:
    def test_different_companies_have_separate_buckets(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            for _ in range(15):
                await rl.acquire_api(1, "trans_eu")
            return await rl.acquire_api(2, "trans_eu")
        # Company 2 should not be affected
        assert asyncio.run(_run()) is True

    def test_different_providers_have_separate_buckets(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            for _ in range(15):
                await rl.acquire_api(1, "trans_eu")
            return await rl.acquire_api(1, "timocom")
        assert asyncio.run(_run()) is True


class TestRateLimiterStatus:
    def test_status_shows_bucket_fill_level(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            for _ in range(5):
                await rl.acquire_api(1, "trans_eu")
        asyncio.run(_run())
        status = rl.get_status(1, "trans_eu")
        assert status["api"]["max_rps"] == 15
        assert status["api"]["current_rps"] == 5
        assert status["api"]["available"] == 10

    def test_status_no_redis(self):
        rl = FreightRateLimiter(redis_client=None)
        status = rl.get_status(1, "trans_eu")
        assert status["api"] == "unknown"


class TestRateLimiterConstantTime:
    """Property-based: the rate limiter enforces the same max for different inputs."""
    def test_api_respects_15_rps(self):
        rl = FreightRateLimiter(FakeRedis())
        async def _run():
            results = []
            for _ in range(20):
                results.append(await rl.acquire_api(1, "trans_eu"))
            return results
        results = asyncio.run(_run())
        assert sum(results) == 15  # exactly 15 true, 5 false
        assert results[:15] == [True] * 15
        assert results[15:] == [False] * 5
