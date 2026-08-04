"""Operion Runtime Diagnostics Framework.

A zero-instrumentation observability layer that monkey-patches key
application components to record timing, detect bottlenecks, and
explain exactly why Operion becomes slow, freezes, or blocks.

Usage in main.py::

    from diagnostics import DiagnosticsEngine
    engine = DiagnosticsEngine(output_dir="logs/diagnostics")
    engine.install_all()          # activate all probes
    # ... normal startup ...
    engine.start_monitoring()     # begin periodic sampling
    # ... app runs ...
    engine.shutdown()             # stop monitoring + generate report
"""

from __future__ import annotations

import atexit
import importlib
import json
import logging
import os
import threading
import time
from typing import Any

from diagnostics.store import DiagnosticStore
from diagnostics.models import DiagnosticCategory, Span, Event

logger = logging.getLogger("diagnostics")

# ── Probe registry — used by install_all() ──────────────────────────
_PROBES_REGISTRY: list[tuple[str, str, str]] = [
    # (name, module_path, class_name)
    ("startup",             "diagnostics.startup_timeline",       "StartupProbe"),
    ("view_lifecycle",      "diagnostics.view_lifecycle",        "ViewLifecycleProbe"),
    ("widget_tracker",      "diagnostics.widget_tracker",        "WidgetTrackerProbe"),
    ("event_loop",          "diagnostics.event_loop_monitor",    "EventLoopProbe"),
    ("timer_diagnostics",   "diagnostics.timer_diagnostics",     "TimerDiagnosticsProbe"),
    ("signal_diagnostics",  "diagnostics.signal_diagnostics",    "SignalDiagnosticsProbe"),
    ("workerpool",          "diagnostics.workerpool_diagnostics","WorkerPoolProbe"),
    ("database",            "diagnostics.database_diagnostics",  "DatabaseProbe"),
    ("paint",               "diagnostics.paint_diagnostics",     "PaintProbe"),
    ("memory",              "diagnostics.memory_diagnostics",    "MemoryProbe"),
    ("eventbus",            "diagnostics.eventbus_diagnostics",  "EventBusProbe"),
    ("navigation",          "diagnostics.navigation_profiler",   "NavigationProbe"),
    ("fullscreen",          "diagnostics.fullscreen_diagnostics","FullscreenProbe"),
    ("freeze",              "diagnostics.freeze_detector",       "FreezeDetectorProbe"),
]

# ── Global store singleton ────────────────────────────────────────────
_store: DiagnosticStore | None = None


def get_store() -> DiagnosticStore:
    global _store
    if _store is None:
        _store = DiagnosticStore()
    return _store


# ── Diagnostics Engine ────────────────────────────────────────────────


class DiagnosticsEngine:
    """Central coordinator for all diagnostic probes."""

    DEFAULT_SAMPLE_INTERVAL_S = 2.0

    def __init__(
        self,
        output_dir: str = "logs/diagnostics",
        install_all: bool = False,
    ):
        self.output_dir = output_dir
        self._report_generated = False
        os.makedirs(output_dir, exist_ok=True)
        self.store = get_store()

        self._probes: dict[str, Any] = {}
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._start_ts: float = 0.0

        if install_all:
            self.install_all()

    # ── Probe installation ──────────────────────────────────────────

    def install(self, name: str, probe: Any) -> None:
        """Register and activate a diagnostic probe."""
        if name in self._probes:
            logger.debug("[DIAG] Probe '%s' already installed, skipping", name)
            return
        self._probes[name] = probe
        probe._store = self.store
        if hasattr(probe, "install"):
            try:
                probe.install()
                logger.info("[DIAG] Installed probe: %s", name)
            except Exception as exc:
                logger.error("[DIAG] Failed to install probe %s: %s", name, exc)

    def install_all(self) -> None:
        """Install every available probe.

        Each probe import + install is wrapped in try/except so a
        single missing or broken probe never crashes the engine.
        Must be called BEFORE any target classes are instantiated.
        """
        for name, module_path, class_name in _PROBES_REGISTRY:
            try:
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                # StartupProbe accepts output_dir; all others just take the store
                if name == "startup":
                    instance = cls(self.store, output_dir=self.output_dir)
                else:
                    instance = cls(self.store)
                self.install(name, instance)
            except ImportError as exc:
                logger.warning(
                    "[DIAG] Probe '%s' skipped (import error): %s", name, exc
                )
            except Exception as exc:
                logger.error(
                    "[DIAG] Probe '%s' failed to install: %s", name, exc
                )

    def install_subset(self, names: list[str]) -> None:
        """Install only the named probes — useful for development."""
        for name, module_path, class_name in _PROBES_REGISTRY:
            if name in names:
                try:
                    mod = importlib.import_module(module_path)
                    cls = getattr(mod, class_name)
                    self.install(name, cls(self.store))
                except Exception as exc:
                    logger.error(
                        "[DIAG] Probe '%s' failed to install: %s", name, exc
                    )

    # ── Lifecycle ───────────────────────────────────────────────────

    def start_monitoring(self) -> None:
        """Begin periodic sampling probes (memory, event loop, freeze)."""
        if self._running:
            return
        self._running = True
        self._start_ts = time.perf_counter()
        atexit.register(self.shutdown)

        for name, probe in self._probes.items():
            if hasattr(probe, "start"):
                try:
                    probe.start()
                    logger.info("[DIAG] Started probe: %s", name)
                except Exception as exc:
                    logger.error("[DIAG] Failed to start probe %s: %s", name, exc)

        # Background sampler for periodic metric collection
        self._monitor_thread = threading.Thread(
            target=self._sampler_loop, daemon=True, name="diag-sampler"
        )
        self._monitor_thread.start()
        logger.info("[DIAG] Monitoring started")

    def stop_monitoring(self) -> None:
        """Stop all probes. Idempotent — safe to call multiple times."""
        if not self._running:
            return
        self._running = False
        for name, probe in self._probes.items():
            if hasattr(probe, "stop"):
                try:
                    probe.stop()
                except Exception as exc:
                    logger.error("[DIAG] Failed to stop probe %s: %s", name, exc)
        self._monitor_thread = None
        logger.info("[DIAG] Monitoring stopped")

    def _sampler_loop(self) -> None:
        """Background loop for periodic metric sampling.

        Respects per-probe ``sample_interval_s`` attribute if set.
        Defaults to 2s for all probes.
        """
        last_sample: dict[str, float] = {}
        while self._running:
            try:
                now = time.perf_counter()
                for name, probe in self._probes.items():
                    if not hasattr(probe, "sample"):
                        continue
                    interval = getattr(probe, "sample_interval_s", self.DEFAULT_SAMPLE_INTERVAL_S)
                    last_ts = last_sample.get(name, 0)
                    if now - last_ts >= interval:
                        try:
                            probe.sample()
                        except Exception:
                            pass
                        last_sample[name] = now
            except Exception:
                pass
            # Poll _running every 250ms for responsiveness
            for _ in range(4):
                if not self._running:
                    return
                time.sleep(0.25)

    # ── Report generation ───────────────────────────────────────────

    def generate_report(self) -> str:
        """Produce the final runtime diagnostics report.

        Does NOT stop monitoring — call ``stop_monitoring()`` first
        if you want a point-in-time snapshot.
        """
        from diagnostics.reporter import ReportGenerator
        reporter = ReportGenerator(self.store, self.output_dir)
        report_path = reporter.generate_all()
        self._report_generated = True
        logger.info("[DIAG] Report generated: %s", report_path)
        return report_path

    def export_timeline_json(self) -> str:
        """Export raw timeline as JSON for external tools."""
        path = os.path.join(self.output_dir, "diagnostic_timeline.json")
        data = {
            "spans": [s.to_dict() for s in self.store.get_all_spans()],
            "events": [e.to_dict() for e in self.store.get_all_events()],
            "metrics": self.store.get_all_gauges(),
            "counters": self.store.get_all_counters(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("[DIAG] Timeline exported to %s", path)
        return path

    def shutdown(self) -> None:
        """Clean shutdown — stop monitoring, export, generate report."""
        atexit.unregister(self.shutdown)
        self.stop_monitoring()
        if not self._report_generated:
            self.generate_report()
        self.export_timeline_json()
        for name, probe in self._probes.items():
            if hasattr(probe, "uninstall"):
                try:
                    probe.uninstall()
                except Exception:
                    pass
        self._probes.clear()
        logger.info("[DIAG] Diagnostics engine shut down")


# ── Module-level convenience ──────────────────────────────────────────

_engine: DiagnosticsEngine | None = None


def get_engine() -> DiagnosticsEngine:
    global _engine
    if _engine is None:
        _engine = DiagnosticsEngine()
    return _engine


def install_and_start(output_dir: str = "logs/diagnostics") -> DiagnosticsEngine:
    """One-shot setup: create engine, install all probes, start monitoring."""
    global _engine
    _engine = DiagnosticsEngine(output_dir=output_dir)
    _engine.install_all()
    _engine.start_monitoring()
    return _engine
