"""Tag repository — CRUD for client_tags table."""
import logging
from typing import Any, Dict, List

from repositories import BaseRepository

logger = logging.getLogger(__name__)


class TagRepository(BaseRepository):
    TABLE = "client_tags"
    COLUMNS = ["id", "client_id", "tag", "company_id"]

    def get_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE client_id = ? {self._company_filter()} ORDER BY tag ASC",
            (client_id,) + self._company_params(),
        )

    def add(self, client_id: int, tag: str) -> None:
        try:
            data = {"client_id": client_id, "tag": tag.strip()}
            self._validate_columns(data, extra_allowed={"company_id"})
            data = self._set_company_from_context(data)
            cols = ", ".join(data.keys())
            vals = ", ".join("?" for _ in data)
            self._execute(
                f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
                tuple(data.values()),
            )
        except Exception:
            logger.debug("Tag already exists for client %d: %s", client_id, tag)

    def remove(self, client_id: int, tag: str) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE client_id = ? AND tag = ? {self._company_filter()}",
            (client_id, tag.strip()) + self._company_params(),
        )

    def get_all_tags(self) -> List[str]:
        rows = self._fetchall(
            f"SELECT DISTINCT tag FROM {self.TABLE} WHERE 1=1 {self._company_filter()} ORDER BY tag ASC",
            self._company_params(),
        )
        return [r["tag"] for r in rows]

    def get_clients_by_tag(self, tag: str) -> List[int]:
        rows = self._fetchall(
            f"SELECT client_id FROM {self.TABLE} WHERE tag = ? {self._company_filter()}",
            (tag.strip(),) + self._company_params(),
        )
        return [r["client_id"] for r in rows]
