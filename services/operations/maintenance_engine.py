import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from repositories.fleet_repository import FleetRepository
from repositories.trip_repository import TripRepository
from services.fleet_maintenance_service import (
    FleetMaintenanceService,
    MaintType,
)
from services.operations.alert_manager import AlertManager, AlertType, Severity
from services.operations.event_bus import (
    DAILY_CHECK,
    MAINTENANCE_ADDED,
    SYSTEM_STARTUP,
    TRUCK_CREATED,
    TRUCK_UPDATED,
    EventBus,
)
from services.operations.rules import Rules

logger = logging.getLogger("operations.maintenance_engine")


class MaintenanceEngine:
    def __init__(self, db):
        self._db = db
        self._alert_mgr = AlertManager()
        self._event_bus = EventBus()
        self._rules = Rules()
        self._subscribe()

    def _subscribe(self):
        self._event_bus.subscribe(TRUCK_CREATED, self._on_truck_event)
        self._event_bus.subscribe(TRUCK_UPDATED, self._on_truck_event)
        self._event_bus.subscribe(MAINTENANCE_ADDED, self._on_maintenance_event)
        self._event_bus.subscribe(DAILY_CHECK, self._on_daily_check)
        self._event_bus.subscribe(SYSTEM_STARTUP, self._on_system_startup)
        logger.info("MaintenanceEngine subscribed to events")

    def shutdown(self):
        try:
            self._event_bus.unsubscribe(TRUCK_CREATED, self._on_truck_event)
            self._event_bus.unsubscribe(TRUCK_UPDATED, self._on_truck_event)
            self._event_bus.unsubscribe(MAINTENANCE_ADDED, self._on_maintenance_event)
            self._event_bus.unsubscribe(DAILY_CHECK, self._on_daily_check)
            self._event_bus.unsubscribe(SYSTEM_STARTUP, self._on_system_startup)
            logger.debug("MaintenanceEngine unsubscribed events")
        except Exception:
            pass

    # ── Event handlers ─────────────────────────────────────────────

    def _on_truck_event(self, ev: dict[str, Any]) -> None:
        truck_id = ev["data"].get("truck_id")
        if truck_id:
            self.evaluate_truck(truck_id)

    def _on_maintenance_event(self, ev: dict[str, Any]) -> None:
        truck_id = ev["data"].get("truck_id")
        if truck_id:
            self.evaluate_truck(truck_id)

    def _on_daily_check(self, ev: dict[str, Any]) -> None:
        self.evaluate_all()

    def _on_system_startup(self, ev: dict[str, Any]) -> None:
        self.evaluate_all()

    # ── Evaluation ─────────────────────────────────────────────────

    def evaluate_all(self) -> int:
        count = 0
        try:
            trucks = self._db.get_all_trucks(active_only=True)
            for t in trucks:
                count += self._evaluate_single(t)
            count += self.evaluate_driver_hours()
            count += self._evaluate_document_expiries()
            count += self._evaluate_contract_expiries()
        except Exception as e:
            logger.error("evaluate_all failed: %s", e)
        logger.info("MaintenanceEngine evaluated all trucks: %d alerts generated", count)
        return count

    def evaluate_truck(self, truck_id: int) -> int:
        count = 0
        try:
            truck = FleetRepository(self._db).get_by_id(truck_id)
            if truck:
                count = self._evaluate_single(truck)
        except Exception as e:
            logger.error("evaluate_truck %s failed: %s", truck_id, e)
        return count

    _ALERT_TYPES_EVALUATED = {
        AlertType.INSPECTION, AlertType.INSURANCE, AlertType.MAINTENANCE,
        AlertType.INACTIVE_TRUCK, AlertType.TACHOGRAPH_EXPIRY,
    }

    @staticmethod
    def _log_eval_failure(context: str, exc: BaseException, truck_id=None, plate=""):
        """Log a structured warning for evaluation failures (never silent)."""
        tid = f" truck={truck_id}" if truck_id else ""
        logger.warning("Maint eval %s failed%s: %s", context, tid, exc)

    def _evaluate_single(self, truck: dict[str, Any]) -> int:
        count = 0
        truck_id = str(truck["id"])
        truck_id_int = int(truck["id"])
        plate = truck.get("plate_number", "?")
        today = datetime.now()

        # Track which single-alert types still have an active condition,
        # so we can resolve stale alerts after evaluation completes.
        active_conditions: set[AlertType] = set()

        # ── Inspection expiry ──────────────────────────────────────
        insp_val = truck.get("inspection_expiry")
        if insp_val:
            try:
                expiry = datetime.strptime(insp_val, "%Y-%m-%d")
                diff = (expiry - today).days
                warning_days = self._rules.get("inspection_warning_days", 10)
                existing = self._alert_mgr.get_active_by_type_and_entity(AlertType.INSPECTION, truck_id)
                if diff < 0:
                    active_conditions.add(AlertType.INSPECTION)
                    if not existing:
                        self._alert_mgr.create_alert(
                            AlertType.INSPECTION, Severity.CRITICAL,
                            f"Inspection expired for {plate}",
                            f"ITP expired {abs(diff)} days ago on {insp_val}",
                            truck_id=truck_id,
                        )
                        count += 1
                elif diff <= warning_days:
                    active_conditions.add(AlertType.INSPECTION)
                    if not existing:
                        self._alert_mgr.create_alert(
                            AlertType.INSPECTION, Severity.WARNING,
                            f"Inspection due for {plate}",
                            f"ITP expires in {diff} days on {insp_val}",
                            truck_id=truck_id,
                        )
                        count += 1
            except Exception as exc:
                self._log_eval_failure("inspection", exc, truck_id, plate)

        # ── Insurance expiry ───────────────────────────────────────
        ins_val = truck.get("insurance_expiry")
        if ins_val:
            try:
                expiry = datetime.strptime(ins_val, "%Y-%m-%d")
                diff = (expiry - today).days
                warning_days = self._rules.get("insurance_warning_days", 10)
                existing = self._alert_mgr.get_active_by_type_and_entity(AlertType.INSURANCE, truck_id)
                if diff < 0:
                    active_conditions.add(AlertType.INSURANCE)
                    if not existing:
                        self._alert_mgr.create_alert(
                            AlertType.INSURANCE, Severity.CRITICAL,
                            f"Insurance expired for {plate}",
                            f"Insurance expired {abs(diff)} days ago on {ins_val}",
                            truck_id=truck_id,
                        )
                        count += 1
                elif diff <= warning_days:
                    active_conditions.add(AlertType.INSURANCE)
                    if not existing:
                        self._alert_mgr.create_alert(
                            AlertType.INSURANCE, Severity.WARNING,
                            f"Insurance due for {plate}",
                            f"Insurance expires in {diff} days on {ins_val}",
                            truck_id=truck_id,
                        )
                        count += 1
            except Exception as exc:
                self._log_eval_failure("insurance", exc, truck_id, plate)

        # ── Maintenance schedules (replaces legacy maintenance_due field) ──
        _schedule_alert_created = False
        _schedules_evaluated = False
        try:
            maint_svc = FleetMaintenanceService(self._db)
            schedules = maint_svc.get_schedules(truck_id=truck_id_int)
            km_buffer = self._rules.get("service_km_buffer", 5000)

            for s in schedules:
                _schedules_evaluated = True
                pred = maint_svc.predict_next_service(truck_id_int, s["maintenance_type"])
                if not pred:
                    continue
                try:
                    mt = MaintType(pred["type"])
                except ValueError:
                    mt = MaintType.CUSTOM
                display_name = mt.value.replace("_", " ").title()

                if pred.get("overdue"):
                    reason = ""
                    if pred.get("due_by_km") == 0:
                        reason = "KM overdue"
                    elif pred.get("remaining_days") is not None and pred["remaining_days"] <= 0:
                        reason = "past due date"
                    else:
                        reason = "overdue"
                    # Check if a matching maintenance alert already exists
                    existing = self._alert_mgr.get_active_by_type_and_entity(
                        AlertType.MAINTENANCE, truck_id
                    )
                    if not existing:
                        self._alert_mgr.create_alert(
                            AlertType.MAINTENANCE, Severity.CRITICAL,
                            f"{display_name} overdue for {plate}",
                            f"{display_name} — {reason}",
                            truck_id=truck_id,
                        )
                        count += 1
                        _schedule_alert_created = True
                elif pred.get("remaining_km") is not None and pred["remaining_km"] < km_buffer:
                    existing = self._alert_mgr.get_active_by_type_and_entity(
                        AlertType.MAINTENANCE, truck_id
                    )
                    if not existing:
                        self._alert_mgr.create_alert(
                            AlertType.MAINTENANCE, Severity.WARNING,
                            f"{display_name} due soon for {plate}",
                            f"{pred['remaining_km']:,.0f} km remaining until next service",
                            truck_id=truck_id,
                        )
                        count += 1
                        _schedule_alert_created = True
        except Exception as exc:
            self._log_eval_failure("schedules", exc, truck_id, plate)

        # ── Inactive truck (query by truck_id FK, not plate string) ─────
        inactive_days = self._rules.get("inactive_truck_days", 30)
        try:
            last_activity = TripRepository(self._db).get_last_activity_by_truck_id(truck_id_int)
            if last_activity:
                last_date = datetime.strptime(last_activity[:10], "%Y-%m-%d")
                idle = (today - last_date).days
                existing = self._alert_mgr.get_active_by_type_and_entity(AlertType.INACTIVE_TRUCK, truck_id)
                if idle > inactive_days:
                    active_conditions.add(AlertType.INACTIVE_TRUCK)
                    if not existing:
                        self._alert_mgr.create_alert(
                            AlertType.INACTIVE_TRUCK, Severity.INFO,
                            f"Truck {plate} inactive",
                            f"No trips for {idle} days (last: {last_activity[:10]})",
                            truck_id=truck_id,
                        )
                        count += 1
        except Exception as exc:
            self._log_eval_failure("inactive_truck", exc, truck_id, plate)

        # ── Tachograph calibration expiry ──────────────────────────
        count += self.evaluate_tachograph_calibration_for_truck(truck)

        # ── Resolve stale single-alert types ─────────────────────────
        for atype in self._ALERT_TYPES_EVALUATED:
            if atype in (AlertType.MAINTENANCE, AlertType.TACHOGRAPH_EXPIRY):
                continue
            if atype not in active_conditions:
                try:
                    stale = self._alert_mgr.get_active_by_type_and_entity(atype, truck_id)
                    if stale:
                        self._alert_mgr.resolve_alert(stale.id)
                except Exception as exc:
                    self._log_eval_failure(f"resolve_stale_{atype.value}", exc, truck_id, plate)

        # ── Resolve stale MAINTENANCE alerts ─────────────────────────
        # Only when the schedule evaluation actually ran and no schedule
        # triggered an alert, resolve any leftover MAINTENANCE alert.
        if _schedules_evaluated and not _schedule_alert_created:
            stale_maint = self._alert_mgr.get_active_by_type_and_entity(
                AlertType.MAINTENANCE, truck_id
            )
            if stale_maint:
                self._alert_mgr.resolve_alert(stale_maint.id)

        return count

    # ── Tachograph evaluations ───────────────────────────────────

    def evaluate_tachograph_calibration_for_truck(self, truck: dict[str, Any]) -> int:
        """Evaluate tachograph calibration expiry for a single truck."""
        count = 0
        truck_id = str(truck["id"])
        plate = truck.get("plate_number", "?")
        try:
            from repositories.tacho_vehicle_data_repository import TachoVehicleDataRepository
            repo = TachoVehicleDataRepository(self._db)
            latest = repo.get_latest_by_truck(int(truck_id))
            if not latest or not latest.get("calibration_expiry"):
                return 0
            expiry_str = latest["calibration_expiry"]
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            days_remaining = (expiry - date.today()).days

            if days_remaining < 0:
                severity = Severity.CRITICAL
                msg = f"Tachograph calibration EXPIRED {abs(days_remaining)} days ago — Truck {plate}"
            elif days_remaining <= 7:
                severity = Severity.CRITICAL
                msg = f"Tachograph calibration expires in {days_remaining} days — Truck {plate}"
            elif days_remaining <= 30:
                severity = Severity.WARNING
                msg = f"Tachograph calibration expires in {days_remaining} days — Truck {plate}"
            else:
                # Calibration is still more than 30 days away — resolve
                # any stale tacho alert that may exist from a previous
                # evaluation pass.
                existing = self._alert_mgr.get_active_by_type_and_entity(
                    AlertType.TACHOGRAPH_EXPIRY, truck_id
                )
                if existing:
                    self._alert_mgr.resolve_alert(existing.id)
                return 0

            existing = self._alert_mgr.get_active_by_type_and_entity(
                AlertType.TACHOGRAPH_EXPIRY, truck_id
            )
            if not existing:
                self._alert_mgr.create_alert(
                    AlertType.TACHOGRAPH_EXPIRY,
                    severity,
                    f"Tachograph calibration for {plate}",
                    msg,
                    truck_id=truck_id,
                    metadata={
                        "calibration_expiry": expiry_str,
                        "days_remaining": days_remaining,
                    },
                )
                count += 1
            elif existing.severity != severity:
                self._alert_mgr.update_severity(existing.id, severity, msg)
        except Exception as e:
            logger.debug("evaluate_tachograph_calibration_for_truck failed: %s", e)
        return count

    def evaluate_tachograph_calibration(self) -> int:
        """Evaluate tachograph calibration expiry for all active trucks."""
        count = 0
        try:
            from repositories.fleet_repository import FleetRepository
            fleet_repo = FleetRepository(self._db)
            for truck in fleet_repo.get_active_trucks():
                count += self.evaluate_tachograph_calibration_for_truck(truck)
        except Exception as e:
            logger.error("evaluate_tachograph_calibration failed: %s", e)
        return count

    def evaluate_driver_hours(self) -> int:
        """Check for EU driving hours violations in recent tacho data (last 14 days)."""
        count = 0
        try:
            from repositories.driver_repository import DriverRepository
            from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
            driver_repo = DriverRepository(self._db)
            activity_repo = TachoDriverActivityRepository(self._db)
            all_drivers = driver_repo.get_active_drivers()
            from_date = date.today() - timedelta(days=14)

            for driver in all_drivers:
                driver_id = driver["id"]
                records = activity_repo.get_by_driver(driver_id, from_date)
                if not records:
                    continue

                # Weekly total (last 7 days)
                cutoff_7 = date.today() - timedelta(days=7)
                last_7 = [r for r in records if r.get("activity_date") and r["activity_date"] >= cutoff_7.isoformat()]
                weekly_driving_h = sum(r.get("driving_minutes", 0) or 0 for r in last_7) / 60

                if weekly_driving_h > 56:
                    msg = f"Driver {driver.get('name', '?')}: weekly driving {weekly_driving_h:.1f}h exceeds 56h EU limit"
                    if self._create_driver_alert_if_new(
                        AlertType.DRIVER_HOURS_WEEKLY, str(driver_id), Severity.CRITICAL, msg
                    ):
                        count += 1
                elif weekly_driving_h > 50:
                    msg = f"Driver {driver.get('name', '?')}: weekly driving {weekly_driving_h:.1f}h approaching 56h EU limit"
                    if self._create_driver_alert_if_new(
                        AlertType.DRIVER_HOURS_WEEKLY, str(driver_id), Severity.WARNING, msg
                    ):
                        count += 1

                # Daily violations from stored records
                for record in records:
                    violations = json.loads(record.get("violations") or "[]")
                    for v in violations:
                        msg = f"Driver {driver.get('name', '?')} — {v} on {record.get('activity_date', '?')}"
                        if self._create_driver_alert_if_new(
                            AlertType.DRIVER_HOURS_DAILY, str(driver_id), Severity.WARNING, msg
                        ):
                            count += 1
        except Exception as e:
            logger.error("evaluate_driver_hours failed: %s", e)
        return count

    def _create_driver_alert_if_new(self, alert_type: AlertType, driver_id: str,
                                    severity: Severity, message: str) -> bool:
        """Create a driver alert if none exists for this type+driver. Returns True if created."""
        existing = self._alert_mgr.get_active_by_type_and_entity(
            alert_type, driver_id, entity_field="driver_id"
        )
        if not existing:
            self._alert_mgr.create_alert(
                alert_type=alert_type,
                severity=severity,
                title=message[:60],
                message=message,
                driver_id=driver_id,
            )
            return True
        return False

    # ── Document / Contract Expiry Checks ───────────────────────────

    def _evaluate_document_expiries(self) -> int:
        try:
            from repositories.document_repository import DocumentRepository
            from services.document.expiry_service import ExpiryService
            svc = ExpiryService(DocumentRepository(self._db))
            return svc.evaluate_document_expiries(alert_mgr=self._alert_mgr)
        except Exception as e:
            logger.debug("Document expiry check skipped: %s", e)
        return 0

    def _evaluate_contract_expiries(self) -> int:
        try:
            from datetime import datetime

            from repositories.document_repository import DocumentRepository
            from services.document.contract_service import ContractService
            svc = ContractService(DocumentRepository(self._db))
            count = 0
            contracts = svc.get_expiring_contracts(30)
            today = datetime.now().strftime("%Y-%m-%d")
            for c in contracts:
                severity = Severity.CRITICAL if today > (c.get("end_date") or "") else Severity.WARNING
                self._alert_mgr.create_alert(
                    alert_type=AlertType.CONTRACT_EXPIRY,
                    severity=severity,
                    title=f"Contract expiring: {c.get('contract_type', '')}",
                    message=f"Contract #{c.get('id')} for client #{c.get('client_id')} expires {c.get('end_date')}",
                    truck_id=None, trip_id=None,
                    metadata={"contract_id": c["id"], "client_id": c.get("client_id")},
                )
                count += 1
            return count
        except Exception as e:
            logger.debug("Contract expiry check skipped: %s", e)
        return 0
