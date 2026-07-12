"""Trip repository — all trip DB access consolidated here."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class TripRepository(BaseRepository):
    TABLE = "trips"
    TABLE_CMR_COUNTER = "cmr_counter"
    COLUMNS = [
        "id", "created_at", "truck_number", "driver_name", "client_name",
        "distance_km", "total_price_eur", "rate_per_km", "gross_per_km", "net_profit",
        "start_date", "end_date", "payment_date", "extra_costs", "fuel_cost", "toll_cost",
        "salary_cost", "currency", "status", "loading_country", "delivery_country",
        "driver_id", "route_history_v2_id", "truck_consumption_l_per_100km", "context_json",
        "client_id", "truck_id", "price_pre_vat", "vat_percent", "cmr_number", "cmr_sequence",
        "cargo_description", "cargo_marks", "package_count", "package_type", "gross_weight_kg",
        "volume_m3", "hs_code", "carrier_instructions", "carrier_reservations",
        "special_agreements", "carriage_payer", "documents_attached", "place_of_loading",
        "place_of_loading_date", "adr_info_json", "cmr_status", "cmr_remarks",
        "company_id",
    ]
    COLUMNS_CMR_COUNTER = ["id", "year", "sequence_number"]

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_documents_attached(self, trip_id: int) -> list[int]:
        import json
        try:
            row = self._fetchone(
                f"SELECT documents_attached FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
                (trip_id,) + self._company_params(),
            )
        except Exception:
            return []
        if not row:
            return []
        raw = row.get("documents_attached")
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if not isinstance(parsed, list):
            return []
        out: list[int] = []
        for x in parsed:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out

    def get_by_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (trip_id,) + self._company_params(),
        )

    def get_all(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            self._company_params() + (limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

    def update(self, trip_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (trip_id,) + self._company_params(),
        )

    def get_next_cmr_sequence(self, year: int) -> tuple[str, int]:
        import time
        seq = 1
        for attempt in range(3):
            try:
                self.begin_transaction()
                row = self._fetchone(
                    f"SELECT sequence_number FROM {self.TABLE_CMR_COUNTER} WHERE year = ?",
                    (year,),
                )
                if row:
                    seq = int(row["sequence_number"]) + 1
                    self._execute(
                        f"UPDATE {self.TABLE_CMR_COUNTER} SET sequence_number = ? WHERE year = ?",
                        (seq, year),
                        commit=False,
                    )
                else:
                    seq = 1
                    self._execute(
                        f"INSERT INTO {self.TABLE_CMR_COUNTER} (year, sequence_number) VALUES (?, ?)",
                        (year, seq),
                        commit=False,
                    )
                self.commit_transaction()
                break
            except Exception as e:
                self.rollback_transaction()
                if attempt < 2:
                    time.sleep(0.1)
                    continue
                logger = __import__('logging').getLogger(__name__)
                logger.warning("cmr_counter DB error after 3 retries: %s", e)
                seq = int(datetime.now().timestamp()) % 100000
        cmr_number = f"CMR-{year}-{seq:06d}"
        return cmr_number, seq

    def get_by_ids(self, trip_ids: List[int]) -> List[Dict[str, Any]]:
        if not trip_ids:
            return []
        placeholders = ",".join("?" for _ in trip_ids)
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE id IN ({placeholders}) {self._company_filter()}",
            tuple(trip_ids) + self._company_params(),
        )

    def get_last_activity_by_truck_id(self, truck_id: int) -> Optional[str]:
        row = self._fetchone(
            f"SELECT MAX(created_at) AS last_activity FROM {self.TABLE} WHERE truck_id = ? {self._company_filter()}",
            (truck_id,) + self._company_params(),
        )
        return row["last_activity"] if row else None

    def update_cmr_fields(self, trip_id: int, cmr_number: str, cmr_seq: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET cmr_number = ?, cmr_sequence = ?, cmr_status = 'generated' WHERE id = ? {self._company_filter()}",
            (cmr_number, cmr_seq, trip_id) + self._company_params(),
        )

    def delete(self, trip_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (trip_id,) + self._company_params(),
        )

    # ── Status history ──────────────────────────────────────────────

    def record_status_history(self, trip_id: int, old_status: str, new_status: str, trigger: str) -> Optional[int]:
        """Insert a row into trip_status_history and return the new row id."""
        from datetime import datetime
        return self._execute_insert(
            "INSERT INTO trip_status_history (trip_id, old_status, new_status, trigger, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (trip_id, old_status, new_status, trigger, datetime.now().isoformat()),
        )

    # ── Domain-specific queries ───────────────────────────────────────

    def get_by_driver_id(self, driver_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE driver_id = ? {self._company_filter()} ORDER BY created_at DESC",
            (driver_id,) + self._company_params(),
        )

    def get_filtered(self, search: str = "", truck: str = "", status: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        """Dynamic filter for trip history with pagination."""
        query = f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()}"
        params: list = list(self._company_params())
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
            f"SELECT * FROM {self.TABLE} WHERE status IN ({placeholders}) {self._company_filter()} ORDER BY created_at DESC",
            tuple(statuses) + self._company_params(),
        )

    def get_by_date_range(self, start: str, end: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE created_at >= ? AND created_at <= ? {self._company_filter()} ORDER BY created_at DESC",
            (start, end) + self._company_params(),
        )

    def get_by_truck_number(self, truck_number: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_number = ? {self._company_filter()} ORDER BY created_at DESC",
            (truck_number,) + self._company_params(),
        )

    def get_by_truck_id(self, truck_id: int) -> List[Dict[str, Any]]:
        """Return trips for a given truck by canonical FK."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE truck_id = ? {self._company_filter()} ORDER BY created_at DESC",
            (truck_id,) + self._company_params(),
        )

    def get_last_activity(self, truck_number: str) -> Optional[str]:
        row = self._fetchone(
            f"SELECT MAX(created_at) AS last_date FROM {self.TABLE} WHERE truck_number = ? {self._company_filter()}",
            (truck_number,) + self._company_params(),
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
                  {self._company_filter()}
                GROUP BY start_date
                ORDER BY start_date""",
            (start, end) + self._company_params(),
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
                   {self._company_filter("tr")}
                 GROUP BY COALESCE(tr.truck_id, tr.truck_number)
                 ORDER BY revenue DESC
                 LIMIT ?""",
            (month_start, month_end, limit) + self._company_params(),
        )

    # ── Document Automation matchers ─────────────────────────────────────

    def get_by_cmr_number(self, cmr_number: str) -> List[Dict[str, Any]]:
        """Return trips whose ``cmr_number`` column matches the given value."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            "WHERE cmr_number IS NOT NULL AND TRIM(cmr_number) != '' "
            "AND LOWER(TRIM(cmr_number)) = LOWER(TRIM(?)) "
            f"{self._company_filter()} "
            "ORDER BY id DESC",
            (cmr_number,) + self._company_params(),
        )

    def get_by_invoice_via_trip_invoice(self, invoice_number: str) -> List[Dict[str, Any]]:
        """Return trips linked to an invoice whose number matches."""
        return self._fetchall(
            f"""SELECT t.* FROM {self.TABLE} t
                 JOIN invoices i ON i.trip_id = t.id
                 WHERE LOWER(TRIM(i.invoice_number)) = LOWER(TRIM(?))
                 {self._company_filter("t")}
                 ORDER BY t.id DESC""",
            (invoice_number,) + self._company_params(),
        )

    def get_by_truck_plate(self, plate: str) -> List[Dict[str, Any]]:
        """Return trips where truck_number matches OR trucks.plate_number matches."""
        return self._fetchall(
            f"""SELECT tr.* FROM {self.TABLE} tr
                 LEFT JOIN trucks t ON tr.truck_id = t.id
                 WHERE (LOWER(TRIM(COALESCE(tr.truck_number, ''))) = LOWER(TRIM(?))
                     OR LOWER(TRIM(COALESCE(t.plate_number, ''))) = LOWER(TRIM(?)))
                 {self._company_filter("tr")}
                 ORDER BY tr.id DESC
                 LIMIT 20""",
            (plate, plate) + self._company_params(),
        )

    def get_by_driver_name(self, driver_name: str) -> List[Dict[str, Any]]:
        """Return trips where driver_name fuzzy-matches the given value."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            "WHERE driver_name IS NOT NULL AND TRIM(driver_name) != '' "
            "AND LOWER(driver_name) LIKE LOWER(?) "
            f"{self._company_filter()} "
            "ORDER BY id DESC LIMIT 20",
            (f"%{driver_name.strip()}%",) + self._company_params(),
        )

    def get_active_excluding_statuses(
        self, exclude_statuses: List[str], limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Return trips NOT in the given statuses (i.e. active/ongoing trips only)."""
        placeholders = ", ".join("?" for _ in exclude_statuses)
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE (status NOT IN ({placeholders}) "
            f"OR status IS NULL OR status = '') "
            f"{self._company_filter()} "
            f"ORDER BY created_at DESC LIMIT ?",
            tuple(exclude_statuses) + (limit,) + self._company_params(),
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
            f"{self._company_filter()} "
            f"ORDER BY created_at DESC LIMIT ?",
            tuple(params) + tuple(statuses) + self._company_params() + (limit,),
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
            f"{self._company_filter()} "
            f"ORDER BY created_at DESC LIMIT ?",
            (driver_id,) + tuple(statuses) + self._company_params() + (limit,),
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
            f"WHERE ({where_truck}) AND "
            f"(status NOT IN ('Delivered','Completed','Done','Cancelled','Paid') "
            f"OR status IS NULL OR status = '') "
            f"{self._company_filter()}",
            tuple(params) + self._company_params(),
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
            f"OR status IS NULL OR status = '') "
            f"{self._company_filter()}",
            (driver_id,) + self._company_params(),
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
            f"{self._company_filter()} "
            "ORDER BY id DESC LIMIT ?",
            (start, end) + self._company_params() + (limit,),
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
            f"{self._company_filter()} "
            "ORDER BY ABS(JULIANDAY(start_date) - JULIANDAY(?)) ASC LIMIT ?",
            (start, end) + self._company_params() + (target_date, limit),
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
            f"{self._company_filter()} "
            "ORDER BY id DESC LIMIT ?",
            (f"%{q}%",) + self._company_params() + (limit,),
        )
