"""Fleet (truck + maintenance) repository — all truck & maintenance DB access."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class FleetRepository(BaseRepository):
    TABLE = "trucks"
    TABLE_MAINT_RECORDS = "maintenance_records"
    TABLE_MAINT_SCHEDULES = "maintenance_schedules"
    TABLE_HEALTH_SCORES = "truck_health_scores"
    COLUMNS = [
        "id", "plate_number", "model", "manufacturer", "year", "vin",
        "fuel_consumption", "mileage", "monthly_rate", "status",
        "insurance_expiry", "inspection_expiry", "maintenance_due",
        "tachograph_expiry", "active_status", "tracking_device_id",
        "trailer_plate", "max_payload_kg", "cmr_insurance_number", "cmr_insurance_expiry",
    ]

    # ── Truck CRUD ───────────────────────────────────────────────────

    def get_by_id(self, truck_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (truck_id,)
        )

    def get_all(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} ORDER BY plate_number ASC LIMIT ? OFFSET ?",
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

    def update(self, truck_id: int, data: Dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (truck_id,),
        )

    def delete(self, truck_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (truck_id,))

    # ── Truck domain queries ─────────────────────────────────────────

    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE status = ? ORDER BY plate_number ASC",
            (status,),
        )

    def get_maintenance_records_with_attachments(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT id, truck_id, maintenance_type, date, attachment_path "
            f"FROM {self.TABLE_MAINT_RECORDS} "
            f"WHERE attachment_path IS NOT NULL AND attachment_path != ''"
        )

    def get_active_trucks(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE active_status = 1 ORDER BY plate_number ASC"
        )

    def get_by_plate(self, plate: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE plate_number = ?", (plate,)
        )

    def get_by_vin(self, vin: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE vin = ?", (vin,)
        )

    def get_by_tracking_device_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE tracking_device_id = ?", (device_id,)
        )

    def update_fields(self, truck_id: int, fields: Dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(fields.values()) + (truck_id,),
        )

    def get_by_driver_id(self, driver_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT DISTINCT t.* FROM {self.TABLE} t
                JOIN trips tr ON tr.truck_id = t.id
                WHERE tr.driver_id = ?
                ORDER BY t.plate_number ASC""",
            (driver_id,),
        )

    def count_active(self) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE active_status = 1"
        )
        return row["cnt"] if row else 0

    def get_truck_mileage(self, truck_id: int) -> Optional[float]:
        row = self._fetchone(
            f"SELECT mileage FROM {self.TABLE} WHERE id = ?", (truck_id,)
        )
        return float(row["mileage"]) if row and row.get("mileage") is not None else None

    def get_active_truck_ids(self) -> List[int]:
        rows = self._fetchall(
            f"SELECT id FROM {self.TABLE} WHERE active_status = 1"
        )
        return [r["id"] for r in rows]

    def get_expiring_insurance(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE insurance_expiry IS NOT NULL AND insurance_expiry != ''"
            " AND insurance_expiry <= date('now', '+' || ? || ' days')",
            (days_ahead,),
        )

    # ── Maintenance Records CRUD ─────────────────────────────────────

    def add_maintenance_record(
        self, truck_id: int, maint_type: str, date: str,
        km: Optional[float] = None, cost: Optional[float] = None,
        notes: str = "", provider: str = "", attachment: str = "",
        created_at: str = "",
    ) -> int:
        return self._execute_insert(
            f"INSERT INTO {self.TABLE_MAINT_RECORDS} "
            f"(truck_id, maintenance_type, date, km, cost, notes, service_provider, attachment_path, created_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (truck_id, maint_type, date, km, cost, notes, provider, attachment, created_at),
        )

    def get_maintenance_records(
        self, truck_id: Optional[int] = None, maint_type: Optional[str] = None,
        limit: int = 100, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: list = []
        if truck_id is not None:
            conditions.append("truck_id = ?")
            params.append(truck_id)
        if maint_type:
            conditions.append("maintenance_type = ?")
            params.append(maint_type)
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_MAINT_RECORDS} {where}ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )

    def count_maintenance_records(
        self, truck_id: Optional[int] = None, maint_type: Optional[str] = None,
        since_date: Optional[str] = None,
    ) -> int:
        conditions = []
        params: list = []
        if truck_id is not None:
            conditions.append("truck_id = ?")
            params.append(truck_id)
        if maint_type:
            conditions.append("maintenance_type = ?")
            params.append(maint_type)
        if since_date:
            conditions.append("date >= ?")
            params.append(since_date)
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE_MAINT_RECORDS} {where}",
            tuple(params),
        )
        return row["cnt"] if row else 0

    def get_maintenance_record_truck_id(self, record_id: int) -> Optional[int]:
        row = self._fetchone(
            f"SELECT truck_id FROM {self.TABLE_MAINT_RECORDS} WHERE id = ?",
            (record_id,),
        )
        return row["truck_id"] if row else None

    def update_maintenance_record(
        self, record_id: int, maint_type: str, date: str,
        km: Optional[float] = None, cost: Optional[float] = None,
        provider: str = "", notes: str = "",
    ) -> None:
        self._execute(
            f"UPDATE {self.TABLE_MAINT_RECORDS} SET maintenance_type=?, date=?, km=?, cost=?, service_provider=?, notes=? WHERE id=?",
            (maint_type, date, km, cost, provider, notes, record_id),
        )

    def delete_maintenance_record(self, record_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE_MAINT_RECORDS} WHERE id = ?", (record_id,)
        )

    def get_maintenance_type_counts(self, truck_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT maintenance_type, COUNT(*) as cnt FROM {self.TABLE_MAINT_RECORDS} "
            f"WHERE truck_id = ? GROUP BY maintenance_type HAVING cnt >= 3",
            (truck_id,),
        )

    def get_maintenance_last_date(self, truck_id: int) -> Optional[str]:
        row = self._fetchone(
            f"SELECT date FROM {self.TABLE_MAINT_RECORDS} WHERE truck_id = ? ORDER BY date DESC LIMIT 1",
            (truck_id,),
        )
        return row["date"] if row else None

    def sum_maintenance_cost(self, since_date: Optional[str] = None) -> float:
        query = f"SELECT COALESCE(SUM(cost), 0) AS total FROM {self.TABLE_MAINT_RECORDS}"
        params = ()
        if since_date:
            query += " WHERE date >= ?"
            params = (since_date,)
        row = self._fetchone(query, params)
        return float(row["total"]) if row else 0.0

    def get_maintenance_cost_by_type(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT maintenance_type, SUM(cost) as total FROM {self.TABLE_MAINT_RECORDS} GROUP BY maintenance_type ORDER BY total DESC"
        )

    def get_maintenance_count_by_type(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT maintenance_type, COUNT(*) as cnt FROM {self.TABLE_MAINT_RECORDS} GROUP BY maintenance_type ORDER BY cnt DESC"
        )

    def get_top_maintained_trucks(self, limit: int = 5) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT truck_id, COALESCE(SUM(cost), 0) as total FROM {self.TABLE_MAINT_RECORDS} GROUP BY truck_id ORDER BY total LIMIT ?",
            (limit,),
        )

    # ── Maintenance Schedules CRUD ───────────────────────────────────

    def add_maintenance_schedule(
        self, truck_id: int, maint_type: str,
        interval_km: Optional[float] = None, interval_months: Optional[int] = None,
        fixed_expiry_date: str = "", last_done_km: Optional[float] = None,
        last_done_date: str = "", created_at: str = "",
    ) -> int:
        return self._execute_insert(
            f"INSERT INTO {self.TABLE_MAINT_SCHEDULES} "
            f"(truck_id, maintenance_type, interval_km, interval_months, fixed_expiry_date, last_done_km, last_done_date, active, created_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (truck_id, maint_type, interval_km, interval_months, fixed_expiry_date, last_done_km, last_done_date, created_at),
        )

    def get_maintenance_schedules(self, truck_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if truck_id is not None:
            return self._fetchall(
                f"SELECT * FROM {self.TABLE_MAINT_SCHEDULES} WHERE truck_id = ? AND active = 1 ORDER BY id",
                (truck_id,),
            )
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_MAINT_SCHEDULES} WHERE active = 1 ORDER BY truck_id, id"
        )

    def get_maintenance_schedule(self, truck_id: int, maint_type: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE_MAINT_SCHEDULES} WHERE truck_id = ? AND maintenance_type = ? AND active = 1",
            (truck_id, maint_type),
        )

    def get_schedule_truck_id(self, schedule_id: int) -> Optional[int]:
        row = self._fetchone(
            f"SELECT truck_id FROM {self.TABLE_MAINT_SCHEDULES} WHERE id = ?",
            (schedule_id,),
        )
        return row["truck_id"] if row else None

    def update_maintenance_schedule(self, schedule_id: int, **fields: Any) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._execute(
            f"UPDATE {self.TABLE_MAINT_SCHEDULES} SET {sets} WHERE id = ?",
            tuple(fields.values()) + (schedule_id,),
        )

    def delete_maintenance_schedule(self, schedule_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE_MAINT_SCHEDULES} WHERE id = ?", (schedule_id,)
        )

    def count_active_maintenance_schedules(self) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE_MAINT_SCHEDULES} WHERE active = 1"
        )
        return row["cnt"] if row else 0

    def get_all_schedules_flat(self) -> List[Dict[str, Any]]:
        """Return all active schedules with truck plate and current mileage joined."""
        return self._fetchall(
            f"""SELECT s.*, t.plate_number, t.mileage AS current_km
                FROM {self.TABLE_MAINT_SCHEDULES} s
                LEFT JOIN trucks t ON t.id = s.truck_id
                WHERE s.active = 1
                ORDER BY s.truck_id, s.maintenance_type"""
        )

    # ── Analytics Queries ────────────────────────────────────────────

    def get_maintenance_cost_truck_monthly(self, since: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT truck_id,
                       substr(date, 1, 7) AS ym,
                       COALESCE(SUM(cost), 0) AS total
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL
                GROUP BY truck_id, ym
                ORDER BY ym, truck_id""",
            (since,),
        )

    def get_maintenance_cost_monthly(self, since: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT substr(date, 1, 7) AS ym,
                       COALESCE(SUM(cost), 0) AS total
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL
                GROUP BY ym
                ORDER BY ym""",
            (since,),
        )

    def get_maintenance_truck_summary(self, since: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT truck_id,
                       COALESCE(SUM(cost), 0) AS total_ytd,
                       COALESCE(AVG(cost), 0) AS avg_cost,
                       COUNT(*) AS service_count
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL
                GROUP BY truck_id
                ORDER BY total_ytd DESC""",
            (since,),
        )

    def get_maintenance_most_expensive_category(self, since: str) -> List[Dict[str, Any]]:
        rows = self._fetchall(
            f"""SELECT truck_id, maintenance_type, COALESCE(SUM(cost), 0) AS total
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL
                GROUP BY truck_id, maintenance_type
                ORDER BY truck_id, total DESC""",
            (since,),
        )
        seen = set()
        result = []
        for r in rows:
            if r["truck_id"] not in seen:
                seen.add(r["truck_id"])
                result.append(r)
        return result

    # ── Truck Health Scores ─────────────────────────────────────────

    def upsert_truck_health(
        self, truck_id: int, score: int, compliance_pct: float,
        overdue_count: int, recurring_issues: int,
        downtime_days: int, last_updated: str,
    ) -> None:
        self._execute(
            f"INSERT OR REPLACE INTO {self.TABLE_HEALTH_SCORES} "
            f"(truck_id, score, compliance_pct, overdue_count, recurring_issues, downtime_days, last_updated) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?)",
            (truck_id, score, compliance_pct, overdue_count, recurring_issues, downtime_days, last_updated),
        )

    def get_truck_health(self, truck_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE_HEALTH_SCORES} WHERE truck_id = ?",
            (truck_id,),
        )

    def get_all_truck_health(self) -> List[Dict[str, Any]]:
        return self._fetchall(f"SELECT * FROM {self.TABLE_HEALTH_SCORES}")
