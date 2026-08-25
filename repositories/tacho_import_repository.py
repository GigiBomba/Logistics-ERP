"""Tacho import repository."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class TachoImportRepository(BaseRepository):
    TABLE = "tacho_imports"
    COLUMNS = [
        "id", "imported_at", "file_name", "file_type", "file_hash",
        "truck_id", "driver_id", "parse_status", "raw_json", "notes", "company_id",
    ]

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def get_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE file_hash = ? {self._company_filter()} ORDER BY id DESC LIMIT 1",
            (file_hash,) + self._company_params(),
        )

    def get_recent(self, limit: int = 50, company_id=None) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()} ORDER BY imported_at DESC LIMIT ?",
            self._company_params() + (limit,),
        )

    def get_by_id(self, import_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (import_id,) + self._company_params(),
        )
