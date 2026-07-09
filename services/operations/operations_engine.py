import logging
import threading
from datetime import datetime
from typing import Optional

from services.operations.alert_manager import Alert, AlertManager, AlertType, Severity
from services.operations.cmr_auto_generator import AutoCMRGenerator
from services.operations.dunner_engine import DunnerEngine
from services.operations.event_bus import (
    DAILY_CHECK,
    SYSTEM_STARTUP,
    TRIP_STATUS_CHANGED,
    EventBus,
)
from services.operations.maintenance_engine import MaintenanceEngine
from services.operations.notification_center import NotificationCenter
from services.operations.rules import Rules
from services.operations.trip_status_workflow import TripStatusWorkflow
from services.operations.undo_stack import UndoStack

logger = logging.getLogger("operations.operations_engine")


class OperationsEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db=None, prefs=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db=None, prefs=None):
        if self._initialized:
            if db is not None and self._db is None:
                self._db = db
            return
        self._initialized = True
        self._db = db
        self._prefs = prefs
        self._event_bus = EventBus()
        self._event_bus.inject_db(db)
        self._alert_mgr = AlertManager(db)
        self._rules = Rules()
        from services.trip_service import TripService
        self._trip_service = TripService(db) if db else None
        self._maintenance_engine = MaintenanceEngine(db) if db else None
        self._notification_center = NotificationCenter(db) if db else None
        self._dunner_engine = DunnerEngine(db, self._notification_center, prefs) if db else None
        self._undo_stack = UndoStack()
        self._cmr_generator = AutoCMRGenerator(db, prefs, self._alert_mgr) if db else None
        self._trip_workflow = TripStatusWorkflow(
            db, self._trip_service, self._event_bus, self._maintenance_engine, self._undo_stack,
        ) if db else None
        self._stop_event = threading.Event()
        self._stop_event.set()  # start as stopped
        logger.info("OperationsEngine initialized")

    def undo_last(self) -> bool:
        cmd = self._undo_stack.last_undo_command()
        if not cmd:
            return False
        current_status = None
        try:
            trip = self._trip_service.get_by_id(cmd.trip_id) if self._trip_service else None
            if trip:
                current_status = trip.get("status")
        except Exception:
            pass
        cmd = self._undo_stack.undo(current_status=current_status)
        if not cmd:
            return False
        return self.force_trip_status(cmd.trip_id, cmd.old_status, skip_undo=True)

    def redo_last(self) -> bool:
        cmd = self._undo_stack.redo()
        if not cmd:
            return False
        return self.force_trip_status(cmd.trip_id, cmd.new_status, skip_undo=True)

    @property
    def undo_stack(self):
        return self._undo_stack

    def start(self):
        if not self._stop_event.is_set():
            return  # already running
        self._stop_event.clear()
        self._event_bus.publish(SYSTEM_STARTUP, {})
        self._schedule_daily_check()
        if self._maintenance_engine:
            self._maintenance_engine.evaluate_all()
        if self._dunner_engine:
            self._dunner_engine.evaluate_all()
        if self._db:
            self._configure_smtp_from_db()
            self.migrate_existing_data()
        self._event_bus.subscribe(TRIP_STATUS_CHANGED, self._cmr_generator.on_trip_in_transit)
        logger.info("OperationsEngine started")

    def _schedule_daily_check(self):
        if hasattr(self, "_daily_timer"):
            self._daily_timer.cancel()
        def _publish_and_reschedule():
            if self._stop_event.is_set():
                return
            self._event_bus.publish(DAILY_CHECK, {})
            if self._maintenance_engine:
                self._maintenance_engine.evaluate_all()
            if self._stop_event.is_set():
                return
            self._daily_timer = threading.Timer(86400, _publish_and_reschedule)
            self._daily_timer.daemon = True
            self._daily_timer.start()
        self._daily_timer = threading.Timer(86400, _publish_and_reschedule)
        self._daily_timer.daemon = True
        self._daily_timer.start()

    def _configure_smtp_from_db(self):
        if not self._prefs:
            return
        try:
            cfg = self._prefs.get_smtp_config()
            if cfg.get("smtp_server") and cfg.get("smtp_user"):
                port = int(cfg.get("smtp_port", 587))
                self._notification_center.configure_smtp(
                    cfg["smtp_server"], port, cfg["smtp_user"], cfg.get("smtp_password", "")
                )
        except Exception as e:
            logger.debug("Could not configure SMTP from settings: %s", e)

    def stop(self):
        self._stop_event.set()
        if hasattr(self, "_daily_timer"):
            self._daily_timer.cancel()
        if self._dunner_engine:
            self._dunner_engine.shutdown()
        if self._cmr_generator:
            self._event_bus.unsubscribe(TRIP_STATUS_CHANGED, self._cmr_generator.on_trip_in_transit)
        logger.info("OperationsEngine stopped")

    def get_active_alerts(self, limit: int = 200) -> list[Alert]:
        return self._alert_mgr.get_active_alerts(limit=limit)

    def get_alerts(
        self,
        alert_type: Optional[AlertType] = None,
        severity: Optional[Severity] = None,
        truck_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> list[Alert]:
        return self._alert_mgr.get_alerts(
            alert_type=alert_type,
            severity=severity,
            truck_id=truck_id,
            resolved=resolved,
            limit=limit,
        )

    def resolve_alert(self, alert_id: str) -> Optional[Alert]:
        return self._alert_mgr.resolve_alert(alert_id)

    def get_active_count(self) -> int:
        return self._alert_mgr.get_active_count()

    def get_active_alert_count(self) -> int:
        return self.get_active_count()

    def evaluate_all(self) -> int:
        if self._maintenance_engine:
            return self._maintenance_engine.evaluate_all()
        return 0

    def evaluate_truck(self, truck_id: str) -> int:
        if self._maintenance_engine:
            return self._maintenance_engine.evaluate_truck(truck_id)
        return 0

    def get_valid_transitions(self, current_status: str) -> list[str]:
        """Return list of valid next statuses based on current status."""
        return self._trip_workflow.get_valid_transitions(current_status) if self._trip_workflow else []

    def force_trip_status(self, trip_id: int, new_status: str, skip_undo: bool = False) -> bool:
        """Force a trip to a specific status, updating odometer if completed."""
        if not self._trip_workflow:
            logger.error("force_trip_status: TripStatusWorkflow not available")
            return False
        return self._trip_workflow.force_trip_status(trip_id, new_status, skip_undo=skip_undo)

    @property
    def alert_manager(self) -> AlertManager:
        return self._alert_mgr

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def notification_center(self) -> Optional[NotificationCenter]:
        return self._notification_center

    def migrate_existing_data(self) -> dict[str, int]:
        results = {"trucks": 0, "trips": 0, "overdue_invoices": 0}
        if not self._db:
            return results
        logger.info("migrate_existing_data: starting backfill...")
        try:
            trucks = self._db.get_all_trucks(active_only=True)
            results["trucks"] = len(trucks)
            for t in trucks:
                self._maintenance_engine._evaluate_single(t)
            logger.info("migrate_existing_data: evaluated %d trucks", results["trucks"])
        except Exception as e:
            logger.error("migrate_existing_data truck eval failed: %s", e)

        try:
            trips = self._trip_service.get_by_statuses(
                ["Delivered", "Livrat", "Facturat", "Invoiced", "Paid"],
            ) if self._trip_service else []
            results["trips"] = len(trips)
            today = datetime.now()
            overdue_days = self._rules.get("unpaid_invoice_days", 30)
            batch: list[Alert] = []
            for t in trips:
                trip_id = t["id"]
                price = t.get("total_price_eur", 0)
                created_at = t.get("created_at", "")
                status = t.get("status", "")
                if status in ("Delivered", "Livrat", "Facturat", "Invoiced"):
                    try:
                        created = datetime.strptime(created_at[:10], "%Y-%m-%d")
                        age = (today - created).days
                        if age > overdue_days:
                            batch.append(Alert(
                                type=AlertType.OVERDUE_INVOICE,
                                severity=Severity.CRITICAL,
                                title=f"Overdue invoice for trip #{trip_id}",
                                message=f"Trip delivered but unpaid for {age} days ({created_at[:10]}), amount: {price:.2f} EUR",
                                trip_id=str(trip_id),
                            ))
                    except Exception:
                        logger.debug("migrate_existing_data: failed to evaluate trip #%d", trip_id, exc_info=True)
            if batch:
                results["overdue_invoices"] = self._alert_mgr.create_alerts_batch(batch)
            logger.info("migrate_existing_data: checked %d trips, %d overdue invoices",
                        results["trips"], results["overdue_invoices"])
        except Exception as e:
            logger.error("migrate_existing_data trip eval failed: %s", e)

        logger.info("migrate_existing_data complete: %s", results)
        return results
