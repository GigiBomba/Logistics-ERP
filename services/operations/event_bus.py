import logging
import threading
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Callable, Optional

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

PROFORMA_CREATED = "proforma.created"
RECEIPT_CREATED = "receipt.created"

DRIVER_CREATED = "driver.created"
DRIVER_UPDATED = "driver.updated"
DRIVER_DELETED = "driver.deleted"

CLIENT_CREATED = "client.created"
CLIENT_UPDATED = "client.updated"
CLIENT_DELETED = "client.deleted"

DOCUMENT_OCR_RAN = "document.ocr_ran"

TRIP_CONFLICT = "trip.conflict"
SETTINGS_UPDATED = "settings.updated"
TOUR_REPLAY_REQUESTED = "tour.replay_requested"

ALERT_CREATED = "alert.created"
ALERT_RESOLVED = "alert.resolved"

DOCUMENT_UPLOADED = "document.uploaded"
DOCUMENT_ARCHIVED = "document.archived"
DOCUMENT_DELETED = "document.deleted"
DOCUMENT_LINKED = "document.linked"
DOCUMENT_UNLINKED = "document.unlinked"

# ── Document Automation Pipeline events ─────────────────────────────
DOCUMENT_IMPORTED = "document.automation.imported"
DOCUMENT_PROCESSED = "document.automation.processed"
DOCUMENT_OCR_COMPLETE = "document.automation.ocr_complete"
DOCUMENT_MATCHED = "document.automation.matched"
DOCUMENT_GROUPED = "document.automation.grouped"
PACKAGE_SENT = "package.sent"

# ── Telemetry / recovery events ──────────────────────────────────────
RETRY_TRIGGERED = "retry.triggered"
ROLLBACK_EXECUTED = "rollback.executed"
EXTERNAL_API_FAILED = "external_api.failed"
OCR_LOW_CONFIDENCE = "ocr.low_confidence"

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
    CLIENT_CREATED, CLIENT_UPDATED, CLIENT_DELETED,
    TRIP_CONFLICT, SETTINGS_UPDATED,
    ALERT_CREATED, ALERT_RESOLVED,
    DAILY_CHECK, SYSTEM_STARTUP,
    DOCUMENT_UPLOADED, DOCUMENT_ARCHIVED, DOCUMENT_DELETED,
    DOCUMENT_LINKED, DOCUMENT_UNLINKED,
    DOCUMENT_IMPORTED, DOCUMENT_PROCESSED, DOCUMENT_OCR_COMPLETE,
    DOCUMENT_MATCHED, DOCUMENT_GROUPED, PACKAGE_SENT,
    DOCUMENT_OCR_RAN,
    RETRY_TRIGGERED, ROLLBACK_EXECUTED,
    EXTERNAL_API_FAILED, OCR_LOW_CONFIDENCE,
]


class EventBus:
    """Central event bus for the operations layer.

    Singleton for backward compatibility. For AI/headless use, call
    ``EventBus.get_instance()`` to obtain the singleton, or use
    ``EventBus.reset_instance()`` + ``EventBus()`` to start with
    a clean slate. All dependencies should be injected explicitly
    via ``get_instance(db=...)`` to avoid hidden global state.
    """
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
        self._subscribers: dict[str, list[Callable]] = {ev: [] for ev in ALL_EVENTS}
        self._subscribers_lock = threading.Lock()
        self._history: deque[dict[str, Any]] = deque(maxlen=100)
        logger.info("EventBus initialized with %d event types", len(ALL_EVENTS))

    # ── Factory / lifecycle (AI/headless support) ──────────────────

    @classmethod
    def get_instance(cls, db=None):
        """Get or create the singleton. Accepts dependencies for injection.

        For AI/headless use: pass all dependencies explicitly to avoid
        hidden global state.
        """
        if cls._instance is None:
            cls._instance = cls()
        if db is not None:
            cls._instance.inject_db(db)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton. Use before headless/test execution."""
        cls._instance = None

    def reset(self):
        """Clear all subscribers and history — use for a clean state."""
        with self._subscribers_lock:
            self._subscribers = {ev: [] for ev in ALL_EVENTS}
            self._history.clear()

    # ── Public API ─────────────────────────────────────────────────

    def publish(self, event_type: str, data: Optional[dict[str, Any]] = None, timestamp: Optional[str] = None) -> None:
        ev = {
            "id": uuid.uuid4().hex[:12],
            "type": event_type,
            "data": data or {},
            "timestamp": timestamp or datetime.now().isoformat(),
        }
        with self._subscribers_lock:
            self._history.append(ev)
            callbacks = list(self._subscribers.get(event_type, []))
        if not callbacks:
            logger.debug("Event %s published (no subscribers)", event_type)
            return

        for cb in callbacks:
            try:
                cb(ev)
            except Exception as e:
                logger.error("Subscriber error for %s: %s", event_type, e)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._subscribers_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
        logger.debug("Subscriber registered for %s", event_type)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        with self._subscribers_lock:
            callbacks = self._subscribers.get(event_type, [])
            if callback in callbacks:
                callbacks.remove(callback)
        logger.debug("Subscriber unregistered for %s", event_type)

    def get_history(self, event_type: Optional[str] = None, limit: int = 50) -> list[dict]:
        with self._subscribers_lock:
            items = list(self._history)
        if event_type:
            return [e for e in items[-limit:] if e["type"] == event_type]
        return items[-limit:]

    def inject_db(self, db) -> None:
        """Inject a shared DatabaseManager reference so no new connection is created."""
        self._db = db

    def abort_if_trip_is_archived(self, trip_id: int) -> bool:
        """Check if a trip is archived; return True if archived (caller should skip)."""
        if not hasattr(self, "_db") or self._db is None:
            return False
        try:
            from services.trip_service import TripService
            svc = TripService(self._db)
            trip = svc.get_by_id(trip_id)
            return trip.get("archived") == 1 if trip else False
        except Exception:
            return False


# ── Module-level shared singleton ────────────────────────────────────
# Use this import in views so all subscribe/publish calls go through the
# same EventBus instance.  ``EventBus()`` also returns this singleton.
shared_event_bus = EventBus()

