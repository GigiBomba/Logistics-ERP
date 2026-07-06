import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from repositories.alert_repository import AlertRepository
from services.operations.event_bus import ALERT_CREATED, ALERT_RESOLVED, EventBus

logger = logging.getLogger("operations.alert_manager")


class AlertType(str, Enum):
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    INSURANCE = "insurance"
    OVERDUE_INVOICE = "overdue_invoice"
    TRIP_DELAY = "trip_delay"
    INACTIVE_TRUCK = "inactive_truck"
    ROUTE_ISSUE = "route_issue"
    COMPLIANCE_WARNING = "compliance_warning"
    COMPLIANCE_RISK = "compliance_risk"
    TACHOGRAPH_EXPIRY = "tachograph_expiry"
    DRIVER_HOURS_WEEKLY = "driver_hours_weekly"
    DRIVER_HOURS_DAILY = "driver_hours_daily"
    DOCUMENT_EXPIRY = "document_expiry"
    CONTRACT_EXPIRY = "contract_expiry"
    POLICY_VIOLATION = "policy_violation"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


_alert_types_display = {
    AlertType.MAINTENANCE: "Maintenance",
    AlertType.INSPECTION: "Inspection",
    AlertType.INSURANCE: "Insurance",
    AlertType.OVERDUE_INVOICE: "Overdue Invoice",
    AlertType.TRIP_DELAY: "Trip Delay",
    AlertType.INACTIVE_TRUCK: "Inactive Truck",
    AlertType.ROUTE_ISSUE: "Route Issue",
    AlertType.COMPLIANCE_WARNING: "Compliance Warning",
    AlertType.COMPLIANCE_RISK: "Compliance Risk",
    AlertType.POLICY_VIOLATION: "Policy Violation",
    AlertType.TACHOGRAPH_EXPIRY: "Tachograph Calibration",
    AlertType.DRIVER_HOURS_WEEKLY: "Driver Hours Weekly",
    AlertType.DRIVER_HOURS_DAILY: "Driver Hours Daily",
    AlertType.DOCUMENT_EXPIRY: "Document Expiry",
    AlertType.CONTRACT_EXPIRY: "Contract Expiry",
}


@dataclass
class Alert:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: AlertType = AlertType.COMPLIANCE_WARNING
    severity: Severity = Severity.WARNING
    title: str = ""
    message: str = ""
    truck_id: Optional[str] = None
    trip_id: Optional[str] = None
    driver_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved: bool = False
    resolved_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def display_type(self) -> str:
        return _alert_types_display.get(self.type, self.type.value)


class AlertManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db=None):
        if self._initialized:
            if db is not None and self._db is None:
                self._db = db
            return
        self._initialized = True
        self._db = db
        self._alerts: dict[str, Alert] = {}
        self._alerts_lock = threading.Lock()
        self._max_alerts = 5000
        self._notification_playing = False
        self._event_bus = EventBus()
        self._alert_repo = AlertRepository(db) if db is not None else None
        if self._db is not None:
            self._load_from_db()
        logger.info("AlertManager initialized (db=%s)", self._db is not None)

    # ── CRUD ───────────────────────────────────────────────────────

    def _find_duplicate(self, alert_type: AlertType, truck_id: Optional[str],
                        trip_id: Optional[str], message: str) -> Optional[Alert]:
        """Find an existing active alert that would be a duplicate of a new one."""
        for a in self._alerts.values():
            if a.resolved:
                continue
            if a.type != alert_type:
                continue
            if a.truck_id != truck_id:
                continue
            if a.trip_id != trip_id:
                continue
            if a.message != message:
                continue
            return a
        return None

    def create_alerts_batch(self, alerts: list[Alert]) -> int:
        """Bulk-persist multiple alerts in a single transaction. Returns count inserted."""
        if self._alert_repo is None or not alerts:
            return 0
        count = 0
        with self._alerts_lock:
            alert_tuples = []
            for alert in alerts:
                self._alerts[alert.id] = alert
                alert_tuples.append((
                    alert.id,
                    alert.type.value,
                    alert.severity.value,
                    alert.title,
                    alert.message,
                    alert.truck_id,
                    int(alert.trip_id) if alert.trip_id and str(alert.trip_id).isdigit() else None,
                    alert.created_at,
                    1 if alert.resolved else 0,
                    alert.resolved_at,
                    json.dumps(alert.metadata, ensure_ascii=False, default=str) if alert.metadata else None,
                ))
            count = self._alert_repo.create_batch(alert_tuples)
        return count

    def create_alert(
        self,
        alert_type: AlertType,
        severity: Severity,
        title: str,
        message: str,
        truck_id: Optional[str] = None,
        trip_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Alert:
        with self._alerts_lock:
            dup = self._find_duplicate(alert_type, truck_id, trip_id, message)
            if dup is not None:
                logger.debug("Duplicate alert found, resolving old one: %s", dup.id)
                dup.resolved = True
                dup.resolved_at = datetime.now().isoformat()
                self._persist_resolution(dup)

            alert = Alert(
                type=alert_type,
                severity=severity,
                title=title,
                message=message,
                truck_id=truck_id,
                trip_id=trip_id,
                metadata=metadata or {},
            )
            self._alerts[alert.id] = alert
            self._persist_alert(alert)
            if len(self._alerts) > self._max_alerts:
                resolved = [a for a in self._alerts.values() if a.resolved]
                if resolved:
                    oldest = min(resolved, key=lambda a: a.created_at)
                    del self._alerts[oldest.id]
                    logger.debug("Evicted oldest resolved alert: %s", oldest.id)
                else:
                    oldest = min(self._alerts.values(), key=lambda a: a.created_at)
                    del self._alerts[oldest.id]
                    logger.debug("Evicted oldest alert (all active): %s", oldest.id)
            alert_copy = alert.to_dict()
            self._event_bus.publish(ALERT_CREATED, {"alert": alert_copy})
        logger.info("Alert created: [%s] %s — %s", severity.value, alert_type.value, title)
        self._play_notification()
        return alert

    def resolve_alert(self, alert_id: str) -> Optional[Alert]:
        with self._alerts_lock:
            alert = self._alerts.get(alert_id)
            if alert and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.now().isoformat()
                self._persist_resolution(alert)
                alert_copy = alert.to_dict()
                self._event_bus.publish(ALERT_RESOLVED, {"alert": alert_copy})
            else:
                alert_copy = None
        if alert_copy:
            logger.info("Alert resolved: %s", alert_id)
        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        return self._alerts.get(alert_id)

    def get_alerts(
        self,
        alert_type: Optional[AlertType] = None,
        severity: Optional[Severity] = None,
        truck_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> list[Alert]:
        results = list(self._alerts.values())
        if alert_type:
            results = [a for a in results if a.type == alert_type]
        if severity:
            results = [a for a in results if a.severity == severity]
        if truck_id:
            results = [a for a in results if a.truck_id == truck_id]
        if resolved is not None:
            results = [a for a in results if a.resolved == resolved]
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results[:limit]

    def get_active_alerts(self, limit: int = 100) -> list[Alert]:
        return self.get_alerts(resolved=False, limit=limit)

    def get_active_count(self) -> int:
        return sum(1 for a in self._alerts.values() if not a.resolved)

    def resolve_by_truck(self, truck_id: str, alert_type: Optional[AlertType] = None) -> int:
        count = 0
        for a in list(self._alerts.values()):
            if a.truck_id == truck_id and not a.resolved:
                if alert_type is None or a.type == alert_type:
                    self.resolve_alert(a.id)
                    count += 1
        return count

    def get_active_by_type_and_entity(
        self, alert_type: AlertType, entity_id: str, entity_field: str = "truck_id"
    ) -> Optional[Alert]:
        """Return the most recent active alert of a given type for an entity."""
        matches = [
            a for a in self._alerts.values()
            if not a.resolved
            and a.type == alert_type
            and getattr(a, entity_field, None) == str(entity_id)
        ]
        if not matches:
            return None
        return max(matches, key=lambda a: a.created_at or "")

    def update_severity(self, alert_id: str, severity: Severity, new_message: Optional[str] = None):
        alert = self._alerts.get(alert_id)
        if alert:
            alert.severity = severity
            if new_message is not None:
                alert.message = new_message
            logger.info("Alert %s severity updated to %s", alert_id, severity.value)

    def _play_notification(self) -> None:
        """Play a notification sound in a background thread."""
        if self._notification_playing:
            return
        self._notification_playing = True
        def _play():
            try:
                import winsound
                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
            except ImportError:
                pass
            except Exception:
                pass
            finally:
                self._notification_playing = False
        threading.Thread(target=_play, daemon=True).start()

    def cleanup_old(self, days: int = 90) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._alerts_lock:
            to_remove = [aid for aid, a in self._alerts.items()
                         if a.created_at < cutoff and a.resolved]
            for aid in to_remove:
                del self._alerts[aid]
        if self._alert_repo is not None:
            try:
                self._alert_repo.cleanup_old(days)
            except Exception:
                logger.exception("Failed to clean up old alerts from DB")
        logger.info("Cleaned up %d old alerts (>%d days)", len(to_remove), days)
        return len(to_remove)

    # ── Persistence helpers ──────────────────────────────────────────

    def _load_from_db(self) -> None:
        """Load unresolved alerts from the database into the in-memory cache."""
        if self._db is None or self._alert_repo is None:
            return
        try:
            rows = self._alert_repo.get_unresolved()
            loaded = 0
            for r in rows:
                alert_id = r["id"]
                if alert_id in self._alerts:
                    existing = self._alerts[alert_id]
                    if r.get("resolved_at") and not existing.resolved:
                        existing.resolved = True
                        existing.resolved_at = r["resolved_at"]
                    continue
                try:
                    metadata = json.loads(r["metadata_json"]) if r.get("metadata_json") else {}
                except Exception:
                    metadata = {}
                alert = Alert(
                    id=alert_id,
                    type=AlertType(r["type"]),
                    severity=Severity(r["severity"]),
                    title=r["title"] or "",
                    message=r["message"] or "",
                    truck_id=r["truck_id"],
                    trip_id=str(r["trip_id"]) if r.get("trip_id") else None,
                    created_at=r["created_at"] or "",
                    resolved=bool(r["resolved"]),
                    resolved_at=r["resolved_at"],
                    metadata=metadata,
                )
                self._alerts[alert_id] = alert
                loaded += 1
            logger.info("Loaded %d unresolved alerts from database", loaded)
        except Exception:
            logger.exception("Failed to load alerts from database")

    def _persist_alert(self, alert: Alert) -> None:
        if self._alert_repo is None:
            return
        try:
            self._alert_repo.create(
                id=alert.id,
                alert_type=alert.type.value,
                severity=alert.severity.value,
                title=alert.title,
                message=alert.message,
                truck_id=alert.truck_id,
                trip_id=int(alert.trip_id) if alert.trip_id and str(alert.trip_id).isdigit() else None,
                created_at=alert.created_at,
                resolved=1 if alert.resolved else 0,
                resolved_at=alert.resolved_at,
                metadata_json=json.dumps(alert.metadata, ensure_ascii=False, default=str) if alert.metadata else None,
            )
        except Exception:
            logger.exception("Failed to persist alert %s", alert.id)

    def _persist_resolution(self, alert: Alert) -> None:
        if self._alert_repo is None:
            return
        try:
            self._alert_repo.resolve(alert.id, alert.resolved_at)
        except Exception:
            logger.exception("Failed to persist alert resolution %s", alert.id)
