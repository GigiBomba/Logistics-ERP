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
        # Check if column already exists to avoid running migration on every instantiation
        cols = self._fetchall(f"PRAGMA table_info({self.TABLE})")
        if any(r["name"] == "is_committed" for r in cols):
            return
        self._execute(
            f"ALTER TABLE {self.TABLE} ADD COLUMN is_committed INTEGER NOT NULL DEFAULT 0"
        )

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_by_id(self, route_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (route_id,)
        )

    def get_all(self, limit: int = 100, offset: int = 0, include_archived: bool = False) -> List[Dict[str, Any]]:
        if include_archived:
            return self._fetchall(
                f"SELECT * FROM {self.TABLE} WHERE is_committed >= 0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE archived_at IS NULL AND is_committed >= 0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
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

    def archive(self, route_id: int, archived_at: Optional[str] = None) -> None:
        from datetime import datetime
        ts = archived_at or datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self._execute(
            f"UPDATE {self.TABLE} SET archived_at = ? WHERE id = ?",
            (ts, route_id),
        )

    def commit(self, route_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET is_committed = 1 WHERE id = ?",
            (route_id,),
        )

    def discard(self, route_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET is_committed = -1 WHERE id = ?",
            (route_id,),
        )

    def count(self) -> int:
        row = self._fetchone(f"SELECT COUNT(*) AS cnt FROM {self.TABLE}")
        return row["cnt"] if row else 0

    # ── Upsert (fingerprint-based dedup) ───────────────────────────────

    def upsert(self, data: Dict[str, Any], fingerprint: str) -> int:
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
            f"SELECT id FROM {self.TABLE} WHERE route_fingerprint = ?",
            (fingerprint,),
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
                    FROM {self.TABLE} WHERE is_committed >= 0"""
        params: List[Any] = []
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
        query = f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE is_committed >= 0"
        params: List[Any] = []
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

    # ── Maintenance / housekeeping ─────────────────────────────────────

    def clear_all(self) -> int:
        cursor = self.db.conn.execute(f"DELETE FROM {self.TABLE}")
        self.db.conn.commit()
        return cursor.rowcount

    def prune_before(self, cutoff_iso: str) -> int:
        cursor = self.db.conn.execute(
            f"DELETE FROM {self.TABLE} WHERE last_calculated_at < ?",
            (cutoff_iso,),
        )
        self.db.conn.commit()
        return cursor.rowcount
