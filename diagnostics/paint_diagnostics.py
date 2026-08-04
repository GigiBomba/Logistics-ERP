"""Paint Diagnostics Probe — monitor QWidget paintEvent timing and paint storms.

Monkey-patches ``PySide6.QtWidgets.QWidget.paintEvent`` at the class level
to measure paint duration, detect paint storms (>5 paints in 100ms on any
widget), and flag slow main-window paints (>33 ms).

**CRITICAL**: paintEvent is the single most performance-sensitive code path.
Overhead is minimised with a fast guard, no extraneous allocations in the
hot path, and locks only used for probe-level shared state.

Detection events
----------------
- ``paint.storm`` — >5 paint events in 100ms on the same widget (debounced 10s)
- ``paint.main_window_slow`` — QMainWindow paint taking >33 ms

Metrics
-------
- ``paint.rate_per_sec`` — paints per second (from 500-sample rolling window)
- ``paint.slow_ratio`` — fraction of paints taking >16 ms
- ``paint.count.<ClassName>`` — per-class paint counts (top-5 at sample time)
- Spans recorded for paints taking >5 ms
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections import deque
from typing import Any

from PySide6.QtWidgets import QWidget, QMainWindow

from diagnostics.models import DiagnosticCategory, Span, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.paint_diagnostics")


class PaintProbe:
    """Monitors QWidget paintEvent timing, storms, and slow paints.

    Usage::

        probe = PaintProbe(store)
        probe.install()     # patches QWidget.paintEvent
        probe.sample()      # periodic check (called by engine)
        probe.uninstall()   # restores original paintEvent
    """

    sample_interval_s: float = 2.0

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._installed = False
        self._original_paint: Any = None
        self._enabled = True

        # Lock protects all probe-level mutable state below.
        self._lock = threading.Lock()

        # Storm detection debounce: widget id (int) -> last storm event time
        self._storm_debounce: dict[int, float] = {}

        # Rolling window of paint timestamps for rate calculation (last 500)
        self._paint_rate_window: deque[float] = deque(maxlen=500)

        # Per-class paint count for top-N widget class identification
        self._paint_count_per_class: dict[str, int] = {}

        # Counter totals
        self._paint_total = 0
        self._paint_slow = 0

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch ``QWidget.paintEvent`` with a timed wrapper."""
        if self._installed:
            return

        self._original_paint = QWidget.paintEvent
        probe = self

        @functools.wraps(self._original_paint)
        def _patched_paint(self: QWidget, event: Any) -> Any:
            # ── Fast guard ──────────────────────────────────────────
            if not probe._enabled:
                return probe._original_paint(self, event)

            start = time.perf_counter()
            try:
                return probe._original_paint(self, event)
            finally:
                elapsed = (time.perf_counter() - start) * 1000.0

                cls_name = type(self).__name__

                # ── Lock-protected probe-level bookkeeping ──────────
                with probe._lock:
                    probe._paint_total += 1
                    if elapsed > 16.0:
                        probe._paint_slow += 1
                    probe._paint_count_per_class[cls_name] = (
                        probe._paint_count_per_class.get(cls_name, 0) + 1
                    )
                    probe._paint_rate_window.append(start)

                # ── Span for paints slower than 5 ms ────────────────
                if elapsed > 5.0:
                    probe.store.record_span(Span(
                        name=f"paint.{cls_name}",
                        category=DiagnosticCategory.PAINT,
                        start_time=start,
                        end_time=time.perf_counter(),
                        metadata={"elapsed_ms": round(elapsed, 2)},
                    ))

                # ── Storm detection (per-widget deque) ──────────────
                ts_deque: deque[float] | None = getattr(
                    self, "_diag_paint_ts", None
                )
                if ts_deque is None:
                    ts_deque = deque(maxlen=20)
                    self._diag_paint_ts = ts_deque  # type: ignore[attr-defined]
                ts_deque.append(start)

                now = start  # same perf_counter time base
                cutoff = now - 0.1  # 100 ms window
                recent = sum(1 for t in ts_deque if t > cutoff)
                if recent > 5:
                    widget_id = id(self)
                    with probe._lock:
                        last_storm = probe._storm_debounce.get(widget_id, 0.0)
                        if now - last_storm > 10.0:  # debounce 10 s
                            probe._storm_debounce[widget_id] = now
                            probe.store.record_event(Event(
                                name="paint.storm",
                                category=DiagnosticCategory.PAINT,
                                metadata={
                                    "widget_type": cls_name,
                                    "paints_in_100ms": recent,
                                },
                            ))

                # ── QMainWindow slow paint (> 33 ms) ───────────────
                if isinstance(self, QMainWindow) and elapsed > 33.0:
                    probe.store.record_event(Event(
                        name="paint.main_window_slow",
                        category=DiagnosticCategory.PAINT,
                        metadata={
                            "widget_type": cls_name,
                            "elapsed_ms": round(elapsed, 1),
                        },
                    ))

        QWidget.paintEvent = _patched_paint
        self._installed = True
        logger.info("[DIAG] PaintProbe installed")

    def uninstall(self) -> None:
        """Restore original ``QWidget.paintEvent``."""
        if self._installed and self._original_paint is not None:
            QWidget.paintEvent = self._original_paint
            self._installed = False
            with self._lock:
                self._paint_rate_window.clear()
                self._paint_count_per_class.clear()
                self._paint_total = 0
                self._paint_slow = 0
                self._storm_debounce.clear()
            logger.info("[DIAG] PaintProbe uninstalled")

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic gauge and top-N reporting.

        Called by ``DiagnosticsEngine._sampler_loop`` every ~2 s.
        """
        try:
            now = time.perf_counter()
            with self._lock:
                # ── Paint rate (paints / sec) ───────────────────────
                recent = [t for t in self._paint_rate_window if now - t < 1.0]
                self.store.set_gauge("paint.rate_per_sec", float(len(recent)))

                # ── Slow paint ratio ─────────────────────────────────
                total = self._paint_total
                slow = self._paint_slow
                if total > 0:
                    self.store.set_gauge("paint.slow_ratio", slow / total)

                # ── Top-5 widget classes by paint count ──────────────
                sorted_classes = sorted(
                    self._paint_count_per_class.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
                for cls_name, count in sorted_classes:
                    self.store.set_gauge(
                        f"paint.count.{cls_name}", float(count)
                    )
        except Exception:
            logger.exception("[DIAG] PaintProbe.sample failed — suppressed")
