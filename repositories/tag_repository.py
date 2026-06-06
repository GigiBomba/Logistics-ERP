"""Tag repository — CRUD for client_tags table."""
from typing import Any, Dict, List

from repositories import BaseRepository


class TagRepository(BaseRepository):
    TABLE = "client_tags"

    def get_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE client_id = ? ORDER BY tag ASC",
            (client_id,),
        )

    def add(self, client_id: int, tag: str) -> None:
        from sqlite3 import IntegrityError
        try:
            self._execute(
                f"INSERT INTO {self.TABLE} (client_id, tag) VALUES (?, ?)",
                (client_id, tag.strip()),
            )
        except IntegrityError:
            pass

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
