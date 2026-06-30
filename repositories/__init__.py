"""Base repository providing shared database access patterns."""
import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger("repositories")


class BaseRepository:
    """Base repository with configurable auto-commit.

    Most read operations are auto-committed by the ``ConnectionPool``
    WAL mode.  Write operations default to auto-commit but callers can
    pass ``commit=False`` to defer the commit until a batch is done.
    """

    def __init__(self, db):
        self.db = db

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        return self.db.row_to_dict(self.db.conn.execute(query, params).fetchone())

    def _fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        return self.db.rows_to_dicts(self.db.conn.execute(query, params).fetchall())

    def _execute(self, query: str, params: tuple = (), commit: bool = True) -> None:
        self.db.conn.execute(query, params)
        if commit:
            self.db.conn.commit()

    def _execute_insert(self, query: str, params: tuple = (), commit: bool = True) -> int:
        cursor = self.db.conn.execute(query, params)
        if commit:
            self.db.conn.commit()
        return cursor.lastrowid

    def begin_transaction(self) -> None:
        self.db.conn.execute("BEGIN")

    def commit_transaction(self) -> None:
        self.db.conn.commit()

    def rollback_transaction(self) -> None:
        self.db.conn.rollback()
