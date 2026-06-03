"""Base repository providing shared database access patterns."""
import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger("repositories")


class BaseRepository:
    def __init__(self, db):
        self.db = db

    def _fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        return self.db.row_to_dict(self.db.conn.execute(query, params).fetchone())

    def _fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        return self.db.rows_to_dicts(self.db.conn.execute(query, params).fetchall())

    def _execute(self, query: str, params: tuple = ()) -> None:
        self.db.conn.execute(query, params)
        self.db.conn.commit()

    def _execute_insert(self, query: str, params: tuple = ()) -> int:
        cursor = self.db.conn.execute(query, params)
        self.db.conn.commit()
        return cursor.lastrowid
