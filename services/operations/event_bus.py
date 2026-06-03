import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("operations.event_bus")

# ── Canonical event type constants ──────────────────────────────────

TRIP_CREATED = "trip.created"
TRIP_UPDATED = "trip.updated"
TRIP_DELETED = "trip.deleted"
TRIP_STATUS_CHANGED = "trip.status_changed"
TRIP_ARCHIVED = "trip.archived"
TRIP_ASSIGNED = "trip.assigned"

ROUTE_CALCULATED = "route.calculated"
ROUTE_ASSIGNED = "route.assigned"

TRUCK_CREATED = "truck.created"
TRUCK_UPDATED = "truck.updated"
TRUCK_DELETED = "truck.deleted"
TRUCK_ODOMETER_UPDATED = "truck.odometer_updated"

MAINTENANCE_ADDED = "maintenance.added"
MAINTENANCE_DELETED = "maintenance.deleted"

INVOICE_CREATED = "invoice.created"
INVOICE_PAID = "invoice.paid"
INVOICE_EMAILED = "invoice.emailed"

DRIVER_CREATED = "driver.created"
DRIVER_UPDATED = "driver.updated"
DRIVER_DELETED = "driver.deleted"

TRIP_CONFLICT = "trip.conflict"
SETTINGS_UPDATED = "settings.updated"

ALERT_CREATED = "alert.created"
ALERT_RESOLVED = "alert.resolved"

VALID_TRANSITIONS = {
    "Planned": ["Loading", "Cancelled"],
    "Loading": ["Planned", "In Transit", "Cancelled"],
    "In Transit": ["Loading", "Delivered", "Cancelled"],
    "Delivered": ["In Transit", "Invoiced", "Cancelled"],
    "Invoiced": ["Delivered", "Paid", "Cancelled"],
    "Paid": ["Invoiced"],
    "Cancelled": ["Planned"],
}

DAILY_CHECK = "system.daily_check"
SYSTEM_STARTUP = "system.startup"

ALL_EVENTS = [
    TRIP_CREATED, TRIP_UPDATED, TRIP_DELETED, TRIP_STATUS_CHANGED, TRIP_ARCHIVED, TRIP_ASSIGNED,
    ROUTE_CALCULATED, ROUTE_ASSIGNED,
    TRUCK_CREATED, TRUCK_UPDATED, TRUCK_DELETED, TRUCK_ODOMETER_UPDATED,
    MAINTENANCE_ADDED, MAINTENANCE_DELETED,
    INVOICE_CREATED, INVOICE_PAID, INVOICE_EMAILED,
    DRIVER_CREATED, DRIVER_UPDATED, DRIVER_DELETED,
    TRIP_CONFLICT, SETTINGS_UPDATED,
    ALERT_CREATED, ALERT_RESOLVED,
    DAILY_CHECK, SYSTEM_STARTUP,
]


class EventBus:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._subscribers: Dict[str, List[Callable]] = {ev: [] for ev in ALL_EVENTS}
        self._history: List[Dict[str, Any]] = []
        self._history_max = 1000
        logger.info("EventBus initialized with %d event types", len(ALL_EVENTS))

    # ── Public API ─────────────────────────────────────────────────

    def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        ev = {
            "id": uuid.uuid4().hex[:12],
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._history.append(ev)
        if len(self._history) > self._history_max:
            self._history.pop(0)

        callbacks = self._subscribers.get(event_type, [])
        if not callbacks:
            logger.debug("Event %s published (no subscribers)", event_type)
            return

        for cb in list(callbacks):
            try:
                cb(ev)
            except Exception as e:
                logger.error("Subscriber error for %s: %s", event_type, e)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug("Subscriber registered for %s (total %d)", event_type, len(self._subscribers[event_type]))

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        callbacks = self._subscribers.get(event_type, [])
        if callback in callbacks:
            callbacks.remove(callback)
            logger.debug("Subscriber unregistered for %s", event_type)

    def get_history(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        if event_type:
            return [e for e in self._history[-limit:] if e["type"] == event_type]
        return list(self._history[-limit:])

    def abort_if_trip_is_archived(self, trip_id: int) -> bool:
        """Check if a trip is archived; return True if archived (caller should skip)."""
        try:
            from services.trip_service import TripService
            from database.db_manager import DatabaseManager
            db = DatabaseManager(self._db_path if hasattr(self, '_db_path') else "data/cashflow.db")
            svc = TripService(db)
            trip = svc.get_by_id(trip_id)
            return trip.get("archived") == 1 if trip else False
        except Exception:
            return False

