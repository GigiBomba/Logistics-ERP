"""MaintenanceViewModel — centralized QObject service facade for maintenance UI.

Serves as the single source of truth between maintenance views and the
service/repository layer. Provides:
- Cached + debounced refresh: coalesces rapid requests into a single refresh
- Lazy sub-service creation (FleetMaintenanceService, AlertManager)
- EventBus subscription (once) with dirty-flag tracking
- Qt signals for reactive UI updates
"""
from __future__ import annotations

import logging
import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

from services.fleet_maintenance_service import FleetMaintenanceService, TruckHealth
from services.operations.alert_manager import Alert, AlertType, Severity
from services.operations.event_bus import (
    ALERT_CREATED,
    ALERT_RESOLVED,
    MAINTENANCE_ADDED,
    MAINTENANCE_DELETED,
    TRUCK_CREATED,
    TRUCK_UPDATED,
    EventBus,
)
from services.operations.operations_engine import OperationsEngine
from ui.models.alert_list_model import AlertListModel
from ui.models.tacho_status_model import TachoStatusModel

# Default KPI values so the control panel never renders ``"N/A"`` strings
# that break numeric comparisons when a remote summary lacks a key.
_REMOTE_SUMMARY_DEFAULTS: dict[str, Any] = {
    "avg_health": 0,
    "trucks_needing_service": 0,
    "overdue_schedules": 0,
    "cost_30d": 0.0,
    "total_cost": 0.0,
    "total_records": 0,
    "records_30d": 0,
    "cost_by_type": {},
    "count_by_type": {},
    "top_maintained_trucks": [],
}


class MaintenanceViewModel(QObject):
    """Central maintenance data facade.

    Emits ``data_changed`` after any refresh completes so views can
    reactively update without polling.
    """

    data_changed = Signal()
    summary_changed = Signal(dict)

    def __init__(self, parent=None, db=None, ops=None,
                 control_service=None, maintenance_service=None):
        super().__init__(parent)
        self._db = db
        self._ops = ops or OperationsEngine()
        self._event_bus = EventBus()

        # Remote-capable services injected when running without a local DB.
        # ``control_service`` handles alerts / resolve; ``maintenance_service``
        # handles the summary / health surface.
        self._control_service = control_service
        self._maintenance_service = maintenance_service

        # Lazy service
        self._maint_svc: FleetMaintenanceService | None = None

        # Cache
        self._summary_cache: dict[str, Any] | None = None
        self._summary_ts: float = 0.0
        self._summary_ttl: float = 60.0
        self._health_cache: dict[int, TruckHealth] = {}
        self._dirty: bool = True

        # Debounce
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._do_refresh)

        # Models
        self.alert_model = AlertListModel(self)
        self.tacho_model = TachoStatusModel(self)

        # Subscribe once
        self._subscribe()

    # ── Properties ─────────────────────────────────────────────────

    @property
    def maint_svc(self) -> FleetMaintenanceService:
        if self._maint_svc is None:
            self._maint_svc = FleetMaintenanceService(self._db)
        return self._maint_svc

    # ── Event subscriptions (once, shared) ─────────────────────────

    def _subscribe(self) -> None:
        for ev in (ALERT_CREATED, ALERT_RESOLVED, MAINTENANCE_ADDED,
                   MAINTENANCE_DELETED, TRUCK_CREATED, TRUCK_UPDATED):
            self._event_bus.subscribe(ev, self._on_any_event)

    def _on_any_event(self, ev=None) -> None:
        self._dirty = True
        self._debounce_timer.start()

    # ── Public refresh API ─────────────────────────────────────────

    def refresh(self) -> None:
        """Request a refresh (debounced)."""
        self._debounce_timer.start()

    def refresh_now(self) -> None:
        """Force an immediate refresh, bypassing debounce."""
        self._debounce_timer.stop()
        self._do_refresh()

    def _do_refresh(self) -> None:
        """Fetch fresh data and emit signals.

        Always emits ``data_changed`` so the UI never gets stuck on a
        loading placeholder — even when individual sub-refresh calls fail.
        """
        if not self._db and self._control_service is None and self._maintenance_service is None:
            logger.warning("MaintenanceViewModel: no db, emitting empty data_changed")
            self.data_changed.emit()
            return
        try:
            if self._control_service is not None:
                # Remote mode — alerts come from the control service.
                items = self._control_service.alerts(kind="maintenance")
                self.alert_model.set_alerts(self._remote_alerts(items))
            else:
                self.alert_model.refresh_from(self._ops)
        except Exception as e:
            logger.warning("MaintenanceViewModel: alert_model refresh failed: %s", e)
        try:
            if self._db is not None:
                self.tacho_model.refresh(self._db)
        except Exception as e:
            logger.warning("MaintenanceViewModel: tacho_model refresh failed: %s", e)
        try:
            self._invalidate_summary_cache()
        except Exception as e:
            logger.warning("MaintenanceViewModel: invalidate_summary_cache failed: %s", e)
        self._dirty = False
        self.data_changed.emit()

    @staticmethod
    def _remote_alerts(items) -> list[Alert]:
        """Map remote alert dicts onto the local ``Alert`` dataclass.

        Unknown type/severity strings fall back to sensible defaults so the
        filter proxy (which filters on ``AlertType``/``Severity``) keeps
        working over remote data.
        """
        alerts: list[Alert] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            try:
                atype = AlertType(str(item.get("type", "compliance_warning")))
            except ValueError:
                atype = AlertType.COMPLIANCE_WARNING
            try:
                sev = Severity(str(item.get("severity", "warning")))
            except ValueError:
                sev = Severity.WARNING
            alerts.append(Alert(
                id=str(item.get("id", "")),
                type=atype,
                severity=sev,
                title=item.get("title", "") or item.get("message", "") or "",
                message=item.get("message", "") or "",
                truck_id=item.get("truck_id"),
                trip_id=item.get("trip_id"),
                driver_id=item.get("driver_id"),
                created_at=item.get("created_at", "") or "",
                resolved=bool(item.get("resolved", item.get("status") in ("resolved", "done"))),
            ))
        return alerts

    # ── Summary (cached 60s) ───────────────────────────────────────

    def _invalidate_summary_cache(self) -> None:
        self._summary_cache = None
        self._summary_ts = 0.0

    def _fetch_remote_summary(self) -> dict[str, Any]:
        """Best-effort summary from the injected remote maintenance service."""
        svc = self._maintenance_service or self._control_service
        raw: dict[str, Any] = {}
        if svc is not None and hasattr(svc, "get_summary"):
            try:
                raw = svc.get_summary()
            except TypeError:
                raw = svc.get_summary(force=True)
            except Exception as e:
                logger.warning("MaintenanceViewModel: remote summary failed: %s", e)
        result: dict[str, Any] = {
            **dict(_REMOTE_SUMMARY_DEFAULTS),
            **({} if not isinstance(raw, dict) else raw),
        }
        # Derive total_cost from monthly rows when the payload carries them.
        if not result.get("total_cost") and isinstance(raw, dict):
            monthly = raw.get("cost_monthly") or []
            total = 0.0
            for row in monthly:
                if not isinstance(row, dict):
                    continue
                total += float(row.get("total", row.get("cost", 0)) or 0)
            result["total_cost"] = total
        return result

    def get_summary(self) -> dict[str, Any]:
        now = time.time()
        if self._summary_cache and (now - self._summary_ts) < self._summary_ttl:
            return self._summary_cache
        prev = self._summary_cache
        if not self._db and (self._control_service is not None
                             or self._maintenance_service is not None):
            self._summary_cache = self._fetch_remote_summary()
        elif not self._db:
            # No local DB and no remote services — emit default zeros rather
            # than constructing a DB-backed maintenance service.
            self._summary_cache = dict(_REMOTE_SUMMARY_DEFAULTS)
        else:
            self._summary_cache = self.maint_svc.get_summary(force=True)
        self._summary_ts = now
        if self._summary_cache != prev:
            self.summary_changed.emit(self._summary_cache)
        return self._summary_cache

    # ── Health (with LRU-style cache) ──────────────────────────────

    def get_health(self, truck_id: int, force: bool = False) -> TruckHealth:
        if not force and truck_id in self._health_cache:
            return self._health_cache[truck_id]
        h: TruckHealth
        if not self._db:
            if (self._maintenance_service is not None
                    and hasattr(self._maintenance_service, "get_health")):
                try:
                    h = self._maintenance_service.get_health(
                        truck_id, force_refresh=force,
                    )
                except TypeError:
                    h = self._maintenance_service.get_health(truck_id)
                except Exception as e:
                    logger.warning(
                        "MaintenanceViewModel: remote health failed for truck %s: %s",
                        truck_id, e,
                    )
                    h = TruckHealth(truck_id=truck_id)
            else:
                # No local DB and no remote health source — default health.
                h = TruckHealth(truck_id=truck_id)
        else:
            h = self.maint_svc.get_health(truck_id, force_refresh=force)
        self._health_cache[truck_id] = h
        return h

    def get_all_health(self) -> list[TruckHealth]:
        if not self._db:
            if (self._maintenance_service is not None
                    and hasattr(self._maintenance_service, "get_all_health")):
                try:
                    return self._maintenance_service.get_all_health()
                except Exception as e:
                    logger.warning("MaintenanceViewModel: remote all-health failed: %s", e)
                    return []
            return []
        return self.maint_svc.get_all_health()

    # ── Alert helpers ──────────────────────────────────────────────

    def resolve_alert(self, alert_id: str) -> None:
        if self._control_service is not None:
            self._control_service.resolve_alert(alert_id)
        else:
            self._ops.resolve_alert(alert_id)
        self.refresh_now()

    # ── Cleanup ────────────────────────────────────────────────────

    def shutdown(self) -> None:
        self._debounce_timer.stop()
        for ev in (ALERT_CREATED, ALERT_RESOLVED, MAINTENANCE_ADDED,
                   MAINTENANCE_DELETED, TRUCK_CREATED, TRUCK_UPDATED):
            self._event_bus.unsubscribe(ev, self._on_any_event)
