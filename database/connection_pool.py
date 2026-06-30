"""Thread-local SQLite connections to eliminate write contention.

Each thread gets its own ``sqlite3.Connection`` so that writes on one
thread never block reads or writes on another.  WAL journal mode is
enabled so readers and writers can proceed concurrently.

Usage (via DatabaseManager)::

    db = DatabaseManager("data/cashflow.db")
    db.conn.execute("SELECT 1")   # main thread
    # ... in a worker thread ...
    db.conn.execute("SELECT 2")   # same API, different connection
"""

from __future__ import annotations

import sqlite3
import threading
from typing import Optional


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

    # ── Public API ────────────────────────────────────────────────────────

    def __enter__(self) -> ConnectionPool:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close_all()

    @property
    def conn(self) -> sqlite3.Connection:
        """Return the current thread's connection (create if missing)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            c = sqlite3.connect(
                self._db_path,
                timeout=self._timeout,
                check_same_thread=True,
            )
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            # Set WAL journal mode once on the first connection;
            # subsequent connections inherit it from the database file.
            if not self._wal_configured:
                c.execute("PRAGMA journal_mode=WAL")
                self._wal_configured = True
            self._local.conn = c
            with self._lock:
                self._connections.append(c)
        return self._local.conn

    def close_all(self) -> None:
        """Close every connection managed by this pool.

        Safe to call multiple times.  Intended for app shutdown.
        """
        with self._lock:
            for c in self._connections:
                try:
                    c.close()
                except Exception:
                    pass
            self._connections.clear()
        # Clear the current thread's reference so ``conn`` will
        # re-create if called after shutdown.
        if hasattr(self._local, "conn"):
            try:
                self._local.conn = None
            except Exception:
                pass
