"""Integration tests for PostgresConnectionPool against a running PostgreSQL.

These tests require a running PostgreSQL instance at the DSN specified by
``OPERION_TEST_POSTGRES_DSN`` (defaults to ``tests/test_config.py``'s
``TEST_POSTGRES_DSN``).  All tests are skipped if PG is unreachable.

Mark with ``@pytest.mark.postgresql``.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator

import psycopg2
import pytest

from database.connection_pool import PostgresConnectionPool

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEST_POSTGRES_DSN = os.environ.get(
    "OPERION_TEST_POSTGRES_DSN",
    "postgresql://operion:operion_test_ci@localhost:5432/operion_test",
)


def pg_reachable(dsn: str = TEST_POSTGRES_DSN) -> bool:
    """Return ``True`` if PostgreSQL responds to a connection attempt."""
    try:
        conn = psycopg2.connect(dsn, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pool():
    """Create a small PostgresConnectionPool and tear it down after the test."""
    p = PostgresConnectionPool(
        TEST_POSTGRES_DSN,
        min_connections=1,
        max_connections=2,
    )
    yield p
    p.close_all()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.postgresql
class TestPostgresConnectionPool:
    """Integration tests for PostgresConnectionPool."""

    def test_pool_init_and_close(self):
        """Connect to running PG, check out a connection, verify it works, return it."""
        pool = PostgresConnectionPool(
            TEST_POSTGRES_DSN,
            min_connections=1,
            max_connections=2,
        )
        try:
            conn = pool.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1 AS result")
            row = cur.fetchone()
            assert row is not None
            assert row["result"] == 1  # type: ignore[index]
            cur.close()
            pool.return_connection(conn)
        finally:
            pool.close_all()

    def test_pool_health_check(self, pool):
        """Verify that health_check() returns True when PG is reachable."""
        assert pool.health_check() is True

    def test_pool_max_connections(self, pool):
        """Verify we can check out up to max_connections connections."""
        conns = []
        try:
            for _ in range(2):  # pool is configured with max_connections=2
                c = pool.get_connection()
                cur = c.cursor()
                cur.execute("SELECT 1")
                assert cur.fetchone() is not None
                cur.close()
                conns.append(c)
            # Both connections should work independently
            assert len(conns) == 2
        finally:
            for c in conns:
                pool.return_connection(c)

    def test_pool_multiple_connections(self):
        """Check out multiple connections simultaneously — each executes independently."""
        pool = PostgresConnectionPool(
            TEST_POSTGRES_DSN,
            min_connections=1,
            max_connections=4,
        )
        results: list[tuple[int, int]] = []
        errors: list[tuple[int, Exception]] = []
        lock = threading.Lock()

        def worker(thread_id: int) -> None:
            try:
                conn = pool.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT %s AS val", (thread_id,))
                row = cur.fetchone()
                cur.close()
                pool.return_connection(conn)
                with lock:
                    results.append((thread_id, row["val"]))  # type: ignore[index]
            except Exception as e:
                with lock:
                    errors.append((thread_id, e))

        workers = 4
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futs = [executor.submit(worker, i) for i in range(workers)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(("submit", e))

        pool.close_all()
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == workers
        # Every thread should have correctly received its own id back
        for tid, val in results:
            assert val == tid, f"Thread {tid} got value {val}"


# ---------------------------------------------------------------------------
# Module-level skip-if-unreachable guard
# ---------------------------------------------------------------------------


def pytest_configure() -> None:
    """Register the ``postgresql`` marker if running standalone."""
    pass


def pytest_report_header() -> list[str]:
    return [f"PostgreSQL DSN: {TEST_POSTGRES_DSN}"]


# Module-level check: skip all tests if PG is unreachable
if not pg_reachable():
    pytest.skip(
        f"PostgreSQL is not reachable at {TEST_POSTGRES_DSN} — "
        f"skipping all tests in {__name__}",
        allow_module_level=True,
    )

# psycopg2.pool may be unavailable in some installs — the pool wraps
# ThreadedConnectionPool, so skip the module rather than fail at import.
try:
    import psycopg2.pool  # noqa: F401
except Exception:
    pytest.skip(
        "psycopg2.pool is unavailable — skipping PostgreSQL pool tests",
        allow_module_level=True,
    )
