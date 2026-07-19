"""Base QWidget for all Operion ERP views.

Provides lifecycle management: timers, event bus subscriptions, i18n listeners,
and clean shutdown. Every view should inherit from this instead of QWidget.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QScrollArea, QWidget

from services.i18n import register_listener, unregister_listener
from services.operations.event_bus import EventBus, shared_event_bus as _shared_event_bus

logger = logging.getLogger(__name__)


class BaseView(QScrollArea):
    """Base class for all Operion ERP view modules.

    Lifecycle hooks:
        _build_ui(self)     — override to build widgets (called once in __init__)
        _load_data(self)    — override to load initial data (called from wakeup)
        _on_shutdown(self)  — override for view-specific cleanup

    Example::

        class MyView(BaseView):
            def _build_ui(self):
                self._label = QLabel("Hello", self)
                ...

            def _load_data(self):
                self._trip_service.get_filtered(search="", callback=self._on_data)
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._event_bus: EventBus = _shared_event_bus
        self._subs: list[tuple[EventBus, str, Callable]] = []
        self._timers: list[QTimer] = []
        self._i18n_id: Callable[[str], None] | None = None
        self._shutdown_flag: bool = False

    # ── Qt event overrides ──────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Ensure shutdown is called when the widget is closed."""
        self.shutdown()
        super().closeEvent(event)

    # ── Lifecycle ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Override to construct widgets. Called once from __init__."""

    def _load_data(self) -> None:
        """Override to load initial data. Called from wakeup()."""

    def _on_shutdown(self) -> None:
        """Override for view-specific cleanup."""

    def wakeup(self) -> None:
        """Called when the view becomes active (e.g. on tab switch)."""
        if not self._shutdown_flag:
            self._load_data()

    def shutdown(self) -> None:
        """Stops all timers, unsubscribes event bus, unregisters i18n.
        
        Safe to call multiple times.
        """
        if self._shutdown_flag:
            return
        self._shutdown_flag = True

        try:
            self._on_shutdown()
        except Exception:
            logger.exception("Error in _on_shutdown for %s", type(self).__name__)

        for timer in self._timers:
            try:
                timer.stop()
            except Exception:
                pass

        for bus, event, callback in self._subs:
            try:
                bus.unsubscribe(event, callback)
            except Exception:
                pass
        self._subs.clear()
        self._timers.clear()

        if self._i18n_id is not None:
            try:
                unregister_listener(self._i18n_id)
            except Exception:
                pass
            self._i18n_id = None

    # ── Timer helpers ──────────────────────────────────────────

    def _add_timer(self, interval_ms: int, callback: Callable) -> QTimer:
        """Create a repeating timer that stops on shutdown."""
        timer = QTimer(self)
        timer.timeout.connect(callback)
        timer.start(interval_ms)
        self._timers.append(timer)
        return timer

    def _add_shot(self, delay_ms: int, callback: Callable) -> QTimer:
        """Create a single-shot timer that cleans up after firing."""
        from PySide6.QtCore import QTimer as QtTimer
        timer = QtTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._safe_call(callback))
        timer.start(delay_ms)
        return timer

    # ── Event bus helpers ──────────────────────────────────────

    def _subscribe(self, event: str, callback: Callable) -> None:
        """Subscribe to an EventBus event that auto-unsubscribes on shutdown."""
        self._event_bus.subscribe(event, callback)
        self._subs.append((self._event_bus, event, callback))

    def _publish(self, event: str, data: dict[str, Any] | None = None) -> None:
        self._event_bus.publish(event, data)

    # ── i18n helper ────────────────────────────────────────────

    def _register_i18n(self, callback: Callable[[str], None]) -> None:
        """Register a language-change callback that auto-unregisters on shutdown."""
        if self._i18n_id is not None:
            try:
                unregister_listener(self._i18n_id)
            except Exception:
                pass
        self._i18n_id = register_listener(callback)

    # ── Internal helpers ───────────────────────────────────────

    def _safe_call(self, callback: Callable, *args, **kwargs) -> None:
        if not self._shutdown_flag:
            try:
                callback(*args, **kwargs)
            except Exception:
                logger.exception("Error in deferred call for %s", type(self).__name__)
