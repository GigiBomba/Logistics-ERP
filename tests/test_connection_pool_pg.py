"""Integration tests for PostgresConnectionPool against a running PostgreSQL.

These tests require a running PostgreSQL instance at the DSN specified by
``OPERION_TEST_POSTGRES_DSN`` (defaults to the per-file isolated
``operion_test_pool`` database).  All tests are skipped if PG is unreachable.

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
    "postgresql://operion:operion_test_ci@localhost:5432/operion_test_pool",
)

#: Per-file isolated database name — this module owns ``operion_test_pool`` so
#: it never contends with other test files' DDL on the shared ``operion_test``
#: database (xdist `-n 2` concurrent runs).
_TEST_DB_NAME = "operion_test_pool"

#: Admin DSN: connect to the always-existing ``operion_test`` database so the
#: (superuser) ``operion`` role can issue CREATE/DROP DATABASE for the
#: per-file database above.
_BASE_DSN = "postgresql://operion:operion_test_ci@localhost:5432/operion_test"


def _ensure_test_db() -> None:
    """Create the per-file test database (idempotent; superuser required).

    No-op when ``OPERION_TEST_POSTGRES_DSN`` is set explicitly — the caller
    pointed us at a database of their choosing, and we must not touch it.
    """
    if os.environ.get("OPERION_TEST_POSTGRES_DSN"):
        return
    import psycopg2
    from psycopg2 import sql as pgsql

    try:
        conn = psycopg2.connect(_BASE_DSN)
        conn.autocommit = True  # CREATE DATABASE cannot run inside a transaction
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_TEST_DB_NAME,))
        if not cur.fetchone():
            cur.execute(
                pgsql.SQL("CREATE DATABASE {}").format(pgsql.Identifier(_TEST_DB_NAME))
            )
        cur.close()
        conn.close()
    except Exception:
        # Best-effort: the DB may already exist (idempotent) or PG may be
        # unreachable (the module-level guard below skips).
        pass


def _drop_test_db() -> None:
    """Drop the per-file test database at module teardown (best-effort)."""
    if os.environ.get("OPERION_TEST_POSTGRES_DSN"):
        return
    import psycopg2
    from psycopg2 import sql as pgsql

    try:
        conn = psycopg2.connect(_BASE_DSN)
        conn.autocommit = True
        cur = conn.cursor()
        # Never force-kill another session's connections — if any remain,
        # leave the DB in place (mirrors tests/integration/conftest.py).
        cur.execute(
            "SELECT COUNT(*) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (_TEST_DB_NAME,),
        )
        row = cur.fetchone()
        other_sessions = (row[0] if row else 0) or 0
        if not other_sessions:
            cur.execute(
                pgsql.SQL("DROP DATABASE IF EXISTS {}").format(
                    pgsql.Identifier(_TEST_DB_NAME)
                )
            )
        cur.close()
        conn.close()
    except Exception:
        pass  # a failed drop must not fail tests


@pytest.fixture(scope="module", autouse=True)
def _per_file_test_db():
    """Drop the per-file database after this module's tests finish."""
    yield
    _drop_test_db()


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


# Module-level check: create the per-file DB first (pg_reachable() below
# would skip if the database does not exist yet), then skip if PG is
# unreachable.
_ensure_test_db()
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
