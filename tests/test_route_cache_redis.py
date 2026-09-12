"""Tests for the optional cross-worker (Redis) route/geocode cache mirror.

The RouteCache/GeocodeCache in ``services.route_service`` keep their in-memory
fast path as the primary storage and optionally mirror values to a shared Redis
so multiple uvicorn workers (compose.prod.yaml runs ``--workers 4``) don't
re-issue redundant GraphHopper/Nominatim calls.

Two invariants are exercised here:

1. **Multi-tenant isolation** — every Redis key embeds the current company id
   (``operion:route:{company_id}:{md5}`` / ``operion:geocode:{company_id}:{addr}``),
   so two companies never share an entry.
2. **Graceful degradation** — when Redis is down/unconfigured the caches fall
   back to byte-identical in-memory-only behaviour (desktop single-process
   deployment is unaffected).
"""
from __future__ import annotations

import unittest
from unittest import mock

import pytest

from database.tenant_context import clear_context, set_company_context
from services.route_service import GeocodeCache, RouteCache


class FakeRedisCache:
    """In-memory stand-in for ``backend.cache.RedisCache`` (the shared mirror).

    Two worker cache instances sharing one ``FakeRedisCache`` simulate two
    uvicorn workers sharing one real Redis.
    """

    def __init__(self):
        self._store = {}
        self._locks = {}
        self.is_enabled = True
        self.written_keys = []

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ttl=None):
        self._store[key] = value
        self.written_keys.append(key)

    def acquire_lock(self, key, ttl):
        if key in self._locks:
            return None
        self._locks[key] = "token"
        return "token"

    def release_lock(self, key, token):
        if self._locks.get(key) == token:
            del self._locks[key]


POINTS = [(48.8566, 2.3522), (44.4268, 26.1025)]
ROUTE_RESULT = {"distance_km": 123.0, "geometry": [[1.0, 2.0], [3.0, 4.0]]}


@pytest.fixture(autouse=True)
def _clean_tenant_context():
    yield
    clear_context()


class TestRouteCacheRedisSharing:
    def test_value_written_by_one_worker_read_by_another(self):
        """Two instances sharing a Redis mirror share route values (worker A -> B)."""
        fake = FakeRedisCache()  # the shared Redis
        worker1 = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        worker2 = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)  # empty in-memory
        set_company_context(7)
        worker1.set(POINTS, "truck", dict(ROUTE_RESULT))
        # worker2's in-memory is empty but reads the value from the shared Redis.
        assert worker2.get(POINTS, "truck") == ROUTE_RESULT

    def test_geocode_written_by_one_worker_read_by_another(self):
        fake = FakeRedisCache()
        w1 = GeocodeCache(max_size=10, ttl_seconds=604800, redis=fake)
        w2 = GeocodeCache(max_size=10, ttl_seconds=604800, redis=fake)
        set_company_context(3)
        w1.set("Paris", (48.8566, 2.3522))
        assert w2.get("Paris") == (48.8566, 2.3522)

    def test_compute_not_invoked_when_redis_has_value(self):
        """get_or_compute_shared must NOT call compute_fn when Redis has the value."""
        fake = FakeRedisCache()
        set_company_context(9)
        worker1 = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        worker2 = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        worker1.set(POINTS, "truck", dict(ROUTE_RESULT))

        calls = []

        def compute():
            calls.append(1)
            return {"distance_km": 999.0}

        value, from_cache = worker2.get_or_compute_shared(POINTS, "truck", compute)
        assert calls == []  # compute_fn was NOT invoked
        assert from_cache is True
        assert value == ROUTE_RESULT

    def test_redis_lock_prevents_cross_worker_stampede(self):
        """While one worker holds the compute lock, another bounded-waits and
        does not compute redundantly once the value is published."""
        fake = FakeRedisCache()
        set_company_context(11)
        worker1 = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        worker2 = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)

        key = worker1._make_key(POINTS, "truck")
        lock_key = worker1._redis_key(key, "route-lock")
        value_key = worker1._redis_key(key, "route")
        # Worker1 claims the cross-worker compute lock.
        assert fake.acquire_lock(lock_key, ttl=60) == "token"

        calls = []

        def compute():
            calls.append(1)
            return dict(ROUTE_RESULT)

        import threading

        def publish():
            # Simulate worker1 finishing its compute and publishing to Redis.
            # NOTE: the Redis key/lock strings are captured in the main thread —
            # contextvars do NOT propagate to the spawned thread, so computing
            # them inside publish would yield a company-less (None) key.
            fake.set(value_key, dict(ROUTE_RESULT), ttl=3600)
            fake.release_lock(lock_key, "token")

        t = threading.Thread(target=publish)
        t.start()
        value, from_cache = worker2.get_or_compute_shared(
            POINTS, "truck", compute, lock_wait=5.0
        )
        t.join()
        # worker2 saw the published value (from_cache True) and did not compute.
        assert calls == []
        assert from_cache is True
        assert value == ROUTE_RESULT


class TestCompanyScopedKeys:
    def test_company_scoped_keys_differ_between_companies(self):
        """Two companies must never map to the same Redis key."""
        fake = FakeRedisCache()
        cache = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        local = cache._make_key(POINTS, "truck")

        set_company_context(1)
        key_c1 = cache._redis_key(local, "route")
        set_company_context(2)
        key_c2 = cache._redis_key(local, "route")

        assert key_c1 != key_c2
        assert "1" in key_c1 and "2" in key_c2
        assert key_c1.startswith("operion:route:1:")
        assert key_c2.startswith("operion:route:2:")

    def test_geocode_keys_are_company_scoped(self):
        fake = FakeRedisCache()
        g = GeocodeCache(max_size=10, ttl_seconds=604800, redis=fake)
        set_company_context(1)
        k1 = g._redis_key("Paris")
        set_company_context(2)
        k2 = g._redis_key("Paris")
        assert k1 != k2
        assert k1 == "operion:geocode:1:Paris"
        assert k2 == "operion:geocode:2:Paris"

    def test_company_a_cannot_read_company_b_value(self):
        """Cross-tenant reads must miss: company B never sees company A's entry.

        Uses two separate worker instances (company A and company B) sharing one
        Redis mirror. The in-memory cache is intentionally left non-company
        scoped (byte-identical desktop behaviour), so isolation is enforced at
        the shared Redis key level — a fresh worker for company B must miss.
        """
        fake = FakeRedisCache()
        worker_a = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        worker_b = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        set_company_context(1)
        worker_a.set(POINTS, "truck", dict(ROUTE_RESULT))
        set_company_context(2)
        # worker_b has empty in-memory; reads Redis under company 2's key -> miss
        assert worker_b.get(POINTS, "truck") is None

    def test_no_company_context_never_shares(self):
        """Without a company context the mirror is skipped (safety guard)."""
        fake = FakeRedisCache()
        cache = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        clear_context()
        assert cache._redis_ready() is False
        # get/set still work purely in-memory and never touch Redis.
        cache.set(POINTS, "truck", dict(ROUTE_RESULT))
        assert cache.get(POINTS, "truck") == ROUTE_RESULT
        assert fake.written_keys == []


class TestRedisDownFallback:
    def test_redis_client_raising_degrades_to_in_memory(self):
        """If the Redis client raises, the cache must silently fall back to
        in-memory-only (no crash, compute still runs)."""

        class RaisingRedis(FakeRedisCache):
            def get(self, key):
                raise RuntimeError("connection refused")

            def set(self, key, value, ttl=None):
                raise RuntimeError("connection refused")

            def acquire_lock(self, key, ttl):
                raise RuntimeError("connection refused")

            def release_lock(self, key, token):
                raise RuntimeError("connection refused")

        set_company_context(4)
        cache = RouteCache(max_size=10, ttl_seconds=3600, redis=RaisingRedis())

        # get with Redis down -> in-memory miss -> None
        assert cache.get(POINTS, "truck") is None
        # set with Redis down must not raise and still populate in-memory
        cache.set(POINTS, "truck", dict(ROUTE_RESULT))
        assert cache.get(POINTS, "truck") == ROUTE_RESULT

        # get_or_compute_shared with Redis down computes (falls back)
        calls = []

        def compute():
            calls.append(1)
            return {"distance_km": 7.0}

        value, from_cache = cache.get_or_compute_shared(
            [(1.0, 2.0), (3.0, 4.0)], "truck", compute
        )
        assert calls == [1]
        assert from_cache is False
        assert value == {"distance_km": 7.0}

    def test_redis_disabled_degrades_to_in_memory(self):
        """is_enabled == False (Redis unreachable at connect) -> in-memory only."""
        fake = FakeRedisCache()
        fake.is_enabled = False
        set_company_context(5)
        cache = RouteCache(max_size=10, ttl_seconds=3600, redis=fake)
        assert cache._redis_ready() is False
        cache.set(POINTS, "truck", dict(ROUTE_RESULT))
        assert cache.get(POINTS, "truck") == ROUTE_RESULT
        assert fake.written_keys == []

    def test_no_redis_mirror_preserves_byte_identical_in_memory(self):
        """Default construction (no Redis) keeps the original in-memory behaviour."""
        cache = RouteCache(max_size=10, ttl_seconds=3600)  # redis=None
        assert cache._redis is None
        assert cache.get(POINTS, "truck") is None
        cache.set(POINTS, "truck", dict(ROUTE_RESULT))
        assert cache.get(POINTS, "truck") == ROUTE_RESULT


if __name__ == "__main__":
    unittest.main()
