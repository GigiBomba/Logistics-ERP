"""
Invariant History — Trend Analysis Engine

Computes trends from execution history for visualization and stability scoring.
Every public method on TrendEngine returns structured TrendResult or list[dict]
suitable for chart rendering, dashboards, and downstream scoring.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from invariant_history.models import (
    TrendPoint,
    TrendResult,
    HistoryExecutionRecord,
    HistoryQuery,
)
from invariant_history.storage import HistoryStorage


class TrendEngine:
    """Trend analysis engine that computes trends from execution history.

    Uses the storage layer to fetch historical execution records, then
    computes aggregated metrics, points, and trend direction indicators.
    """

    def __init__(self, storage: HistoryStorage) -> None:
        self.storage = storage

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_trend_result(
        metric: str,
        points: list[TrendPoint],
        higher_is_better: bool = True,
    ) -> TrendResult:
        """Build a TrendResult with computed stats, direction, and change %.

        Splits the sorted points into first-half / second-half and compares
        their averages to determine whether the metric is improving, degrading,
        or stable.
        """
        if not points:
            return TrendResult(
                metric=metric,
                points=[],
                period_start="",
                period_end="",
                sample_count=0,
            )

        # Sort by timestamp ascending
        sorted_points = sorted(points, key=lambda p: p.timestamp)
        values = [p.value for p in sorted_points]

        min_value = min(values)
        max_value = max(values)
        avg_value = sum(values) / len(values)

        # Split into first and second halves
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]

        if not first_half or not second_half:
            # Too few points for a meaningful comparison
            return TrendResult(
                metric=metric,
                points=sorted_points,
                period_start=sorted_points[0].timestamp,
                period_end=sorted_points[-1].timestamp,
                sample_count=len(sorted_points),
                min_value=min_value,
                max_value=max_value,
                avg_value=avg_value,
                trend_direction="stable",
                change_pct=0.0,
            )

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        # Percentage change
        if first_avg != 0:
            change_pct = ((second_avg - first_avg) / abs(first_avg)) * 100.0
        else:
            change_pct = 100.0 if second_avg != 0 else 0.0

        # Trend direction (1 % threshold for stability)
        threshold = 0.01
        if first_avg != 0:
            ratio = second_avg / abs(first_avg)
        else:
            ratio = 1.0 if second_avg == 0 else float("inf")

        if higher_is_better:
            if ratio > 1.0 + threshold:
                trend_direction = "improving"
            elif ratio < 1.0 - threshold:
                trend_direction = "degrading"
            else:
                trend_direction = "stable"
        else:
            # Lower-is-better metrics (failures, execution time)
            if ratio < 1.0 - threshold:
                trend_direction = "improving"
            elif ratio > 1.0 + threshold:
                trend_direction = "degrading"
            else:
                trend_direction = "stable"

        return TrendResult(
            metric=metric,
            points=sorted_points,
            period_start=sorted_points[0].timestamp,
            period_end=sorted_points[-1].timestamp,
            sample_count=len(sorted_points),
            min_value=min_value,
            max_value=max_value,
            avg_value=round(avg_value, 4),
            trend_direction=trend_direction,
            change_pct=round(change_pct, 2),
        )

    # ------------------------------------------------------------------
    # Per-execution trends
    # ------------------------------------------------------------------

    def pass_rate_over_time(self, limit: int = 30) -> TrendResult:
        """Pass rate percentage for each of the last *limit* executions."""
        records = self.storage.get_all_executions(limit=limit)
        points: list[TrendPoint] = []
        for rec in records:
            total = rec.total_invariants or 1
            pass_rate = (rec.passed / total) * 100.0
            points.append(
                TrendPoint(
                    label=rec.execution_id,
                    value=round(pass_rate, 2),
                    timestamp=rec.timestamp,
                    metadata={"execution_id": rec.execution_id},
                )
            )
        return self._compute_trend_result("pass_rate", points, higher_is_better=True)

    def critical_failures_over_time(self, limit: int = 30) -> TrendResult:
        """Count of critical failures for each of the last *limit* executions."""
        records = self.storage.get_all_executions(limit=limit)
        points: list[TrendPoint] = []
        for rec in records:
            points.append(
                TrendPoint(
                    label=rec.execution_id,
                    value=float(rec.critical_failures),
                    timestamp=rec.timestamp,
                    metadata={"execution_id": rec.execution_id},
                )
            )
        return self._compute_trend_result(
            "critical_failures", points, higher_is_better=False
        )

    def execution_time_over_time(self, limit: int = 30) -> TrendResult:
        """Average execution duration (ms) for each of the last *limit* executions."""
        records = self.storage.get_all_executions(limit=limit)
        points: list[TrendPoint] = []
        for rec in records:
            points.append(
                TrendPoint(
                    label=rec.execution_id,
                    value=rec.execution_duration_ms,
                    timestamp=rec.timestamp,
                    metadata={"execution_id": rec.execution_id},
                )
            )
        return self._compute_trend_result(
            "execution_time_ms", points, higher_is_better=False
        )

    # ------------------------------------------------------------------
    # Invariant ranking
    # ------------------------------------------------------------------

    def slowest_invariants(self, limit: int = 20) -> list[dict]:
        """Rank invariants by average execution time (descending)."""
        records = self.storage.get_all_executions(limit=1000)

        # Aggregate execution times per invariant
        agg: dict[str, dict[str, Any]] = {}
        for rec in records:
            for inv in rec.invariants:
                data = agg.get(inv.invariant_id)
                if data is None:
                    data = {
                        "invariant_id": inv.invariant_id,
                        "title": inv.title,
                        "category": inv.category,
                        "module": inv.module,
                        "severity": inv.severity,
                        "execution_times": [],
                        "execution_count": 0,
                    }
                    agg[inv.invariant_id] = data
                data["execution_times"].append(inv.execution_time_ms)
                data["execution_count"] += 1

        result: list[dict[str, Any]] = []
        for inv_id, data in agg.items():
            times = data["execution_times"]
            avg_time = sum(times) / len(times) if times else 0.0
            result.append(
                {
                    "invariant_id": inv_id,
                    "title": data["title"],
                    "category": data["category"],
                    "module": data["module"],
                    "severity": data["severity"],
                    "avg_execution_time_ms": round(avg_time, 2),
                    "max_execution_time_ms": round(max(times), 2),
                    "execution_count": data["execution_count"],
                }
            )

        result.sort(key=lambda x: x["avg_execution_time_ms"], reverse=True)
        return result[:limit]

    def most_failing_invariants(self, limit: int = 20) -> list[dict]:
        """Rank invariants by failure count, with last failure and avg interval."""
        records = self.storage.get_all_executions(limit=1000)

        # Aggregate failures per invariant
        agg: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "invariant_id": "",
                "title": "",
                "category": "",
                "module": "",
                "severity": "",
                "failure_count": 0,
                "failure_timestamps": [],
                "total_executions": 0,
            }
        )

        for rec in records:
            for inv in rec.invariants:
                key = inv.invariant_id
                entry = agg[key]
                if not entry["invariant_id"]:
                    entry.update(
                        {
                            "invariant_id": inv.invariant_id,
                            "title": inv.title,
                            "category": inv.category,
                            "module": inv.module,
                            "severity": inv.severity,
                        }
                    )
                entry["total_executions"] += 1
                if inv.result == "fail":
                    entry["failure_count"] += 1
                    entry["failure_timestamps"].append(rec.timestamp)

        result: list[dict[str, Any]] = []
        for inv_id, data in agg.items():
            if data["failure_count"] == 0:
                continue

            timestamps = sorted(data["failure_timestamps"])

            # Compute average interval between failures (in hours)
            intervals: list[float] = []
            for i in range(1, len(timestamps)):
                try:
                    t1 = datetime.fromisoformat(timestamps[i - 1])
                    t2 = datetime.fromisoformat(timestamps[i])
                    intervals.append((t2 - t1).total_seconds() / 3600.0)
                except (ValueError, TypeError):
                    pass
            avg_interval_hours = (
                sum(intervals) / len(intervals) if intervals else 0.0
            )

            total = data["total_executions"]
            result.append(
                {
                    "invariant_id": inv_id,
                    "title": data["title"],
                    "category": data["category"],
                    "module": data["module"],
                    "severity": data["severity"],
                    "failure_count": data["failure_count"],
                    "last_failure": timestamps[-1] if timestamps else "",
                    "avg_failure_interval_hours": round(avg_interval_hours, 2),
                    "total_executions": total,
                    "failure_rate": round(
                        (data["failure_count"] / total) * 100.0, 2
                    )
                    if total
                    else 0.0,
                }
            )

        result.sort(key=lambda x: x["failure_count"], reverse=True)
        return result[:limit]

    # ------------------------------------------------------------------
    # Module / invariant-specific trends
    # ------------------------------------------------------------------

    def module_reliability_over_time(
        self, module: str, limit: int = 30
    ) -> TrendResult:
        """Reliability trend (% pass) for a specific module over time."""
        records = self.storage.get_all_executions(limit=limit)
        points: list[TrendPoint] = []
        for rec in records:
            module_invs = [inv for inv in rec.invariants if inv.module == module]
            if not module_invs:
                continue
            passed = sum(1 for inv in module_invs if inv.result == "pass")
            total = len(module_invs)
            reliability = (passed / total) * 100.0 if total else 0.0
            points.append(
                TrendPoint(
                    label=rec.execution_id,
                    value=round(reliability, 2),
                    timestamp=rec.timestamp,
                    metadata={
                        "execution_id": rec.execution_id,
                        "module": module,
                        "passed": passed,
                        "total": total,
                    },
                )
            )
        return self._compute_trend_result(
            f"module_reliability_{module}", points, higher_is_better=True
        )

    def invariant_trend(
        self, invariant_id: str, limit: int = 50
    ) -> TrendResult:
        """Pass/fail timeline (1.0 / 0.0) for a specific invariant."""
        records = self.storage.get_executions_for_invariant(
            invariant_id, limit=limit
        )
        points: list[TrendPoint] = []
        for rec in records:
            for inv in rec.invariants:
                if inv.invariant_id == invariant_id:
                    value = 1.0 if inv.result == "pass" else 0.0
                    points.append(
                        TrendPoint(
                            label=rec.execution_id,
                            value=value,
                            timestamp=rec.timestamp,
                            metadata={
                                "execution_id": rec.execution_id,
                                "result": inv.result,
                                "execution_time_ms": inv.execution_time_ms,
                                "failure_reason": inv.failure_reason,
                            },
                        )
                    )
                    break
        return self._compute_trend_result(
            f"invariant_{invariant_id}", points, higher_is_better=True
        )

    def execution_time_trend_for_invariant(
        self, invariant_id: str, limit: int = 50
    ) -> TrendResult:
        """Execution time trend (ms) for a specific invariant."""
        records = self.storage.get_executions_for_invariant(
            invariant_id, limit=limit
        )
        points: list[TrendPoint] = []
        for rec in records:
            for inv in rec.invariants:
                if inv.invariant_id == invariant_id:
                    points.append(
                        TrendPoint(
                            label=rec.execution_id,
                            value=inv.execution_time_ms,
                            timestamp=rec.timestamp,
                            metadata={
                                "execution_id": rec.execution_id,
                                "result": inv.result,
                            },
                        )
                    )
                    break
        return self._compute_trend_result(
            f"exec_time_{invariant_id}", points, higher_is_better=False
        )
