"""Base QWidget for all Operion ERP views.

Provides lifecycle management: timers, event bus subscriptions, i18n listeners,
and clean shutdown. Every view should inherit from this instead of QWidget.

Performance optimizations:
- Async data loading via WorkerPool (QThreadPool)
- Skeleton/loading states during background work
- Staleness-based refresh to avoid redundant reloads
- Timing instrumentation for all lifecycle methods
- Loading state tracking to prevent duplicate loads
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QScrollArea, QWidget

from services.i18n import register_listener, unregister_listener
from services.operations.event_bus import EventBus, shared_event_bus as _shared_event_bus
from ui.performance_timer import PerfTimer
from ui.skeleton_widgets import SkeletonManager
from ui.worker_pool import WorkerPool

logger = logging.getLogger(__name__)

# Default staleness window in seconds — views can override
DEFAULT_STALENESS_SECONDS = 30


class BaseView(QScrollArea):
    """Base class for all Operion ERP view modules.

    Lifecycle hooks:
        _build_ui(self)        — override to build widgets (called once in __init__)
        _load_data_async(self) — override to start async data loading
        _on_shutdown(self)     — override for view-specific cleanup
        _get_staleness_key(self) — override to return a cache-busting key

    Async loading pattern::

        def _load_data_async(self):
            self._show_loading()
            WorkerPool.run(
                fn=lambda: self._trip_service.get_filtered(search=""),
                on_result=self._on_trips_loaded,
                on_error=self._on_error,
            )

        def _on_trips_loaded(self, data):
            self._hide_loading()
            self._update_table(data)

        def _get_staleness_key(self):
            return "trips"  # Content type for staleness tracking
    """

    # Override in subclass to set staleness window (seconds)
    STALENESS_SECONDS: float | None = DEFAULT_STALENESS_SECONDS

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._event_bus: EventBus = _shared_event_bus
        self._subs: list[tuple[EventBus, str, Callable]] = []
        self._timers: list[QTimer] = []
        self._i18n_id: Callable[[str], None] | None = None
        self._shutdown_flag: bool = False
        self._loading: bool = False
        self._loaded: bool = False
        self._last_load_ts: float = 0.0

        # Skeleton manager for loading states
        self._skeleton_mgr = SkeletonManager(self)

        # Track time of last data load per content key
        self._staleness_timestamps: dict[str, float] = {}

    # ── Qt event overrides ──────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Ensure shutdown is called when the widget is closed."""
        self.shutdown()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        """Keep skeleton overlay sized to parent."""
        super().resizeEvent(event)
        if self._skeleton_mgr:
            self._skeleton_mgr.resize(self.width(), self.height())

    # ── Lifecycle ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Override to construct widgets. Called once from __init__."""

    def _load_data_async(self) -> None:
        """Override to start async data loading via WorkerPool.

        Called from wakeup(). Default implementation calls the old
        synchronous _load_data() for backward compatibility.

        Migrate to async::

            def _load_data_async(self):
                self._show_loading()
                WorkerPool.run(
                    fn=self._fetch_data,
                    on_result=self._on_data,
                )
        """
        # Backward compatibility: call old _load_data synchronously
        # but wrap in timer so UI has a chance to render first
        QTimer.singleShot(0, self._load_data)

    def _load_data(self) -> None:
        """Override to load initial data synchronously.

        DEPRECATED: Override _load_data_async instead for async loading.
        """

    def _on_shutdown(self) -> None:
        """Override for view-specific cleanup."""

    def _get_staleness_key(self) -> str | None:
        """Return a key identifying the content type for staleness tracking.

        Override in subclasses. Returns None to always refresh.
        """
        return None

    def _is_stale(self, key: str | None = None) -> bool:
        """Check if the data for *key* is stale and needs refresh.

        Returns True if staleness is disabled or data hasn't been loaded.
        """
        if self.STALENESS_SECONDS is None:
            return True
        if not self._loaded:
            return True
        cache_key = key or self._get_staleness_key()
        if cache_key is None:
            return True
        last_ts = self._staleness_timestamps.get(cache_key, 0.0)
        return (time.time() - last_ts) > self.STALENESS_SECONDS

    def _mark_loaded(self, key: str | None = None) -> None:
        """Mark data as loaded for staleness tracking."""
        self._loaded = True
        self._last_load_ts = time.time()
        cache_key = key or self._get_staleness_key()
        if cache_key:
            self._staleness_timestamps[cache_key] = time.time()

    def _show_loading(self) -> None:
        """Show skeleton loading state."""
        self._loading = True
        self._skeleton_mgr.show()

    def _hide_loading(self) -> None:
        """Hide skeleton loading state."""
        self._loading = False
        self._skeleton_mgr.hide()

    def wakeup(self) -> None:
        """Called when the view becomes active (e.g. on tab switch).

        Starts async data loading if not currently loading.
        Shows skeleton immediately for instant perceived navigation.
        """
        if self._shutdown_flag:
            return

        with PerfTimer(f"{type(self).__name__}.wakeup"):
            # Check staleness — skip if recently loaded
            if not self._is_stale():
                logger.debug(
                    "%s.wakeup: skipping (fresh, last_load=%.1fs ago)",
                    type(self).__name__,
                    time.time() - self._last_load_ts,
                )
                return

            # Prevent duplicate concurrent loads
            if self._loading:
                logger.debug("%s.wakeup: skipping (already loading)", type(self).__name__)
                return

            # Show skeleton immediately
            self._show_loading()

            # Start async loading (on next event loop tick to let skeleton render)
            QTimer.singleShot(0, self._load_data_async)

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

        self._loading = False

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
