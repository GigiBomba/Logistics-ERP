"""Remote operations stub — EventBus provider without DB dependency.

Mirrors the public surface of ``services.operations.operations_engine.OperationsEngine``
so that ``MainWindow`` and all views that accept an ``ops`` parameter can
subscribe to local event notifications even in remote-only mode.

The stub creates a local ``EventBus`` for in-process pub/sub.  No database
access is performed — alerts and notifications are delivered via the API
client, not through local SQL queries.

Usage::

    from client.remote_ops_stub import RemoteOpsStub
    ops = RemoteOpsStub(api_client=my_api_client)
    ops.start()
    ops.event_bus.subscribe("alert_created", handler)
"""

from __future__ import annotations

import logging
from typing import Any

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


class RemoteOpsStub:
    """Provides ``EventBus`` and lifecycle stubs for remote-only mode.

    ``start()`` and ``stop()`` are no-ops.  ``event_bus`` returns a
    shared local ``EventBus`` instance that views can subscribe to for
    inter-component communication without touching the database.

    Alert methods return empty lists/counts — alerts are delivered
    via the API and triggered through the EventBus.

    ``undo_stack`` returns a no-op ``_UndoStackStub`` so views that
    call ``self.ops.undo_stack.clear()`` do not crash.
    """

    def __init__(self, api_client: Any = None) -> None:
        from services.operations.event_bus import EventBus
        self.event_bus = EventBus()
        self._api_client = api_client
        self.undo_stack = _UndoStackStub()

    def start(self) -> None:
        """No-op — remote mode does not run a background alert engine."""
        pass

    def stop(self) -> None:
        """No-op — remote mode has no background threads to shut down."""
        pass

    def _configure_smtp_from_db(self) -> None:
        """No-op — SMTP settings come from the API or remote preferences."""
        pass

    def get_active_alerts(self, limit: int = 50) -> list:
        """Return empty list — alerts come from EventBus / API polling."""
        return []

    def get_active_alert_count(self) -> int:
        """Return 0 — alert count set via EventBus."""
        return 0
