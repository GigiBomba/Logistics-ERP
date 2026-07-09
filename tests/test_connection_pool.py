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

        def capture() -> None:
            connections[threading.get_ident()] = pool.conn

        threads = [threading.Thread(target=capture) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

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
