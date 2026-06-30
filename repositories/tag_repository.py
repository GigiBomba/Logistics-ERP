"""Tag repository — CRUD for client_tags table."""
import logging
import sqlite3
from typing import Any, Dict, List

from repositories import BaseRepository

logger = logging.getLogger(__name__)


class TagRepository(BaseRepository):
    TABLE = "client_tags"

    def get_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE client_id = ? ORDER BY tag ASC",
            (client_id,),
        )

    def add(self, client_id: int, tag: str) -> None:
        try:
            self._execute(
                f"INSERT INTO {self.TABLE} (client_id, tag) VALUES (?, ?)",
                (client_id, tag.strip()),
            )
        except sqlite3.IntegrityError:
            logger.debug("Tag already exists for client %d: %s", client_id, tag)

    def remove(self, client_id: int, tag: str) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE client_id = ? AND tag = ?",
            (client_id, tag.strip()),
        )

    def get_all_tags(self) -> List[str]:
        rows = self._fetchall(f"SELECT DISTINCT tag FROM {self.TABLE} ORDER BY tag ASC")
        return [r["tag"] for r in rows]

    def get_clients_by_tag(self, tag: str) -> List[int]:
        rows = self._fetchall(
            f"SELECT client_id FROM {self.TABLE} WHERE tag = ?", (tag.strip(),)
        )
        return [r["client_id"] for r in rows]
