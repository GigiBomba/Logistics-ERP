"""Stress tests: database connection pool under route calculation load."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


class TestStressConnectionPool:
    """Stress tests for ConnectionPool behaviour under heavy route calculation."""

    @pytest.fixture
    def db(self):
        return make_db()

    @pytest.fixture
    def mock_route_service(self):
        """Create a mock RouteService that simulates a 200ms calculation delay."""
        svc = MagicMock()
        svc.calculate_route.side_effect = lambda *a, **kw: (
            time.sleep(0.2) or {"distance_km": 500, "duration_h": 5, "polyline": "mock"}
        )
        return svc

    # ── test 1: Route calc connection pool stress (200 threads, 200ms delay) ──

    def test_route_calc_connection_pool_stress(self, db, mock_route_service):
        """200 threads calling route calculation with 200ms mock delay.

        Each thread should get its own thread-local connection from the pool.
        Verify no exceptions, no deadlocks, and all threads complete.
        """
        from database.connection_pool import ConnectionPool

        pool = ConnectionPool(":memory:")
        errors = []
        results = []
        lock = threading.Lock()

        def calc_route(thread_id: int):
            try:
                conn = pool.conn
                conn.execute("SELECT 1")  # verify connection works
                result = mock_route_service.calculate_route(
                    points=[(52.52, 13.40), (48.85, 2.35)],
                    profile="truck",
                )
                with lock:
                    results.append((thread_id, result))
            except Exception as e:
                with lock:
                    errors.append((thread_id, e))

        with ThreadPoolExecutor(max_workers=200) as executor:
            futs = [executor.submit(calc_route, i) for i in range(200)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    errors.append(("pool_submit", e))

        pool.close_all()

        assert len(errors) == 0, (
            f"route_calc_connection_pool_stress: {len(errors)} errors occurred: {errors[:3]}"
        )
        assert len(results) == 200, (
            f"Expected 200 results, got {len(results)}"
        )

    # ── test 2: Pool exhaustion recovery ────────────────────────────────

    def test_route_calc_pool_exhaustion_recovery(self, db, mock_route_service):
        """300 threads, then 10 more after a pause — verify second batch succeeds."""
        from database.connection_pool import ConnectionPool

        pool = ConnectionPool(":memory:")
        first_batch_errors = []
        second_batch_errors = []
        second_batch_results = []
        lock = threading.Lock()

        def heavy_task(_id: int, duration: float = 0.3):
            try:
                conn = pool.conn
                conn.execute("SELECT 1")
                time.sleep(duration)
                return _id
            except Exception as e:
                with lock:
                    first_batch_errors.append((_id, e))
                return None

        # First batch: 300 threads
        with ThreadPoolExecutor(max_workers=300) as executor:
            futs = [executor.submit(heavy_task, i, 0.3) for i in range(300)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        first_batch_errors.append(("submit", e))

        # Small pause to let pool settle
        time.sleep(0.5)

        # Second batch: 10 threads — should all succeed
        def light_task(_id: int):
            try:
                conn = pool.conn
                conn.execute("SELECT 1")
                with lock:
                    second_batch_results.append(_id)
                return _id
            except Exception as e:
                with lock:
                    second_batch_errors.append((_id, e))
                return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futs = [executor.submit(light_task, 300 + i) for i in range(10)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        second_batch_errors.append(("submit", e))

        pool.close_all()

        assert len(second_batch_errors) == 0, (
            f"pool_exhaustion_recovery: {len(second_batch_errors)} errors in second batch: "
            f"{second_batch_errors[:3]}"
        )
        assert len(second_batch_results) == 10, (
            f"Expected 10 results in second batch, got {len(second_batch_results)}"
        )
