"""Navigation Profiler Probe — measure MainWindow navigation performance.

Monkey-patches ``MainWindow._switch_module`` to time every navigation,
track cache hit/miss ratios, and emit events for slow transitions.
"""

from __future__ import annotations

import functools
import logging
from typing import Any

from diagnostics.models import DiagnosticCategory, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.navigation_profiler")

SLOW_NAV_THRESHOLD_MS = 1000


class NavigationProbe:
    """Probes navigation performance by wrapping ``_switch_module``.

    Usage::

        probe = NavigationProbe(store)
        probe.install()     # patches MainWindow._switch_module
        probe.sample()      # updates gauges (called by engine)
    """

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._original: Any = None
        self._installed = False

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch ``MainWindow._switch_module`` to add timing."""
        if self._installed:
            return

        import ui.main_window as mw_module

        _original = mw_module.MainWindow._switch_module
        store = self.store

        @functools.wraps(_original)
        def _patched_switch(self, key: str, data: dict[str, Any] | None = None) -> Any:  # noqa: ANN001
            from_key = getattr(self, "_active_module", None) or "startup"
            span = store.begin_span(
                f"navigation.{from_key}_to_{key}",
                category=DiagnosticCategory.NAVIGATION,
                metadata={"from": from_key, "to": key},
            )

            cache_hit = key in self._module_cache
            store.increment("navigation.cache_hit" if cache_hit else "navigation.cache_miss")

            try:
                return _original(self, key, data)
            finally:
                store.end_span(span)
                store.increment(f"navigation.switch_count.{key}")

                if span.elapsed_ms > SLOW_NAV_THRESHOLD_MS:
                    store.record_event(Event(
                        name="navigation.slow",
                        category=DiagnosticCategory.NAVIGATION,
                        metadata={
                            "from": from_key,
                            "to": key,
                            "elapsed_ms": round(span.elapsed_ms, 1),
                            "cache_hit": cache_hit,
                        },
                    ))

        mw_module.MainWindow._switch_module = _patched_switch
        self._original = _original
        self._installed = True
        logger.info("[DIAG] NavigationProbe installed")

    def uninstall(self) -> None:
        """Restore original ``MainWindow._switch_module``."""
        if self._installed and self._original is not None:
            import ui.main_window as mw_module

            mw_module.MainWindow._switch_module = self._original
            self._installed = False
            logger.info("[DIAG] NavigationProbe uninstalled")

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Update navigation-related gauges.

        Computes and sets:
          - ``navigation.cache_hit_ratio``
          - ``navigation.avg_time_ms``
          - ``navigation.slow_count``
        """
        store = self.store

        # Cache hit ratio
        hits = store.get_counter("navigation.cache_hit")
        misses = store.get_counter("navigation.cache_miss")
        total = hits + misses
        ratio = hits / total if total > 0 else 0.0
        store.set_gauge("navigation.cache_hit_ratio", ratio)

        # Average navigation time from recent spans (1000 most recent entries provides
        # statistically meaningful sample without excessive memory overhead)
        nav_spans = store.get_spans(category=DiagnosticCategory.NAVIGATION, limit=1000)
        if nav_spans:
            avg_ms = sum(s.elapsed_ms for s in nav_spans) / len(nav_spans)
            slow_count = sum(1 for s in nav_spans if s.elapsed_ms > SLOW_NAV_THRESHOLD_MS)
            store.set_gauge("navigation.avg_time_ms", round(avg_ms, 2))
            store.set_gauge("navigation.slow_count", float(slow_count))

            # Top-5 slowest navigation targets
            nav_by_target: dict[str, list[float]] = {}
            for s in nav_spans:
                target = s.metadata.get("to", "unknown")
                nav_by_target.setdefault(target, []).append(s.elapsed_ms)

            top5 = sorted(nav_by_target.items(), key=lambda x: max(x[1]), reverse=True)[:5]
            for idx, (target, times) in enumerate(top5):
                store.set_gauge(
                    f"navigation.top5_slow_{idx}",
                    round(max(times), 1),
                    labels={"target": target, "count": str(len(times))},
                )
        else:
            store.set_gauge("navigation.avg_time_ms", 0.0)
            store.set_gauge("navigation.slow_count", 0.0)
