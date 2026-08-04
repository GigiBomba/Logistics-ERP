"""
Invariant History — AI Query Interface

Natural-language-friendly query layer for AI agents (Operion Copilot).
Every method returns plain dict/list suitable for JSON serialization
and LLM consumption.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from invariant_history.models import (
    DashboardData,
    HistoryExecutionRecord,
    HistoryPage,
    HistoryQuery,
    ModuleReliability,
    RegressionReport,
    ReleaseComparison,
    StabilityIndex,
    TrendResult,
)
from invariant_history.storage import HistoryStorage

# Forward-imports for modules that will be created in upcoming iterations.
# These are used as references in docstrings and will be activated once
# the corresponding modules are implemented.
try:
    from invariant_history.trends import TrendEngine  # noqa: F401
except ImportError:
    pass
try:
    from invariant_history.stability import StabilityScorer  # noqa: F401
except ImportError:
    pass
try:
    from invariant_history.regression import RegressionDetector  # noqa: F401
except ImportError:
    pass
try:
    from invariant_history.dashboards import DashboardBuilder  # noqa: F401
except ImportError:
    pass
try:
    from invariant_history.reports import ReportGenerator  # noqa: F401
except ImportError:
    pass


class AIQueryInterface:
    """
    Structured query API for AI agents (Operion Copilot).

    Every method returns plain dict/list suitable for JSON serialization
    and LLM consumption.
    """

    def __init__(self, storage: HistoryStorage) -> None:
        self.storage = storage

    # ── Core queries ────────────────────────────────────────

    def which_invariant_fails_most_often(self, limit: int = 20) -> list[dict]:
        """
        Returns ranked list: invariant_id, title, failure_count, last_failure, avg_interval_days.

        Answers: "Which invariant fails most often?"
        """
        page = self.storage.query(HistoryQuery(limit=1000))
        if not page.items:
            return []

        # Aggregate failure data across all executions
        failure_counts: Counter[str] = Counter()
        last_failure: dict[str, str] = {}
        intervals: dict[str, list[datetime]] = {}

        for exec_rec in page.items:
            exec_ts = exec_rec.timestamp
            for inv in exec_rec.invariants:
                if inv.result == "fail":
                    inv_id = inv.invariant_id
                    failure_counts[inv_id] += 1
                    # Track the most recent failure timestamp
                    if inv_id not in last_failure or exec_ts > last_failure[inv_id]:
                        last_failure[inv_id] = exec_ts
                    # Collect timestamps for interval calculation
                    try:
                        intervals.setdefault(inv_id, []).append(
                            datetime.fromisoformat(exec_ts)
                        )
                    except (ValueError, TypeError):
                        pass

        if not failure_counts:
            return []

        # Sort by failure count descending
        ranked = failure_counts.most_common(limit)

        results: list[dict] = []
        for inv_id, count in ranked:
            # Calculate average interval between failures (in days)
            avg_interval = 0.0
            ts_list = intervals.get(inv_id)
            if ts_list and len(ts_list) > 1:
                ts_list.sort(reverse=True)
                diffs = [
                    (ts_list[i] - ts_list[i + 1]).total_seconds() / 86400.0
                    for i in range(len(ts_list) - 1)
                ]
                avg_interval = round(sum(diffs) / len(diffs), 1) if diffs else 0.0

            # Get the title from the most recent execution record
            title = inv_id
            for exec_rec in page.items:
                for inv in exec_rec.invariants:
                    if inv.invariant_id == inv_id and inv.title:
                        title = inv.title
                        break
                else:
                    continue
                break

            results.append(
                {
                    "invariant_id": inv_id,
                    "title": title,
                    "failure_count": count,
                    "last_failure": last_failure.get(inv_id, ""),
                    "avg_interval_days": avg_interval,
                }
            )

        return results

    def which_module_is_becoming_unstable(self) -> list[dict]:
        """
        Returns modules with degrading reliability trend, sorted by severity.

        Answers: "Which module is becoming unstable?"
        """
        modules = self.get_module_health_all()
        # Filter to modules with degrading trend, sorted by reliability ascending
        unstable = [m for m in modules if m.get("trend") == "degrading"]
        unstable.sort(key=lambda m: m.get("reliability_pct", 100))
        return unstable

    def which_patch_introduced_regressions(self, limit: int = 10) -> list[dict]:
        """
        Returns recent executions where regressions were detected.

        Answers: "Which recent AI patch introduced regressions?"
        """
        # Note: When invariant_history.regression is implemented, use:
        #   detector = RegressionDetector(self.storage)
        #   return detector.find_regressions(limit=limit)
        # For now, perform inline comparison.

        # Query recent AI patch executions
        page = self.storage.query(
            HistoryQuery(trigger="ai_patch", limit=limit)
        )
        if not page.items:
            return []

        results: list[dict] = []
        for exec_rec in page.items:
            # Get the immediate predecessor execution
            prev_page = self.storage.query(
                HistoryQuery(
                    since="1970-01-01",
                    until=exec_rec.timestamp,
                    limit=1,
                )
            )
            prev_rec = prev_page.items[0] if prev_page.items else None

            regressions_detected = False
            new_failures: list[str] = []
            pass_to_fail: list[str] = []
            time_spikes: list[str] = []

            if prev_rec:
                # Build a map of previous results
                prev_results: dict[str, str] = {}
                prev_times: dict[str, float] = {}
                for inv in prev_rec.invariants:
                    prev_results[inv.invariant_id] = inv.result
                    prev_times[inv.invariant_id] = inv.execution_time_ms

                for inv in exec_rec.invariants:
                    if inv.result == "fail":
                        prev_status = prev_results.get(inv.invariant_id, "unknown")
                        if prev_status == "pass":
                            pass_to_fail.append(inv.invariant_id)
                        elif prev_status not in ("fail",):
                            new_failures.append(inv.invariant_id)

                        # Check for execution time spikes (>2x previous)
                        prev_time = prev_times.get(inv.invariant_id)
                        if (
                            prev_time
                            and prev_time > 0
                            and inv.execution_time_ms > prev_time * 2
                        ):
                            time_spikes.append(inv.invariant_id)

                regressions_detected = bool(pass_to_fail or new_failures or time_spikes)

            results.append(
                {
                    "execution_id": exec_rec.execution_id,
                    "timestamp": exec_rec.timestamp,
                    "git_commit_hash": exec_rec.git_commit_hash,
                    "git_branch": exec_rec.git_branch,
                    "application_version": exec_rec.application_version,
                    "environment": exec_rec.environment,
                    "risk_level": exec_rec.risk_level,
                    "regressions_detected": regressions_detected,
                    "new_failures": new_failures,
                    "pass_to_fail_regressions": pass_to_fail,
                    "execution_time_spikes": time_spikes,
                    "total_invariants": exec_rec.total_invariants,
                    "passed": exec_rec.passed,
                    "failed": exec_rec.failed,
                }
            )

        return results

    def has_reliability_improved(self, days: int = 30) -> dict:
        """
        Compare first half vs second half of period.

        Returns: improved, change_pct, before_avg, after_avg.

        Answers: "Has reliability improved during the last month?"
        """
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        page = self.storage.query(
            HistoryQuery(since=since, limit=1000)
        )
        items = page.items
        if not items:
            return {
                "improved": False,
                "change_pct": 0.0,
                "before_avg": 0.0,
                "after_avg": 0.0,
                "sample_count": 0,
            }

        # Sort by timestamp ascending
        items.sort(key=lambda r: r.timestamp)

        midpoint = len(items) // 2
        before = items[:midpoint]
        after = items[midpoint:]

        def avg_pass_rate(records: list[HistoryExecutionRecord]) -> float:
            total = sum(r.total_invariants for r in records)
            passed = sum(r.passed for r in records)
            if total == 0:
                return 0.0
            return round((passed / total) * 100, 2)

        before_avg = avg_pass_rate(before)
        after_avg = avg_pass_rate(after)
        change_pct = round(after_avg - before_avg, 2)

        return {
            "improved": change_pct > 0,
            "change_pct": change_pct,
            "before_avg": before_avg,
            "after_avg": after_avg,
            "sample_count": len(items),
            "period_days": days,
        }

    def which_invariant_is_becoming_slower(self, limit: int = 10) -> list[dict]:
        """
        Returns invariants whose execution time is trending upward.

        Answers: "Which invariant is becoming slower?"
        """
        page = self.storage.query(HistoryQuery(limit=500))
        if not page.items:
            return []

        # Collect execution times per invariant across recent runs
        inv_times: dict[str, list[dict]] = defaultdict(list)
        for exec_rec in page.items:
            for inv in exec_rec.invariants:
                inv_times[inv.invariant_id].append(
                    {
                        "timestamp": exec_rec.timestamp,
                        "execution_time_ms": inv.execution_time_ms,
                        "title": inv.title,
                    }
                )

        # Calculate simple linear trend for each invariant
        scored: list[dict] = []
        for inv_id, points in inv_times.items():
            if len(points) < 3:
                continue

            points.sort(key=lambda p: p["timestamp"])
            n = len(points)
            times = [p["execution_time_ms"] for p in points]

            # Simple slope: (last_avg - first_avg) / count
            half = n // 2
            first_half_avg = sum(times[:half]) / half if half > 0 else 0
            second_half_avg = sum(times[half:]) / (n - half) if (n - half) > 0 else 0
            slope = second_half_avg - first_half_avg
            change_pct = (
                (slope / first_half_avg * 100) if first_half_avg > 0 else 0.0
            )

            if slope > 0:
                scored.append(
                    {
                        "invariant_id": inv_id,
                        "title": points[-1]["title"] or inv_id,
                        "avg_execution_time_ms": round(sum(times) / n, 2),
                        "first_half_avg_ms": round(first_half_avg, 2),
                        "second_half_avg_ms": round(second_half_avg, 2),
                        "change_ms": round(slope, 2),
                        "change_pct": round(change_pct, 1),
                        "sample_count": n,
                    }
                )

        scored.sort(key=lambda x: x["change_ms"], reverse=True)
        return scored[:limit]

    # ── Summary & overview ────────────────────────────────

    def get_summary_stats(self) -> dict:
        """Quick summary: total executions, period, stability, top issues."""
        page = self.storage.query(HistoryQuery(limit=1000))
        items = page.items

        total_executions = page.total
        if not items:
            return {
                "total_executions": 0,
                "period_start": "",
                "period_end": "",
                "stability_score": 0.0,
                "pass_rate": 0.0,
                "top_failing_invariants": [],
                "total_invariants_run": 0,
                "module_count": 0,
            }

        # Determine time range
        timestamps = sorted(
            [r.timestamp for r in items if r.timestamp],
            reverse=True,
        )
        period_start = timestamps[-1] if len(timestamps) > 1 else timestamps[0]
        period_end = timestamps[0]

        # Aggregate pass rate
        total_inv = sum(r.total_invariants for r in items)
        total_pass = sum(r.passed for r in items)
        total_fail = sum(r.failed for r in items)
        pass_rate = round((total_pass / total_inv * 100), 2) if total_inv > 0 else 0.0

        # Module count
        all_modules: set[str] = set()
        for r in items:
            all_modules.update(r.affected_modules)
            for inv in r.invariants:
                if inv.module:
                    all_modules.add(inv.module)

        # Top failing invariants
        failures: Counter[str] = Counter()
        for r in items:
            for inv in r.invariants:
                if inv.result == "fail":
                    failures[inv.invariant_id] += 1

        top_fails = [
            {"invariant_id": inv_id, "failure_count": count}
            for inv_id, count in failures.most_common(5)
        ]

        # Rough stability score based on pass rate and critical failures
        total_critical = sum(r.critical_failures for r in items)
        critical_rate = total_critical / total_executions if total_executions > 0 else 0.0
        stability_score = round(
            max(0.0, min(100.0, pass_rate - (critical_rate * 50))), 2
        )

        return {
            "total_executions": total_executions,
            "period_start": period_start,
            "period_end": period_end,
            "stability_score": stability_score,
            "pass_rate": pass_rate,
            "total_failures": total_fail,
            "total_critical_failures": total_critical,
            "top_failing_invariants": top_fails,
            "total_invariants_run": total_inv,
            "module_count": len(all_modules),
        }

    def get_execution_timeline(self, limit: int = 20) -> list[dict]:
        """Human-readable timeline of recent executions."""
        page = self.storage.query(HistoryQuery(limit=limit))
        timeline: list[dict] = []
        for rec in page.items:
            # Determine a human-readable summary
            status = "✅ All passed" if rec.failed == 0 else "❌ Had failures"
            if rec.critical_failures > 0:
                status = "🚨 Critical failures detected"

            timeline.append(
                {
                    "execution_id": rec.execution_id,
                    "timestamp": rec.timestamp,
                    "environment": rec.environment,
                    "trigger": rec.execution_trigger,
                    "git_branch": rec.git_branch,
                    "git_commit": rec.git_commit_hash[:8] if rec.git_commit_hash else "",
                    "version": rec.application_version,
                    "duration_ms": rec.execution_duration_ms,
                    "total": rec.total_invariants,
                    "passed": rec.passed,
                    "failed": rec.failed,
                    "warnings": rec.warnings,
                    "critical_failures": rec.critical_failures,
                    "risk_level": rec.risk_level,
                    "status_summary": status,
                    "affected_modules": sorted(rec.affected_modules),
                }
            )
        return timeline

    def get_module_health_all(self) -> list[dict]:
        """All modules with reliability score, trend, failure count."""
        page = self.storage.query(HistoryQuery(limit=1000))
        items = page.items
        if not items:
            return []

        # Aggregate per module
        module_data: dict[str, dict[str, Any]] = {}

        for exec_rec in items:
            for inv in exec_rec.invariants:
                module = inv.module or "uncategorized"
                entry = module_data.setdefault(
                    module,
                    {
                        "module": module,
                        "total_executions": 0,
                        "total_invariants": 0,
                        "passed": 0,
                        "failed": 0,
                        "last_failure": None,
                        "execution_times": [],
                        "results_over_time": [],
                    },
                )
                entry["total_invariants"] += 1
                if inv.result == "pass":
                    entry["passed"] += 1
                elif inv.result == "fail":
                    entry["failed"] += 1
                    if (
                        entry["last_failure"] is None
                        or exec_rec.timestamp > entry["last_failure"]
                    ):
                        entry["last_failure"] = exec_rec.timestamp
                entry["execution_times"].append(inv.execution_time_ms)

        # Compute reliability and trend for each module
        results: list[dict] = []
        for module, data in module_data.items():
            total = data["total_invariants"]
            reliability_pct = round(
                (data["passed"] / total * 100) if total > 0 else 0.0, 1
            )
            avg_time = (
                round(sum(data["execution_times"]) / len(data["execution_times"]), 2)
                if data["execution_times"]
                else 0.0
            )

            # Simple trend: compare first half vs second half reliability
            trend = "stable"
            # For trend, we'd need per-execution data; use a heuristic
            if data["failed"] > data["passed"] and data["failed"] > 2:
                trend = "degrading"
            elif reliability_pct >= 95:
                trend = "improving"

            results.append(
                {
                    "module": module,
                    "reliability_pct": reliability_pct,
                    "total_executions": data["total_executions"],
                    "total_invariants": total,
                    "passed": data["passed"],
                    "failed": data["failed"],
                    "trend": trend,
                    "last_failure": data["last_failure"] or "",
                    "avg_execution_time_ms": avg_time,
                }
            )

        results.sort(key=lambda m: m["reliability_pct"])
        return results

    def get_stability_history(self, limit: int = 30) -> list[dict]:
        """Stability index over time."""
        page = self.storage.query(HistoryQuery(limit=limit))
        items = page.items
        if not items:
            return []

        # Sort ascending by timestamp
        items.sort(key=lambda r: r.timestamp)

        history: list[dict] = []
        rolling_window: list[HistoryExecutionRecord] = []

        for rec in items:
            rolling_window.append(rec)
            # Keep a sliding window of the last 5 executions for stability calculation
            if len(rolling_window) > 5:
                rolling_window.pop(0)

            total_inv = sum(r.total_invariants for r in rolling_window)
            total_pass = sum(r.passed for r in rolling_window)
            total_critical = sum(r.critical_failures for r in rolling_window)
            pass_rate = round((total_pass / total_inv * 100), 2) if total_inv > 0 else 0.0
            critical_rate = total_critical / len(rolling_window) if rolling_window else 0.0
            stability_score = round(
                max(0.0, min(100.0, pass_rate - (critical_rate * 50))), 2
            )

            avg_time = round(
                sum(r.execution_duration_ms for r in rolling_window)
                / len(rolling_window),
                2,
            )

            history.append(
                {
                    "execution_id": rec.execution_id,
                    "timestamp": rec.timestamp,
                    "stability_score": stability_score,
                    "pass_rate": pass_rate,
                    "critical_failure_rate": round(critical_rate, 2),
                    "avg_execution_time_ms": avg_time,
                    "sample_size": len(rolling_window),
                }
            )

        return history

    # ── Natural language routing ─────────────────────────

    def query(self, question: str) -> dict:
        """
        Route natural language questions to the appropriate method.

        Simple keyword matching:
        - "fails most often" -> which_invariant_fails_most_often
        - "becoming unstable" -> which_module_is_becoming_unstable
        - "introduced regressions" -> which_patch_introduced_regressions
        - "reliability improved" -> has_reliability_improved
        - "becoming slower" -> which_invariant_is_becoming_slower
        - "summary" -> get_summary_stats
        - default: get_summary_stats
        """
        q = question.lower().strip()

        if "fails most often" in q:
            return {"answer": self.which_invariant_fails_most_often()}
        elif "becoming unstable" in q or "unstable" in q:
            return {"answer": self.which_module_is_becoming_unstable()}
        elif "regression" in q or "introduced" in q:
            return {"answer": self.which_patch_introduced_regressions()}
        elif "reliability improved" in q:
            return {"answer": self.has_reliability_improved()}
        elif "becoming slower" in q or "slower" in q:
            return {"answer": self.which_invariant_is_becoming_slower()}
        elif "summary" in q or "stats" in q or "overview" in q:
            return {"answer": self.get_summary_stats()}
        elif "timeline" in q or "recent" in q:
            return {"answer": self.get_execution_timeline()}
        elif "module health" in q or "module" in q:
            return {"answer": self.get_module_health_all()}
        elif "stability history" in q or "stability" in q:
            return {"answer": self.get_stability_history()}
        else:
            # Default: return summary
            return {
                "answer": self.get_summary_stats(),
                "note": f"Could not map question '{question}' to a specific query. Returning summary.",
            }
