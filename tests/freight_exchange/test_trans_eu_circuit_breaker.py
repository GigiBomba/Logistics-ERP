"""Tests for Redis-backed FreightCircuitBreaker — state transitions, failure threshold, recovery.

Covers: CLOSED->OPEN->HALF_OPEN->CLOSED transitions, failure counting,
success resetting, admin reset, degraded mode (no Redis).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from services.freight_exchange.circuit_breaker import (
    FAILURE_THRESHOLD,
    CircuitBreakerOpenError,
    CircuitState,
    FreightCircuitBreaker,
)


class FakeRedis:
    """In-memory dict that behaves enough like redis.Redis for circuit breaker tests."""
    def __init__(self):
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value):
        self._data[key] = value
        return True

    def delete(self, *keys):
        for k in keys:
            self._data.pop(k, None)
        return True

    def incr(self, key):
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = str(val)
        return val


@pytest.fixture
def cb():
    return FreightCircuitBreaker(FakeRedis())


@pytest.fixture
def cb_no_redis():
    return FreightCircuitBreaker(redis_client=None)


class TestCircuitBreakerInitial:
    def test_allowed_when_closed(self, cb):
        async def _run():
            return await cb.is_allowed(company_id=1, provider_id="trans_eu")
        assert asyncio.run(_run()) is True

    def test_allowed_when_no_redis(self, cb_no_redis):
        async def _run():
            return await cb_no_redis.is_allowed(1, "trans_eu")
        assert asyncio.run(_run()) is True

    def test_get_state_returns_closed_by_default(self, cb):
        state = cb.get_state(1, "trans_eu")
        assert state["state"] == CircuitState.CLOSED
        assert state["failures"] == 0

    def test_get_state_no_redis(self, cb_no_redis):
        state = cb_no_redis.get_state(1, "trans_eu")
        assert state["state"] == "unknown"


class TestCircuitBreakerFailureThreshold:
    def test_single_failure_does_not_trip(self, cb):
        cb.record_failure(1, "trans_eu")
        state = cb.get_state(1, "trans_eu")
        assert state["state"] == CircuitState.CLOSED
        assert state["failures"] == 1

    def test_five_failures_trips_to_open(self, cb):
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(1, "trans_eu")
        state = cb.get_state(1, "trans_eu")
        assert state["state"] == CircuitState.OPEN

    def test_blocked_when_open(self, cb):
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(1, "trans_eu")
        async def _run():
            return await cb.is_allowed(1, "trans_eu")
        assert asyncio.run(_run()) is False

    def test_success_resets_failure_count(self, cb):
        for _ in range(3):
            cb.record_failure(1, "trans_eu")
        cb.record_success(1, "trans_eu")
        state = cb.get_state(1, "trans_eu")
        assert state["failures"] == 0
        assert state["state"] == CircuitState.CLOSED


class TestCircuitBreakerRecovery:
    def test_recovery_timeout_transitions_to_half_open(self, cb):
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(1, "trans_eu")
        # Simulate time passing by manually setting tripped_at in the past
        redis = cb._redis
        past = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
        redis.set(f"circuit_breaker:freight:1:trans_eu:tripped_at", past)

        async def _run():
            return await cb.is_allowed(1, "trans_eu")
        assert asyncio.run(_run()) is True  # should be HALF_OPEN
        state = cb.get_state(1, "trans_eu")
        assert state["state"] == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self, cb):
        # Trip the circuit
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(1, "trans_eu")

        # Force HALF_OPEN
        redis = cb._redis
        past = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
        redis.set(f"circuit_breaker:freight:1:trans_eu:tripped_at", past)
        async def _run():
            return await cb.is_allowed(1, "trans_eu")  # transitions to HALF_OPEN
        asyncio.run(_run())

        # Success in HALF_OPEN transitions to CLOSED
        cb.record_success(1, "trans_eu")
        state = cb.get_state(1, "trans_eu")
        assert state["state"] == CircuitState.CLOSED

    def test_admin_reset(self, cb):
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(1, "trans_eu")
        cb.reset(1, "trans_eu")
        state = cb.get_state(1, "trans_eu")
        assert state["state"] == CircuitState.CLOSED
        assert state["failures"] == 0


class TestCircuitBreakerIsolation:
    def test_different_providers_independent(self, cb):
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(1, "trans_eu")
        async def _run1():
            return await cb.is_allowed(1, "timocom")
        async def _run2():
            return await cb.is_allowed(1, "trans_eu")
        assert asyncio.run(_run1()) is True  # timocom unaffected
        assert asyncio.run(_run2()) is False  # trans_eu blocked

    def test_different_companies_independent(self, cb):
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(1, "trans_eu")
        async def _run():
            return await cb.is_allowed(2, "trans_eu")
        assert asyncio.run(_run()) is True  # company 2 unaffected
