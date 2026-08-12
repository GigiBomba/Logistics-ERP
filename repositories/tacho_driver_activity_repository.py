"""Tacho driver activity repository."""
from datetime import date
from typing import Any, Dict, List

from repositories import BaseRepository

class TachoDriverActivityRepository(BaseRepository):
    TABLE = "tacho_driver_activity"
    COLUMNS = [
        "id", "import_id", "driver_id", "activity_date", "driving_minutes",
        "work_minutes", "rest_minutes", "avail_minutes", "distance_km",
        "violations", "country_codes", "company_id",
    ]

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def get_by_driver(self, driver_id: int, date_from: date) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? AND activity_date >= ? {self._company_filter()} ORDER BY activity_date DESC",
            (driver_id, date_from.isoformat()) + self._company_params(),
        )

    def get_by_import(self, import_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE import_id = ? {self._company_filter()} ORDER BY activity_date",
            (import_id,) + self._company_params(),
        )

    def delete_by_import(self, import_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE import_id = ? {self._company_filter()}",
            (import_id,) + self._company_params(),
        )
