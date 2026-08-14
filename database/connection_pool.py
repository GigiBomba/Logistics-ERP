"""Thread-local SQLite connections and PostgreSQL connection pool.

SQLite — Each thread gets its own ``sqlite3.Connection`` so that writes on one
thread never block reads or writes on another.  WAL journal mode is
enabled so readers and writers can proceed concurrently.

PostgreSQL — ``PostgresConnectionPool`` wraps
``psycopg2.pool.ThreadedConnectionPool`` to provide a thread-safe
pool of PostgreSQL connections for multi-worker deployments.

Usage (via DatabaseManager)::

    db = DatabaseManager("data/cashflow.db")
    db.conn.execute("SELECT 1")   # main thread
    # ... in a worker thread ...
    db.conn.execute("SELECT 2")   # same API, different connection
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from time import perf_counter
from typing import TYPE_CHECKING, Iterator, Optional

if TYPE_CHECKING:
    from psycopg2.pool import ThreadedConnectionPool

from prometheus_client import Counter, Gauge, Histogram

# Pool metrics
pool_active = Gauge("db_pool_active_connections", "Active DB connections", ["pool_name"])
pool_idle = Gauge("db_pool_idle_connections", "Idle DB connections", ["pool_name"])
pool_max = Gauge("db_pool_max_connections", "Max DB connections", ["pool_name"])
pool_min = Gauge("db_pool_min_connections", "Min DB connections", ["pool_name"])

# Performance metrics
checkout_duration = Histogram(
    "db_checkout_duration_seconds", "Time to get connection from pool",
    buckets=[.001, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5],
)
tx_duration = Histogram(
    "db_transaction_duration_seconds", "Transaction duration",
    buckets=[.001, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30],
)
query_count = Counter("db_queries_total", "Total SQL queries executed", ["engine"])
query_errors = Counter("db_query_errors_total", "SQL query errors", ["engine"])

logger = logging.getLogger(__name__)

class ConnectionPool:
    """Per-thread :class:`sqlite3.Connection` pool.

    Every call to :attr:`conn` returns the calling thread's dedicated
    connection, creating it on first access.  Connections are configured
    with WAL journal mode, row factory, and foreign keys enabled.
    """

    def __init__(self, db_path: str, timeout: int = 30) -> None:
        self._db_path = db_path
        self._timeout = timeout
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._lock = threading.Lock()
        # WAL mode is set on the first connection's conn property access.
        # Concurrent connections inherit it from the database file.
        self._wal_configured = False
        # Incremented on close_all(); threads with a stale generation
        # detect that their cached connection was closed by another thread.
        self._generation = 0

    # ── Public API ────────────────────────────────────────────────────────

    def __enter__(self) -> ConnectionPool:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close_all()

    @property
    def conn(self) -> sqlite3.Connection:
        """Return the current thread's connection (create if missing)."""
        if (
            not hasattr(self._local, "conn")
            or self._local.conn is None
            or getattr(self._local, "_pool_gen", 0) != self._generation
        ):
            c = sqlite3.connect(
                self._db_path,
                timeout=self._timeout,
                check_same_thread=True,
            )
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            # Switching a database to WAL mode needs an exclusive lock — two
            # threads creating their first connection concurrently would both
            # run the PRAGMA and one would die with "database is locked".
            # Serialise it; later connections inherit WAL from the file.
            if not self._wal_configured:
                with self._lock:
                    if not self._wal_configured:
                        c.execute("PRAGMA journal_mode=WAL")
                        self._wal_configured = True
            self._local.conn = c
            self._local._pool_gen = self._generation
            with self._lock:
                self._connections.append(c)
        return self._local.conn

    def close_all(self) -> None:
        """Close every connection managed by this pool.

        Safe to call multiple times.  Intended for app shutdown.
        After calling, the pool is reset and future ``.conn`` accesses
        create fresh connections.
        """
        with self._lock:
            for c in self._connections:
                try:
                    c.close()
                except Exception:
                    pass
            self._connections.clear()
        # Clear thread-local references in the current thread so
        # the next ``.conn`` access creates a new connection.
        # Other threads that had connections will detect stale
        # references via ``.conn`` checking ``_generation``.
        try:
            del self._local.conn
        except AttributeError:
            pass
        self._generation += 1


class PostgresConnectionPool:
    """Thread-safe PostgreSQL connection pool.

    Wraps ``psycopg2.pool.ThreadedConnectionPool`` to provide
    connection pooling for PostgreSQL in multi-worker deployments.

    The pool maintains a set of reusable connections, reducing the
    overhead of establishing a new connection for every request.
    """

    def __init__(
        self,
        dsn: str,
        min_connections: int = 2,
        max_connections: int = 20,
    ) -> None:
        self._dsn = dsn
        self._pool: Optional["ThreadedConnectionPool"] = None
        self._min = min_connections
        self._max = max_connections
        self._local = threading.local()
        self._initialize()

    def _initialize(self) -> None:
        """Create the connection pool."""
        import psycopg2
        import psycopg2.pool

        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                self._min, self._max, self._dsn,
            )
            logger.info(
                "PostgreSQL pool created: min=%d max=%d dsn=%s",
                self._min, self._max, self._dsn.replace("password=", "password=*** "),
            )
            self.update_pool_stats()
        except Exception as e:
            logger.error("Failed to create PostgreSQL pool: %s", e)
            raise

    # ── Prometheus metrics ──────────────────────────────────────────

    @contextmanager
    def record_checkout(self) -> Iterator[None]:
        """Context manager that records the duration of a pool checkout."""
        start = perf_counter()
        try:
            yield
        finally:
            checkout_duration.observe(perf_counter() - start)

    @contextmanager
    def checkout_time(self) -> Iterator[None]:
        """Context manager that records ``get_connection()`` call duration.

        Wraps ``get_connection()`` so callers can time the checkout::

            with pool.checkout_time():
                conn = pool.get_connection()
        """
        with self.record_checkout():
            yield

    def record_query(self, engine: str = "postgresql") -> None:
        """Increment the total query counter."""
        query_count.labels(engine=engine).inc()

    def record_error(self, engine: str = "postgresql") -> None:
        """Increment the query error counter."""
        query_errors.labels(engine=engine).inc()

    def update_pool_stats(self) -> None:
        """Set pool capacity gauges from current configuration.

        :attr:`pool_active` and :attr:`pool_idle` are best-effort since
        ``psycopg2.pool.ThreadedConnectionPool`` does not expose those
        counts directly — they are reported as 0 / unavailable.
        """
        pool_min.labels(pool_name="postgresql").set(self._min)
        pool_max.labels(pool_name="postgresql").set(self._max)
        # ThreadedConnectionPool does not expose active/idle counts,
        # so we leave those at 0 (default).

    def get_connection(self):
        """Get a connection from the pool (uncached, one-time borrow).

        Each call obtains a *new* connection from the pool.  Callers
        **must** return it via :meth:`return_connection` when done,
        preferably using the :meth:`_borrow_connection` context manager
        on ``DatabaseManager``.

        For the common case where a thread reuses the same connection
        (the ``conn`` property pattern), use :meth:`get_cached_connection`.
        """
        if not self._pool:
            raise RuntimeError("Connection pool not initialized")
        conn = self._pool.getconn()
        conn.autocommit = False
        import psycopg2.extras
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def get_cached_connection(self):
        """Get the current thread's cached connection from the pool.

        On first access, obtains a new connection and caches it in
        thread-local storage.  Subsequent calls return the same
        connection without touching the pool.
        """
        if not self._pool:
            raise RuntimeError("Connection pool not initialized")
        if (
            not hasattr(self._local, "conn")
            or self._local.conn is None
        ):
            conn = self._pool.getconn()
            conn.autocommit = False
            import psycopg2.extras
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            self._local.conn = conn
        else:
            # Self-heal: a failed statement leaves the implicit transaction
            # aborted (InFailedSqlTransaction); roll back so the cached
            # connection is usable for the next request instead of failing
            # every subsequent statement on this thread.
            cached = self._local.conn
            try:
                import psycopg2.extensions
                if cached.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
                    cached.rollback()
                    logger.info("PostgreSQL cached connection rolled back (aborted transaction)")
            except Exception:
                pass
        return self._local.conn

    def return_connection(self, conn) -> None:
        """Return a borrowed connection to the pool.

        Use this to return connections obtained via :meth:`get_connection`.
        Connections obtained via :meth:`get_cached_connection` should
        **not** be returned individually — they are returned when
        :meth:`close_all` is called.
        """
        if self._pool and conn:
            try:
                self._pool.putconn(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def close_all(self) -> None:
        """Close all connections in the pool.

        Safe to call multiple times.  Intended for app shutdown.
        Returns all cached thread-local connections to the pool
        before closing.
        """
        if self._pool:
            # Return the current thread's cached connection first
            if hasattr(self._local, "conn") and self._local.conn is not None:
                try:
                    self._pool.putconn(self._local.conn)
                except Exception:
                    try:
                        self._local.conn.close()
                    except Exception:
                        pass
                self._local.conn = None
            try:
                self._pool.closeall()
                logger.info("PostgreSQL pool closed")
            except Exception as e:
                logger.warning("Error closing PostgreSQL pool: %s", e)
            finally:
                self._pool = None

    def health_check(self) -> bool:
        """Check if the database is reachable by executing a simple query.

        Returns ``True`` if PostgreSQL responds to ``SELECT 1``,
        ``False`` otherwise.
        """
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return True
        except Exception:
            return False
        finally:
            if conn is not None:
                try:
                    self.return_connection(conn)
                except Exception:
                    pass

    @property
    def stats(self) -> dict:
        """Return pool statistics."""
        if not self._pool:
            return {"min": 0, "max": 0, "used": 0, "status": "inactive"}
        # ThreadedConnectionPool doesn't expose usage stats directly
        return {
            "min": self._min,
            "max": self._max,
            "status": "active",
        }
