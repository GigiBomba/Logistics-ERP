"""Base repository providing shared database access patterns."""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("repositories")


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

    def _validate_columns(self, data: dict, extra_allowed: set = None) -> None:
        """Reject any key in *data* that is not in self.COLUMNS.

        Raises ``ValueError`` with a clear message listing the invalid keys.
        This prevents SQL injection via malicious column names in
        ``create()`` and ``update()`` methods.
        """
        allowed = set(self.COLUMNS)
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
        return getattr(self.db, "user_company_id", None)

    @property
    def _user_role(self):
        return getattr(self.db, "user_role", "")

    @property
    def _scoped(self) -> bool:
        """True if the current request is scoped to a non-admin company."""
        cid = self._user_company_id
        return cid is not None and self._user_role != "admin"

    def _company_filter(self, alias: str = "") -> str:
        """Return an SQL fragment ``AND alias.company_id = ?`` (with ``?`` placeholder).

        Returns empty string for admins (who see all tenants).

        Usage::

            clause = self._company_filter("t")
            params = self._company_params()
            self._fetchall(f"SELECT * FROM trips t WHERE t.id = ? {clause}", (tid,) + params)
        """
        if self._scoped:
            prefix = f"{alias}." if alias else ""
            return f"AND {prefix}company_id = ?"
        return ""

    def _company_params(self) -> tuple:
        """Return the parameter tuple for the company filter clause.

        Returns ``(company_id,)`` for scoped users, ``()`` for admins.
        """
        if self._scoped:
            return (self._user_company_id,)
        return ()

    def _set_company_from_context(self, data: dict) -> dict:
        """Inject the current user's company_id into *data* for INSERT.

        For admin users (no company scope), ``company_id`` is not injected
        — the caller must provide it explicitly.
        """
        if self._scoped:
            data["company_id"] = self._user_company_id
        return data

    def _adapt_query(self, query: str) -> str:
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            return query.replace("?", "%s")
        return query

    def _adapt_insert(self, query: str) -> str:
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            query = query.replace("?", "%s")
            if "RETURNING" not in query.upper():
                query = query.rstrip(";") + " RETURNING id"
        return query

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        q = self._adapt_query(query)
        return self.db.row_to_dict(self.db.conn.execute(q, params).fetchone())

    def _fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        q = self._adapt_query(query)
        return self.db.rows_to_dicts(self.db.conn.execute(q, params).fetchall())

    def _execute(self, query: str, params: tuple = (), commit: bool = True) -> None:
        q = self._adapt_query(query)
        self.db.conn.execute(q, params)
        if commit:
            self.db.conn.commit()

    def _execute_insert(self, query: str, params: tuple = (), commit: bool = True) -> int:
        q = self._adapt_insert(query)
        cursor = self.db.conn.execute(q, params)
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            row = cursor.fetchone()
            last_id = row["id"] if row else 0
        else:
            last_id = cursor.lastrowid
        if commit:
            self.db.conn.commit()
        return last_id

    def _execute_with_count(self, query: str, params: tuple = (), commit: bool = True) -> int:
        q = self._adapt_query(query)
        cursor = self.db.conn.execute(q, params)
        if commit:
            self.db.conn.commit()
        return cursor.rowcount

    def begin_transaction(self) -> None:
        self.db.conn.execute("BEGIN")

    def commit_transaction(self) -> None:
        self.db.conn.commit()

    def rollback_transaction(self) -> None:
        self.db.conn.execute("ROLLBACK")
