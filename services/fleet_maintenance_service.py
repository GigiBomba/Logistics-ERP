import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from database.db_manager import DatabaseManager
from repositories.fleet_repository import FleetRepository

logger = logging.getLogger("fleet_maintenance")


class MaintType(str, Enum):
    OIL_CHANGE = "oil_change"
    TIRE_REPLACEMENT = "tire_replacement"
    BRAKES = "brakes"
    ENGINE = "engine"
    TRANSMISSION = "transmission"
    INSPECTION = "inspection"
    INSURANCE = "insurance"
    REPAIRS = "repairs"
    CUSTOM = "custom"


MAINT_DISPLAY = {
    MaintType.OIL_CHANGE: "Oil Change",
    MaintType.TIRE_REPLACEMENT: "Tire Replacement",
    MaintType.BRAKES: "Brakes",
    MaintType.ENGINE: "Engine",
    MaintType.TRANSMISSION: "Transmission",
    MaintType.INSPECTION: "Inspection",
    MaintType.INSURANCE: "Insurance",
    MaintType.REPAIRS: "Repairs",
    MaintType.CUSTOM: "Custom",
}

MAINT_ICONS = {
    MaintType.OIL_CHANGE: "\U0001F6E1\uFE0F",
    MaintType.TIRE_REPLACEMENT: "\U0001F7E5",
    MaintType.BRAKES: "\u26D4",
    MaintType.ENGINE: "\u2699\uFE0F",
    MaintType.TRANSMISSION: "\u26A1",
    MaintType.INSPECTION: "\U0001F4CB",
    MaintType.INSURANCE: "\U0001F3E6",
    MaintType.REPAIRS: "\U0001F527",
    MaintType.CUSTOM: "\u2699\uFE0F",
}

MAINT_DEFAULT_INTERVALS = {
    MaintType.OIL_CHANGE: (15000, 6),
    MaintType.TIRE_REPLACEMENT: (60000, 24),
    MaintType.BRAKES: (40000, 12),
    MaintType.ENGINE: (100000, 36),
    MaintType.TRANSMISSION: (80000, 24),
    MaintType.INSPECTION: (None, 12),
    MaintType.INSURANCE: (None, 12),
    MaintType.REPAIRS: (None, None),
    MaintType.CUSTOM: (None, None),
}


@dataclass
class MaintRecord:
    id: int = 0
    truck_id: int = 0
    maintenance_type: str = "custom"
    date: str = ""
    km: Optional[float] = None
    cost: Optional[float] = None
    notes: str = ""
    service_provider: str = ""
    attachment_path: str = ""
    created_at: str = ""

    def display_type(self) -> str:
        try:
            return MAINT_DISPLAY.get(MaintType(self.maintenance_type), self.maintenance_type.replace("_", " ").title())
        except ValueError:
            return self.maintenance_type.replace("_", " ").title()

    def icon(self) -> str:
        try:
            return MAINT_ICONS.get(MaintType(self.maintenance_type), "\u2699\uFE0F")
        except ValueError:
            return "\u2699\uFE0F"


@dataclass
class MaintSchedule:
    id: int = 0
    truck_id: int = 0
    maintenance_type: str = "custom"
    interval_km: Optional[float] = None
    interval_months: Optional[int] = None
    fixed_expiry_date: str = ""
    last_done_km: Optional[float] = None
    last_done_date: str = ""
    active: int = 1
    created_at: str = ""


@dataclass
class TruckHealth:
    truck_id: int = 0
    score: int = 100
    compliance_pct: float = 100.0
    overdue_count: int = 0
    recurring_issues: int = 0
    downtime_days: int = 0
    last_updated: str = ""


class FleetMaintenanceService:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self._fleet_repo = FleetRepository(db)
        self._health_cache: Dict[int, TruckHealth] = {}
        self._cache_lock = threading.Lock()
        self._summary_cache: Optional[Dict[str, Any]] = None
        self._summary_ts: Optional[float] = None
        self._summary_ttl = 60.0

    # ── Maintenance Records ────────────────────────────────────────

    def add_record(
        self,
        truck_id: int,
        maint_type: str,
        date: str,
        km: Optional[float] = None,
        cost: Optional[float] = None,
        notes: str = "",
        provider: str = "",
        attachment: str = "",
    ) -> int:
        now = datetime.now().isoformat()
        rid = self._fleet_repo.add_maintenance_record(
            truck_id, maint_type, date, km, cost, notes, provider, attachment, now,
        )
        self._invalidate_cache(truck_id)
        logger.info("Maint record %d added for truck %d: %s", rid, truck_id, maint_type)
        
        # Auto-update corresponding schedule's last_done_km and last_done_date
        self._auto_update_schedule_on_service(truck_id, maint_type, date, km)
        
        return rid

    def _auto_update_schedule_on_service(
        self, truck_id: int, maint_type: str, date: str, km: Optional[float]
    ) -> None:
        """Auto-update maintenance schedule when a service record is added."""
        try:
            # Check if there's a schedule for this truck and maintenance type
            schedule = self._fleet_repo.get_maintenance_schedule(truck_id, maint_type)
            if not schedule:
                return
            
            # Get truck's current odometer reading
            current_km = self._fleet_repo.get_truck_mileage(truck_id)
            
            # Use the provided km if available, otherwise use truck's current odometer
            service_km = km if km is not None else current_km
            
            # Update the schedule's last_done_km and last_done_date
            update_fields = {"last_done_date": date}
            if service_km is not None:
                update_fields["last_done_km"] = service_km
            
            self._fleet_repo.update_maintenance_schedule(schedule["id"], **update_fields)
            logger.info(
                "Auto-updated schedule %d for truck %d: last_done_km=%s, last_done_date=%s",
                schedule["id"], truck_id, service_km, date
            )
        except Exception as e:
            logger.warning("Failed to auto-update schedule for truck %d: %s", truck_id, e)

    def get_records(
        self, truck_id: Optional[int] = None, maint_type: Optional[str] = None,
        limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        return self._fleet_repo.get_maintenance_records(truck_id, maint_type, limit, offset)

    def get_record_count(self, truck_id: Optional[int] = None, maint_type: Optional[str] = None) -> int:
        return self._fleet_repo.count_maintenance_records(truck_id, maint_type)

    def update_record(self, record_id: int, maint_type: str, date: str,
                      km: Optional[float] = None, cost: Optional[float] = None,
                      provider: str = "", notes: str = "") -> bool:
        truck_id = self._fleet_repo.get_maintenance_record_truck_id(record_id)
        if truck_id is None:
            return False
        self._fleet_repo.update_maintenance_record(record_id, maint_type, date, km, cost, provider, notes)
        self._invalidate_cache(truck_id)
        return True

    def delete_record(self, record_id: int) -> bool:
        truck_id = self._fleet_repo.get_maintenance_record_truck_id(record_id)
        if truck_id is None:
            return False
        self._fleet_repo.delete_maintenance_record(record_id)
        self._invalidate_cache(truck_id)
        return True

    # ── Schedules ──────────────────────────────────────────────────

    def add_schedule(
        self, truck_id: int, maint_type: str,
        interval_km: Optional[float] = None,
        interval_months: Optional[int] = None,
        fixed_expiry_date: str = "",
        last_done_km: Optional[float] = None,
        last_done_date: str = "",
    ) -> int:
        now = datetime.now().isoformat()
        sid = self._fleet_repo.add_maintenance_schedule(
            truck_id, maint_type, interval_km, interval_months,
            fixed_expiry_date, last_done_km, last_done_date, now,
        )
        self._invalidate_cache(truck_id)
        return sid

    def get_schedules(self, truck_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._fleet_repo.get_maintenance_schedules(truck_id)

    def update_schedule(
        self, schedule_id: int,
        interval_km: Optional[float] = None,
        interval_months: Optional[int] = None,
        fixed_expiry_date: str = "",
        last_done_km: Optional[float] = None,
        last_done_date: str = "",
        active: Optional[int] = None,
    ) -> bool:
        fields = {}
        if interval_km is not None:
            fields["interval_km"] = interval_km
        if interval_months is not None:
            fields["interval_months"] = interval_months
        if fixed_expiry_date:
            fields["fixed_expiry_date"] = fixed_expiry_date
        if last_done_km is not None:
            fields["last_done_km"] = last_done_km
        if last_done_date:
            fields["last_done_date"] = last_done_date
        if active is not None:
            fields["active"] = active
        if not fields:
            return False
        self._fleet_repo.update_maintenance_schedule(schedule_id, **fields)
        truck_id = self._fleet_repo.get_schedule_truck_id(schedule_id)
        if truck_id is not None:
            self._invalidate_cache(truck_id)
        return True

    def delete_schedule(self, schedule_id: int) -> bool:
        truck_id = self._fleet_repo.get_schedule_truck_id(schedule_id)
        if truck_id is None:
            return False
        self._fleet_repo.delete_maintenance_schedule(schedule_id)
        self._invalidate_cache(truck_id)
        return True

    # ── Predictions ────────────────────────────────────────────────

    def predict_next_service(self, truck_id: int, maint_type: str) -> Optional[Dict[str, Any]]:
        s = self._fleet_repo.get_maintenance_schedule(truck_id, maint_type)
        if not s:
            return None
        last_km = s.get("last_done_km")
        last_date = s.get("last_done_date")
        interval_km = s.get("interval_km")
        interval_months = s.get("interval_months")
        fixed_expiry = s.get("fixed_expiry_date")

        truck = self._fleet_repo.get_truck_mileage(truck_id)
        current_km = truck if truck is not None else 0

        result = {"type": maint_type, "due_by_km": None, "due_by_date": None, "overdue": False, "due_km": None}

        if fixed_expiry:
            result["due_by_date"] = fixed_expiry
            try:
                expiry = datetime.strptime(fixed_expiry, "%Y-%m-%d")
                if expiry < datetime.now():
                    result["overdue"] = True
            except Exception:
                pass

        km_remaining = None
        if interval_km and last_km is not None:
            next_km = float(last_km) + interval_km
            result["due_km"] = next_km
            remaining = next_km - current_km
            result["due_by_km"] = max(0, remaining)
            if remaining <= 0:
                result["overdue"] = True
            km_remaining = remaining

        date_remaining = None
        if interval_months and last_date:
            try:
                last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                due_dt = last_dt + timedelta(days=interval_months * 30)
                result["due_by_date"] = due_dt.strftime("%d/%m/%Y")
                remaining_days = (due_dt - datetime.now()).days
                date_remaining = remaining_days
                if remaining_days <= 0:
                    result["overdue"] = True
            except Exception:
                pass

        result["current_km"] = current_km
        result["remaining_km"] = km_remaining
        result["remaining_days"] = date_remaining

        return result

    def predict_all_upcoming(self, truck_id: int, days_ahead: int = 30) -> List[Dict[str, Any]]:
        results = []
        for mt in MaintType:
            pred = self.predict_next_service(truck_id, mt.value)
            if pred and (pred.get("overdue") or (
                pred.get("remaining_days") is not None and pred["remaining_days"] <= days_ahead
            )):
                results.append(pred)
        return results

    # ── Health Score ───────────────────────────────────────────────

    def compute_health(self, truck_id: int) -> TruckHealth:
        now = datetime.now()

        overdue = 0
        schedules = self.get_schedules(truck_id)
        for s in schedules:
            pred = self.predict_next_service(truck_id, s["maintenance_type"])
            if pred and pred.get("overdue"):
                overdue += 1

        recurring = 0
        type_counts = self._fleet_repo.get_maintenance_type_counts(truck_id)
        recurring = len(type_counts)

        downtime = 0
        try:
            last_date = self._fleet_repo.get_maintenance_last_date(truck_id)
            if last_date:
                try:
                    last_dt = datetime.strptime(last_date[:10], "%Y-%m-%d")
                    downtime = (now - last_dt).days
                except Exception:
                    pass
        except Exception:
            pass

        penalty = overdue * 15 + recurring * 10 + min(downtime // 30, 30)
        score = max(0, 100 - penalty)
        compliance = max(0, 100 - overdue * 10)

        health = TruckHealth(
            truck_id=truck_id,
            score=score,
            compliance_pct=compliance,
            overdue_count=overdue,
            recurring_issues=recurring,
            downtime_days=downtime,
            last_updated=now.isoformat(),
        )

        with self._cache_lock:
            self._health_cache[truck_id] = health

        self._fleet_repo.upsert_truck_health(
            truck_id, score, compliance, overdue, recurring, downtime, now.isoformat(),
        )

        return health

    def get_health(self, truck_id: int, force_refresh: bool = False) -> TruckHealth:
        if not force_refresh:
            with self._cache_lock:
                if truck_id in self._health_cache:
                    return self._health_cache[truck_id]
        row = self._fleet_repo.get_truck_health(truck_id)
        if row and not force_refresh:
            health = TruckHealth(**row)
            with self._cache_lock:
                self._health_cache[truck_id] = health
            return health
        return self.compute_health(truck_id)

    def get_all_health(self, force_refresh: bool = False) -> List[TruckHealth]:
        if force_refresh:
            ids = self._fleet_repo.get_active_truck_ids()
            return [self.compute_health(tid) for tid in ids]
        rows = self._fleet_repo.get_all_truck_health()
        results = []
        for r in rows:
            health = TruckHealth(**r)
            with self._cache_lock:
                self._health_cache[health.truck_id] = health
            results.append(health)
        return results

    # ── Summary / Dashboard ────────────────────────────────────────

    def get_summary(self, force: bool = False) -> Dict[str, Any]:
        now_ts = datetime.now().timestamp()
        if not force and self._summary_cache and (now_ts - (self._summary_ts or 0)) < self._summary_ttl:
            return self._summary_cache

        result = {}

        result["total_records"] = self._fleet_repo.count_maintenance_records()
        result["total_cost"] = self._fleet_repo.sum_maintenance_cost()

        _30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        result["cost_30d"] = self._fleet_repo.sum_maintenance_cost(since_date=_30d)
        result["records_30d"] = self._fleet_repo.count_maintenance_records(since_date=_30d)

        result["trucks_needing_service"] = self._fleet_repo.count_active_maintenance_schedules()

        overdue_schedules = 0
        for s in self.get_schedules():
            pred = self.predict_next_service(s["truck_id"], s["maintenance_type"])
            if pred and pred.get("overdue"):
                overdue_schedules += 1
        result["overdue_schedules"] = overdue_schedules

        type_cost = self._fleet_repo.get_maintenance_cost_by_type()
        result["cost_by_type"] = {r["maintenance_type"]: float(r["total"]) for r in type_cost}

        type_count = self._fleet_repo.get_maintenance_count_by_type()
        result["count_by_type"] = {r["maintenance_type"]: r["cnt"] for r in type_count}

        cheapest_trucks = self._fleet_repo.get_top_maintained_trucks(limit=5)
        result["top_maintained_trucks"] = [{"truck_id": r["truck_id"], "total_cost": float(r["total"])} for r in cheapest_trucks]

        health_scores = self.get_all_health()
        result["avg_health"] = round(sum(h.score for h in health_scores) / max(len(health_scores), 1), 1)

        self._summary_cache = result
        self._summary_ts = now_ts
        return result

    def _invalidate_cache(self, truck_id: int):
        with self._cache_lock:
            self._health_cache.pop(truck_id, None)
        self._summary_cache = None
        self._summary_ts = None
