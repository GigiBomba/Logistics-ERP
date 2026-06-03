"""Tacho driver activity repository."""
from typing import Any, Dict, List, Optional
from datetime import date

from repositories import BaseRepository


class TachoDriverActivityRepository(BaseRepository):
    TABLE = "tacho_driver_activity"

    def create(self, data: Dict[str, Any]) -> int:
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_by_driver(self, driver_id: int, from_date: date) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? AND activity_date >= ? ORDER BY activity_date DESC",
            (driver_id, from_date.isoformat()),
        )

    def get_by_import(self, import_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE import_id = ? ORDER BY activity_date",
            (import_id,),
        )

    def delete_by_import(self, import_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE import_id = ?", (import_id,)
        )
