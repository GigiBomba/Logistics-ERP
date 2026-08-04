"""
Invariant History — Regression Detection Engine

Detects regressions across invariant executions by analyzing pass/fail transitions,
execution time spikes, module reliability changes, and anomalous executions.
"""

from __future__ import annotations

import statistics
from typing import Any

from invariant_history.models import (
    HistoryExecutionRecord,
    HistoryInvariantRecord,
    HistoryQuery,
    RegressionReport,
)
from invariant_history.storage import HistoryStorage
from invariant_history.trends import TrendEngine


class RegressionDetector:
    """Detects regressions and anomalies across invariant executions."""

    def __init__(self, storage: HistoryStorage, trends: TrendEngine) -> None:
        self._storage = storage
        self._trends = trends

    # ── Public API ────────────────────────────────────────

    def detect_regressions(self, limit: int = 30) -> RegressionReport:
        """
        Detect regressions across the last N executions.

        Checks:
        1. pass_to_fail: invariants that changed from PASS to FAIL
        2. execution_time_spikes: invariants where execution time doubled
        3. reliability_decreases: modules where reliability dropped >5%
        4. new_failures: invariants that never failed before but are now failing
        """
        executions = self._storage.query(HistoryQuery(limit=limit)).items
        if len(executions) < 2:
            return RegressionReport()

        # Sort chronologically (oldest first)
        executions.sort(key=lambda e: e.timestamp)
        current = executions[-1]   # most recent
        previous = executions[-2]  # immediate predecessor

        # Build lookup maps
        previous_map: dict[str, HistoryInvariantRecord] = {
            inv.invariant_id: inv for inv in previous.invariants
        }
        current_map: dict[str, HistoryInvariantRecord] = {
            inv.invariant_id: inv for inv in current.invariants
        }

        pass_to_fail: list[dict[str, Any]] = []
        execution_time_spikes: list[dict[str, Any]] = []

        for inv_id, prev_inv in previous_map.items():
            if inv_id not in current_map:
                continue
            curr_inv = current_map[inv_id]

            # 1. pass_to_fail
            if prev_inv.result in ("pass", "") and curr_inv.result == "fail":
                pass_to_fail.append({
                    "invariant_id": inv_id,
                    "title": curr_inv.title,
                    "module": curr_inv.module or "unknown",
                    "severity": curr_inv.severity,
                    "previous_result": prev_inv.result,
                    "current_result": curr_inv.result,
                    "failure_reason": curr_inv.failure_reason or "",
                })

            # 2. execution_time_spikes (doubled)
            if (
                prev_inv.execution_time_ms > 0
                and curr_inv.execution_time_ms > prev_inv.execution_time_ms * 2
            ):
                execution_time_spikes.append({
                    "invariant_id": inv_id,
                    "title": curr_inv.title,
                    "module": curr_inv.module or "unknown",
                    "previous_time_ms": round(prev_inv.execution_time_ms, 1),
                    "current_time_ms": round(curr_inv.execution_time_ms, 1),
                    "increase_pct": round(
                        (curr_inv.execution_time_ms / prev_inv.execution_time_ms - 1) * 100, 1
                    ),
                })

        # 3. reliability_decreases (>5% drop per module)
        reliability_decreases = self._compute_module_reliability_change(previous, current)

        # 4. new_failures: never failed in any prior execution
        new_failures: list[dict[str, Any]] = []
        for inv in current.invariants:
            if inv.result != "fail":
                continue
            ever_failed = False
            for prev_exec in executions[:-1]:
                for prev_inv in prev_exec.invariants:
                    if prev_inv.invariant_id == inv.invariant_id and prev_inv.result == "fail":
                        ever_failed = True
                        break
                if ever_failed:
                    break
            if not ever_failed:
                new_failures.append({
                    "invariant_id": inv.invariant_id,
                    "title": inv.title,
                    "module": inv.module or "unknown",
                    "severity": inv.severity,
                    "failure_reason": inv.failure_reason or "",
                })

        return RegressionReport(
            new_failures=new_failures,
            pass_to_fail=pass_to_fail,
            execution_time_spikes=execution_time_spikes,
            reliability_decreases=reliability_decreases,
        )

    def compare_executions(
        self, baseline_id: str, target_id: str
    ) -> RegressionReport:
        """
        Compare two specific executions.

        Returns list of:
        - new_failures: fails in target that passed in baseline
        - pass_to_fail: same as new_failures (duplicated for clarity)
        - execution_time_spikes: time increased >100%
        - new_invariants: present in target but not baseline
        - removed_invariants: present in baseline but not target
        """
        baseline = self._storage.get_execution(baseline_id)
        target = self._storage.get_execution(target_id)

        if baseline is None:
            raise ValueError(f"Baseline execution not found: {baseline_id}")
        if target is None:
            raise ValueError(f"Target execution not found: {target_id}")

        baseline_map: dict[str, HistoryInvariantRecord] = {
            inv.invariant_id: inv for inv in baseline.invariants
        }
        target_map: dict[str, HistoryInvariantRecord] = {
            inv.invariant_id: inv for inv in target.invariants
        }

        baseline_ids = set(baseline_map.keys())
        target_ids = set(target_map.keys())

        new_invariants = sorted(target_ids - baseline_ids)
        removed_invariants = sorted(baseline_ids - target_ids)

        pass_to_fail: list[dict[str, Any]] = []
        execution_time_spikes: list[dict[str, Any]] = []

        for inv_id in baseline_ids & target_ids:
            b_inv = baseline_map[inv_id]
            t_inv = target_map[inv_id]

            # new_failures / pass_to_fail
            if b_inv.result in ("pass", "") and t_inv.result == "fail":
                entry = {
                    "invariant_id": inv_id,
                    "title": t_inv.title,
                    "module": t_inv.module or "unknown",
                    "severity": t_inv.severity,
                    "baseline_result": b_inv.result,
                    "target_result": t_inv.result,
                    "failure_reason": t_inv.failure_reason or "",
                }
                pass_to_fail.append(entry)

            # execution_time_spikes
            if (
                b_inv.execution_time_ms > 0
                and t_inv.execution_time_ms > b_inv.execution_time_ms * 2
            ):
                execution_time_spikes.append({
                    "invariant_id": inv_id,
                    "title": t_inv.title,
                    "module": t_inv.module or "unknown",
                    "baseline_time_ms": round(b_inv.execution_time_ms, 1),
                    "target_time_ms": round(t_inv.execution_time_ms, 1),
                    "increase_pct": round(
                        (t_inv.execution_time_ms / b_inv.execution_time_ms - 1) * 100, 1
                    ),
                })

        # reliability_decreases
        reliability_decreases = self._compute_module_reliability_change(baseline, target)

        return RegressionReport(
            new_failures=pass_to_fail,  # same content as pass_to_fail per spec
            pass_to_fail=pass_to_fail,
            execution_time_spikes=execution_time_spikes,
            reliability_decreases=reliability_decreases,
            new_invariants=new_invariants,
            removed_invariants=removed_invariants,
        )

    def detect_anomalous_executions(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Flag executions that are anomalous:
        - Pass rate dropped >10% below rolling average
        - Execution time >2x rolling average
        - Critical failures >3x rolling average
        """
        executions = self._storage.query(HistoryQuery(limit=limit)).items
        if len(executions) < 5:
            return []

        executions.sort(key=lambda e: e.timestamp)

        pass_rates = [
            e.passed / max(e.total_invariants, 1) * 100 for e in executions
        ]
        exec_times = [e.execution_duration_ms for e in executions]
        critical_counts = [e.critical_failures for e in executions]

        avg_pass_rate = statistics.mean(pass_rates)
        avg_exec_time = statistics.mean(exec_times)
        avg_critical = statistics.mean(critical_counts)

        anomalous: list[dict[str, Any]] = []

        for e in executions:
            pass_rate = e.passed / max(e.total_invariants, 1) * 100
            reasons: list[str] = []

            if avg_pass_rate > 0 and pass_rate < avg_pass_rate * 0.9:
                drop = round(avg_pass_rate - pass_rate, 1)
                reasons.append(
                    f"pass_rate_dropped_{drop}pct "
                    f"(actual={pass_rate:.1f}%, avg={avg_pass_rate:.1f}%)"
                )

            if avg_exec_time > 0 and e.execution_duration_ms > avg_exec_time * 2:
                ratio = round(e.execution_duration_ms / avg_exec_time, 1)
                reasons.append(
                    f"execution_time_{ratio}x_avg "
                    f"(actual={e.execution_duration_ms:.0f}ms, avg={avg_exec_time:.0f}ms)"
                )

            if avg_critical > 0 and e.critical_failures > avg_critical * 3:
                reasons.append(
                    f"critical_failures_{e.critical_failures}_vs_avg_{avg_critical:.1f}"
                )

            if reasons:
                anomalous.append({
                    "execution_id": e.execution_id,
                    "timestamp": e.timestamp,
                    "pass_rate": round(pass_rate, 1),
                    "execution_duration_ms": e.execution_duration_ms,
                    "critical_failures": e.critical_failures,
                    "total_invariants": e.total_invariants,
                    "failed": e.failed,
                    "reasons": reasons,
                    "anomaly_score": len(reasons),
                })

        return anomalous

    # ── Internal Helpers ────────────────────────────────

    def _compute_module_reliability_change(
        self,
        baseline: HistoryExecutionRecord,
        target: HistoryExecutionRecord,
    ) -> list[dict[str, Any]]:
        """
        Compute reliability changes per module between two executions.

        Returns entries where reliability dropped more than 5%.
        """
        def _module_stats(record: HistoryExecutionRecord) -> dict[str, dict[str, int]]:
            stats: dict[str, dict[str, int]] = {}
            for inv in record.invariants:
                mod = inv.module or "unknown"
                if mod not in stats:
                    stats[mod] = {"passed": 0, "failed": 0, "total": 0}
                stats[mod]["total"] += 1
                if inv.result == "pass":
                    stats[mod]["passed"] += 1
                else:
                    stats[mod]["failed"] += 1
            return stats

        b_stats = _module_stats(baseline)
        t_stats = _module_stats(target)

        all_modules = set(b_stats.keys()) | set(t_stats.keys())
        decreases: list[dict[str, Any]] = []

        for mod in sorted(all_modules):
            b = b_stats.get(mod, {"passed": 0, "failed": 0, "total": 0})
            t = t_stats.get(mod, {"passed": 0, "failed": 0, "total": 0})

            b_reliability = (b["passed"] / max(b["total"], 1)) * 100
            t_reliability = (t["passed"] / max(t["total"], 1)) * 100
            change = round(t_reliability - b_reliability, 1)

            if change < -5.0:
                decreases.append({
                    "module": mod,
                    "baseline_reliability_pct": round(b_reliability, 1),
                    "target_reliability_pct": round(t_reliability, 1),
                    "change_pct": change,
                    "baseline_passed": b["passed"],
                    "baseline_failed": b["failed"],
                    "target_passed": t["passed"],
                    "target_failed": t["failed"],
                })

        return decreases
