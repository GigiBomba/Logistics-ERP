"""Event Loop Monitor Probe — measure UI thread responsiveness.

Creates a high-precision ``QTimer`` that fires every ~16 ms (≈ 60 FPS)
to record frame times, detect blocked frames, and maintain a rolling
histogram of event-loop responsiveness.

Unlike most probes in the framework this is **not** a monkey-patch.
It is a standalone heartbeat timer that observes the event loop from
inside the loop itself — if the timer callback is delayed, the loop
is busy.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

from diagnostics.models import DiagnosticCategory, Event, Gauge
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.event_loop")

# ── Constants ──────────────────────────────────────────────────────────
HEARTBEAT_INTERVAL_MS = 16      # ≈ 60 FPS
HISTOGRAM_MAXLEN = 120          # ~2 s of history at 16 ms
FPS_SAMPLE_WINDOW = 60          # number of frames to average for FPS
BLOCKED_THRESHOLDS_MS = [16, 33, 50, 100, 250, 500, 1000]

HISTOGRAM_BUCKETS = [
    (0, 8, "0_8"),
    (8, 16, "8_16"),
    (16, 33, "16_33"),
    (33, 50, "33_50"),
    (50, 100, "50_100"),
    (100, 250, "100_250"),
    (250, 500, "250_500"),
    (500, 1000, "500_1000"),
    (1000, float("inf"), "1000_plus"),
]


class EventLoopProbe:
    """Measures event-loop responsiveness via a high-frequency heartbeat.

    Usage::

        probe = EventLoopProbe(store)
        probe.install()   # creates the QTimer (requires QApplication)
        probe.start()     # starts the timer
        ...
        probe.stop()      # pauses the timer
        probe.uninstall() # destroys the timer, frees resources

    The engine calls ``sample()`` periodically to compute histograms
    and FPS from the rolling window of frame times.
    """

    sample_interval_s: float = 2.0

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._timer: QTimer | None = None
        self._installed = False
        self._running = False

        # Rolling history of frame times (ms)
        self._frame_times: deque[float] = deque(maxlen=HISTOGRAM_MAXLEN)

        # Last tick timestamp
        self._last_tick: float = 0.0

        # Suppression set: which blocked-threshold events we have already
        # emitted, keyed by threshold.  Reset every sample cycle so we
        # can warn again if blocking persists.
        self._blocked_emitted: set[str] = set()

    # ── install / start / stop / uninstall ────────────────────────────

    def install(self) -> None:
        """Create the heartbeat timer.

        Safe to call multiple times — the timer is created only once.
        Requires that a ``QApplication`` already exists.
        """
        if self._installed:
            return
        if QApplication.instance() is None:
            logger.warning("[DIAG] EventLoopProbe.install() skipped — no QApplication instance")
            return

        self._timer = QTimer()  # no parent — lives for app lifetime
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._heartbeat)
        # Interval set on start()
        self._installed = True
        logger.info("[DIAG] EventLoopProbe installed")

    def start(self) -> None:
        """Start the heartbeat timer.

        Calls ``install()`` if not already installed so callers can
        safely call ``start()`` directly.
        """
        if not self._installed:
            self.install()
        if self._running or self._timer is None:
            return
        self._last_tick = time.perf_counter()
        self._blocked_emitted.clear()
        self._timer.start(HEARTBEAT_INTERVAL_MS)
        self._running = True
        logger.info("[DIAG] EventLoopProbe started")

    def stop(self) -> None:
        """Stop the heartbeat timer.  Idempotent."""
        if self._running and self._timer is not None:
            self._timer.stop()
        self._running = False

    def uninstall(self) -> None:
        """Stop and destroy the timer.  Restore initial state."""
        self.stop()
        if self._timer is not None:
            self._timer.timeout.disconnect(self._heartbeat)
            self._timer.deleteLater()
            self._timer = None
        self._installed = False
        self._frame_times.clear()
        self._last_tick = 0.0
        logger.info("[DIAG] EventLoopProbe uninstalled")

    # ── Heartbeat callback ────────────────────────────────────────────

    def _heartbeat(self) -> None:
        """Called every ~16 ms by the QTimer.

        Measures elapsed time since the last tick, records metrics,
        and detects blocked frames beyond configured thresholds.
        """
        try:
            now = time.perf_counter()
            if self._last_tick <= 0:
                self._last_tick = now
                return

            elapsed_ms = (now - self._last_tick) * 1000.0
            self._last_tick = now

            # Record the frame time
            self._frame_times.append(elapsed_ms)

            # Gauges
            self.store.set_gauge("event_loop.frame_time_ms", elapsed_ms)

            # Counter
            self.store.increment("event_loop.frames_total")

            # Blocked-frame detection
            for threshold in BLOCKED_THRESHOLDS_MS:
                if elapsed_ms >= threshold:
                    key = f"blocked_{threshold}"
                    if key not in self._blocked_emitted:
                        self._blocked_emitted.add(key)
                        self.store.record_event(Event(
                            name=f"event_loop.frame_blocked_{threshold}ms",
                            category=DiagnosticCategory.EVENT_LOOP,
                            metadata={
                                "elapsed_ms": round(elapsed_ms, 2),
                                "threshold_ms": threshold,
                            },
                        ))

        except Exception:
            logger.exception("[DIAG] EventLoopProbe._heartbeat failed — suppressed")

    # ── Sampling (called by engine sampler loop) ──────────────────────

    def sample(self) -> None:
        """Compute histogram buckets and FPS from the rolling window.

        Called periodically by ``DiagnosticsEngine._sampler_loop``.
        """
        try:
            # ── Histogram ───────────────────────────────────────────
            with_thread_lock = list(self._frame_times)  # snapshot
            if not with_thread_lock:
                return

            bucket_counts: dict[str, float] = {
                bname: 0.0 for _, _, bname in HISTOGRAM_BUCKETS
            }
            for ft in with_thread_lock:
                for lo, hi, bname in HISTOGRAM_BUCKETS:
                    if lo <= ft < hi:
                        bucket_counts[bname] += 1.0
                        break

            for bname, count in bucket_counts.items():
                self.store.set_gauge(f"event_loop.histogram.{bname}", count)

            # ── FPS ─────────────────────────────────────────────────
            recent = with_thread_lock[-FPS_SAMPLE_WINDOW:]
            if recent:
                avg_frame_ms = sum(recent) / len(recent)
                fps = 1000.0 / avg_frame_ms if avg_frame_ms > 0 else 0.0
                self.store.set_gauge("event_loop.fps", fps)

            # Allow blocked events to be re-emitted next cycle
            self._blocked_emitted.clear()

        except Exception:
            logger.exception("[DIAG] EventLoopProbe.sample failed — suppressed")
