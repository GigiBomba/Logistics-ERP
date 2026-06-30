"""Trip repository — all trip DB access consolidated here."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class TripRepository(BaseRepository):
    TABLE = "trips"

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_by_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (trip_id,)
        )

    def get_all(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update(self, trip_id: int, data: Dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (trip_id,),
        )

    def delete(self, trip_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (trip_id,))

    # ── Domain-specific queries ───────────────────────────────────────

    def get_by_driver_id(self, driver_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? ORDER BY created_at DESC",
            (driver_id,),
        )

    def get_filtered(self, search: str = "", truck: str = "", status: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        """Dynamic filter for trip history with pagination."""
        query = f"SELECT * FROM {self.TABLE} WHERE 1=1"
        params: list = []
        if search:
            query += " AND (client_name LIKE ? OR driver_name LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if truck:
            query += " AND truck_number = ?"
            params.append(truck)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self._fetchall(query, tuple(params))

    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self.get_by_statuses([status])

    def get_by_statuses(self, statuses: List[str]) -> List[Dict[str, Any]]:
        placeholders = ", ".join("?" for _ in statuses)
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE status IN ({placeholders}) ORDER BY created_at DESC",
            tuple(statuses),
        )

    def get_by_date_range(self, start: str, end: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC",
            (start, end),
        )

    def get_by_truck_number(self, truck_number: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_number = ? ORDER BY created_at DESC",
            (truck_number,),
        )

    def get_by_truck_id(self, truck_id: int) -> List[Dict[str, Any]]:
        """Return trips for a given truck by canonical FK."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? ORDER BY created_at DESC",
            (truck_id,),
        )

    def get_last_activity(self, truck_number: str) -> Optional[str]:
        row = self._fetchone(
            f"SELECT MAX(created_at) AS last_date FROM {self.TABLE} WHERE truck_number = ?",
            (truck_number,),
        )
        return row["last_date"] if row else None

    def get_daily_profit(self, start: str, end: str) -> List[tuple]:
        """Return daily profit for date range: list of (day_str, profit)."""
        start = start.strip()
        end = end.strip()
        rows = self._fetchall(
            f"""SELECT start_date AS day,
                       SUM(COALESCE(net_profit,
                           total_price_eur - COALESCE(fuel_cost,0)
                           - COALESCE(toll_cost,0) - COALESCE(salary_cost,0)
                           - COALESCE(extra_costs,0), 0)) AS profit
                FROM {self.TABLE}
                WHERE LENGTH(start_date) >= 10
                  AND start_date >= ?
                  AND start_date <= ?
                  AND LOWER(status) IN ('delivered', 'completed', 'done', 'paid')
                GROUP BY start_date
                ORDER BY start_date""",
            (start, end),
        )
        return [(r["day"], float(r["profit"] or 0)) for r in rows]

    def get_top_trucks_by_revenue(self, month_start: str, month_end: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Return top trucks by revenue for a date range (canonical truck_id grouping)."""
        month_start = month_start.strip()
        month_end = month_end.strip()
        return self._fetchall(
            f"""SELECT COALESCE(t.plate_number, tr.truck_number) AS truck_number,
                       SUM(COALESCE(tr.total_price_eur, 0)) AS revenue
                 FROM {self.TABLE} tr
                 LEFT JOIN trucks t ON tr.truck_id = t.id
                 WHERE LENGTH(tr.start_date) >= 10
                   AND tr.start_date >= ?
                   AND tr.start_date <= ?
                   AND LOWER(tr.status) IN ('delivered', 'completed', 'done', 'paid')
                 GROUP BY COALESCE(tr.truck_id, tr.truck_number)
                 ORDER BY revenue DESC
                 LIMIT ?""",
            (month_start, month_end, limit),
        )

    # ── Document Automation matchers ─────────────────────────────────────

    def get_by_cmr_number(self, cmr_number: str) -> List[Dict[str, Any]]:
        """Return trips whose ``cmr_number`` column matches the given value."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            "WHERE cmr_number IS NOT NULL AND TRIM(cmr_number) != '' "
            "AND LOWER(TRIM(cmr_number)) = LOWER(TRIM(?)) "
            "ORDER BY id DESC",
            (cmr_number,),
        )

    def get_by_invoice_via_trip_invoice(self, invoice_number: str) -> List[Dict[str, Any]]:
        """Return trips linked to an invoice whose number matches."""
        return self._fetchall(
            f"""SELECT t.* FROM {self.TABLE} t
                 JOIN invoices i ON i.trip_id = t.id
                 WHERE LOWER(TRIM(i.invoice_number)) = LOWER(TRIM(?))
                 ORDER BY t.id DESC""",
            (invoice_number,),
        )

    def get_by_truck_plate(self, plate: str) -> List[Dict[str, Any]]:
        """Return trips where truck_number matches OR trucks.plate_number matches."""
        return self._fetchall(
            f"""SELECT tr.* FROM {self.TABLE} tr
                 LEFT JOIN trucks t ON tr.truck_id = t.id
                 WHERE LOWER(TRIM(COALESCE(tr.truck_number, ''))) = LOWER(TRIM(?))
                    OR LOWER(TRIM(COALESCE(t.plate_number, ''))) = LOWER(TRIM(?))
                 ORDER BY tr.id DESC
                 LIMIT 20""",
            (plate, plate),
        )

    def get_by_driver_name(self, driver_name: str) -> List[Dict[str, Any]]:
        """Return trips where driver_name fuzzy-matches the given value."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            "WHERE driver_name IS NOT NULL AND TRIM(driver_name) != '' "
            "AND LOWER(driver_name) LIKE LOWER(?) "
            "ORDER BY id DESC LIMIT 20",
            (f"%{driver_name.strip()}%",),
        )

    def get_active_excluding_statuses(
        self, exclude_statuses: List[str], limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Return trips NOT in the given statuses (i.e. active/ongoing trips only)."""
        placeholders = ", ".join("?" for _ in exclude_statuses)
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE status NOT IN ({placeholders}) "
            f"OR status IS NULL OR status = '' "
            f"ORDER BY created_at DESC LIMIT ?",
            tuple(exclude_statuses) + (limit,),
        )

    def get_active_for_truck(
        self, truck_plate: str = "", truck_id: Optional[int] = None,
        exclude_statuses: Optional[List[str]] = None, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return active trips for a given truck by plate or FK ID."""
        if not truck_plate and not truck_id:
            return []
        statuses = exclude_statuses or ["Delivered", "Completed", "Done", "Cancelled", "Paid"]
        placeholders = ", ".join("?" for _ in statuses)
        conditions = []
        params: list = []
        if truck_id:
            conditions.append("truck_id = ?")
            params.append(truck_id)
        if truck_plate:
            conditions.append("truck_number = ?")
            params.append(truck_plate)
        where = f"({' OR '.join(conditions)})"
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE {where} AND (status NOT IN ({placeholders}) OR status IS NULL OR status = '') "
            f"ORDER BY created_at DESC LIMIT ?",
            tuple(params) + tuple(statuses) + (limit,),
        )

    def get_active_for_driver(
        self, driver_id: int,
        exclude_statuses: Optional[List[str]] = None, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return active trips for a given driver."""
        statuses = exclude_statuses or ["Delivered", "Completed", "Done", "Cancelled", "Paid"]
        placeholders = ", ".join("?" for _ in statuses)
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE driver_id = ? AND (status NOT IN ({placeholders}) OR status IS NULL OR status = '') "
            f"ORDER BY created_at DESC LIMIT ?",
            (driver_id,) + tuple(statuses) + (limit,),
        )

    def get_latest_eta_for_truck(
        self, truck_plate: str = "", truck_id: Optional[int] = None,
    ) -> Optional[str]:
        """Return the latest end_date among active trips for a truck."""
        if not truck_plate and not truck_id:
            return None
        conditions = []
        params: list = []
        if truck_id:
            conditions.append("truck_id = ?")
            params.append(truck_id)
        if truck_plate:
            conditions.append("truck_number = ?")
            params.append(truck_plate)
        where_truck = f"({' OR '.join(conditions)})"
        row = self._fetchone(
            f"SELECT MAX(end_date) AS latest_end FROM {self.TABLE} "
            f"WHERE {where_truck} AND "
            f"(status NOT IN ('Delivered','Completed','Done','Cancelled','Paid') "
            f"OR status IS NULL OR status = '')",
            tuple(params),
        )
        return row["latest_end"] if row and row["latest_end"] else None

    def get_latest_eta_for_driver(self, driver_id: int) -> Optional[str]:
        """Return the latest end_date among active trips for a driver."""
        if not driver_id:
            return None
        row = self._fetchone(
            f"SELECT MAX(end_date) AS latest_end FROM {self.TABLE} "
            f"WHERE driver_id = ? AND "
            f"(status NOT IN ('Delivered','Completed','Done','Cancelled','Paid') "
            f"OR status IS NULL OR status = '')",
            (driver_id,),
        )
        return row["latest_end"] if row and row["latest_end"] else None

    def get_recent_trips_for_matching(
        self,
        days_back: int = 30,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return recent trips in the last ``days_back`` days for fallback matching."""
        from datetime import datetime, timedelta
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            "WHERE LENGTH(start_date) >= 10 AND start_date >= ? AND start_date <= ? "
            "ORDER BY id DESC LIMIT ?",
            (start, end, limit),
        )

    def get_trips_by_date_proximity(
        self,
        target_date: str,
        window_days: int = 14,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Return trips whose start_date is within ±window_days of target_date."""
        from datetime import datetime, timedelta
        try:
            anchor = datetime.strptime(target_date[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return self.get_recent_trips_for_matching()
        start = (anchor - timedelta(days=window_days)).strftime("%Y-%m-%d")
        end = (anchor + timedelta(days=window_days)).strftime("%Y-%m-%d")
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            "WHERE LENGTH(start_date) >= 10 AND start_date >= ? AND start_date <= ? "
            "ORDER BY ABS(JULIANDAY(start_date) - JULIANDAY(?)) ASC LIMIT ?",
            (start, end, target_date, limit),
        )

    def get_by_client_name_fuzzy(
        self,
        client_query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return trips whose client_name matches the query (case-insensitive LIKE)."""
        q = client_query.strip()
        if not q:
            return []
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            "WHERE client_name IS NOT NULL AND TRIM(client_name) != '' "
            "AND LOWER(client_name) LIKE LOWER(?) "
            "ORDER BY id DESC LIMIT ?",
            (f"%{q}%", limit),
        )
