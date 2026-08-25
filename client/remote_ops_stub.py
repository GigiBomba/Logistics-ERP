"""Remote operations stub — EventBus provider without DB dependency.

Mirrors the public surface of ``services.operations.operations_engine.OperationsEngine``
so that ``MainWindow`` and all views that accept an ``ops`` parameter can
subscribe to local event notifications even in remote-only mode.

The stub creates a local ``EventBus`` for in-process pub/sub.  No database
access is performed — alerts and notifications are delivered via the API
client, not through local SQL queries.

In remote mode the backend runs the real ``OperationsEngine`` workers
against its own database (see ``backend/ops_engine.py``); this stub
SURFACES those results through the alerts API instead of returning a
hollow empty list.

Usage::

    from client.remote_ops_stub import RemoteOpsStub
    ops = RemoteOpsStub(api_client=my_api_client)
    ops.start()
    ops.event_bus.subscribe("alert_created", handler)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("remote_ops")


class _UndoStackStub:
    """No-op stub that mirrors the real ``UndoStack`` interface.

    All operations are silently ignored since remote mode has no local
    database to persist undo/redo state.
    """

    def clear(self) -> None:
        pass

    def push(self, cmd: Any) -> None:
        pass

    def pop(self) -> Any:
        return None

    def can_undo(self) -> bool:
        return False

    def can_redo(self) -> bool:
        return False

    def last_undo_command(self) -> Any:
        return None

    def last_redo_command(self) -> Any:
        return None

    @property
    def commands(self) -> list:
        return []


class _ApiAlert:
    """Lightweight alert view-mapped from the backend alerts API.

    Remote mode has no local ``Alert`` dataclass instances; this object
    carries the same attribute surface (``id``, ``type``, ``severity``,
    ``title``, ``message``, ``created_at``, ``status``) so existing UI
    consumers keep working unchanged.
    """

    __slots__ = (
        "id", "type", "severity", "title", "message", "created_at", "status",
        "truck_id", "trip_id", "resolved",
    )

    def __init__(self, data: dict) -> None:
        self.id: str = str(data.get("id", ""))
        self.type: Any = data.get("type", "compliance_warning")
        self.severity: Any = data.get("severity", "info")
        self.title: str = data.get("title", "") or data.get("message", "")
        self.message: str = data.get("message", "")
        self.created_at: str = data.get("created_at", "")
        self.status: str = data.get("status", "active")
        self.truck_id = data.get("truck_id")
        self.trip_id = data.get("trip_id")
        self.resolved = data.get("status", "active") != "active"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": getattr(self.type, "value", self.type),
            "severity": getattr(self.severity, "value", self.severity),
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at,
            "status": self.status,
            "truck_id": self.truck_id,
            "trip_id": self.trip_id,
            "resolved": self.resolved,
        }


class RemoteOpsStub:
    """Provides ``EventBus`` and lifecycle stubs for remote-only mode.

    ``start()`` and ``stop()`` are no-ops.  ``event_bus`` returns a
    shared local ``EventBus`` instance that views can subscribe to for
    inter-component communication without touching the database.

    Alert methods are API-BACKED: ``get_active_alerts`` reads
    ``GET /api/v1/alerts`` and ``get_active_alert_count`` reads
    ``GET /api/v1/alerts/count`` via the ``ApiClient``.  The backend runs
    the real OperationsEngine workers against its own database, so these
    calls surface genuine server-side alerts.  When no API client is
    available (or the API is unreachable) they degrade to ``[]`` / ``0``
    so the UI never crashes offline.

    ``undo_stack`` returns a no-op ``_UndoStackStub`` so views that
    call ``self.ops.undo_stack.clear()`` do not crash.
    """

    def __init__(self, api_client: Any = None) -> None:
        from services.operations.event_bus import EventBus
        self.event_bus = EventBus()
        self._api_client = api_client
        self.undo_stack = _UndoStackStub()

    def start(self) -> None:
        """No-op — the remote engine runs server-side, not on the desktop."""
        pass

    def stop(self) -> None:
        """No-op — remote mode has no background threads to shut down."""
        pass

    def _configure_smtp_from_db(self) -> None:
        """No-op — SMTP settings come from the API or remote preferences."""
        pass

    def get_active_alerts(self, limit: int = 50) -> list:
        """Return active alerts from ``GET /api/v1/alerts`` (API-backed).

        The backend's OperationsEngine writes alerts to its own database;
        this surfaces them through the alerts list endpoint.
        """
        api = self._api_client
        if api is None:
            return []
        try:
            resp = api.list_alerts(limit=limit)
        except Exception as exc:
            logger.debug("get_active_alerts: API unavailable: %s", exc)
            return []
        items = resp.get("items", []) if isinstance(resp, dict) else []
        return [_ApiAlert(item) for item in items]

    def get_active_alert_count(self) -> int:
        """Return the active-alert count from ``GET /api/v1/alerts/count``."""
        api = self._api_client
        if api is None:
            return 0
        try:
            resp = api.get_alert_count()
        except Exception as exc:
            logger.debug("get_active_alert_count: API unavailable: %s", exc)
            return 0
        if isinstance(resp, dict):
            try:
                return int(resp.get("count", 0))
            except (TypeError, ValueError):
                return 0
        return 0

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert via ``POST /api/v1/alerts/{alert_id}/resolve``."""
        api = self._api_client
        if api is None:
            return False
        try:
            resp = api.resolve_alert(alert_id)
        except Exception as exc:
            logger.debug("resolve_alert: API unavailable: %s", exc)
            return False
        if isinstance(resp, dict):
            return resp.get("status") == "resolved"
        return bool(resp)
