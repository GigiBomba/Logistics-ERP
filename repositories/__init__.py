"""Base repository providing shared database access patterns."""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("repositories")


class BaseRepository:
    """Base repository with configurable auto-commit and multi-engine support.

    SQLite (default): ``?`` placeholders, ``lastrowid`` for inserts.
    PostgreSQL: ``%s`` placeholders, ``RETURNING id`` for inserts.
    """

    def __init__(self, db):
        self.db = db

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
