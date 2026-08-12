"""Base repository providing shared database access patterns.

Tenant context is read from ``database.tenant_context`` (``contextvars``),
NOT from mutable attributes on the shared ``DatabaseManager`` singleton.
This guarantees that concurrent async requests cannot influence each
other's tenant filters.

Auto-commit is OFF by default (``commit=False``).  Services own transaction
boundaries via the ``transaction()`` context manager.

``Decimal`` parameter values are converted to ``float`` for SQLite (which
does not support Decimal binding) and passed through unchanged for PostgreSQL
(where ``NUMERIC`` columns accept Decimal natively).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from database.tenant_context import (
    get_company_id,
    get_user_role,
    get_scoped as _get_scoped,
)

logger = logging.getLogger("repositories")


def _convert_params(params: tuple) -> tuple:
    """Convert Decimal params to float for SQLite compatibility.

    SQLite's ``sqlite3`` driver does not support ``Decimal`` binding.
    PostgreSQL's ``psycopg2`` handles Decimal natively on ``NUMERIC``
    columns.
    """
    return tuple(
        float(p) if isinstance(p, Decimal) else p
        for p in params
    )


class BaseRepository:
    """Base repository with configurable auto-commit and multi-engine support.

    SQLite (default): ``?`` placeholders, ``lastrowid`` for inserts.
    PostgreSQL: ``%s`` placeholders, ``RETURNING id`` for inserts.
    """

    # Subclasses MUST define COLUMNS as a list of valid column names.
    # This is the allowlist used to prevent SQL injection via column names.
    COLUMNS: list = []

    def __init__(self, db):
        self.db = db

    def _validate_columns(self, data: dict, extra_allowed: Optional[Set[str]] = None, columns: Optional[List[str]] = None) -> None:
        """Reject any key in *data* that is not in *columns* (or ``self.COLUMNS``).

        Raises ``ValueError`` with a clear message listing the invalid keys.
        This prevents SQL injection via malicious column names in
        ``create()`` and ``update()`` methods.
        """
        allowed = set(columns if columns is not None else self.COLUMNS)
        if extra_allowed:
            allowed |= extra_allowed
        invalid = set(data.keys()) - allowed
        if invalid:
            raise ValueError(
                f"Invalid column(s) for {self.__class__.__name__}: "
                f"{', '.join(sorted(invalid))}. "
                f"Allowed columns: {', '.join(sorted(allowed))}"
            )

    @property
    def _user_company_id(self):
        """Return the current tenant-scoped company ID from context."""
        return get_company_id()

    @property
    def _user_role(self):
        """Return the current user's role from context."""
        return get_user_role()

    @property
    def _scoped(self) -> bool:
        """True if the current request is scoped to a non-admin company."""
        return _get_scoped()

    def _company_filter(self, alias: str = "") -> str:
        """Return an SQL fragment ``AND alias.company_id = ?`` (with ``?`` placeholder).

        Returns empty string for admins (who see all tenants).
        """
        if self._scoped:
            prefix = f"{alias}." if alias else ""
            return f"AND {prefix}company_id = ?"
        return ""

    def _company_params(self) -> tuple:
        """Return the parameter tuple for the company filter clause."""
        if self._scoped:
            return (self._user_company_id,)
        return ()

    def _company_filter_for(self, company_id, alias: str = "") -> str:
        """Explicit tenant-scoping fragment for callers that pass company_id.

        The API layer resolves ``company_id`` from the JWT on every request;
        the context-based ``_company_filter`` is not populated in the HTTP
        path.  When ``company_id`` is provided (non-zero) this returns
        ``AND alias.company_id = ?`` so the row/rows are scoped regardless of
        context.  For admin / unscoped callers (``company_id`` 0 or ``None``)
        it falls back to the context filter (admin → no filter, all tenants).
        """
        if company_id:
            prefix = f"{alias}." if alias else ""
            return f"AND {prefix}company_id = ?"
        return self._company_filter(alias)

    def _company_params_for(self, company_id) -> tuple:
        """Parameter tuple matching :meth:`_company_filter_for`."""
        if company_id:
            return (company_id,)
        return self._company_params()

    def _set_company_from_context(self, data: dict) -> dict:
        """Inject the current user's company_id into *data* for INSERT."""
        if self._scoped:
            data["company_id"] = self._user_company_id
        return data

    def _adapt_query(self, query: str) -> str:
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            q = query.replace("?", "%s")
            if "INSERT OR IGNORE INTO" in q:
                q = q.replace("INSERT OR IGNORE INTO", "INSERT INTO")
                if "ON CONFLICT" not in q.upper():
                    q = q.rstrip(";") + " ON CONFLICT DO NOTHING"
            elif "INSERT OR REPLACE INTO" in q:
                q = q.replace("INSERT OR REPLACE INTO", "INSERT INTO")
                if "ON CONFLICT" not in q.upper():
                    import re
                    m = re.match(
                        r"INSERT\s+INTO\s+\w+\s*\(([^)]+)\)\s*VALUES",
                        q, re.IGNORECASE,
                    )
                    if m:
                        cols = [c.strip() for c in m.group(1).split(",")]
                        if cols:
                            conflict_col = cols[0]
                            set_clause = ", ".join(
                                f"{c} = EXCLUDED.{c}" for c in cols
                            )
                            q = q.rstrip(";") + (
                                f" ON CONFLICT ({conflict_col}) DO UPDATE SET {set_clause}"
                            )
            return q
        return query

    def _adapt_insert(self, query: str) -> str:
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            query = query.replace("?", "%s")
            if "RETURNING" not in query.upper():
                query = query.rstrip(";") + " RETURNING id"
        return query

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        q = self._adapt_query(query)
        return self.db.row_to_dict(self.db.execute(q, _convert_params(params)).fetchone())

    def _fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        q = self._adapt_query(query)
        return self.db.rows_to_dicts(self.db.execute(q, _convert_params(params)).fetchall())

    @staticmethod
    def _rollback_if_implicit(conn, was_in_tx: bool) -> None:
        """Roll back a transaction that an aborted DML statement implicitly opened.

        Python's ``sqlite3`` (legacy ``isolation_level=""``) auto-issues
        ``BEGIN`` *before* the first INSERT/UPDATE/DELETE.  When that statement
        then raises (UNIQUE constraint, ``database is locked``, …) the implicit
        transaction stays open and — in WAL mode — the connection keeps the DB
        write lock indefinitely, wedging every other connection's writes.
        Callers that manage their own transaction boundaries (``BEGIN IMMEDIATE``
        / ``transaction()``) started the transaction *before* us (``was_in_tx``),
        so those are left untouched and the caller's own rollback handles them.
        """
        if was_in_tx:
            return
        try:
            if hasattr(conn, "in_transaction") and conn.in_transaction:
                conn.rollback()
        except Exception:
            pass

    def _execute(self, query: str, params: tuple = (), commit: bool = False) -> None:
        """Execute SQL.  Does NOT auto-commit — callers must pass ``commit=True``
        or wrap in ``transaction()`` context manager."""
        q = self._adapt_query(query)
        conn = self.db.conn
        # Strict ``is True``: sqlite3 exposes a real bool, while test doubles
        # (MagicMock) and PostgreSQL connections return truthy/non-bool objects
        # that must NOT be treated as an open transaction.
        was_in_tx = getattr(conn, "in_transaction", None) is True
        try:
            self.db.execute(q, _convert_params(params))
        except Exception:
            # A failed DML inside sqlite's implicit transaction would otherwise
            # leak the WAL write lock on this pooled connection.
            self._rollback_if_implicit(conn, was_in_tx)
            raise
        # Skip the commit when a transaction is already open: the caller owns
        # the commit boundary (``begin_transaction()`` / ``commit_transaction()``
        # or the ``transaction()`` context manager).  Committing per-statement
        # inside an explicit transaction defeats batching (one fsync per row)
        # and silently breaks rollback atomicity.
        if commit and not was_in_tx:
            conn.commit()

    def _execute_insert(self, query: str, params: tuple = (), commit: bool = False) -> int:
        """Execute INSERT.  Does NOT auto-commit."""
        q = self._adapt_insert(query)
        conn = self.db.conn
        was_in_tx = getattr(conn, "in_transaction", None) is True
        try:
            cursor = self.db.execute(q, _convert_params(params))
        except Exception:
            self._rollback_if_implicit(conn, was_in_tx)
            raise
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            row = cursor.fetchone()
            last_id = row["id"] if row else 0
        else:
            last_id = cursor.lastrowid
        if commit and not was_in_tx:
            conn.commit()
        return last_id

    def _execute_with_count(self, query: str, params: tuple = (), commit: bool = False) -> int:
        """Execute SQL and return row count.  Does NOT auto-commit."""
        q = self._adapt_query(query)
        conn = self.db.conn
        was_in_tx = getattr(conn, "in_transaction", None) is True
        try:
            cursor = self.db.execute(q, _convert_params(params))
        except Exception:
            self._rollback_if_implicit(conn, was_in_tx)
            raise
        if commit and not was_in_tx:
            conn.commit()
        return cursor.rowcount

    @contextmanager
    def transaction(self):
        """Context manager for safer transaction management."""
        self.begin_transaction()
        try:
            yield self
            self.commit_transaction()
        except Exception:
            self.rollback_transaction()
            raise

    def begin_transaction(self) -> None:
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            # psycopg2 (autocommit=False) opens transactions implicitly;
            # "BEGIN IMMEDIATE" is SQLite-only syntax and would raise.
            return
        self.db.execute("BEGIN IMMEDIATE")

    def commit_transaction(self) -> None:
        self.db.conn.commit()

    def rollback_transaction(self) -> None:
        self.db.conn.rollback()
