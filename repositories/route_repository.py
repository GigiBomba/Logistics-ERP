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
        "route_summary_json", "archived_at", "is_committed",
    ]

    _migrate_done: bool = False

    def __init__(self, db):
        super().__init__(db)
        if not RouteRepository._migrate_done:
            self._run_migration()
            RouteRepository._migrate_done = True

    def _run_migration(self):
        # 1. Ensure is_committed column exists
        cols = self._fetchall(f"PRAGMA table_info({self.TABLE})")
        if not any(r["name"] == "is_committed" for r in cols):
            self._execute(
                f"ALTER TABLE {self.TABLE} ADD COLUMN is_committed INTEGER NOT NULL DEFAULT 0"
            )
        # 2. Ensure unique index on route_fingerprint (required by ON CONFLICT in upsert)
        self._execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_route_fingerprint ON {self.TABLE}(route_fingerprint)"
        )

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_by_id(self, route_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (route_id,) + self._company_params(),
        )

    def get_all(self, limit: int = 100, offset: int = 0, include_archived: bool = False) -> List[Dict[str, Any]]:
        if include_archived:
            return self._fetchall(
                f"SELECT * FROM {self.TABLE} WHERE is_committed >= 0 {self._company_filter()} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset) + self._company_params(),
            )
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE archived_at IS NULL AND is_committed >= 0 {self._company_filter()} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset) + self._company_params(),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        filtered = {k: v for k, v in data.items() if k != "id"}
        cols = ", ".join(filtered.keys())
        vals = ", ".join("?" for _ in filtered)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(filtered.values()),
        )

    def update(self, route_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (route_id,) + self._company_params(),
        )

    def delete(self, route_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (route_id,) + self._company_params(),
        )

    # ── Domain-specific queries ───────────────────────────────────────

    def get_stops_json(self, route_id: int) -> Optional[str]:
        row = self._fetchone(
            f"SELECT stops_json FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (route_id,) + self._company_params(),
        )
        return row["stops_json"] if row else None

    def get_by_trip_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        """Fetch the route associated with a trip via route_history_v2_id."""
        return self._fetchone(
            f"""SELECT r.* FROM {self.TABLE} r
                JOIN trips t ON t.route_history_v2_id = r.id
                WHERE t.id = ? {self._company_filter('r')}""",
            (trip_id,) + self._company_params(),
        )

    def get_by_truck(self, truck_id: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? {self._company_filter()} ORDER BY created_at DESC",
            (truck_id,) + self._company_params(),
        )

    def get_by_profile(self, profile: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE profile = ? {self._company_filter()} ORDER BY created_at DESC",
            (profile,) + self._company_params(),
        )

    def get_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE route_fingerprint = ? {self._company_filter()}",
            (fingerprint,) + self._company_params(),
        )

    def archive(self, route_id: int, archived_at: Optional[str] = None) -> None:
        from datetime import datetime
        ts = archived_at or datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self._execute(
            f"UPDATE {self.TABLE} SET archived_at = ? WHERE id = ? {self._company_filter()}",
            (ts, route_id,) + self._company_params(),
        )

    def commit(self, route_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET is_committed = 1 WHERE id = ? {self._company_filter()}",
            (route_id,) + self._company_params(),
        )

    def discard(self, route_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET is_committed = -1 WHERE id = ? {self._company_filter()}",
            (route_id,) + self._company_params(),
        )

    def count(self) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE 1=1 {self._company_filter()}",
            self._company_params(),
        )
        return row["cnt"] if row else 0

    # ── Upsert (fingerprint-based dedup) ───────────────────────────────

    def upsert(self, data: Dict[str, Any], fingerprint: str) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        filtered = {k: v for k, v in data.items() if k != "id"}
        cols = ", ".join(filtered.keys())
        vals = ", ".join("?" for _ in filtered)
        set_clauses = ", ".join(
            f"{k} = excluded.{k}" for k in filtered
            if k not in ("route_fingerprint", "calculation_count", "created_at", "is_committed")
        )
        return self._execute_insert(
            f"""INSERT INTO {self.TABLE} ({cols})
                VALUES ({vals})
                ON CONFLICT(route_fingerprint) DO UPDATE SET
                    last_calculated_at = excluded.last_calculated_at,
                    calculation_count = {self.TABLE}.calculation_count + 1,
                    metadata_version = excluded.metadata_version,
                    {set_clauses}""",
            tuple(filtered.values()),
        )

    def get_id_by_fingerprint(self, fingerprint: str) -> Optional[int]:
        row = self._fetchone(
            f"SELECT id FROM {self.TABLE} WHERE route_fingerprint = ? {self._company_filter()}",
            (fingerprint,) + self._company_params(),
        )
        return int(row["id"]) if row else None

    # ── Dynamic search ─────────────────────────────────────────────────

    _SORT_COLUMNS = {
        "last_calculated_at", "created_at", "total_distance_km",
        "duration_min", "truck_label", "profile",
    }

    def search(
        self,
        search: str = "",
        truck: str = "",
        profile: str = "",
        include_archived: bool = False,
        sort_by: str = "last_calculated_at",
        sort_dir: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        order_col = sort_by if sort_by in self._SORT_COLUMNS else "last_calculated_at"
        direction = "ASC" if sort_dir.upper() == "ASC" else "DESC"
        query = f"""SELECT id, route_fingerprint, created_at, last_calculated_at,
                           calculation_count, total_distance_km, duration_min, truck_id,
                           truck_label, profile, excluded_countries_json,
                           countries_traversed_json, metadata_version, stops_json,
                           archived_at, is_committed
                    FROM {self.TABLE} WHERE is_committed >= 0 {self._company_filter()}"""
        params: List[Any] = list(self._company_params())
        if not include_archived:
            query += " AND archived_at IS NULL"
        if search:
            query += " AND (stops_json LIKE ? OR truck_label LIKE ? OR profile LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        if truck:
            query += " AND (truck_id = ? OR truck_label LIKE ?)"
            params.extend([truck, f"%{truck}%"])
        if profile:
            query += " AND profile = ?"
            params.append(profile)
        query += f" ORDER BY {order_col} {direction}, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self._fetchall(query, tuple(params))

    def count_filtered(
        self,
        search: str = "",
        truck: str = "",
        profile: str = "",
        include_archived: bool = False,
    ) -> int:
        query = f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE is_committed >= 0 {self._company_filter()}"
        params: List[Any] = list(self._company_params())
        if not include_archived:
            query += " AND archived_at IS NULL"
        if search:
            query += " AND (stops_json LIKE ? OR truck_label LIKE ? OR profile LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        if truck:
            query += " AND (truck_id = ? OR truck_label LIKE ?)"
            params.extend([truck, f"%{truck}%"])
        if profile:
            query += " AND profile = ?"
            params.append(profile)
        row = self._fetchone(query, tuple(params))
        return row["cnt"] if row else 0

    # ── Statistics / analytics (memory-efficient, no BLOBs) ────────────

    def get_statistics_aggregate(self, include_archived: bool = False) -> Dict[str, Any]:
        """Return aggregate route_count and total_distance in SQL (no BLOBs loaded)."""
        archive_clause = "" if include_archived else "AND archived_at IS NULL"
        row = self._fetchone(
            f"""SELECT COUNT(*) AS route_count,
                       COALESCE(SUM(total_distance_km), 0) AS total_distance
                FROM {self.TABLE}
                WHERE is_committed >= 0 {archive_clause} {self._company_filter()}""",
            self._company_params(),
        )
        return row if row else {"route_count": 0, "total_distance": 0}

    def get_stops_for_statistics(self, limit: int = 100000, include_archived: bool = False):
        """Return only stops_json (no geometry BLOBs) for destination counting."""
        archive_clause = "" if include_archived else "AND archived_at IS NULL"
        return self._fetchall(
            f"""SELECT stops_json
                FROM {self.TABLE}
                WHERE is_committed >= 0 {archive_clause} {self._company_filter()}
                LIMIT ?""",
            self._company_params() + (limit,),
        )

    def get_countries_and_durations(self, limit: int = 100000, include_archived: bool = False):
        """Return only countries_traversed_json and duration_min (no geometry BLOBs) for analytics."""
        archive_clause = "" if include_archived else "AND archived_at IS NULL"
        return self._fetchall(
            f"""SELECT countries_traversed_json, duration_min
                FROM {self.TABLE}
                WHERE is_committed >= 0 {archive_clause} {self._company_filter()}
                LIMIT ?""",
            self._company_params() + (limit,),
        )

    # ── Maintenance / housekeeping ─────────────────────────────────────

    def clear_all(self) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE 1=1 {self._company_filter()}",
            self._company_params(),
        )

    def prune_before(self, cutoff_iso: str) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE last_calculated_at < datetime(?) {self._company_filter()}",
            (cutoff_iso,) + self._company_params(),
        )
