"""Thread-safe diagnostic data store.

Central repository for all spans, events, gauges, counters, and freeze
reports collected by the diagnostics framework.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, Optional

from diagnostics.models import (
    DiagnosticCategory,
    Span,
    Event,
    Gauge,
    Counter,
    FreezeReport,
)


class DiagnosticStore:
    """Thread-safe central store for all diagnostic data.

    All writes acquire a lock.  Reads acquire the same lock so callers
    always see a consistent snapshot.  High-frequency event types are
    ring-buffered to cap memory usage.
    """

    MAX_SPANS = 50_000
    MAX_EVENTS = 100_000
    MAX_GAUGES_PER_NAME = 10_000
    MAX_FREEZE_REPORTS = 100

    def __init__(self):
        self._lock = threading.RLock()

        # Timed operations
        self._spans: list[Span] = []

        # Point-in-time events
        self._events: list[Event] = []

        # Metrics
        self._gauges: dict[str, list[Gauge]] = defaultdict(list)
        self._counters: dict[str, Counter] = {}

        # Freeze reports
        self._freeze_reports: list[FreezeReport] = []

        # Indexes for fast lookup
        self._spans_by_category: dict[DiagnosticCategory, list[Span]] = defaultdict(list)
        self._spans_by_name: dict[str, list[Span]] = defaultdict(list)

        # Startup-specific
        self._startup_span: Optional[Span] = None

    # ── Spans ──────────────────────────────────────────────────────

    def record_span(self, span: Span) -> None:
        """Store a completed span."""
        with self._lock:
            self._spans.append(span)
            if len(self._spans) > self.MAX_SPANS:
                self._spans.pop(0)
            self._spans_by_category[span.category].append(span)
            self._spans_by_name[span.name].append(span)

    def begin_span(
        self,
        name: str,
        category: DiagnosticCategory,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Span:
        """Create and record a span that hasn't finished yet."""
        span = Span(
            name=name,
            category=category,
            parent_id=parent_id,
            metadata=metadata or {},
        )
        return span

    def end_span(self, span: Span, metadata: Optional[dict] = None) -> Span:
        """Finish a span and record it."""
        span.finish()
        if metadata:
            span.metadata.update(metadata)
        self.record_span(span)
        return span

    def get_spans(
        self,
        category: Optional[DiagnosticCategory] = None,
        name: Optional[str] = None,
        min_ms: float = 0.0,
        limit: int = 1000,
    ) -> list[Span]:
        """Query spans with optional filters."""
        with self._lock:
            if category and name:
                results = [s for s in self._spans_by_name.get(name, [])
                           if s.category == category]
            elif category:
                results = list(self._spans_by_category.get(category, []))
            elif name:
                results = list(self._spans_by_name.get(name, []))
            else:
                results = list(self._spans)

            if min_ms > 0:
                results = [s for s in results if s.elapsed_ms >= min_ms]
            return sorted(results, key=lambda s: s.elapsed_ms, reverse=True)[:limit]

    def get_all_spans(self) -> list[Span]:
        with self._lock:
            return list(self._spans)

    def get_slowest_spans(self, n: int = 50) -> list[Span]:
        """Return the *n* slowest spans across all categories."""
        with self._lock:
            sorted_spans = sorted(self._spans, key=lambda s: s.elapsed_ms, reverse=True)
            return sorted_spans[:n]

    # ── Startup span ───────────────────────────────────────────────

    def set_startup_span(self, span: Span) -> None:
        self._startup_span = span

    def get_startup_span(self) -> Optional[Span]:
        return self._startup_span

    # ── Events ─────────────────────────────────────────────────────

    def record_event(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.MAX_EVENTS:
                self._events.pop(0)

    def get_all_events(self) -> list[Event]:
        with self._lock:
            return list(self._events)

    # ── Gauges ─────────────────────────────────────────────────────

    def record_gauge(self, gauge: Gauge) -> None:
        with self._lock:
            self._gauges[gauge.name].append(gauge)
            if len(self._gauges[gauge.name]) > self.MAX_GAUGES_PER_NAME:
                self._gauges[gauge.name].pop(0)

    def set_gauge(self, name: str, value: float, labels: Optional[dict] = None) -> None:
        self.record_gauge(Gauge(name=name, value=value, labels=labels or {}))

    def get_gauge_history(self, name: str) -> list[Gauge]:
        with self._lock:
            return list(self._gauges.get(name, []))

    def get_latest_gauge(self, name: str) -> Optional[Gauge]:
        with self._lock:
            history = self._gauges.get(name, [])
            return history[-1] if history else None

    def get_all_gauges(self) -> dict[str, list[dict]]:
        with self._lock:
            return {
                name: [{"value": g.value, "timestamp": g.timestamp, "labels": g.labels}
                       for g in gauges]
                for name, gauges in self._gauges.items()
            }

    # ── Counters ───────────────────────────────────────────────────

    def increment(self, name: str, delta: int = 1) -> None:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name=name)
            self._counters[name].value += delta

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, Counter(name=name)).value

    def get_all_counters(self) -> dict[str, int]:
        with self._lock:
            return {k: v.value for k, v in self._counters.items()}

    # ── Freeze reports ─────────────────────────────────────────────

    def record_freeze(self, report: FreezeReport) -> None:
        with self._lock:
            self._freeze_reports.append(report)
            if len(self._freeze_reports) > self.MAX_FREEZE_REPORTS:
                self._freeze_reports.pop(0)

    def get_freeze_reports(self) -> list[FreezeReport]:
        with self._lock:
            return list(self._freeze_reports)

    # ── Category summaries ─────────────────────────────────────────

    def category_summary(self) -> dict[str, dict[str, float]]:
        """Aggregate stats per category: total_ms, count, avg_ms, max_ms."""
        with self._lock:
            summary: dict[str, dict] = {}
            for span in self._spans:
                cat = span.category.value
                if cat not in summary:
                    summary[cat] = {"total_ms": 0.0, "count": 0, "max_ms": 0.0}
                summary[cat]["total_ms"] += span.elapsed_ms
                summary[cat]["count"] += 1
                if span.elapsed_ms > summary[cat]["max_ms"]:
                    summary[cat]["max_ms"] = span.elapsed_ms
            for cat in summary:
                c = summary[cat]["count"]
                summary[cat]["avg_ms"] = round(summary[cat]["total_ms"] / c, 2) if c else 0
                summary[cat]["total_ms"] = round(summary[cat]["total_ms"], 2)
            return summary

    def snapshot(self) -> dict[str, Any]:
        """Return a point-in-time summary of all diagnostic data."""
        with self._lock:
            return {
                "span_count": len(self._spans),
                "event_count": len(self._events),
                "gauge_count": sum(len(v) for v in self._gauges.values()),
                "freeze_count": len(self._freeze_reports),
                "counter_snapshot": {k: v.value for k, v in self._counters.items()},
                "category_summary": self.category_summary(),
                "slowest_spans": [
                    {"name": s.name, "elapsed_ms": round(s.elapsed_ms, 1), "category": s.category.value}
                    for s in sorted(self._spans, key=lambda x: x.elapsed_ms, reverse=True)[:20]
                ],
            }

    def clear(self) -> None:
        """Reset all collected data."""
        with self._lock:
            self._spans.clear()
            self._events.clear()
            self._gauges.clear()
            self._counters.clear()
            self._freeze_reports.clear()
            self._spans_by_category.clear()
            self._spans_by_name.clear()
            self._startup_span = None
