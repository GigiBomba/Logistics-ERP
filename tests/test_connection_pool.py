"""Tests for database.connection_pool — ConnectionPool thread-local SQLite pool.

Covers: initialisation, connection acquisition & properties, thread isolation,
pool lifecycle (close/reset/stale-recycle), context manager, thread safety,
timeout behaviour, error handling, and connection tracking metrics.
"""

from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from database.connection_pool import ConnectionPool


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def pool():
    """Create an in-memory ConnectionPool (auto-closes on cleanup)."""
    with ConnectionPool(":memory:") as p:
        yield p


@pytest.fixture
def file_pool(tmp_path):
    """Create a file-based ConnectionPool (auto-closes on cleanup).

    A real file is needed for tests that rely on journal_mode or write-lock
    contention (e.g. WAL-mode and timeout tests).
    """
    db_file = tmp_path / "connection_pool_test.db"
    with ConnectionPool(str(db_file)) as p:
        yield p


# ── Initialisation ────────────────────────────────────────────────────────


class TestConnectionPoolInit:
    """Pool construction and default / custom parameters."""

    def test_default_params(self):
        pool = ConnectionPool(":memory:")
        try:
            assert pool._db_path == ":memory:"
            assert pool._timeout == 30
            assert pool._generation == 0
            assert not pool._wal_configured
            assert pool._connections == []
        finally:
            pool.close_all()

    def test_custom_timeout(self):
        pool = ConnectionPool(":memory:", timeout=5)
        try:
            assert pool._timeout == 5
        finally:
            pool.close_all()

    def test_custom_db_path(self):
        pool = ConnectionPool("/some/custom/db.sqlite")
        try:
            assert pool._db_path == "/some/custom/db.sqlite"
        finally:
            pool.close_all()


# ── Connection Acquisition ────────────────────────────────────────────────


class TestConnectionAcquisition:
    """Acquiring connections from the pool."""

    def test_get_connection_returns_sqlite3_connection(self, pool):
        conn = pool.conn
        assert isinstance(conn, sqlite3.Connection)

    def test_same_thread_returns_same_object(self, pool):
        conn1 = pool.conn
        conn2 = pool.conn
        assert conn1 is conn2

    def test_different_threads_get_different_connections(self, pool):
        connections: dict[int, sqlite3.Connection] = {}
        errors: list[BaseException] = []
        # Barrier makes all four threads start touching the pool at the same
        # time.  Worker exceptions are collected and reported instead of being
        # silently swallowed by the thread (which made this flaky on loaded
        # CI runners — assert 2 == 4 because threads died before capturing).
        ready = threading.Barrier(4)

        def capture() -> None:
            try:
                ready.wait(timeout=10)
                connections[threading.get_ident()] = pool.conn
            except BaseException as exc:  # noqa: BLE001 — surface, don't swallow
                errors.append(exc)

        threads = [threading.Thread(target=capture) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"worker thread(s) failed: {errors}"
        assert len(connections) == 4
        # All returned objects are distinct
        assert len({id(c) for c in connections.values()}) == 4
        # None should be None
        assert all(c is not None for c in connections.values())


# ── Connection Properties ────────────────────────────────────────────────


class TestConnectionProperties:
    """Verify connections have the expected configuration applied."""

    def test_row_factory_is_sqlite3_row(self, pool):
        conn = pool.conn
        assert conn.row_factory is sqlite3.Row

    def test_row_factory_enables_dict_like_access(self, pool):
        conn = pool.conn
        conn.execute("CREATE TABLE IF NOT EXISTS person (name, age)")
        conn.execute("INSERT INTO person VALUES ('Alice', 30)")
        row = conn.execute("SELECT * FROM person").fetchone()
        assert dict(row) == {"name": "Alice", "age": 30}

    def test_foreign_keys_pragma_enabled(self, pool):
        conn = pool.conn
        (fk_enabled,) = conn.execute("PRAGMA foreign_keys").fetchone()
        assert fk_enabled == 1

    def test_wal_mode_on_file_database(self, file_pool):
        """WAL journal mode is configured on first connection."""
        conn = file_pool.conn
        (mode,) = conn.execute("PRAGMA journal_mode").fetchone()
        assert mode.upper() == "WAL"


# ── Connection Validity ──────────────────────────────────────────────────


class TestConnectionValidity:
    """Connections are alive and usable."""

    def test_connection_is_alive(self, pool):
        conn = pool.conn
        (result,) = conn.execute("SELECT 1").fetchone()
        assert result == 1

    def test_create_tables_and_query(self, pool):
        conn = pool.conn
        conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO items VALUES (1, 'hello')")
        conn.commit()
        rows = conn.execute("SELECT val FROM items ORDER BY id").fetchall()
        assert [r["val"] for r in rows] == ["hello"]


# ── Pool Lifecycle (close / reset / generation) ──────────────────────────


class TestPoolLifecycle:
    """Pool cleanup, close, reset, and stale-connection recycling."""

    def test_close_all_closes_connections(self, pool):
        conn = pool.conn
        pool.close_all()
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_close_all_resets_internal_state(self, pool):
        pool.conn
        pool.close_all()
        assert pool._connections == []
        assert pool._generation == 1  # incremented

    def test_close_all_multiple_calls_are_idempotent(self, pool):
        pool.close_all()
        pool.close_all()  # should not raise
        pool.close_all()  # should not raise

    def test_conn_after_close_all_creates_fresh_connection(self, pool):
        conn1 = pool.conn
        pool.close_all()
        conn2 = pool.conn
        assert conn1 is not conn2
        conn2.execute("SELECT 1")  # fresh connection is usable

    def test_stale_connection_is_recycled(self, pool):
        """When another thread calls close_all(), this thread's cached
        connection becomes stale and is replaced on next ``.conn`` access."""
        conn1 = pool.conn
        pool.close_all()
        # The current thread still has _local.conn = conn1, but the
        # generation has advanced, so the next access should recreate.
        conn2 = pool.conn
        assert conn1 is not conn2
        # conn1 should now be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn1.execute("SELECT 1")


# ── Context Manager ──────────────────────────────────────────────────────


class TestContextManager:
    """Context-manager support (``with pool:``)."""

    def test_enter_returns_pool_instance(self):
        with ConnectionPool(":memory:") as pool:
            assert isinstance(pool, ConnectionPool)

    def test_exit_closes_all_connections(self):
        with ConnectionPool(":memory:") as pool:
            conn = pool.conn
            conn.execute("SELECT 1")
        # After exit, the connection should be closed.
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


# ── Thread Safety ────────────────────────────────────────────────────────


class TestThreadSafety:
    """Concurrent access from multiple threads is safe."""

    def test_concurrent_conn_access(self):
        """Many threads can acquire their own connection simultaneously."""
        pool = ConnectionPool(":memory:")
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker() -> None:
            try:
                c = pool.conn
                c.execute("SELECT 1")
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        pool.close_all()
        assert errors == []

    def test_concurrent_close_all_during_access(self):
        """close_all() can be called while other threads are using .conn.

        This test exercises the generation mechanism: threads with stale
        connections simply create new ones on the next access.
        """
        pool = ConnectionPool(":memory:")
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(5):
                try:
                    c = pool.conn
                    c.execute("SELECT 1")
                    with lock:
                        results.append("ok")
                except Exception:
                    with lock:
                        results.append("err")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()

        # Issue close_all() multiple times while workers run
        for _ in range(3):
            pool.close_all()
            time.sleep(0.02)

        for t in threads:
            t.join(timeout=5)

        pool.close_all()
        # Most accesses should succeed; the generation mechanism handles
        # concurrent close_all gracefully.
        assert results.count("err") < len(results) // 2


# ── Timeout Behaviour ────────────────────────────────────────────────────


class TestTimeoutBehaviour:
    """Pool timeout passed to sqlite3.connect behaves correctly."""

    def test_timeout_parameter_stored(self):
        pool = ConnectionPool(":memory:", timeout=7)
        try:
            assert pool._timeout == 7
        finally:
            pool.close_all()

    def test_lock_contention_raises_timeout(self, tmp_path):
        """When two threads contend for a write lock, the second thread
        receives an OperationalError after the configured timeout."""
        db_file = str(tmp_path / "locktest.db")
        pool = ConnectionPool(db_file, timeout=1)

        lock_held = threading.Event()
        got_timeout = threading.Event()

        def hold_write_lock() -> None:
            conn = pool.conn
            conn.execute("CREATE TABLE IF NOT EXISTS t (x INTEGER)")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO t VALUES (1)")
            lock_held.set()          # signal that lock is taken
            time.sleep(5)            # keep holding it
            conn.execute("COMMIT")

        def contend_write() -> None:
            conn = pool.conn
            assert lock_held.wait(timeout=10), "lock_held event not set"
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT INTO t VALUES (2)")
            except sqlite3.OperationalError:
                got_timeout.set()

        t1 = threading.Thread(target=hold_write_lock, daemon=True)
        t2 = threading.Thread(target=contend_write, daemon=True)

        t1.start()
        time.sleep(0.2)  # give t1 a head start to acquire the lock
        t2.start()
        t2.join(timeout=15)
        pool.close_all()
        t1.join(timeout=10)

        assert got_timeout.is_set(), (
            "Expected sqlite3.OperationalError due to timeout"
        )


# ── Error Handling ───────────────────────────────────────────────────────


class TestErrorHandling:
    """Error conditions and edge cases."""

    def test_invalid_db_path_raises_operational_error(self, tmp_path):
        pool = ConnectionPool(str(tmp_path / "nonexistent" / "db.sqlite"))
        with pytest.raises(sqlite3.OperationalError):
            _ = pool.conn
        pool.close_all()

    def test_execute_on_closed_connection_raises(self, pool):
        conn = pool.conn
        pool.close_all()
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


# ── Statistics / Connection Tracking ─────────────────────────────────────


class TestPoolMetrics:
    """Pool tracks the number of live connections."""

    def test_tracks_connections_from_main_thread(self, pool):
        pool.conn
        assert len(pool._connections) == 1

    def test_tracks_connections_from_multiple_threads(self, pool):
        """Each thread's ``.conn`` access appends to the shared list."""

        def touch() -> None:
            pool.conn

        threads = [threading.Thread(target=touch) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(pool._connections) == 5

    def test_close_all_clears_tracking_list(self, pool):
        pool.conn
        pool.close_all()
        assert len(pool._connections) == 0


# ── Max Connections Enforcement ─────────────────────────────────────────


class TestMaxConnections:
    """Pool does not cap connections — each thread creates its own.

    These tests document that the pool grows unbounded with threads and
    verify that every distinct thread can acquire its own connection.
    """

    def test_pool_grows_with_thread_count(self):
        pool = ConnectionPool(":memory:")
        n_threads = 12

        def touch() -> None:
            pool.conn

        threads = [threading.Thread(target=touch) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(pool._connections) == n_threads
        pool.close_all()

    def test_each_thread_connection_is_independent(self):
        """Threads get independent database sessions.

        With ``:memory:`` SQLite, each :func:`sqlite3.connect` call creates a
        *private* in-memory database, so data written by one thread is
        invisible to others — proving isolation.
        """
        pool = ConnectionPool(":memory:")
        per_thread_data: dict[int, list[tuple]] = {}
        lock = threading.Lock()

        def worker(tid: int) -> None:
            conn = pool.conn
            conn.execute("CREATE TABLE IF NOT EXISTS isolated (tid INTEGER, payload TEXT)")
            conn.execute("INSERT INTO isolated VALUES (?, ?)", (tid, f"data-{tid}"))
            conn.commit()
            rows = conn.execute("SELECT payload FROM isolated WHERE tid = ?", (tid,)).fetchall()
            with lock:
                per_thread_data[tid] = [(r["payload"],) for r in rows]

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        pool.close_all()

        # Each thread should see its own data
        for i in range(3):
            assert per_thread_data[i] == [(f"data-{i}",)]


# ══════════════════════════════════════════════════════════════════════
#  PostgresConnectionPool
# ══════════════════════════════════════════════════════════════════════

from unittest.mock import MagicMock, patch

# These tests mock psycopg2 so no real PostgreSQL connection is needed.
# Each test patches database.connection_pool.psycopg2 before importing
# PostgresConnectionPool to avoid import-time side effects.


_PSYCOPG2_PATCHED: list[str] = []


def _patch_psycopg2():
    """Install mock psycopg2 modules into sys.modules.

    connection_pool.py uses ``import psycopg2`` / ``import psycopg2.pool``
    / ``import psycopg2.extras`` inside its methods.  We install mocks
    at the ``sys.modules`` level so those imports grab our mocks.
    """
    import sys

    mock_psycopg2 = MagicMock()
    mock_pool = MagicMock()
    mock_extras = MagicMock()

    mock_psycopg2.pool = mock_pool
    mock_psycopg2.extras = mock_extras

    # Track what we've added so _unpatch_psycopg2 can clean up
    _PSYCOPG2_PATCHED.clear()
    for key in ("psycopg2", "psycopg2.pool", "psycopg2.extras"):
        if key not in sys.modules:
            _PSYCOPG2_PATCHED.append(key)
        sys.modules[key] = {
            "psycopg2": mock_psycopg2,
            "psycopg2.pool": mock_pool,
            "psycopg2.extras": mock_extras,
        }[key]

    return mock_pool, mock_extras


def _unpatch_psycopg2():
    """Remove mock psycopg2 entries we added to sys.modules."""
    import sys

    for key in _PSYCOPG2_PATCHED:
        sys.modules.pop(key, None)
    _PSYCOPG2_PATCHED.clear()


# ── PostgresConnectionPool Initialisation ──────────────────────────────


class TestPostgresPoolInit:
    """Pool construction and configuration."""

    def test_default_params(self):
        """Default min=2, max=20."""
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://user:pass@localhost/db")
            try:
                assert pool._min == 2
                assert pool._max == 20
                assert pool._dsn == "postgresql://user:pass@localhost/db"
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_custom_min_max(self):
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool(
                "postgresql://u:p@h/d", min_connections=5, max_connections=50,
            )
            try:
                assert pool._min == 5
                assert pool._max == 50
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_initializes_pool_on_construction(self):
        """The pool is created in __init__ via _initialize()."""
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                mock_pool_mod.ThreadedConnectionPool.assert_called_once_with(
                    pool._min, pool._max, pool._dsn,
                )
                assert pool._pool is not None
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_init_failure_raises(self):
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            mock_pool_mod.ThreadedConnectionPool.side_effect = Exception("connection refused")
            with pytest.raises(Exception, match="connection refused"):
                PostgresConnectionPool("postgresql://u:p@h/d")
        finally:
            _unpatch_psycopg2()

    def test_dsn_passed_correctly(self):
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            dsn = "postgresql://operion:operion@localhost:5432/operion"
            pool = PostgresConnectionPool(dsn)
            try:
                mock_pool_mod.ThreadedConnectionPool.assert_called_once()
                call_args = mock_pool_mod.ThreadedConnectionPool.call_args
                assert call_args[0][2] == dsn, (
                    f"DSN mismatch: expected {dsn}, got {call_args[0][2]}"
                )
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()


# ── Connection Management ──────────────────────────────────────────────


class TestPostgresConnectionManagement:
    """Acquire, release, and cache connections."""

    def test_get_connection_returns_connection(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                conn = pool.get_connection()
                assert conn is not None
                assert conn.autocommit is False
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_get_connection_sets_cursor_factory(self):
        _pool_mod, mock_extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                conn = pool.get_connection()
                assert conn.cursor_factory == mock_extras.RealDictCursor
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_return_connection_puts_back(self):
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                conn = pool.get_connection()
                pool.return_connection(conn)
                pool_inst = mock_pool_mod.ThreadedConnectionPool.return_value
                pool_inst.putconn.assert_called_with(conn)
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_get_cached_connection_returns_same(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                conn1 = pool.get_cached_connection()
                conn2 = pool.get_cached_connection()
                assert conn1 is conn2, "Cached connections should be the same object"
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_get_cached_connection_isolation(self):
        """Different threads get different cached connections."""
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            pool_inst = mock_pool_mod.ThreadedConnectionPool.return_value
            # Return a unique MagicMock per call to simulate distinct connections
            pool_inst.getconn.side_effect = lambda: MagicMock()

            connections: dict[int, object] = {}
            errors: list[BaseException] = []
            # Barrier + error collection: worker exceptions were silently
            # swallowed before, making this flaky on loaded CI runners.
            ready = threading.Barrier(3)
            lock = threading.Lock()

            def worker() -> None:
                try:
                    ready.wait(timeout=10)
                    c = pool.get_cached_connection()
                    with lock:
                        connections[threading.get_ident()] = c
                except BaseException as exc:  # noqa: BLE001 — surface, don't swallow
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            pool.close_all()
            assert not errors, f"worker thread(s) failed: {errors}"
            assert len({id(c) for c in connections.values()}) == 3, (
                "Each thread should get a distinct cached connection"
            )
        finally:
            _unpatch_psycopg2()

    def test_return_connection_handles_none(self):
        """return_connection(None) should not raise."""
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                pool.return_connection(None)  # should not raise
                pool.return_connection(None)  # twice
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_get_connection_after_close_all_raises(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            pool.close_all()
            with pytest.raises(RuntimeError, match="not initialized"):
                pool.get_connection()
        finally:
            _unpatch_psycopg2()


# ── Pool Exhaustion ────────────────────────────────────────────────────


class TestPostgresPoolExhaustion:
    """Behaviour when pool reaches max connections."""

    def test_getconn_raises_when_exhausted(self):
        """When pool.getconn() raises, the error propagates."""
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                pool_inst = mock_pool_mod.ThreadedConnectionPool.return_value
                pool_inst.getconn.side_effect = Exception("pool exhausted")
                with pytest.raises(Exception, match="pool exhausted"):
                    pool.get_connection()
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_get_cached_connection_raises_when_exhausted(self):
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                pool_inst = mock_pool_mod.ThreadedConnectionPool.return_value
                pool_inst.getconn.side_effect = Exception("Too many connections")
                with pytest.raises(Exception, match="Too many connections"):
                    pool.get_cached_connection()
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_return_connection_frees_slot(self):
        """After returning a connection, getconn can succeed again."""
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                pool_inst = mock_pool_mod.ThreadedConnectionPool.return_value
                mock_conn = MagicMock()
                mock_conn2 = MagicMock()
                pool_inst.getconn.side_effect = [mock_conn, mock_conn2]

                conn = pool.get_connection()
                pool.return_connection(conn)
                pool_inst.putconn.assert_called_with(conn)

                # After returning a connection, a new one should be obtainable
                conn2 = pool.get_connection()
                assert conn2 is not None
                assert conn2 is mock_conn2
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()


# ── Empty Pool Handling ────────────────────────────────────────────────


class TestPostgresEmptyPool:
    """Operations when pool is closed or not initialised."""

    def test_get_connection_after_close(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            pool.close_all()
            with pytest.raises(RuntimeError, match="not initialized"):
                pool.get_connection()
        finally:
            _unpatch_psycopg2()

    def test_get_cached_connection_after_close(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            pool.close_all()
            with pytest.raises(RuntimeError, match="not initialized"):
                pool.get_cached_connection()
        finally:
            _unpatch_psycopg2()

    def test_close_all_on_empty_pool(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            pool.close_all()
            # Second close_all should be safe
            pool.close_all()
            pool.close_all()  # third call also safe
        finally:
            _unpatch_psycopg2()

    def test_return_connection_to_closed_pool(self):
        """Returning a connection after pool is closed is safe."""
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            conn = pool.get_connection()
            pool.close_all()
            pool.return_connection(conn)  # should not raise (pool is None)
        finally:
            _unpatch_psycopg2()

    def test_close_all_returns_cached_connections(self):
        """close_all returns the current thread's cached connection to pool."""
        mock_pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            pool_inst = mock_pool_mod.ThreadedConnectionPool.return_value

            conn = pool.get_cached_connection()
            pool.close_all()

            # The cached connection should have been returned to the pool
            pool_inst.putconn.assert_called_with(conn)
        finally:
            _unpatch_psycopg2()


# ── Thread Safety ──────────────────────────────────────────────────────


class TestPostgresThreadSafety:
    """Concurrent access from multiple threads is safe."""

    def test_concurrent_get_connection(self):
        """Multiple threads can get connections concurrently."""
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            errors: list[Exception] = []
            lock = threading.Lock()

            def worker() -> None:
                try:
                    c = pool.get_connection()
                    assert c is not None
                    pool.return_connection(c)
                except Exception as exc:
                    with lock:
                        errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            pool.close_all()
            assert errors == [], f"Concurrent get_connection raised: {errors}"
        finally:
            _unpatch_psycopg2()

    def test_concurrent_get_cached_connection(self):
        """Multiple threads can get and reuse cached connections."""
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            results: list[str] = []
            lock = threading.Lock()

            def worker() -> None:
                for _ in range(3):
                    try:
                        c = pool.get_cached_connection()
                        assert c is not None
                        with lock:
                            results.append("ok")
                    except Exception:
                        with lock:
                            results.append("err")

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            pool.close_all()
            assert "err" not in results, (
                "Errors occurred in cached connection access"
            )
        finally:
            _unpatch_psycopg2()

    def test_concurrent_close_all(self):
        """close_all can be called while threads use get_connection."""
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")

            def worker() -> None:
                for _ in range(5):
                    try:
                        c = pool.get_connection()
                        pool.return_connection(c)
                    except Exception:
                        pass

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()

            for _ in range(3):
                pool.close_all()
                time.sleep(0.02)

            for t in threads:
                t.join(timeout=5)

            # After final close_all, pool should be None
            assert pool._pool is None
        finally:
            _unpatch_psycopg2()


# ── Statistics ─────────────────────────────────────────────────────────


class TestPostgresStats:
    """Pool statistics reporting."""

    def test_stats_active(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            try:
                stats = pool.stats
                assert stats["min"] == 2
                assert stats["max"] == 20
                assert stats["status"] == "active"
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()

    def test_stats_inactive_after_close(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool("postgresql://u:p@h/d")
            pool.close_all()
            stats = pool.stats
            assert stats["status"] == "inactive"
            assert stats["min"] == 0
            assert stats["max"] == 0
        finally:
            _unpatch_psycopg2()

    def test_stats_after_custom_config(self):
        _pool_mod, _extras = _patch_psycopg2()
        try:
            from database.connection_pool import PostgresConnectionPool

            pool = PostgresConnectionPool(
                "postgresql://u:p@h/d", min_connections=5, max_connections=100,
            )
            try:
                stats = pool.stats
                assert stats["min"] == 5
                assert stats["max"] == 100
            finally:
                pool.close_all()
        finally:
            _unpatch_psycopg2()
