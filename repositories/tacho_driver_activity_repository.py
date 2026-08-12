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
        # ``tacho_driver_activity`` has NO ``company_id`` column in the base
        # schema (database/schema.py ``TABLE_TACHO_DRIVER_ACTIVITY``), so
        # ``company_id`` is injected ONLY when a scoped deployment actually
        # has the column (detected at runtime) — otherwise the INSERT would
        # fail in production, exactly like the ``get_by_driver`` company-filter
        # bug fixed in Phase 1C.  Rows are import/driver-scoped; callers
        # company-verify the driver first.
        self._validate_columns(data)
        if self._scoped and self._has_column("company_id"):
            data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def _has_column(self, column: str) -> bool:
        """Return True if the table has *column* (runtime schema detection)."""
        try:
            cols = [r[1] for r in self.db.conn.execute(
                f"PRAGMA table_info({self.TABLE})"
            ).fetchall()]
            return column in cols
        except Exception:
            return False

    def get_by_driver(self, driver_id: int, date_from: date, company_id=None) -> List[Dict[str, Any]]:
        """Return tacho activity rows for *driver_id* from *date_from* onwards.

        NOTE: the ``tacho_driver_activity`` table has NO ``company_id`` column
        (database/schema.py ``TABLE_TACHO_DRIVER_ACTIVITY``), so the query is
        scoped by ``driver_id`` only — deliberately WITHOUT
        ``self._company_filter()`` (which would emit an invalid
        ``AND company_id = ?`` in scoped deployments).  Callers must
        company-verify the driver first (404 otherwise).  ``company_id`` is
        accepted for signature compatibility and intentionally unused.
        """
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? AND activity_date >= ? ORDER BY activity_date DESC",
            (driver_id, date_from.isoformat()),
        )

    def get_by_import(self, import_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE import_id = ? {self._company_filter()} ORDER BY activity_date",
            (import_id,) + self._company_params(),
        )

    def delete_by_import(self, import_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE import_id = ? {self._company_filter()}",
            (import_id,) + self._company_params(), commit=True,
		)
