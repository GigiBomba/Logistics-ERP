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
    """Orchestrates all operations-layer services.

    Singleton for backward compatibility. For AI/headless use, call
    ``OperationsEngine.get_instance(db, prefs)`` or the factory
    ``OperationsEngine.create(...)`` which accepts every dependency
    explicitly — no hidden global state.

    All dependencies should be injected, not created internally.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db=None, prefs=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    # ── Factory / lifecycle (AI/headless support) ──────────────────

    @classmethod
    def get_instance(cls, db=None, prefs=None):
        """Get or create the singleton. Accepts dependencies for injection.

        For AI/headless use: pass all dependencies explicitly to avoid
        hidden global state.
        """
        if cls._instance is None:
            cls._instance = cls(db, prefs)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton. Use before headless/test execution."""
        cls._instance = None

    @classmethod
    def create(cls, db, prefs=None, event_bus=None, alert_mgr=None, rules=None,
               trip_service=None, maintenance_engine=None, notification_center=None,
               dunner_engine=None, undo_stack=None, cmr_generator=None, trip_workflow=None):
        """Factory constructor — accept all service dependencies explicitly.

        Bypasses the singleton to return a fresh instance. Use for testing
        and AI/headless scenarios where deterministic state is needed.

        All dependencies should be injected, not created internally.
        """
        instance = object.__new__(cls)
        instance._initialized = False
        instance._initialize(
            db=db, prefs=prefs, event_bus=event_bus, alert_mgr=alert_mgr,
            rules=rules, trip_service=trip_service,
            maintenance_engine=maintenance_engine,
            notification_center=notification_center,
            dunner_engine=dunner_engine, undo_stack=undo_stack,
            cmr_generator=cmr_generator, trip_workflow=trip_workflow,
        )
        return instance

    def __init__(self, db=None, prefs=None):
        if self._initialized:
            if db is not None and self._db is None:
                self._db = db
            return
        self._initialized = True
        self._initialize(db=db, prefs=prefs)

    def _initialize(self, db=None, prefs=None, event_bus=None, alert_mgr=None, rules=None,
                    trip_service=None, maintenance_engine=None, notification_center=None,
                    dunner_engine=None, undo_stack=None, cmr_generator=None, trip_workflow=None):
        """Shared initializer — accepts explicit dependencies or creates defaults."""
        self._db = db
        self._prefs = prefs
        self._event_bus = event_bus if event_bus is not None else EventBus()
        self._event_bus.inject_db(db)
        self._alert_mgr = alert_mgr if alert_mgr is not None else AlertManager(db)
        self._rules = rules if rules is not None else Rules()
        self._trip_service = trip_service
        self._maintenance_engine = maintenance_engine
        self._notification_center = notification_center
        self._dunner_engine = dunner_engine
        self._undo_stack = undo_stack if undo_stack is not None else UndoStack()
        self._cmr_generator = cmr_generator
        self._trip_workflow = trip_workflow
        # Create default service instances if db is available and none provided
        if db is not None:
            if self._trip_service is None:
                from services.trip_service import TripService
                self._trip_service = TripService(db)
            if self._maintenance_engine is None:
                self._maintenance_engine = MaintenanceEngine(db)
            if self._notification_center is None:
                self._notification_center = NotificationCenter(db)
            if self._dunner_engine is None:
                self._dunner_engine = DunnerEngine(db, self._notification_center, prefs)
            if self._cmr_generator is None:
                self._cmr_generator = AutoCMRGenerator(db, prefs, self._alert_mgr)
            if self._trip_workflow is None:
                self._trip_workflow = TripStatusWorkflow(
                    db, self._trip_service, self._event_bus, self._maintenance_engine, self._undo_stack,
                )
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
