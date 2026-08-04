"""Fullscreen Diagnostics Probe — monitor fullscreen transitions and resize events.

Installs a global event filter on ``QApplication`` to intercept
``WindowStateChange`` events and instrument resize events that occur
while the window is fullscreen.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication

from diagnostics.models import DiagnosticCategory, Event, Span
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.fullscreen_diagnostics")

SLOW_TRANSITION_THRESHOLD_MS = 500


class FullscreenEventFilter(QObject):
    """QObject event filter that monitors fullscreen state and resize events."""

    def __init__(self, store: DiagnosticStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._fullscreen = False
        self._enter_ts: float = 0.0
        self._resize_count: int = 0

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Intercept WindowStateChange and Resize events."""
        if event.type() == QEvent.Type.WindowStateChange:
            self._on_window_state_change(obj, event)
        elif event.type() == QEvent.Type.Resize:
            self._on_resize(obj, event)

        return False  # Never consume the event

    def _on_window_state_change(self, obj: QObject, event: QEvent) -> None:
        """Handle entering / exiting fullscreen."""
        old = event.oldState()
        new = obj.windowState()

        entering = bool(new & Qt.WindowFullScreen) and not bool(old & Qt.WindowFullScreen)
        exiting = bool(old & Qt.WindowFullScreen) and not bool(new & Qt.WindowFullScreen)

        if entering:
            self._fullscreen = True
            self._enter_ts = time.perf_counter()
            self._resize_count = 0
            self._store.record_event(Event(
                name="fullscreen.enter",
                category=DiagnosticCategory.FULLSCREEN,
                metadata={"window_class": type(obj).__name__},
            ))
            logger.info("[DIAG] Fullscreen entered on %s", type(obj).__name__)

        if exiting:
            self._fullscreen = False
            duration_ms = (time.perf_counter() - self._enter_ts) * 1000.0 if self._enter_ts else 0.0
            self._store.record_span(Span(
                name="fullscreen.session",
                category=DiagnosticCategory.FULLSCREEN,
                start_time=self._enter_ts or time.perf_counter(),
                end_time=time.perf_counter(),
                metadata={"duration_ms": round(duration_ms, 1), "resize_events": self._resize_count},
            ))
            if duration_ms > SLOW_TRANSITION_THRESHOLD_MS:
                self._store.record_event(Event(
                    name="fullscreen.transition_slow",
                    category=DiagnosticCategory.FULLSCREEN,
                    metadata={"duration_ms": round(duration_ms, 1)},
                ))
            logger.info("[DIAG] Fullscreen exited (duration=%.0fms, resizes=%d)",
                        duration_ms, self._resize_count)

    def _on_resize(self, obj: QObject, event: QEvent) -> None:
        """Track resize events while in fullscreen mode."""
        if not self._fullscreen:
            return
        self._resize_count += 1
        try:
            size = event.size()
            self._store.set_gauge("fullscreen.width", float(size.width()))
            self._store.set_gauge("fullscreen.height", float(size.height()))
        except AttributeError:
            pass  # Some resize events may not carry a size


class FullscreenProbe:
    """Probes fullscreen transitions via a global QApplication event filter.

    Usage::

        probe = FullscreenProbe(store)
        probe.install()     # installs global event filter
        probe.sample()      # updates gauges (called by engine)
    """

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._filter: FullscreenEventFilter | None = None

    def install(self) -> None:
        """Install a global event filter on ``QApplication``."""
        if self._filter is not None:
            return

        app = QApplication.instance()
        if app is None:
            logger.warning("[DIAG] FullscreenProbe: No QApplication instance — cannot install")
            return

        self._filter = FullscreenEventFilter(self.store)
        app.installEventFilter(self._filter)
        logger.info("[DIAG] FullscreenProbe installed")

    def sample(self) -> None:
        """Report current fullscreen state as a gauge."""
        active = 1.0 if (self._filter and self._filter._fullscreen) else 0.0
        self.store.set_gauge("fullscreen.active", active)

    def uninstall(self) -> None:
        """Remove the event filter and clean up."""
        if self._filter is None:
            return

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self._filter)

        self._filter = None
        logger.info("[DIAG] FullscreenProbe uninstalled")
