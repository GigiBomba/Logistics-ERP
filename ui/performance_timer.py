"""Performance timing infrastructure for Operion ERP.

Provides context managers and decorators to measure execution time of
critical code paths: tab switches, widget creation, DB queries, rendering.

Usage::

    from ui.performance_timer import PerfTimer, timing_report

    with PerfTimer("overview.load_data") as t:
        self._load_data_sync()

    # Get accumulated report
    report = timing_report()
"""

from __future__ import annotations

import contextlib
import functools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Thread-safe global accumulator ────────────────────────────────────

_lock = Lock()
_timings: dict[str, list[float]] = defaultdict(list)
_calls: dict[str, int] = defaultdict(int)


def _record(label: str, elapsed_ms: float) -> None:
    """Record a single timing sample."""
    with _lock:
        _timings[label].append(elapsed_ms)
        _calls[label] += 1


def reset_timings() -> None:
    """Clear all accumulated timing data."""
    with _lock:
        _timings.clear()
        _calls.clear()


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class TimingSample:
    """A single timing measurement."""
    label: str
    elapsed_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class TimingSummary:
    """Aggregate statistics for a timing label."""
    label: str
    count: int
    total_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


def _percentile(values: list[float], p: float) -> float:
    """Compute the *p*th percentile of *values* (0-100)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (p / 100.0) * (len(sorted_vals) - 1)
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_vals):
        return sorted_vals[f] * (1 - c) + sorted_vals[f + 1] * c
    return sorted_vals[-1]


# ── Context Manager ───────────────────────────────────────────────────

class PerfTimer:
    """Context manager that records execution time.

    Can also be used as a decorator::

        @PerfTimer("my_view.load_data")
        def _load_data(self):
            ...

    Args:
        label: Dot-separated identifier (e.g. ``"overview.load_data"``).
        log_level: Log level for the measurement line (default: ``logging.DEBUG``).
        report_on_exit: If True, log summary when the context exits.
    """

    def __init__(
        self,
        label: str,
        log_level: int = logging.DEBUG,
        report_on_exit: bool = False,
    ):
        self._label = label
        self._log_level = log_level
        self._report_on_exit = report_on_exit
        self._start: float | None = None

    def __enter__(self) -> "PerfTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        if self._start is not None:
            elapsed_ms = (time.perf_counter() - self._start) * 1000.0
            _record(self._label, elapsed_ms)
            logger.log(self._log_level, "[PERF] %s: %.2f ms", self._label, elapsed_ms)
            if self._report_on_exit:
                summary = summary_for(self._label)
                if summary:
                    logger.info(
                        "[PERF-SUM] %s: count=%d avg=%.1fms p95=%.1fms total=%.1fms",
                        summary.label, summary.count,
                        summary.avg_ms, summary.p95_ms, summary.total_ms,
                    )

    def __call__(self, func: Callable) -> Callable:
        """Use as a decorator."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper


# ── Decorator shortcut ────────────────────────────────────────────────

def timed(label: str | None = None) -> Callable:
    """Decorator that times a method.

    If *label* is None, uses ``module.ClassName.method_name``.

    Usage::

        @timed("overview.refresh")
        def refresh(self):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func_label = label or f"{func.__module__}.{func.__qualname__}"
        timer = PerfTimer(func_label)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with timer:
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ── Query timing ──────────────────────────────────────────────────────

_slow_query_threshold_ms = 100.0  # Log queries slower than this


def record_query(query: str, elapsed_ms: float, row_count: int = 0) -> None:
    """Record a database query timing."""
    # Truncate query for the label
    short_query = query.strip()[:80].replace("\n", " ")
    label = f"db.{short_query}"
    _record(label, elapsed_ms)
    if elapsed_ms > _slow_query_threshold_ms:
        logger.warning(
            "[SLOW-DB] %.1f ms | %d rows | %s",
            elapsed_ms, row_count, short_query,
        )


# ── Report generation ─────────────────────────────────────────────────

def summary_for(label: str) -> TimingSummary | None:
    """Return aggregate stats for a single label."""
    with _lock:
        values = _timings.get(label, [])
        if not values:
            return None
        count = _calls.get(label, 0)
        total = sum(values)
        return TimingSummary(
            label=label,
            count=count,
            total_ms=total,
            avg_ms=total / count if count else 0,
            min_ms=min(values),
            max_ms=max(values),
            p50_ms=_percentile(values, 50),
            p95_ms=_percentile(values, 95),
            p99_ms=_percentile(values, 99),
        )


def timing_report(prefix: str | None = None) -> list[TimingSummary]:
    """Return sorted list of all accumulated timing summaries.

    Args:
        prefix: If set, only include labels starting with this string.
    """
    with _lock:
        labels = sorted(_timings.keys())

    results: list[TimingSummary] = []
    for label in labels:
        if prefix and not label.startswith(prefix):
            continue
        summary = summary_for(label)
        if summary:
            results.append(summary)
    return results


def timing_table(prefix: str | None = None) -> str:
    """Return a markdown table of all timings."""
    summaries = timing_report(prefix)
    if not summaries:
        return "*No timing data collected.*\n"

    lines = [
        "| Label | Count | Avg (ms) | Min (ms) | Max (ms) | P50 (ms) | P95 (ms) | Total (ms) |",
        "|-------|-------|----------|----------|----------|----------|----------|------------|",
    ]
    for s in summaries:
        lines.append(
            f"| {s.label} | {s.count} | {s.avg_ms:.1f} | {s.min_ms:.1f} | "
            f"{s.max_ms:.1f} | {s.p50_ms:.1f} | {s.p95_ms:.1f} | {s.total_ms:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


def baseline_table(view_timings: dict[str, dict[str, float]]) -> str:
    """Format a baseline performance table from view timing estimates.

    Args:
        view_timings: Nested dict: view_name -> {phase: elapsed_ms}
    """
    lines = [
        "| Tab | Widget Init (ms) | DB Queries (ms) | Render (ms) | Total (ms) |",
        "|-----|-----------------|-----------------|-------------|------------|",
    ]
    for view, phases in sorted(view_timings.items()):
        total = sum(phases.values())
        lines.append(
            f"| {view} | {phases.get('widget_init', 0):.0f} | "
            f"{phases.get('db', 0):.0f} | {phases.get('render', 0):.0f} | "
            f"{total:.0f} |"
        )
    lines.append("")
    return "\n".join(lines)
