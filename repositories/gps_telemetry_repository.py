"""GPS telemetry repository — vehicle position tracking."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class GpsTelemetryRepository(BaseRepository):
    TABLE = "gps_telemetry"
    COLUMNS = [
        "id", "truck_id", "latitude", "longitude", "speed_kmh",
        "heading", "driver_id", "company_id", "recorded_at", "created_at",
    ]

    def get_latest_for_truck(self, truck_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? "
            f"{self._company_filter()} ORDER BY recorded_at DESC LIMIT 1",
            (truck_id,) + self._company_params(),
        )

    def get_history(self, truck_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? "
            f"{self._company_filter()} ORDER BY recorded_at DESC LIMIT ?",
            (truck_id,) + self._company_params() + (limit,),
        )

    def get_by_date_range(
        self, truck_id: int, start: str, end: str, limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? AND recorded_at >= ? "
            f"AND recorded_at <= ? {self._company_filter()} ORDER BY recorded_at LIMIT ?",
            (truck_id, start, end) + self._company_params() + (limit,),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        commit=True)

    def create_many(self, records: List[Dict[str, Any]]) -> int:
        """Bulk-insert telemetry records, deduplicating by (truck_id, recorded_at).

        Each record that lacks an explicit ``company_id`` is stamped with the
        tenant context via ``_set_company_from_context`` so a batch flush never
        writes an unattributed row.  ``INSERT OR IGNORE`` (translated to
        ``ON CONFLICT DO NOTHING`` for PostgreSQL by ``_adapt_query``) makes
        replayed inserts idempotent against the
        ``idx_gps_telemetry_unique(truck_id, recorded_at)`` unique index.
        """
        if not records:
            return 0
        prepared = []
        for r in records:
            data = dict(r)
            if "company_id" not in data or not data.get("company_id"):
                data = self._set_company_from_context(data)
            prepared.append(data)
        cols = ", ".join(prepared[0].keys())
        vals = ", ".join("?" for _ in prepared[0])
        query = self._adapt_query(
            f"INSERT OR IGNORE INTO {self.TABLE} ({cols}) VALUES ({vals})"
        )
        # Double adaptation is intentional: _adapt_query already rewrote
        # INSERT OR IGNORE->ON CONFLICT (and ?->%s) for PG, so executemany's
        # internal _adapt_placeholders pass is a no-op on already-adapted SQL.
        self.db.executemany(query, [tuple(r.values()) for r in prepared])
        self.db.commit()
        return len(prepared)

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        """Delete telemetry rows older than *cutoff*, optionally tenant-scoped.

        Pass ``company_id`` to scope the delete to a single tenant (used by the
        per-company cleanup task).  ``None`` keeps the context-based behaviour
        for desktop/local callers.
        """
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE recorded_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )
