"""Route repository — all route history DB access consolidated here."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class RouteRepository(BaseRepository):
    TABLE = "route_history_v2"
    COLUMNS = [
        "id", "route_fingerprint", "metadata_version", "created_at",
        "last_calculated_at", "calculation_count", "stops_json",
        "geometry_compressed", "geometry_encoding", "total_distance_km",
        "duration_min", "truck_id", "truck_label", "truck_json", "profile",
        "excluded_countries_json", "toll_estimates_json", "fuel_estimates_json",
        "profit_estimates_json", "countries_traversed_json",
        "route_summary_json", "archived_at",
    ]

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_by_id(self, route_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (route_id,)
        )

    def get_all(self, limit: int = 100, offset: int = 0, include_archived: bool = False) -> List[Dict[str, Any]]:
        if include_archived:
            return self._fetchall(
                f"SELECT * FROM {self.TABLE} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE archived_at IS NULL ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        filtered = {k: v for k, v in data.items() if k != "id"}
        cols = ", ".join(filtered.keys())
        vals = ", ".join("?" for _ in filtered)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(filtered.values()),
        )

    def update(self, route_id: int, data: Dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (route_id,),
        )

    def delete(self, route_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (route_id,))

    # ── Domain-specific queries ───────────────────────────────────────

    def get_by_trip_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        """Fetch the route associated with a trip via route_history_v2_id."""
        return self._fetchone(
            f"""SELECT r.* FROM {self.TABLE} r
                JOIN trips t ON t.route_history_v2_id = r.id
                WHERE t.id = ?""",
            (trip_id,),
        )

    def get_by_truck(self, truck_id: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? ORDER BY created_at DESC",
            (truck_id,),
        )

    def get_by_profile(self, profile: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE profile = ? ORDER BY created_at DESC",
            (profile,),
        )

    def get_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE route_fingerprint = ?",
            (fingerprint,),
        )

    def archive(self, route_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET archived_at = datetime('now') WHERE id = ?",
            (route_id,),
        )

    def count(self) -> int:
        row = self._fetchone(f"SELECT COUNT(*) AS cnt FROM {self.TABLE}")
        return row["cnt"] if row else 0
