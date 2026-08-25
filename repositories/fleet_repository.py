"""Fleet (truck + maintenance) repository — all truck & maintenance DB access."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories import BaseRepository


def schedule_is_overdue(row: Dict[str, Any], today: Optional[str] = None) -> bool:
    """Return whether an active maintenance schedule is overdue.

    This is the SINGLE source of truth for the overdue thresholds — both
    ``count_overdue_schedules`` and the mobile maintenance schedule list
    compute overdue through it (no drift between the health-score count and
    the per-schedule ``overdue`` flag):
      - km: current mileage (trucks.mileage) >= last_done_km + interval_km
      - months: last_done_date + interval_months <= today
      - fixed expiry: fixed_expiry_date <= today
    """
    from datetime import datetime
    import calendar

    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")

    def _add_months(source_date, months):
        total_months = source_date.month - 1 + months
        year = source_date.year + total_months // 12
        month = total_months % 12 + 1
        max_day = calendar.monthrange(year, month)[1]
        day = min(source_date.day, max_day)
        return source_date.replace(year=year, month=month, day=day)

    # Check km-based overdue
    current_km = row.get("current_km") or 0
    last_done_km = row.get("last_done_km")
    interval_km = row.get("interval_km")
    if interval_km is not None and last_done_km is not None and current_km >= last_done_km + interval_km:
        return True
    # Check month-based overdue
    interval_months = row.get("interval_months")
    last_done_date = row.get("last_done_date")
    if interval_months is not None and last_done_date:
        try:
            last_done = datetime.strptime(last_done_date[:10], "%Y-%m-%d")
            due_date = _add_months(last_done, int(interval_months))
            if due_date.strftime("%Y-%m-%d") <= today:
                return True
        except (ValueError, TypeError):
            pass
    # Check fixed expiry
    fixed_expiry = row.get("fixed_expiry_date")
    if fixed_expiry and fixed_expiry <= today:
        return True
    return False


class FleetRepository(BaseRepository):
    TABLE = "trucks"
    TABLE_MAINT_RECORDS = "maintenance_records"
    TABLE_MAINT_SCHEDULES = "maintenance_schedules"
    TABLE_HEALTH_SCORES = "truck_health_scores"
    SOFT_DELETE = True
    COLUMNS = [
        "id", "plate_number", "model", "manufacturer", "year", "vin",
        "fuel_consumption", "mileage", "monthly_rate", "status",
        "insurance_expiry", "inspection_expiry", "maintenance_due",
        "tachograph_expiry", "active_status", "tracking_device_id",
        "trailer_plate", "max_payload_kg", "cmr_insurance_number", "cmr_insurance_expiry",
        "odometer_km", "company_id",
    ]
    COLUMNS_MAINT_RECORDS = [
        "id", "truck_id", "maintenance_type", "date", "km", "cost", "notes",
        "service_provider", "attachment_path", "created_at", "company_id",
    ]
    COLUMNS_MAINT_SCHEDULES = [
        "id", "truck_id", "maintenance_type", "interval_km", "interval_months",
        "fixed_expiry_date", "last_done_km", "last_done_date", "active",
        "created_at", "company_id",
    ]
    COLUMNS_HEALTH_SCORES = [
        "truck_id", "score", "compliance_pct", "overdue_count",
        "recurring_issues", "downtime_days", "last_updated", "company_id",
    ]

    # ── Truck CRUD ───────────────────────────────────────────────────

    def get_by_id(self, truck_id: int, company_id=None) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter_for(company_id)} {self._soft_delete_filter()}",
            (truck_id,) + self._company_params_for(company_id),
        )

    def get_trucks_by_ids(self, truck_ids: List[int], company_id=None) -> List[Dict[str, Any]]:
        """Return the subset of *truck_ids* that belong to the given company.

        Single ``id IN (...)`` query so the GPS batch endpoint can verify
        ownership of every truck in one lookup instead of N sequential ones.
        """
        if not truck_ids:
            return []
        placeholders = ", ".join("?" for _ in truck_ids)
        return self._fetchall(
            f"SELECT id FROM {self.TABLE} WHERE id IN ({placeholders}) "
            f"{self._company_filter_for(company_id)} {self._soft_delete_filter()}",
            tuple(truck_ids) + self._company_params_for(company_id),
        )

    def get_all(self, limit: int = 200, offset: int = 0, company_id=None) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter_for(company_id)} {self._soft_delete_filter()} ORDER BY plate_number ASC LIMIT ? OFFSET ?",
            self._company_params_for(company_id) + (limit, offset),
        )

    def create(self, data: Dict[str, Any], company_id=None) -> int:
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        if company_id:
            data["company_id"] = company_id
        filtered = {k: v for k, v in data.items() if k != "id"}
        cols = ", ".join(filtered.keys())
        vals = ", ".join("?" for _ in filtered)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(filtered.values()),
        commit=True)

    def update(self, truck_id: int, data: Dict[str, Any], company_id=None) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter_for(company_id)}",
            tuple(data.values()) + (truck_id,) + self._company_params_for(company_id),
        commit=True)

    def delete(self, truck_id: int, company_id=None) -> None:
        """Soft-delete a truck by stamping ``deleted_at`` (row kept for sync)."""
        from database.time_utils import utc_now_iso
        self._execute(
            f"UPDATE {self.TABLE} SET deleted_at = ? WHERE id = ? {self._company_filter_for(company_id)}",
            (utc_now_iso(), truck_id) + self._company_params_for(company_id),
        commit=True)

    # ── Truck domain queries ─────────────────────────────────────────

    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE status = ? {self._company_filter()} {self._soft_delete_filter()} ORDER BY plate_number ASC",
            (status,) + self._company_params(),
        )

    def get_maintenance_records_with_attachments(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT id, truck_id, maintenance_type, date, attachment_path "
            f"FROM {self.TABLE_MAINT_RECORDS} "
            f"WHERE attachment_path IS NOT NULL AND attachment_path != '' {self._company_filter()} {self._soft_delete_filter()}",
            self._company_params(),
        )

    def get_active_trucks(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE active_status = 1 {self._company_filter()} {self._soft_delete_filter()} ORDER BY plate_number ASC",
            self._company_params(),
        )

    def get_by_plate(self, plate: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE plate_number = ? {self._company_filter()} {self._soft_delete_filter()}",
            (plate,) + self._company_params(),
        )

    def get_by_vin(self, vin: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE vin = ? {self._company_filter()} {self._soft_delete_filter()}",
            (vin,) + self._company_params(),
        )

    def get_by_tracking_device_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE tracking_device_id = ? {self._company_filter()} {self._soft_delete_filter()}",
            (device_id,) + self._company_params(),
        )

    def update_fields(self, truck_id: int, fields: Dict[str, Any]) -> None:
        self._validate_columns(fields)
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(fields.values()) + (truck_id,) + self._company_params(),
        commit=True)

    def get_by_driver_id(self, driver_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT DISTINCT t.* FROM {self.TABLE} t
                JOIN trips tr ON tr.truck_id = t.id
                WHERE tr.driver_id = ? {self._company_filter("t")} {self._soft_delete_filter("t")}
                ORDER BY t.plate_number ASC""",
            (driver_id,) + self._company_params(),
        )

    def count_active(self) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE active_status = 1 {self._company_filter()} {self._soft_delete_filter()}",
            self._company_params(),
        )
        return row["cnt"] if row else 0

    def get_truck_mileage(self, truck_id: int) -> Optional[float]:
        row = self._fetchone(
            f"SELECT mileage FROM {self.TABLE} WHERE id = ? {self._company_filter()} {self._soft_delete_filter()}",
            (truck_id,) + self._company_params(),
        )
        return float(row["mileage"]) if row and row.get("mileage") is not None else None

    def get_active_truck_ids(self) -> List[int]:
        rows = self._fetchall(
            f"SELECT id FROM {self.TABLE} WHERE active_status = 1 {self._company_filter()} {self._soft_delete_filter()}",
            self._company_params(),
        )
        return [r["id"] for r in rows]

    def get_expiring_insurance(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        from datetime import datetime, timedelta
        target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE insurance_expiry IS NOT NULL AND insurance_expiry != ''"
            " AND insurance_expiry <= ?"
            f" {self._company_filter()} {self._soft_delete_filter()}",
            (target_date,) + self._company_params(),
        )

    # ── Maintenance Records CRUD ─────────────────────────────────────

    def add_maintenance_record(
        self, truck_id: int, maint_type: str, date: str,
        km: Optional[float] = None, cost: Optional[float] = None,
        notes: str = "", provider: str = "", attachment: str = "",
        created_at: str = "", company_id=None,
    ) -> int:
        data = {
            "truck_id": truck_id,
            "maintenance_type": maint_type,
            "date": date,
            "km": km,
            "cost": cost,
            "notes": notes,
            "service_provider": provider,
            "attachment_path": attachment,
            "created_at": created_at,
        }
        if company_id:
            data["company_id"] = company_id
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_MAINT_RECORDS))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE_MAINT_RECORDS} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        commit=True)

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
        where = f"WHERE {' AND '.join(conditions)} " if conditions else "WHERE 1=1 "
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_MAINT_RECORDS} {where}{self._company_filter()} {self._soft_delete_filter()} ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            tuple(params) + self._company_params() + (limit, offset),
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
        where = f"WHERE {' AND '.join(conditions)} " if conditions else "WHERE 1=1 "
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE_MAINT_RECORDS} {where}{self._company_filter()} {self._soft_delete_filter()}",
            tuple(params) + self._company_params(),
        )
        return row["cnt"] if row else 0

    def get_maintenance_record_truck_id(self, record_id: int) -> Optional[int]:
        row = self._fetchone(
            f"SELECT truck_id FROM {self.TABLE_MAINT_RECORDS} WHERE id = ? {self._company_filter()} {self._soft_delete_filter()}",
            (record_id,) + self._company_params(),
        )
        return row["truck_id"] if row else None

    def update_maintenance_record(
        self, record_id: int, maint_type: str, date: str,
        km: Optional[float] = None, cost: Optional[float] = None,
        provider: str = "", notes: str = "",
    ) -> None:
        data = {
            "maintenance_type": maint_type,
            "date": date,
            "km": km,
            "cost": cost,
            "service_provider": provider,
            "notes": notes,
        }
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_MAINT_RECORDS))
        self._execute(
            f"UPDATE {self.TABLE_MAINT_RECORDS} SET maintenance_type=?, date=?, km=?, cost=?, service_provider=?, notes=? WHERE id=? {self._company_filter()}",
            (maint_type, date, km, cost, provider, notes, record_id) + self._company_params(),
        commit=True)

    def delete_maintenance_record(self, record_id: int) -> None:
        """Soft-delete a maintenance record by stamping ``deleted_at``."""
        from database.time_utils import utc_now_iso
        self._execute(
            f"UPDATE {self.TABLE_MAINT_RECORDS} SET deleted_at = ? WHERE id = ? {self._company_filter()}",
            (utc_now_iso(), record_id) + self._company_params(),
        commit=True)

    def get_maintenance_type_counts(self, truck_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT maintenance_type, COUNT(*) as cnt FROM {self.TABLE_MAINT_RECORDS} "
            f"WHERE truck_id = ? {self._company_filter()} {self._soft_delete_filter()} GROUP BY maintenance_type HAVING cnt >= 3",
            (truck_id,) + self._company_params(),
        )

    def get_maintenance_last_date(self, truck_id: int) -> Optional[str]:
        row = self._fetchone(
            f"SELECT date FROM {self.TABLE_MAINT_RECORDS} WHERE truck_id = ? {self._company_filter()} {self._soft_delete_filter()} ORDER BY date DESC LIMIT 1",
            (truck_id,) + self._company_params(),
        )
        return row["date"] if row else None

    def sum_maintenance_cost(self, since_date: Optional[str] = None) -> float:
        query = f"SELECT COALESCE(SUM(cost), 0) AS total FROM {self.TABLE_MAINT_RECORDS} WHERE 1=1 {self._company_filter()} {self._soft_delete_filter()}"
        params = list(self._company_params())
        if since_date:
            query += " AND date >= ?"
            params.append(since_date)
        row = self._fetchone(query, tuple(params))
        return float(row["total"]) if row else 0.0

    def get_maintenance_cost_by_type(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT maintenance_type, SUM(cost) as total FROM {self.TABLE_MAINT_RECORDS} WHERE 1=1 {self._company_filter()} {self._soft_delete_filter()} GROUP BY maintenance_type ORDER BY total DESC",
            self._company_params(),
        )

    def get_maintenance_count_by_type(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT maintenance_type, COUNT(*) as cnt FROM {self.TABLE_MAINT_RECORDS} WHERE 1=1 {self._company_filter()} {self._soft_delete_filter()} GROUP BY maintenance_type ORDER BY cnt DESC",
            self._company_params(),
        )

    def get_top_maintained_trucks(self, limit: int = 5) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT truck_id, COALESCE(SUM(cost), 0) as total FROM {self.TABLE_MAINT_RECORDS} WHERE 1=1 {self._company_filter()} {self._soft_delete_filter()} GROUP BY truck_id ORDER BY total DESC LIMIT ?",
            self._company_params() + (limit,),
        )

    # ── Maintenance Schedules CRUD ───────────────────────────────────

    def add_maintenance_schedule(
        self, truck_id: int, maint_type: str,
        interval_km: Optional[float] = None, interval_months: Optional[int] = None,
        fixed_expiry_date: str = "", last_done_km: Optional[float] = None,
        last_done_date: str = "", created_at: str = "",
        company_id: Optional[int] = None,
    ) -> int:
        data = {
            "truck_id": truck_id,
            "maintenance_type": maint_type,
            "interval_km": interval_km,
            "interval_months": interval_months,
            "fixed_expiry_date": fixed_expiry_date,
            "last_done_km": last_done_km,
            "last_done_date": last_done_date,
            "active": 1,
            "created_at": created_at,
        }
        if company_id:
            data["company_id"] = company_id
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_MAINT_SCHEDULES))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE_MAINT_SCHEDULES} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        commit=True)

    def get_maintenance_schedules_with_overdue(
        self, company_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """All active schedules (with truck plate + mileage) flagged ``overdue``.

        ``overdue`` is computed via the shared :func:`schedule_is_overdue`
        thresholds — the same ones the health-score ``count_overdue_schedules``
        uses, so the mobile list can never disagree with the desktop count.
        """
        rows = self._fetchall(
            f"""SELECT s.*, t.plate_number, t.mileage AS current_km
                FROM {self.TABLE_MAINT_SCHEDULES} s
                LEFT JOIN trucks t ON t.id = s.truck_id
                WHERE s.active = 1 {self._company_filter_for(company_id, "s")} {self._soft_delete_filter("s")}
                ORDER BY s.truck_id, s.maintenance_type""",
            self._company_params_for(company_id),
        )
        for r in rows:
            r["overdue"] = schedule_is_overdue(r)
        return rows

    def get_maintenance_schedules(self, truck_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if truck_id is not None:
            return self._fetchall(
                f"SELECT * FROM {self.TABLE_MAINT_SCHEDULES} WHERE truck_id = ? AND active = 1 {self._company_filter()} {self._soft_delete_filter()} ORDER BY id",
                (truck_id,) + self._company_params(),
            )
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_MAINT_SCHEDULES} WHERE active = 1 {self._company_filter()} {self._soft_delete_filter()} ORDER BY truck_id, id",
            self._company_params(),
        )

    def get_maintenance_schedule(self, truck_id: int, maint_type: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE_MAINT_SCHEDULES} WHERE truck_id = ? AND maintenance_type = ? AND active = 1 {self._company_filter()} {self._soft_delete_filter()}",
            (truck_id, maint_type) + self._company_params(),
        )

    def get_schedule_truck_id(self, schedule_id: int) -> Optional[int]:
        row = self._fetchone(
            f"SELECT truck_id FROM {self.TABLE_MAINT_SCHEDULES} WHERE id = ? {self._company_filter()} {self._soft_delete_filter()}",
            (schedule_id,) + self._company_params(),
        )
        return row["truck_id"] if row else None

    def update_maintenance_schedule(self, schedule_id: int, **fields: Any) -> None:
        self._validate_columns(fields, extra_allowed=set(self.COLUMNS_MAINT_SCHEDULES))
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._execute(
            f"UPDATE {self.TABLE_MAINT_SCHEDULES} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(fields.values()) + (schedule_id,) + self._company_params(),
        commit=True)

    def delete_maintenance_schedule(self, schedule_id: int) -> None:
        """Soft-delete a maintenance schedule by stamping ``deleted_at``."""
        from database.time_utils import utc_now_iso
        self._execute(
            f"UPDATE {self.TABLE_MAINT_SCHEDULES} SET deleted_at = ? WHERE id = ? {self._company_filter()}",
            (utc_now_iso(), schedule_id) + self._company_params(),
        commit=True)

    def count_active_maintenance_schedules(self) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE_MAINT_SCHEDULES} WHERE active = 1 {self._company_filter()} {self._soft_delete_filter()}",
            self._company_params(),
        )
        return row["cnt"] if row else 0

    def get_all_schedules_flat(self) -> List[Dict[str, Any]]:
        """Return all active schedules with truck plate and current mileage joined."""
        return self._fetchall(
            f"""SELECT s.*, t.plate_number, t.mileage AS current_km
                FROM {self.TABLE_MAINT_SCHEDULES} s
                LEFT JOIN trucks t ON t.id = s.truck_id
                WHERE s.active = 1 {self._company_filter("s")} {self._soft_delete_filter("s")}
                ORDER BY s.truck_id, s.maintenance_type""",
            self._company_params(),
        )

    def count_overdue_schedules(self) -> int:
        """Return count of active schedules that are overdue based on km, months, or fixed expiry.

        Delegates each row to the shared :func:`schedule_is_overdue` thresholds
        (behaviour-identical to the historical inline logic).
        """
        rows = self._fetchall(
            f"""SELECT s.*, t.mileage AS current_km
                FROM {self.TABLE_MAINT_SCHEDULES} s
                LEFT JOIN trucks t ON t.id = s.truck_id
                WHERE s.active = 1 {self._company_filter("s")} {self._soft_delete_filter("s")}""",
            self._company_params(),
        )
        return sum(1 for r in rows if schedule_is_overdue(r))

    # ── Analytics Queries ────────────────────────────────────────────

    def get_maintenance_cost_truck_monthly(self, date_from: str, company_id=None) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT truck_id,
                       substr(date, 1, 7) AS ym,
                       COALESCE(SUM(cost), 0) AS total
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL {self._company_filter()} {self._soft_delete_filter()}
                GROUP BY truck_id, ym
                ORDER BY ym, truck_id""",
            (date_from,) + self._company_params(),
        )

    def get_maintenance_cost_monthly(self, date_from: str, company_id=None) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT substr(date, 1, 7) AS ym,
                       COALESCE(SUM(cost), 0) AS total
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL {self._company_filter()} {self._soft_delete_filter()}
                GROUP BY ym
                ORDER BY ym""",
            (date_from,) + self._company_params(),
        )

    def get_maintenance_truck_summary(self, date_from: str, company_id=None) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT truck_id,
                       COALESCE(SUM(cost), 0) AS total_ytd,
                       COALESCE(AVG(cost), 0) AS avg_cost,
                       COUNT(*) AS service_count
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL {self._company_filter()} {self._soft_delete_filter()}
                GROUP BY truck_id
                ORDER BY total_ytd DESC""",
            (date_from,) + self._company_params(),
        )

    def get_maintenance_most_expensive_category(self, date_from: str, company_id=None) -> List[Dict[str, Any]]:
        rows = self._fetchall(
            f"""SELECT truck_id, maintenance_type, COALESCE(SUM(cost), 0) AS total
                FROM {self.TABLE_MAINT_RECORDS}
                WHERE date >= ? AND cost IS NOT NULL {self._company_filter()} {self._soft_delete_filter()}
                GROUP BY truck_id, maintenance_type
                ORDER BY truck_id, total DESC""",
            (date_from,) + self._company_params(),
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
        data = {
            "truck_id": truck_id,
            "score": score,
            "compliance_pct": compliance_pct,
            "overdue_count": overdue_count,
            "recurring_issues": recurring_issues,
            "downtime_days": downtime_days,
            "last_updated": last_updated,
        }
        self._validate_columns(data, extra_allowed=set(self.COLUMNS_HEALTH_SCORES))
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT OR REPLACE INTO {self.TABLE_HEALTH_SCORES} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        commit=True)

    def get_truck_health(self, truck_id: int) -> Optional[Dict[str, Any]]:
        # NOTE: truck_health_scores has no deleted_at column — no soft-delete filter.
        return self._fetchone(
            f"SELECT * FROM {self.TABLE_HEALTH_SCORES} WHERE truck_id = ? {self._company_filter()}",
            (truck_id,) + self._company_params(),
        )

    def get_all_truck_health(self) -> List[Dict[str, Any]]:
        # NOTE: truck_health_scores has no deleted_at column — no soft-delete filter.
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_HEALTH_SCORES} WHERE 1=1 {self._company_filter()}",
            self._company_params(),
        )
