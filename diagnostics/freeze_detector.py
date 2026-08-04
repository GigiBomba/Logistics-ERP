"""Freeze Detector Probe — detect and report main-thread freezes.

Two-pronged watchdog:

1. A ``QTimer`` running on the main thread updates ``_last_alive_ts``
   every ``HEARTBEAT_MS`` (100 ms).
2. A daemon background thread polls ``_last_alive_ts`` every
   ``WATCHDOG_INTERVAL_S`` (0.1 s).  If the main thread has not
   heartbeated within ``FREEZE_THRESHOLD_MS`` (1000 ms), it captures
   a stack trace of the main thread and creates a ``FreezeReport``.

When the main thread recovers, the probe finalises the report and emits
diagnostic events, counting repeated freezes that occur within 5 s of
each other.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from diagnostics.models import DiagnosticCategory, Event, FreezeReport
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.freeze_detector")

REPEATED_FREEZE_WINDOW_S = 5
REPEATED_FREEZE_THRESHOLD = 3


class FreezeDetectorProbe:
    """Detects main-thread freezes via a heartbeat timer + watchdog thread.

    Usage::

        probe = FreezeDetectorProbe(store)
        probe.install()     # starts heartbeat timer + watchdog thread
        probe.sample()      # updates gauges (called by engine)
        probe.uninstall()   # restores original state
    """

    HEARTBEAT_MS: int = 100
    FREEZE_THRESHOLD_MS: int = 1000
    WATCHDOG_INTERVAL_S: float = 0.1

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._last_alive_ts: float = 0.0
        self._main_thread_id: int = threading.get_ident()
        self._watchdog: threading.Thread | None = None
        self._heartbeat_timer: QTimer | None = None
        self._running: bool = False

        # Thread lock protecting shared state accessed from both main and watchdog threads
        self._lock = threading.Lock()

        # Freeze tracking state
        self._in_freeze: bool = False
        self._freeze_start_ts: float = 0.0       # monotonic clock (perf_counter) for duration
        self._freeze_start_time: float = 0.0     # wall clock (time.time) for FreezeReport.timestamp
        self._last_freeze_stack: str = ""
        self._repeated_freeze_count: int = 0
        self._last_freeze_ts: float = 0.0

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Start the heartbeat timer and watchdog thread."""
        if self._running:
            return

        self._last_alive_ts = time.perf_counter()

        # Heartbeat on main thread
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.timeout.connect(self._heartbeat)
        self._heartbeat_timer.start(self.HEARTBEAT_MS)
        self._running = True

        # Watchdog daemon thread
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="freeze-watchdog",
        )
        self._watchdog.start()

        logger.info("[DIAG] FreezeDetectorProbe installed")

    def uninstall(self) -> None:
        """Stop the watchdog and heartbeat timer."""
        self.stop()

    def stop(self) -> None:
        """Shut down heartbeat and watchdog. Idempotent."""
        if not self._running:
            return
        self._running = False

        if self._heartbeat_timer is not None:
            try:
                self._heartbeat_timer.stop()
            except Exception:
                pass
            self._heartbeat_timer = None

        self._watchdog = None
        logger.info("[DIAG] FreezeDetectorProbe stopped")

    # ── Heartbeat (called on main thread) ────────────────────────────

    def _heartbeat(self) -> None:
        """Called on the main thread every ``HEARTBEAT_MS``."""
        # Snapshot shared state under lock before releasing the watchdog
        with self._lock:
            was_in_freeze = self._in_freeze
            freeze_start_ts = self._freeze_start_ts
            freeze_start_time = self._freeze_start_time
            freeze_stack = self._last_freeze_stack

        self._last_alive_ts = time.perf_counter()

        # If we were in a freeze and now we're not — finalise the report
        if was_in_freeze:
            freeze_ms = (time.perf_counter() - freeze_start_ts) * 1000.0
            with self._lock:
                self._in_freeze = False

            report = FreezeReport(
                duration_ms=freeze_ms,
                timestamp=freeze_start_time,   # wall clock — safe for time.localtime()
                thread_id=self._main_thread_id,
                stack_trace=freeze_stack,
                memory_mb=self._get_memory_mb(),
            )
            self.store.record_freeze(report)
            self.store.record_event(Event(
                name="freeze.detected",
                category=DiagnosticCategory.FREEZE,
                metadata={
                    "duration_ms": round(freeze_ms, 1),
                    "stack": self._last_freeze_stack[:200],
                },
            ))
            self.store.increment("freeze.detected")
            self.store.set_gauge("freeze.last_duration_ms", freeze_ms)

            # Track repeated freezes (wall-clock time for real-time window)
            now_wall = freeze_start_time
            if self._last_freeze_ts > 0 and (now_wall - self._last_freeze_ts) < REPEATED_FREEZE_WINDOW_S:
                self._repeated_freeze_count += 1
            else:
                self._repeated_freeze_count = 0
            self._last_freeze_ts = now_wall

            if self._repeated_freeze_count >= REPEATED_FREEZE_THRESHOLD:
                self.store.record_event(Event(
                    name="freeze.repeated",
                    category=DiagnosticCategory.FREEZE,
                    metadata={
                        "count": self._repeated_freeze_count,
                        "last_stack": self._last_freeze_stack[:200],
                    },
                ))

            logger.info("[DIAG] Freeze ended: %.0fms (repeated=%d)",
                        freeze_ms, self._repeated_freeze_count)

    # ── Watchdog (runs on background thread) ─────────────────────────

    def _watchdog_loop(self) -> None:
        """Background thread that detects when the main thread stops heartbeating."""
        while self._running:
            try:
                now = time.perf_counter()
                with self._lock:
                    last_ts = self._last_alive_ts
                    in_freeze = self._in_freeze

                elapsed_ms = (now - last_ts) * 1000.0

                if elapsed_ms > self.FREEZE_THRESHOLD_MS and not in_freeze:
                    with self._lock:
                        self._in_freeze = True
                        self._freeze_start_ts = last_ts
                        self._freeze_start_time = time.time()  # wall clock for FreezeReport.timestamp

                    # Capture stack trace of the main thread (outside lock)
                    self._last_freeze_stack = self._capture_main_stack()

                    logger.warning("[DIAG] Freeze detected: %.0fms+, stack:\n%s",
                                   elapsed_ms, self._last_freeze_stack[:500])
            except Exception:
                # Never let the watchdog die
                pass

            time.sleep(self.WATCHDOG_INTERVAL_S)

    def _capture_main_stack(self) -> str:
        """Capture the current stack trace of the main thread."""
        try:
            frames = sys._current_frames()  # noqa: SLF001
            main_frame = frames.get(self._main_thread_id)
            if main_frame is not None:
                stack = traceback.extract_stack(main_frame)
                return "".join(traceback.format_list(stack))
            else:
                return "[main thread frame not found]"
        except Exception as exc:
            return f"[stack capture failed: {exc}]"

    # ── Utility ──────────────────────────────────────────────────────

    def _get_memory_mb(self) -> float:
        """Return current RSS memory usage in MB, or 0 if unavailable."""
        try:
            import psutil

            return float(psutil.Process().memory_info().rss / (1024.0 * 1024.0))
        except ImportError:
            return 0.0
        except Exception:
            return 0.0

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Update freeze-related gauges."""
        with self._lock:
            in_freeze = self._in_freeze
        self.store.set_gauge("freeze.in_freeze", 1.0 if in_freeze else 0.0)
        total = self.store.get_counter("freeze.detected")
        self.store.set_gauge("freeze.total_count", float(total))
