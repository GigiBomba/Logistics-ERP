"""Stress tests: analytics cache stampede and lock contention."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


class TestStressCacheStampede:
    """Stress tests for AnalyticsService in-memory cache under high concurrency."""

    @pytest.fixture
    def db(self):
        return make_db()

    @pytest.fixture
    def analytics_service(self, db):
        from services.analytics_service import AnalyticsService
        svc = AnalyticsService(db)
        # Reduce TTL so tests don't wait forever
        svc.CACHE_TTL = 60.0
        return svc

    def _mock_db_slow(self, delay: float = 0.1):
        """Return a mock DB whose execute calls sleep *delay* seconds."""
        mock_db = MagicMock()
        mock_db.row_to_dict.return_value = None
        mock_db.rows_to_dicts.return_value = []
        real_execute = mock_db.conn.execute
        real_execute.side_effect = lambda *a, **kw: (
            time.sleep(delay) or MagicMock()
        )
        return mock_db

    # ── test 1: Analytics cache stampede — 100 concurrent identical requests ──

    def test_analytics_cache_stampede(self, analytics_service):
        """100 threads calling the same cache key — verify no duplicate computation."""
        call_count = 0
        call_lock = threading.Lock()

        def counting_get_financial(*args, **kwargs):
            with call_lock:
                nonlocal call_count
                call_count += 1
            time.sleep(0.05)  # simulate DB delay
            return {"revenue": 100000}  # canned value — no real DB access needed

        analytics_service._repo.get_financial_analytics = counting_get_financial

        def call_financial():
            return analytics_service.get_financial()

        with ThreadPoolExecutor(max_workers=100) as pool:
            futs = [pool.submit(call_financial) for _ in range(100)]
            for fut in as_completed(futs):
                fut.result()  # propagate exceptions

        # Only the first thread should have hit the DB; subsequent use cache
        assert call_count <= 1, (
            f"Analytics computation called {call_count} times (expected <= 1)"
        )

    # ── test 2: Analytics cache stampede mixed keys — 5 different cache keys ──

    def test_analytics_cache_stampede_mixed_keys(self, analytics_service):
        """50 threads mixing 5 different cache keys — verify no duplicate computation per key."""
        call_counts: dict[str, int] = {}
        call_lock = threading.Lock()

        def make_counter(key_name):
            def wrapper(*args, **kwargs):
                with call_lock:
                    call_counts[key_name] = call_counts.get(key_name, 0) + 1
                time.sleep(0.05)
                return {}  # canned value — no real DB access needed
            return wrapper

        analytics_service._repo.get_financial_analytics = make_counter("financial")
        analytics_service._repo.get_fleet_analytics = make_counter("fleet")
        analytics_service._repo.get_client_analytics = make_counter("client")
        analytics_service._repo.get_driver_analytics = make_counter("driver")
        analytics_service._repo.get_route_profitability = make_counter("route")

        endpoints = [
            analytics_service.get_financial,
            analytics_service.get_fleet,
            analytics_service.get_client_analytics,
            analytics_service.get_driver,
            analytics_service.get_route_profitability,
        ]

        def call_random():
            import random
            fn = random.choice(endpoints)
            return fn()

        with ThreadPoolExecutor(max_workers=50) as pool:
            futs = [pool.submit(call_random) for _ in range(50)]
            for fut in as_completed(futs):
                fut.result()

        # Each key should have been computed at most once
        for key, count in call_counts.items():
            assert count <= 1, (
                f"Cache key '{key}' computed {count} times (expected <= 1)"
            )

    # ── test 3: Cache lock contention — 200 threads different endpoints ──

    def test_cache_lock_contention(self, analytics_service):
        """200 threads calling different analytics endpoints simultaneously.

        Verify all complete without deadlock and each key is computed at most once.
        """
        call_counts: dict[str, int] = {}
        call_lock = threading.Lock()

        def make_counter(key_name):
            def wrapper(*args, **kwargs):
                with call_lock:
                    call_counts[key_name] = call_counts.get(key_name, 0) + 1
                time.sleep(0.03)
                return {}  # canned value — no real DB access needed
            return wrapper

        analytics_service._repo.get_financial_analytics = make_counter("financial")
        analytics_service._repo.get_fleet_analytics = make_counter("fleet")
        analytics_service._repo.get_client_analytics = make_counter("client")
        analytics_service._repo.get_driver_analytics = make_counter("driver")
        analytics_service._repo.get_route_profitability = make_counter("route")
        analytics_service._repo.get_maintenance_alerts = make_counter("maint")
        analytics_service._repo.get_document_analytics = make_counter("docs")
        analytics_service._repo.get_truck_utilization = make_counter("truck_util")

        endpoints = [
            analytics_service.get_financial,
            analytics_service.get_fleet,
            analytics_service.get_client_analytics,
            analytics_service.get_driver,
            analytics_service.get_route_profitability,
            analytics_service.get_maintenance_alerts,
            analytics_service.get_document,
            analytics_service.get_truck_utilization,
        ]

        def call_endpoint():
            import random
            fn = random.choice(endpoints)
            return fn()

        with ThreadPoolExecutor(max_workers=200) as pool:
            futs = [pool.submit(call_endpoint) for _ in range(200)]
            for fut in as_completed(futs):
                fut.result()

        # Verify each key computed at most once
        for key, count in call_counts.items():
            assert count <= 1, (
                f"Cache key '{key}' computed {count} times under contention (expected <= 1)"
            )
