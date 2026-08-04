"""Widget Tracker Probe — monitor QWidget creation / destruction.

Monkey-patches ``PySide6.QtWidgets.QWidget.__init__`` and uses the
``destroyed`` signal to track every widget's lifetime.

Tracking data is keyed by ``id(widget)`` (int) so that **no strong
reference** to the widget is ever stored.  A ``weakref``-based callback
on ``destroyed`` ensures garbage collection is never prevented.

Detection events
----------------
- ``widget.created.{class}`` — emitted on every widget creation
- ``widget.destroyed.{class}`` — emitted on every widget destruction
- ``widget.orphaned`` — widget alive > 300 s without being destroyed
- ``widget.duplicate_storm`` — > 10 instances of the same class created in 60 s
- ``widget.rapid_recreation`` — same widget ID recreated within 100 ms
- ``widget.off_screen`` — widget placed at x < -5000 or y < -5000
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from diagnostics.models import DiagnosticCategory, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.widget_tracker")

# ── Thresholds ──────────────────────────────────────────────────────────
ORPHAN_TIMEOUT_S = 300               # seconds
DUPLICATE_STORM_COUNT = 10           # widgets of same class in window
DUPLICATE_STORM_WINDOW_S = 60        # seconds
RAPID_RECREATION_MS = 100            # same id() reappears within this
OFF_SCREEN_THRESHOLD = -5000         # x or y below this → off-screen


class WidgetTrackerProbe:
    """Monitors QWidget creation and destruction via monkey-patching.

    Uses **weak references** internally — no strong reference to any
    widget is retained so garbage collection is never blocked.
    """

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._widgets: dict[int, dict] = {}         # id(widget) -> info
        self._creation_count: dict[str, int] = {}   # class_name -> count
        self._lock = threading.Lock()
        self._installed = False
        self._original_init: Any = None
        self._orphan_check_ts: float = 0.0

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch ``QWidget.__init__`` to track every widget."""
        if self._installed:
            return

        self._original_init = QWidget.__init__
        probe = self              # captured in closures below
        store = self.store

        @functools.wraps(self._original_init)
        def _patched_init(self: QWidget, *args: Any, **kwargs: Any) -> None:
            # Safety net — never crash widget creation
            try:
                # Call the real __init__ first so the widget is usable
                probe._original_init(self, *args, **kwargs)

                cls_name = type(self).__name__
                wid = id(self)
                now = time.perf_counter()
                parent = self.parent()

                with probe._lock:
                    # ── Rapid-recreation check ─────────────────────
                    prev = probe._widgets.get(wid)
                    if prev is not None:
                        # Same id() appeared before — check interval
                        elapsed = (now - prev["created_at"]) * 1000.0
                        if elapsed < RAPID_RECREATION_MS and not prev.get("rapid_warned"):
                            prev["rapid_warned"] = True
                            store.record_event(Event(
                                name=f"widget.rapid_recreation.{cls_name}",
                                category=DiagnosticCategory.WIDGET,
                                metadata={
                                    "class": cls_name,
                                    "interval_ms": round(elapsed, 1),
                                    "threshold_ms": RAPID_RECREATION_MS,
                                },
                            ))

                    # ── Store tracking info ────────────────────────
                    probe._widgets[wid] = {
                        "class": cls_name,
                        "parent_class": type(parent).__name__ if parent else "None",
                        "created_at": now,
                        "thread": threading.current_thread().name,
                    }
                    probe._creation_count[cls_name] = (
                        probe._creation_count.get(cls_name, 0) + 1
                    )

                # ── Off-screen detection ───────────────────────────
                try:
                    geo = self.geometry()
                    if geo.x() < OFF_SCREEN_THRESHOLD or geo.y() < OFF_SCREEN_THRESHOLD:
                        store.record_event(Event(
                            name=f"widget.off_screen.{cls_name}",
                            category=DiagnosticCategory.WIDGET,
                            metadata={
                                "class": cls_name,
                                "x": geo.x(),
                                "y": geo.y(),
                                "width": geo.width(),
                                "height": geo.height(),
                            },
                        ))
                except Exception:
                    pass

                # ── Counters ───────────────────────────────────────
                store.increment(f"widget.created.{cls_name}")

                # ── Connect destroyed signal ───────────────────────
                def _on_destroyed(
                    _obj: Any,
                    _wid: int = wid,
                    _cls: str = cls_name,
                    _probe: WidgetTrackerProbe = probe,
                ) -> None:
                    with _probe._lock:
                        info = _probe._widgets.pop(_wid, None)
                    if info:
                        lifetime_s = time.perf_counter() - info["created_at"]
                        _probe.store.increment(f"widget.destroyed.{_cls}")
                        _probe.store.record_event(Event(
                            name=f"widget.destroyed.{_cls}",
                            category=DiagnosticCategory.WIDGET,
                            metadata={
                                "lifetime_s": round(lifetime_s, 2),
                                "class": _cls,
                                "parent_class": info.get("parent_class", "None"),
                            },
                        ))

                try:
                    self.destroyed.connect(
                        _on_destroyed,
                        type=Qt.QueuedConnection,
                    )
                except Exception:
                    pass

            except Exception:
                logger.exception(
                    "[DIAG] WidgetTrackerProbe: error in _patched_init for %s",
                    type(self).__name__,
                )

        QWidget.__init__ = _patched_init
        self._installed = True
        logger.info("[DIAG] WidgetTrackerProbe installed")

    def uninstall(self) -> None:
        """Restore original ``QWidget.__init__``."""
        if self._installed and self._original_init is not None:
            QWidget.__init__ = self._original_init
            self._installed = False
            logger.info("[DIAG] WidgetTrackerProbe uninstalled")

    # ── Sampling ──────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic check for leaks, duplicates, and off-screen widgets.

        Called by the ``DiagnosticsEngine`` sampler loop every ~2 s.
        """
        now = time.perf_counter()

        with self._lock:
            # ── Orphan detection (widgets alive > 300 s) ──────────
            for wid, info in list(self._widgets.items()):
                age_s = now - info["created_at"]
                if age_s > ORPHAN_TIMEOUT_S and info.get("orphan_warned") is None:
                    info["orphan_warned"] = True
                    self.store.record_event(Event(
                        name="widget.orphaned",
                        category=DiagnosticCategory.WIDGET,
                        metadata={
                            "class": info["class"],
                            "age_s": round(age_s, 1),
                            "created_at": info["created_at"],
                        },
                    ))

            # ── Duplicate storm: same class created > 10 in last 60 s ──
            threshold = now - DUPLICATE_STORM_WINDOW_S
            recent_counts: dict[str, int] = {}
            for info in self._widgets.values():
                if info["created_at"] > threshold:
                    cls = info["class"]
                    recent_counts[cls] = recent_counts.get(cls, 0) + 1
            for cls_name, count in recent_counts.items():
                if count > DUPLICATE_STORM_COUNT:
                    self.store.record_event(Event(
                        name="widget.duplicate_storm",
                        category=DiagnosticCategory.WIDGET,
                        metadata={
                            "class": cls_name,
                            "count_60s": count,
                            "threshold": DUPLICATE_STORM_COUNT,
                        },
                    ))

        # ── Gauge updates ─────────────────────────────────────────
        app = QApplication.instance()
        if app is not None:
            try:
                all_w = app.allWidgets()
                self.store.set_gauge("widget.alive_count", float(len(all_w)))
            except Exception:
                pass

        self.store.set_gauge("widget.tracked_count", float(len(self._widgets)))

        with self._lock:
            for cls_name, count in self._creation_count.items():
                self.store.set_gauge(
                    f"widget.creation_count.{cls_name}",
                    float(count),
                    labels={"class": cls_name},
                )
