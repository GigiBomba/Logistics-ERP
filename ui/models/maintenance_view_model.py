"""MaintenanceViewModel — centralized QObject service facade for maintenance UI.

Serves as the single source of truth between maintenance views and the
service/repository layer. Provides:
- Cached + debounced refresh: coalesces rapid requests into a single refresh
- Lazy sub-service creation (FleetMaintenanceService, AlertManager)
- EventBus subscription (once) with dirty-flag tracking
- Qt signals for reactive UI updates
"""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from services.fleet_maintenance_service import FleetMaintenanceService, TruckHealth
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

class MaintenanceViewModel(QObject):
    """Central maintenance data facade.

    Emits ``data_changed`` after any refresh completes so views can
    reactively update without polling.
    """

    data_changed = Signal()
    summary_changed = Signal(dict)

    def __init__(self, parent=None, db=None, ops=None):
        super().__init__(parent)
        self._db = db
        self._ops = ops or OperationsEngine()
        self._event_bus = EventBus()

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
        """Fetch fresh data and emit signals."""
        if not self._db:
            return
        try:
            self.alert_model.refresh_from(self._ops)
            self.tacho_model.refresh(self._db)
            self._invalidate_summary_cache()
            self._dirty = False
            self.data_changed.emit()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("MaintenanceViewModel refresh failed")

    # ── Summary (cached 60s) ───────────────────────────────────────

    def _invalidate_summary_cache(self) -> None:
        self._summary_cache = None
        self._summary_ts = 0.0

    def get_summary(self) -> dict[str, Any]:
        now = time.time()
        if self._summary_cache and (now - self._summary_ts) < self._summary_ttl:
            return self._summary_cache
        prev = self._summary_cache
        self._summary_cache = self.maint_svc.get_summary(force=True)
        self._summary_ts = now
        if self._summary_cache != prev:
            self.summary_changed.emit(self._summary_cache)
        return self._summary_cache

    # ── Health (with LRU-style cache) ──────────────────────────────

    def get_health(self, truck_id: int, force: bool = False) -> TruckHealth:
        if not force and truck_id in self._health_cache:
            return self._health_cache[truck_id]
        h = self.maint_svc.get_health(truck_id, force_refresh=force)
        self._health_cache[truck_id] = h
        return h

    def get_all_health(self) -> list[TruckHealth]:
        return self.maint_svc.get_all_health()

    # ── Alert helpers ──────────────────────────────────────────────

    def resolve_alert(self, alert_id: str) -> None:
        self._ops.resolve_alert(alert_id)
        self.refresh_now()

    # ── Cleanup ────────────────────────────────────────────────────

    def shutdown(self) -> None:
        self._debounce_timer.stop()
        for ev in (ALERT_CREATED, ALERT_RESOLVED, MAINTENANCE_ADDED,
                   MAINTENANCE_DELETED, TRUCK_CREATED, TRUCK_UPDATED):
            self._event_bus.unsubscribe(ev, self._on_any_event)
