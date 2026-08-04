"""Signal Diagnostics Probe — monitor PySide6 Signal emit performance.

Monkey-patches ``PySide6.QtCore.Signal.emit`` at the class level to
track emit timing, detect deeply-chained signal cascades, and identify
signal storms (rapid-fire emits of the same signal).

Detection events
----------------
- ``signal.deep_chain`` — emit chain depth exceeds threshold (default 5)
- ``signal.storm`` — >100 emits/s of the same signal (detected at sample())

Metrics
-------
- ``signal.emit_rate.{signal_name}`` — emits per second since last sample
- Spans recorded for sampled emits (every 10th) that take >5 ms
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections import defaultdict
from typing import Any

from diagnostics.models import DiagnosticCategory, Span, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.signal_diagnostics")

# ── Thresholds ──────────────────────────────────────────────────────────
DEEP_CHAIN_THRESHOLD = 5        # emit chain depth → event
STORM_RATE_THRESHOLD = 100      # emits/s of same signal → storm event
SLOW_EMIT_THRESHOLD_MS = 5.0   # sampled emit slower than this → span
SAMPLE_EVERY_N = 10            # record timing for every Nth emit


class SignalDiagnosticsProbe:
    """Monitors PySide6 Signal emit timing, chain depth, and frequency.

    Usage::

        probe = SignalDiagnosticsProbe(store)
        probe.install()     # patches PySide6.QtCore.Signal.emit
        probe.sample()      # periodic check (called by engine)
    """

    sample_interval_s: float = 2.0

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._installed = False
        self._original_emit: Any = None
        self._enabled = True

        # Thread-local emit chain depth
        self._tls = threading.local()

        # Per-signal-name tracking (protected by lock)
        self._lock = threading.Lock()
        self._emit_count: dict[str, int] = {}
        self._emit_sample_counter: dict[str, int] = {}
        self._emit_timestamps: dict[str, list[float]] = defaultdict(list)

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch ``PySide6.QtCore.Signal.emit``."""
        if self._installed:
            return

        from PySide6.QtCore import Signal

        # PySide6's Signal is a descriptor type — class-level .emit doesn't exist.
        # Class-level monkey-patching is only compatible with PyQt.
        if not hasattr(Signal, "emit"):
            logger.info(
                "[DIAG] SignalDiagnosticsProbe: PySide6 Signal descriptor has no "
                "class-level emit — probe not supported on this binding. Skipping."
            )
            return

        self._original_emit = Signal.emit
        probe = self

        @functools.wraps(self._original_emit)
        def _patched_emit(signal_descriptor: Signal, *args: Any) -> Any:
            """Patched Signal.emit — wraps the original with diagnostics."""
            # Fast guard: if probe disabled, pass through immediately
            if not probe._enabled:
                return probe._original_emit(signal_descriptor, *args)

            # ── Chain depth tracking ────────────────────────────────
            depth = getattr(probe._tls, "signal_depth", 0) + 1
            probe._tls.signal_depth = depth
            start = time.perf_counter()

            try:
                # Derive a stable signal name for metrics
                sig_name: str = "unknown"
                try:
                    sig_name = (
                        getattr(signal_descriptor, "name", None)
                        or str(signal_descriptor)[:50]
                    )
                except Exception:
                    sig_name = f"signal_{id(signal_descriptor)}"

                # ── Call the real emit ───────────────────────────────
                result = probe._original_emit(signal_descriptor, *args)

                elapsed = (time.perf_counter() - start) * 1000.0

                with probe._lock:
                    # Track emit count
                    probe._emit_count[sig_name] = (
                        probe._emit_count.get(sig_name, 0) + 1
                    )
                    # Track sample counter (every Nth emit)
                    sample_count = (
                        probe._emit_sample_counter.get(sig_name, 0) + 1
                    )
                    probe._emit_sample_counter[sig_name] = sample_count
                    # Track timestamps for rate calculation
                    probe._emit_timestamps[sig_name].append(start)

                # ── Deep chain detection ─────────────────────────────
                if depth > DEEP_CHAIN_THRESHOLD:
                    probe.store.record_event(Event(
                        name="signal.deep_chain",
                        category=DiagnosticCategory.SIGNAL,
                        metadata={
                            "depth": depth,
                            "signal": sig_name,
                            "threshold": DEEP_CHAIN_THRESHOLD,
                        },
                    ))

                # ── Sampled timing span ──────────────────────────────
                if sample_count % SAMPLE_EVERY_N == 0 and elapsed > SLOW_EMIT_THRESHOLD_MS:
                    probe.store.record_span(Span(
                        name=f"signal.emit.{sig_name}",
                        category=DiagnosticCategory.SIGNAL,
                        start_time=start,
                        end_time=time.perf_counter(),
                        metadata={
                            "elapsed_ms": round(elapsed, 2),
                            "signal": sig_name,
                            "depth": depth,
                        },
                    ))

                return result

            except Exception:
                logger.exception(
                    "[DIAG] Signal emit patch failed — disabling signal probe"
                )
                probe._enabled = False
                # Fall through to original to never break signal emission
                return probe._original_emit(signal_descriptor, *args)

            finally:
                probe._tls.signal_depth = depth - 1

        Signal.emit = _patched_emit
        self._installed = True
        logger.info("[DIAG] SignalDiagnosticsProbe installed")

    def uninstall(self) -> None:
        """Restore original ``Signal.emit``."""
        if not self._installed or self._original_emit is None:
            return
        from PySide6.QtCore import Signal
        # Only restore if our patch is still active (avoids errors on PySide6
        # where install() was skipped because Signal has no class-level emit).
        if hasattr(Signal, "emit") and getattr(Signal, "emit", None) is not self._original_emit:
            Signal.emit = self._original_emit
        self._installed = False
        with self._lock:
            self._emit_count.clear()
            self._emit_sample_counter.clear()
            self._emit_timestamps.clear()
        logger.info("[DIAG] SignalDiagnosticsProbe uninstalled")

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic check for signal storms and emit-rate gauges.

        Called by ``DiagnosticsEngine._sampler_loop`` every ~2 s.
        """
        try:
            now = time.perf_counter()

            with self._lock:
                # Snapshot and clear timestamp buckets for this cycle
                all_timestamps = dict(self._emit_timestamps)
                self._emit_timestamps.clear()

            for sig_name, timestamps in all_timestamps.items():
                # Count emits within the last 1 second
                recent = [t for t in timestamps if now - t < 1.0]
                rate = len(recent)

                # Emit-rate gauge
                self.store.set_gauge(
                    f"signal.emit_rate.{sig_name}", float(rate)
                )

                # Storm detection
                if rate > STORM_RATE_THRESHOLD:
                    self.store.record_event(Event(
                        name="signal.storm",
                        category=DiagnosticCategory.SIGNAL,
                        metadata={
                            "signal": sig_name,
                            "rate_per_sec": rate,
                            "threshold": STORM_RATE_THRESHOLD,
                        },
                    ))

        except Exception:
            logger.exception(
                "[DIAG] SignalDiagnosticsProbe.sample failed — suppressed"
            )
