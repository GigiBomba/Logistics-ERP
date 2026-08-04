"""Memory Diagnostics Probe — passive monitoring of heap, widget, and RSS metrics.

No monkey-patching.  Uses ``tracemalloc`` for Python heap tracking,
``psutil`` for process RSS/VMS, and ``QApplication.allWidgets()`` for
widget-object counts.

Metrics
-------
- ``memory.rss_mb`` — resident set size in MB
- ``memory.vms_mb`` — virtual memory size in MB
- ``memory.widget_count`` — number of live QWidget instances
- ``memory.python_heap_mb`` — current Python heap size (tracemalloc, every 5th sample)
- ``memory.pixmap_cache_limit_kb`` — QPixmapCache cache limit

Detection events
----------------
- ``memory.growth_anomaly`` — RSS grew >10 MB since last sample
- ``memory.alloc_growth`` — tracemalloc reports >1 MB allocation growth at a source line
"""

from __future__ import annotations

import logging
import os
import tracemalloc
from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QPixmapCache
from PySide6.QtWidgets import QApplication

from diagnostics.models import DiagnosticCategory, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.memory_diagnostics")


class MemoryProbe:
    """Passive memory monitor — no monkey-patching.

    Usage::

        probe = MemoryProbe(store)
        probe.install()     # starts tracemalloc
        probe.sample()      # periodic check (called by engine)
        probe.uninstall()   # stops tracemalloc
    """

    sample_interval_s: float = 5.0   # Override the default 2 s sampler interval
    WARMUP_SKIP: int = 10            # Skip first 10 samples to let app stabilise

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._tracemalloc_started = False
        self._process: Any = None
        self._last_snapshot: Any = None
        self._last_rss_mb: float = 0.0
        self._sample_count: int = 0

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Start tracemalloc and acquire a psutil process handle."""
        # ── tracemalloc ─────────────────────────────────────────────
        try:
            if not tracemalloc.is_tracing():
                tracemalloc.start(25)  # 25 frames per allocation
            self._tracemalloc_started = True
        except Exception as exc:
            logger.warning("[DIAG] tracemalloc unavailable: %s", exc)

        # ── psutil process handle ───────────────────────────────────
        try:
            import psutil
            self._process = psutil.Process()
        except ImportError:
            self._process = None
            logger.info("[DIAG] psutil not available — RSS/VMS tracking disabled")

        logger.info("[DIAG] MemoryProbe installed")

    def uninstall(self) -> None:
        """Stop tracemalloc if it was started."""
        if self._tracemalloc_started:
            try:
                tracemalloc.stop()
                self._tracemalloc_started = False
            except Exception:
                logger.exception("[DIAG] Error stopping tracemalloc")
            logger.info("[DIAG] MemoryProbe uninstalled")

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic memory metric collection.

        Called by ``DiagnosticsEngine._sampler_loop`` every ~5 s.
        """
        self._sample_count += 1
        if self._sample_count < self.WARMUP_SKIP:
            return

        # ── RSS / VMS via psutil ────────────────────────────────────
        if self._process is not None:
            try:
                mem = self._process.memory_info()
                rss_mb = mem.rss / (1024.0 * 1024.0)
                vms_mb = mem.vms / (1024.0 * 1024.0)
                self.store.set_gauge("memory.rss_mb", rss_mb)
                self.store.set_gauge("memory.vms_mb", vms_mb)

                # Anomalous growth detection
                growth = rss_mb - self._last_rss_mb
                if self._last_rss_mb > 0.0 and growth > 10.0:
                    self.store.record_event(Event(
                        name="memory.growth_anomaly",
                        category=DiagnosticCategory.MEMORY,
                        metadata={
                            "growth_mb": round(growth, 1),
                            "rss_mb": round(rss_mb, 1),
                        },
                    ))
                self._last_rss_mb = rss_mb
            except Exception:
                logger.exception("[DIAG] psutil memory_info failed — suppressed")

        # ── Widget count & pixmap cache ─────────────────────────────
        try:
            _qapp = QApplication.instance()
            if isinstance(_qapp, QApplication):
                widgets = _qapp.allWidgets()
                self.store.set_gauge("memory.widget_count", float(len(widgets)))
                self.store.set_gauge(
                    "memory.pixmap_cache_limit_kb",
                    float(QPixmapCache.cacheLimit()),
                )
        except Exception:
            logger.exception("[DIAG] Widget/pixmap counting failed — suppressed")

        # ── Tracemalloc snapshot (every 5th sample — expensive) ─────
        if self._tracemalloc_started and self._sample_count % 5 == 0:
            try:
                snapshot = tracemalloc.take_snapshot()
                if self._last_snapshot is not None:
                    top_stats = snapshot.compare_to(self._last_snapshot, "lineno")
                    for stat in top_stats[:5]:
                        if stat.size_diff > 1024 * 1024:  # > 1 MB growth
                            self.store.record_event(Event(
                                name="memory.alloc_growth",
                                category=DiagnosticCategory.MEMORY,
                                metadata={
                                    "size_diff_kb": stat.size_diff // 1024,
                                    "traceback": str(stat.traceback)[:200],
                                },
                            ))
                self._last_snapshot = snapshot

                # Current heap size
                top = snapshot.statistics("lineno")
                heap_bytes = sum(s.size for s in top)
                self.store.set_gauge(
                    "memory.python_heap_mb", heap_bytes / (1024.0 * 1024.0)
                )
            except Exception:
                logger.exception("[DIAG] tracemalloc snapshot failed — suppressed")
