"""Runtime diagnostics report generator.

Produces a comprehensive Markdown report from the current DiagnosticStore
state, covering every probe category.  The output file is written to a
configurable directory and the path is returned to the caller.
"""

from __future__ import annotations

import os
import time

from diagnostics.models import DiagnosticCategory
from diagnostics.store import DiagnosticStore


class ReportGenerator:
    """Generate a Markdown runtime diagnostics report.

    Args:
        store: The DiagnosticStore instance to read data from.
        output_dir: Directory where the report .md file will be written.
    """

    def __init__(self, store: DiagnosticStore, output_dir: str) -> None:
        self.store = store
        self.output_dir = output_dir

    # ── Public API ──────────────────────────────────────────────────

    def generate_all(self) -> str:
        """Build the full report, write it to disk, and return the file path."""
        sections = [
            self._header(),
            self._executive_summary(),
            self._category_breakdown(),
            self._slowest_operations(),
            self._freeze_events(),
            self._memory_summary(),
            self._event_loop_summary(),
            self._event_bus_summary(),
            self._worker_pool_summary(),
            self._navigation_summary(),
            self._database_summary(),
            self._timer_summary(),
            self._paint_summary(),
            self._recommendations(),
        ]

        report = "\n\n".join(sections)
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, "runtime_diagnostics_report.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        return path

    # ── Sections ────────────────────────────────────────────────────

    def _header(self) -> str:
        return f"""# Runtime Diagnostics Report

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Data collected during this session**

---

## 1. Executive Summary

"""

    def _executive_summary(self) -> str:
        snap = self.store.snapshot()
        cs = snap.get("category_summary", {})
        total_ms = sum(c["total_ms"] for c in cs.values())
        freeze_count = snap.get("freeze_count", 0)
        span_count = snap.get("span_count", 0)
        return f"""| Metric | Value |
|--------|-------|
| Total measured time | {total_ms:,.0f} ms ({total_ms / 1000:.1f} s) |
| Spans collected | {span_count} |
| Events logged | {snap.get('event_count', 0)} |
| Freezes detected | {freeze_count} |
| Categories tracked | {len(cs)} |

"""

    def _category_breakdown(self) -> str:
        cs = self.store.category_summary()
        if not cs:
            return "## 2. Category Breakdown\n\n*No data collected.*\n"
        lines = [
            "## 2. Category Breakdown\n",
            "| Category | Total (ms) | Count | Avg (ms) | Max (ms) |",
            "|----------|-----------|-------|---------|---------|",
        ]
        for cat in sorted(cs, key=lambda c: cs[c]["total_ms"], reverse=True):
            d = cs[cat]
            lines.append(
                f"| {cat} | {d['total_ms']:,.1f} | {d['count']} |"
                f" {d['avg_ms']:.1f} | {d['max_ms']:.1f} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _slowest_operations(self) -> str:
        slow = self.store.get_slowest_spans(50)
        if not slow:
            return "## 3. Top 50 Slowest Operations\n\n*No data collected.*\n"
        lines = [
            "## 3. Top 50 Slowest Operations\n",
            "| # | Operation | Elapsed (ms) | Category | Thread |",
            "|---|-----------|-------------|----------|--------|",
        ]
        for i, s in enumerate(slow[:50], 1):
            lines.append(
                f"| {i} | {s.name} | {s.elapsed_ms:,.1f} |"
                f" {s.category.value} | {s.thread_name} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _freeze_events(self) -> str:
        freezes = self.store.get_freeze_reports()
        if not freezes:
            return "## 4. Freeze Events\n\n*No freezes detected.*\n"
        lines = [
            "## 4. Freeze Events\n",
            "| # | Duration (ms) | Time | Stack Trace (first line) |",
            "|---|--------------|------|--------------------------|",
        ]
        for i, f in enumerate(freezes[:20], 1):
            ts = time.strftime("%H:%M:%S", time.localtime(f.timestamp))
            stack_line = (
                f.stack_trace.split("\n")[0][:80] if f.stack_trace else "?"
            )
            lines.append(f"| {i} | {f.duration_ms:,.0f} | {ts} | `{stack_line}` |")
        lines.append("")
        return "\n".join(lines)

    def _memory_summary(self) -> str:
        gauges = self.store.get_all_gauges()
        rss = gauges.get("memory.rss_mb", [])
        widget_c = gauges.get("memory.widget_count", [])
        if not rss:
            return "## 5. Memory\n\n*No memory data collected.*\n"
        lines = [
            "## 5. Memory\n",
            "| Metric | Latest | Peak |",
            "|--------|--------|------|",
        ]
        for name, series in [("RSS (MB)", rss), ("Widget Count", widget_c)]:
            if series:
                vals = [
                    s.get("value", 0) if isinstance(s, dict) else s
                    for s in series
                ]
                latest = vals[-1] if vals else 0
                peak = max(vals) if vals else 0
                lines.append(f"| {name} | {latest:.1f} | {peak:.1f} |")
        lines.append("")
        return "\n".join(lines)

    def _event_loop_summary(self) -> str:
        gauges = self.store.get_all_gauges()
        fps = gauges.get("event_loop.fps", [])
        frame_times = gauges.get("event_loop.frame_time_ms", [])
        if not fps and not frame_times:
            return "## 6. Event Loop\n\n*No event loop data collected.*\n"
        lines = [
            "## 6. Event Loop\n",
            "| Metric | Value |",
            "|--------|-------|",
        ]
        if fps:
            latest = fps[-1]
            val = latest.get("value", 0) if isinstance(latest, dict) else latest
            lines.append(f"| Average FPS | {float(val):.1f} |")
        if frame_times:
            latest = frame_times[-1]
            val = latest.get("value", 0) if isinstance(latest, dict) else latest
            lines.append(f"| Latest frame time | {float(val):.1f} ms |")
            vals = [
                s.get("value", 0) if isinstance(s, dict) else float(s)
                for s in frame_times
            ]
            max_ft = max(vals) if vals else 0
            lines.append(f"| Max frame time | {max_ft:.1f} ms |")
        lines.append("")
        return "\n".join(lines)

    def _event_bus_summary(self) -> str:
        counters = self.store.get_all_counters()
        eb_keys = {k: v for k, v in counters.items() if k.startswith("eventbus.")}
        top_events = sorted(eb_keys.items(), key=lambda x: x[1], reverse=True)[:10]
        if not top_events:
            return "## 7. Event Bus\n\n*No event bus data collected.*\n"
        lines = [
            "## 7. Event Bus\n",
            "| Event | Count |",
            "|-------|-------|",
        ]
        for k, v in top_events:
            lines.append(f"| {k} | {v} |")
        lines.append("")
        return "\n".join(lines)

    def _worker_pool_summary(self) -> str:
        counters = self.store.get_all_counters()
        submitted = counters.get("workerpool.tasks_submitted", 0)
        completed = counters.get("workerpool.tasks_completed", 0)
        return f"""## 8. Worker Pool

| Metric | Value |
|--------|-------|
| Tasks submitted | {submitted} |
| Tasks completed | {completed} |
| Queue depth | {submitted - completed} |

"""

    def _navigation_summary(self) -> str:
        counters = self.store.get_all_counters()
        cache_hits = counters.get("navigation.cache_hit", 0)
        cache_misses = counters.get("navigation.cache_miss", 0)
        total_nav = cache_hits + cache_misses
        hit_ratio = (cache_hits / total_nav * 100) if total_nav > 0 else 0
        return f"""## 9. Navigation

| Metric | Value |
|--------|-------|
| Total navigations | {total_nav} |
| Cache hits | {cache_hits} |
| Cache misses | {cache_misses} |
| Hit ratio | {hit_ratio:.1f}% |

"""

    def _database_summary(self) -> str:
        counters = self.store.get_all_counters()
        total = counters.get("db.queries_total", 0)
        db_counters = {
            k: v
            for k, v in counters.items()
            if k.startswith("db.queries.") and k != "db.queries_total"
        }
        top = sorted(db_counters.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = [
            f"## 10. Database\n",
            f"**Total queries:** {total}\n",
        ]
        if top:
            lines.append("| Query Pattern | Count |")
            lines.append("|--------------|-------|")
            for k, v in top:
                sql = k.replace("db.queries.", "", 1)[:60]
                lines.append(f"| `{sql}` | {v} |")
            lines.append("")
        return "\n".join(lines)

    def _timer_summary(self) -> str:
        gauges = self.store.get_all_gauges()
        active = gauges.get("timer.active_count", [])
        active_val = active[-1].get("value", 0) if active else 0
        return f"""## 11. Timers

| Metric | Value |
|--------|-------|
| Active timers | {active_val} |

"""

    def _paint_summary(self) -> str:
        counters = self.store.get_all_counters()
        total = counters.get("paint.total", 0)
        slow = counters.get("paint.slow", 0)
        slow_ratio = (slow / total * 100) if total > 0 else 0
        return f"""## 12. Paint

| Metric | Value |
|--------|-------|
| Total paints | {total} |
| Slow paints (>16ms) | {slow} |
| Slow ratio | {slow_ratio:.1f}% |

"""

    def _recommendations(self) -> str:
        recs = ["## 13. Recommendations\n"]

        # Rule-based recommendations from collected data
        counters = self.store.get_all_counters()
        spans = self.store.get_slowest_spans(20)
        freezes = self.store.get_freeze_reports()

        if freezes:
            longest = max(f.duration_ms for f in freezes)
            recs.append(
                f"- \u26a0\ufe0f **{len(freezes)} UI freezes detected.**"
                f" Investigate blocking operations on the main thread."
                f" Longest freeze: {longest:.0f}ms."
            )

        db_total = counters.get("db.queries_total", 0)
        if db_total > 100:
            recs.append(
                f"- \U0001f50d **{db_total} database queries executed.**"
                f" Check for N+1 patterns and consider adding"
                f" query caching if not already in place."
            )

        slow_db_events = [
            s
            for s in spans
            if s.category == DiagnosticCategory.DATABASE and s.elapsed_ms > 100
        ]
        if slow_db_events:
            recs.append(
                f"- \U0001f40c **{len(slow_db_events)} slow database queries"
                f" (>100ms).** Top offender:"
                f" `{slow_db_events[0].name}` at"
                f" {slow_db_events[0].elapsed_ms:.0f}ms."
                f" Consider adding indexes or optimizing queries."
            )

        nav_spans = [
            s
            for s in spans
            if s.category == DiagnosticCategory.NAVIGATION and s.elapsed_ms > 500
        ]
        if nav_spans:
            recs.append(
                f"- \U0001f680 **{len(nav_spans)} slow navigations (>500ms).**"
                f" Worst: `{nav_spans[0].name}` at"
                f" {nav_spans[0].elapsed_ms:.0f}ms."
                f" Consider pre-creating views in warmup or"
                f" lazy-loading heavy components."
            )

        paint_total = counters.get("paint.total", 0)
        paint_slow = counters.get("paint.slow", 0)
        if paint_slow > 100:
            recs.append(
                f"- \U0001f3a8 **High paint overhead:** {paint_slow} slow paints"
                f" out of {paint_total}."
                f" Consider reducing widget tree depth, using"
                f" ``setUpdatesEnabled(False)`` during"
                f" batch updates, or double-buffering complex views."
            )

        freeze_spans = [
            s
            for s in spans
            if s.category == DiagnosticCategory.FREEZE
        ]
        if freeze_spans:
            stacks: dict[str, int] = {}
            for f in freezes:
                first_line = (
                    f.stack_trace.split("\n")[0] if f.stack_trace else "unknown"
                )
                stacks[first_line] = stacks.get(first_line, 0) + 1
            if stacks:
                worst = max(stacks.items(), key=lambda x: x[1])
                recs.append(
                    f"- \U0001f504 **Recurring freeze pattern:**"
                    f" `{worst[0][:100]}` occurred {worst[1]} times."
                )

        if not recs[1:]:
            recs.append(
                "*No actionable recommendations. System appears healthy.*"
            )

        return "\n".join(recs)
