"""
Invariant History — Stability Scoring Engine

Computes a global **StabilityIndex** (0‑100) and per‑module **ModuleReliability**
scores by combining pass rates, critical failures, execution times, module
reliabilities, and pass‑to‑fail regressions.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from invariant_history.models import (
    StabilityIndex,
    ModuleReliability,
    HistoryExecutionRecord,
)
from invariant_history.storage import HistoryStorage
from invariant_history.trends import TrendEngine


class StabilityScorer:
    """Stability scoring engine for the invariant system.

    Combines trend data from a ``TrendEngine`` with raw storage queries to
    produce a holistic stability picture.
    """

    def __init__(self, storage: HistoryStorage, trends: TrendEngine) -> None:
        self.storage = storage
        self.trends = trends

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_stability_index(self, limit: int = 30) -> StabilityIndex:
        """Compute a global stability score (0‑100) over the last *limit* executions.

        Weighting
        ---------
        pass_rate_score         35 %   — proportional to overall pass rate
        critical_failure_score  20 %   — full score when zero critical failures
        execution_time_score    10 %   — full score when average ≤ 1 s
        module_reliability_score 25 %  — proportional to average module reliability
        regression_score        10 %   — penalised per pass‑to‑fail regression
        """
        records = self.storage.get_all_executions(limit=limit)
        if not records:
            return StabilityIndex(
                score=0.0,
                pass_rate=0.0,
                critical_failure_rate=0.0,
                avg_execution_time_ms=0.0,
                module_reliability_avg=0.0,
                regression_count=0,
                sample_size=0,
                period_start="",
                period_end="",
                modules=[],
            )

        sorted_records = sorted(records, key=lambda r: r.timestamp)
        total_invariants = sum(r.total_invariants for r in sorted_records)
        total_passed = sum(r.passed for r in sorted_records)
        total_critical = sum(r.critical_failures for r in sorted_records)
        total_exec_time = sum(r.execution_duration_ms for r in sorted_records)
        exec_count = len(sorted_records)

        overall_pass_rate = (
            (total_passed / total_invariants) * 100.0 if total_invariants else 0.0
        )
        avg_exec_time = total_exec_time / exec_count if exec_count else 0.0

        # -- Component scores ------------------------------------------

        # 1. Pass rate (35 %)
        pass_rate_score = (overall_pass_rate / 100.0) * 35.0

        # 2. Critical failures (20 %)
        if total_critical == 0:
            critical_failure_score = 20.0
        else:
            critical_ratio = total_critical / max(1, total_invariants)
            critical_failure_score = 20.0 * (1.0 - min(1.0, critical_ratio))

        # 3. Execution time (10 %) – threshold = 1000 ms
        exec_threshold = 1000.0
        if avg_exec_time <= exec_threshold:
            execution_time_score = 10.0
        else:
            execution_time_score = max(
                0.0, 10.0 * (exec_threshold / max(1.0, avg_exec_time))
            )

        # 4. Module reliability (25 %)
        module_reliabilities = self.compute_all_module_reliabilities(limit=limit)
        avg_module_reliability = (
            sum(m.reliability_pct for m in module_reliabilities)
            / max(1, len(module_reliabilities))
        )
        module_reliability_score = (avg_module_reliability / 100.0) * 25.0

        # 5. Regressions (10 %)
        regression_count = self._count_regressions(sorted_records)
        regression_score = max(0.0, 10.0 - float(regression_count))

        # -- Total ----------------------------------------------------
        total_score = (
            pass_rate_score
            + critical_failure_score
            + execution_time_score
            + module_reliability_score
            + regression_score
        )

        critical_failure_rate = (
            (total_critical / max(1, total_invariants)) * 100.0
        )

        return StabilityIndex(
            score=round(total_score, 2),
            pass_rate=round(overall_pass_rate, 2),
            critical_failure_rate=round(critical_failure_rate, 2),
            avg_execution_time_ms=round(avg_exec_time, 2),
            module_reliability_avg=round(avg_module_reliability, 2),
            regression_count=regression_count,
            sample_size=exec_count,
            period_start=sorted_records[0].timestamp,
            period_end=sorted_records[-1].timestamp,
            modules=module_reliabilities,
        )

    def compute_module_reliabilities(
        self, limit: int = 30
    ) -> list[ModuleReliability]:
        """Compute reliability for every module (delegates to
        :meth:`compute_all_module_reliabilities`)."""
        return self.compute_all_module_reliabilities(limit=limit)

    def compute_all_module_reliabilities(
        self, limit: int = 30
    ) -> list[ModuleReliability]:
        """Compute reliability for every module present in the last *limit* executions.

        For each module the following is calculated:

        * ``reliability_pct`` — (passed / total_invariants) × 100
        * ``total_executions`` — number of times this module appeared
        * ``total_invariants`` — number of invariant evaluations
        * ``passed`` / ``failed`` — breakdown
        * ``trend`` — improving / degrading / stable
        * ``last_failure`` — ISO‑timestamp of the most recent failure
        """
        records = self.storage.get_all_executions(limit=limit)
        if not records:
            return []

        # Aggregate per module
        module_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total_invariants": 0,
                "passed": 0,
                "failed": 0,
                "last_failure": None,
                "execution_count": 0,
                "execution_times": [],
            }
        )

        for rec in records:
            for inv in rec.invariants:
                mod = inv.module or "unknown"
                entry = module_data[mod]
                entry["total_invariants"] += 1
                entry["execution_count"] += 1
                entry["execution_times"].append(inv.execution_time_ms)
                if inv.result == "pass":
                    entry["passed"] += 1
                else:
                    entry["failed"] += 1
                    if entry["last_failure"] is None or rec.timestamp > entry["last_failure"]:
                        entry["last_failure"] = rec.timestamp

        results: list[ModuleReliability] = []
        for mod, data in module_data.items():
            total = data["total_invariants"]
            passed = data["passed"]
            failed = data["failed"]
            reliability = (passed / total * 100.0) if total else 0.0
            trend = self._compute_trend(mod, limit)
            times = data["execution_times"]
            avg_time = sum(times) / len(times) if times else 0.0

            results.append(
                ModuleReliability(
                    module=mod,
                    reliability_pct=round(reliability, 2),
                    total_executions=data["execution_count"],
                    total_invariants=total,
                    passed=passed,
                    failed=failed,
                    trend=trend,
                    last_failure=data["last_failure"],
                    avg_execution_time_ms=round(avg_time, 2),
                )
            )

        results.sort(key=lambda m: m.reliability_pct)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_regressions(
        records: list[HistoryExecutionRecord],
    ) -> int:
        """Count pass‑to‑fail regressions across consecutive executions.

        An invariant is counted as a regression when it passed in one
        execution and fails in the *next* (temporally adjacent) execution.
        """
        if len(records) < 2:
            return 0

        count = 0
        for i in range(1, len(records)):
            prev = records[i - 1]
            curr = records[i]

            prev_pass_ids: set[str] = set()
            for inv in prev.invariants:
                if inv.result == "pass":
                    prev_pass_ids.add(inv.invariant_id)

            for inv in curr.invariants:
                if inv.result == "fail" and inv.invariant_id in prev_pass_ids:
                    count += 1

        return count

    def _compute_trend(self, module: str, limit: int) -> str:
        """Compare recent vs. older pass rates to determine the trend direction.

        Returns ``"improving"``, ``"degrading"``, or ``"stable"`` by delegating
        to the ``TrendEngine.module_reliability_over_time`` method.
        """
        try:
            trend_result = self.trends.module_reliability_over_time(
                module, limit=limit
            )
            return trend_result.trend_direction
        except Exception:
            return "stable"
