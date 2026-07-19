"""Stress and load tests for Trans.eu infrastructure components.

Tests concurrent access, rapid call patterns, resource limits,
and degraded mode behavior.
"""
from __future__ import annotations
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest


class FakeRedis:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}

    def get(self, key):
        with self._lock:
            return self._data.get(key)

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            return True

    def delete(self, *keys):
        with self._lock:
            for k in keys:
                self._data.pop(k, None)
            return True

    def incr(self, key):
        with self._lock:
            val = int(self._data.get(key, 0)) + 1
            self._data[key] = str(val)
            return val

    def zadd(self, key, mapping):
        with self._lock:
            if key not in self._data:
                self._data[key] = {}
            for m, s in mapping.items():
                self._data[key][m] = s
            return len(mapping)

    def zcard(self, key):
        with self._lock:
            if key not in self._data:
                return 0
            return len(self._data[key])

    def zremrangebyscore(self, key, min_s, max_s):
        with self._lock:
            if key not in self._data:
                return 0
            before = len(self._data[key])
            self._data[key] = {k: v for k, v in self._data[key].items() if not (min_s <= v <= max_s)}
            return before - len(self._data[key])

    def expire(self, key, secs):
        return True


class TestRateLimiterConcurrency:
    def test_concurrent_api_calls_allowed_within_limit(self):
        """20 concurrent threads against a 15 RPS limit — must pass only 15."""
        from services.freight_exchange.rate_limiter import FreightRateLimiter
        rl = FreightRateLimiter(FakeRedis())
        results = []

        def _call(idx):
            async def _run():
                return await rl.acquire_api(1, "trans_eu")
            return asyncio.run(_run())

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(_call, i) for i in range(20)]
            for f in as_completed(futures):
                results.append(f.result())

        passed = sum(results)
        assert passed <= 15, f"Too many passed: {passed} (max 15)"

    def test_concurrent_token_calls_allowed_within_limit(self):
        """10 concurrent threads against a 5 RPS token limit — must pass only 5."""
        from services.freight_exchange.rate_limiter import FreightRateLimiter
        rl = FreightRateLimiter(FakeRedis())
        results = []

        def _call(idx):
            async def _run():
                return await rl.acquire_token(1, "trans_eu")
            return asyncio.run(_run())

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_call, i) for i in range(10)]
            for f in as_completed(futures):
                results.append(f.result())

        passed = sum(results)
        assert passed <= 5, f"Too many token passes: {passed} (max 5)"

    def test_rapid_sequential_api_calls_hit_limit(self):
        """100 rapid API calls — only first 15 pass."""
        from services.freight_exchange.rate_limiter import FreightRateLimiter
        rl = FreightRateLimiter(FakeRedis())
        results = []
        for _ in range(100):
            async def _run():
                return await rl.acquire_api(1, "trans_eu")
            results.append(asyncio.run(_run()))
        passed = sum(results)
        assert passed <= 15

    def test_multiple_companies_dont_share_bucket(self):
        """3 companies each sending 15 requests — all must pass."""
        from services.freight_exchange.rate_limiter import FreightRateLimiter
        rl = FreightRateLimiter(FakeRedis())
        results = []
        for cid in [1, 2, 3]:
            for _ in range(15):
                async def _run(c=cid):
                    return await rl.acquire_api(c, "trans_eu")
                results.append(asyncio.run(_run()))
        assert all(results), "Third company should have its own fresh bucket"


class TestCircuitBreakerConcurrency:
    def test_rapid_failures_trip_circuit(self):
        """50 rapid failures — circuit must trip after 5."""
        from services.freight_exchange.circuit_breaker import FreightCircuitBreaker
        cb = FreightCircuitBreaker(FakeRedis())
        for _ in range(50):
            cb.record_failure(1, "trans_eu")
        async def _run():
            return await cb.is_allowed(1, "trans_eu")
        assert asyncio.run(_run()) is False

    def test_success_after_threshold_resets_failures(self):
        """Trip circuit, then succeed — failure count resets but state stays open."""
        from services.freight_exchange.circuit_breaker import FreightCircuitBreaker
        cb = FreightCircuitBreaker(FakeRedis())
        # Trip the circuit (threshold is 5)
        for _ in range(6):
            cb.record_failure(1, "trans_eu")
        # Success after trip resets failures counter but state remains OPEN
        cb.record_success(1, "trans_eu")
        state = cb.get_state(1, "trans_eu")
        # State is still open because record_success only closes from HALF_OPEN
        assert state["state"] == "open"
        # Failures reset to 0
        assert state["failures"] == 0

    def test_multiple_providers_independent(self):
        """2 providers each getting failures — both should trip independently."""
        import asyncio
        from services.freight_exchange.circuit_breaker import FreightCircuitBreaker
        cb = FreightCircuitBreaker(FakeRedis())
        for _ in range(10):
            cb.record_failure(1, "trans_eu")
            cb.record_failure(1, "timocom")
        async def _check_timocom():
            return await cb.is_allowed(1, "timocom")
        async def _check_trans_eu():
            return await cb.is_allowed(1, "trans_eu")
        assert asyncio.run(_check_timocom()) is False
        assert asyncio.run(_check_trans_eu()) is False


class TestDegradedMode:
    def test_no_redis_all_requests_allowed(self):
        from services.freight_exchange.circuit_breaker import FreightCircuitBreaker
        cb = FreightCircuitBreaker(redis_client=None)
        for _ in range(100):
            async def _run():
                return await cb.is_allowed(1, "trans_eu")
            assert asyncio.run(_run()) is True

    def test_no_redis_rate_limiter_always_returns_true(self):
        from services.freight_exchange.rate_limiter import FreightRateLimiter
        rl = FreightRateLimiter(redis_client=None)
        for _ in range(100):
            async def _run():
                return await rl.acquire_api(1, "trans_eu")
            assert asyncio.run(_run()) is True
