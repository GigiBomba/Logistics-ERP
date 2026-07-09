"""Concurrency tests: cache locking and starvation for analytics, routes, and geocoding."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.concurrency


class TestConcurrencyCacheLock:
    """Concurrency tests for cache lock behaviour in various services."""

    @pytest.fixture
    def db(self):
        return make_db()

    # ── test 1: Analytics lock starvation ──────────────────────────────

    def test_analytics_lock_starvation(self, db):
        """10 writer threads (invalidate) + 5 reader threads — verify readers complete within 30s."""
        from services.analytics_service import AnalyticsService

        svc = AnalyticsService(db)

        # Pre-populate cache to give readers something to find
        svc._caches[("financial", (None, None))] = (
            [{"month": "2026-01", "revenue": 1000}], time.time(), (None, None),
        )
        svc._caches[("fleet", (None, None))] = (
            [{"truck": "T1", "profit": 500}], time.time(), (None, None),
        )
        svc._caches[("client", (None, None))] = (
            [{"client": "C1", "revenue": 2000}], time.time(), (None, None),
        )

        reader_completed = threading.Event()
        reader_errors = []
        writer_errors = []
        lock = threading.Lock()

        def reader_thread():
            try:
                for _ in range(200):
                    svc.get_financial()
                    svc.get_fleet()
                    svc.get_client_analytics()
                    time.sleep(0.001)
                reader_completed.set()
            except Exception as e:
                with lock:
                    reader_errors.append(str(e))
                    reader_completed.set()

        def writer_thread():
            try:
                for _ in range(100):
                    svc.invalidate()
                    time.sleep(0.002)
            except Exception as e:
                with lock:
                    writer_errors.append(str(e))

        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=15) as pool:
            readers = [pool.submit(reader_thread) for _ in range(5)]
            writers = [pool.submit(writer_thread) for _ in range(10)]
            all_futs = readers + writers
            for fut in as_completed(all_futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        writer_errors.append(str(e))

        elapsed = time.monotonic() - start

        assert len(reader_errors) == 0, f"Reader errors: {reader_errors}"
        assert len(writer_errors) == 0, f"Writer errors: {writer_errors}"
        assert elapsed < 30.0, (
            f"Readers took {elapsed:.2f}s to complete (expected < 30s)"
        )

    # ── test 2: Route cache concurrent hit/miss ────────────────────────

    def test_route_cache_concurrent_hit_miss(self):
        """50 threads requesting same route calculation with 100ms mock — verify at most 1 GH call."""
        from services.route_service import RouteCache

        cache = RouteCache(max_size=100, ttl_seconds=3600)
        gh_call_count = 0
        gh_call_lock = threading.Lock()

        points = [(52.52, 13.40), (48.85, 2.35)]
        profile = "truck"

        def mock_graphhopper_call():
            with gh_call_lock:
                nonlocal gh_call_count
                gh_call_count += 1
            time.sleep(0.1)  # simulate GH API call
            return {"distance": 878000, "time": 28800, "bbox": [13.4, 48.85, 52.52, 2.35]}

        def request_route():
            return cache.get_or_compute(points, profile, mock_graphhopper_call)

        with ThreadPoolExecutor(max_workers=50) as pool:
            futs = [pool.submit(request_route) for _ in range(50)]
            for fut in as_completed(futs):
                fut.result()

        # With get_or_compute (atomic check-then-set under per-key lock),
        # only 1 thread should compute; all others get the cached result.
        assert gh_call_count <= 1, (
            f"Expected at most 1 GraphHopper call, got {gh_call_count}"
        )

    # ── test 3: Geocode cache concurrent eviction ──────────────────────

    def test_geocode_cache_concurrent_eviction(self):
        """200 threads geocoding different addresses — verify cache size <= max_size."""
        from services.route_service import GeocodeCache

        cache = GeocodeCache(max_size=50, ttl_seconds=3600)

        errors = []
        lock = threading.Lock()

        def geocode(address_idx: int):
            try:
                address = f"{address_idx} Some Street, City, Country"
                result = cache.get(address)
                if result is None:
                    # Simulate geocoding result
                    coords = (48.0 + address_idx * 0.01, 2.0 + address_idx * 0.01)
                    cache.set(address, coords)
            except Exception as e:
                with lock:
                    errors.append((address_idx, str(e)))

        with ThreadPoolExecutor(max_workers=200) as pool:
            futs = [pool.submit(geocode, i) for i in range(200)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Geocode cache errors: {errors}"
        assert len(cache._cache) <= cache.max_size, (
            f"Cache size {len(cache._cache)} exceeds max_size {cache.max_size}"
        )
