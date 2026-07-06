"""Tacho import repository."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class TachoImportRepository(BaseRepository):
    TABLE = "tacho_imports"

    def create(self, data: Dict[str, Any]) -> int:
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE file_hash = ? ORDER BY id DESC LIMIT 1",
            (file_hash,),
        )

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} ORDER BY imported_at DESC LIMIT ?",
            (limit,),
        )

    def get_by_id(self, import_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (import_id,)
        )
