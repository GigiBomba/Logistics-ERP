"""
Invariant History — Dashboard Builder

Builds complete dashboard data structures for visualization.
This is the main integration point for Operion Ops Console, Grafana dashboards,
Prometheus metrics, and custom visualizations.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import Any

from invariant_history.models import (
    DashboardData,
    HistoryExecutionRecord,
    HistoryQuery,
    ModuleReliability,
    RegressionReport,
    StabilityIndex,
    TrendPoint,
    TrendResult,
)
from invariant_history.storage import HistoryStorage
from invariant_history.trends import TrendEngine
from invariant_history.stability import StabilityScorer
from invariant_history.regression import RegressionDetector


class DashboardBuilder:
    """
    Builds complete dashboard data for visualization.

    This is the main integration point for:
    - Operion Ops Console
    - Grafana dashboards
    - Prometheus metrics
    - Custom visualizations
    """

    def __init__(self, storage: HistoryStorage) -> None:
        self._storage = storage
        self._trends = TrendEngine(storage)
        self._stability = StabilityScorer()
        self._regression = RegressionDetector(storage, self._trends)

    # ── Main Dashboard ───────────────────────────────────

    def build_dashboard(self, period_days: int = 30) -> DashboardData:
        """
        Build complete dashboard data including:
        - Stability index
        - Pass rate, critical failures, execution time trends
        - Slowest and most failing invariants
        - Module reliability rankings
        - Top stable/unstable modules
        - Recent regressions
        """
        since = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
        executions = self._storage.get_executions_since(since, limit=500)
        execution_count = len(executions)

        # Stability index
        stability = self._stability.compute(
            self._storage, period_days, executions=executions,
        )

        # Trends
        pass_rate_trend = self._trends.pass_rate_trend(
            period_days=period_days, executions=executions,
        )
        critical_failures_trend = self._trends.critical_failures_trend(
            period_days=period_days, executions=executions,
        )
        execution_time_trend = self._trends.execution_time_trend(
            period_days=period_days, executions=executions,
        )

        # Slowest and most failing invariants
        slowest_invariants = self._compute_slowest_invariants(executions)
        most_failing_invariants = self._compute_most_failing_invariants(executions)

        # Module reliability rankings
        module_reliabilities = self._stability.calculate_module_reliabilities(
            self._storage, period_days=period_days, executions=executions,
        )

        # Recent regressions
        recent_regressions = self._regression.detect_regressions(limit=period_days)

        # Top stable / unstable modules
        top_stable = self.get_top_stable_modules(module_reliabilities)
        top_unstable = self.get_top_unstable_modules(module_reliabilities)

        # Last execution
        last_execution = self._storage.get_last_execution()

        return DashboardData(
            stability=stability,
            pass_rate_trend=pass_rate_trend,
            critical_failures_trend=critical_failures_trend,
            execution_time_trend=execution_time_trend,
            slowest_invariants=slowest_invariants,
            most_failing_invariants=most_failing_invariants,
            module_reliabilities=module_reliabilities,
            recent_regressions=recent_regressions,
            top_stable_modules=top_stable,
            top_unstable_modules=top_unstable,
            last_execution=last_execution,
            execution_count=execution_count,
            period_days=period_days,
        )

    # ── Prometheus Metrics ───────────────────────────────

    def get_series_for_prometheus(self, period_days: int = 30) -> dict[str, list]:
        """
        Return metrics suitable for Prometheus exposition.

        Keys are metric names following Prometheus naming conventions:
        - operion_invariant_pass_rate
        - operion_invariant_critical_failures
        - operion_invariant_execution_time_ms
        - operion_invariant_stability_index
        - operion_invariant_module_reliability{module="trips"}
        """
        since = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
        executions = self._storage.get_executions_since(since, limit=500)

        # Sort chronologically
        executions.sort(key=lambda e: e.timestamp)

        series: dict[str, list] = {
            "operion_invariant_pass_rate": [],
            "operion_invariant_critical_failures": [],
            "operion_invariant_execution_time_ms": [],
            "operion_invariant_stability_index": [],
            "operion_invariant_module_reliability": [],
        }

        for exec_rec in executions:
            ts = self._to_unix_timestamp(exec_rec.timestamp)
            total = max(exec_rec.total_invariants, 1)

            pass_rate = round((exec_rec.passed / total) * 100, 2)
            series["operion_invariant_pass_rate"].append({
                "value": pass_rate,
                "timestamp": ts,
                "labels": {"execution_id": exec_rec.execution_id},
            })

            series["operion_invariant_critical_failures"].append({
                "value": exec_rec.critical_failures,
                "timestamp": ts,
                "labels": {"execution_id": exec_rec.execution_id},
            })

            series["operion_invariant_execution_time_ms"].append({
                "value": exec_rec.execution_duration_ms,
                "timestamp": ts,
                "labels": {"execution_id": exec_rec.execution_id},
            })

        # Stability index as a single gauge
        stability = self._stability.compute(
            self._storage, period_days, executions=executions,
        )
        now_ts = self._to_unix_timestamp(datetime.utcnow().isoformat())
        series["operion_invariant_stability_index"].append({
            "value": round(stability.score, 2),
            "timestamp": now_ts,
            "labels": {"period_days": str(period_days)},
        })

        # Module reliability — one entry per module with module label
        modules = self._stability.calculate_module_reliabilities(
            self._storage, period_days=period_days, executions=executions,
        )
        for mod in modules:
            series["operion_invariant_module_reliability"].append({
                "value": round(mod.reliability_pct, 2),
                "timestamp": now_ts,
                "labels": {
                    "module": mod.module,
                    "trend": mod.trend,
                },
            })

        return series

    # ── Module Rankings ──────────────────────────────────

    def get_top_stable_modules(
        self, modules: list[ModuleReliability], n: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top N most reliable modules."""
        sorted_modules = sorted(
            modules, key=lambda m: m.reliability_pct, reverse=True,
        )
        return [
            {
                "module": m.module,
                "reliability_pct": round(m.reliability_pct, 1),
                "total_invariants": m.total_invariants,
                "passed": m.passed,
                "failed": m.failed,
                "trend": m.trend,
                "avg_execution_time_ms": round(m.avg_execution_time_ms, 1),
            }
            for m in sorted_modules[:n]
        ]

    def get_top_unstable_modules(
        self, modules: list[ModuleReliability], n: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top N least reliable modules."""
        sorted_modules = sorted(
            modules, key=lambda m: m.reliability_pct,
        )
        return [
            {
                "module": m.module,
                "reliability_pct": round(m.reliability_pct, 1),
                "total_invariants": m.total_invariants,
                "passed": m.passed,
                "failed": m.failed,
                "trend": m.trend,
                "avg_execution_time_ms": round(m.avg_execution_time_ms, 1),
            }
            for m in sorted_modules[:n]
        ]

    # ── Internal Computations ────────────────────────────

    def _compute_slowest_invariants(
        self, executions: list[HistoryExecutionRecord],
    ) -> list[dict[str, Any]]:
        """
        Find the slowest invariants across all executions.

        Returns invariants sorted by average execution time descending.
        """
        inv_times: dict[str, list[float]] = {}
        inv_meta: dict[str, dict[str, Any]] = {}

        for exec_rec in executions:
            for inv in exec_rec.invariants:
                inv_id = inv.invariant_id
                if inv_id not in inv_times:
                    inv_times[inv_id] = []
                    inv_meta[inv_id] = {
                        "invariant_id": inv_id,
                        "title": inv.title,
                        "module": inv.module or "unknown",
                        "category": inv.category,
                    }
                inv_times[inv_id].append(inv.execution_time_ms)

        result = []
        for inv_id, times in inv_times.items():
            avg_time = statistics.mean(times)
            max_time = max(times)
            result.append({
                **inv_meta[inv_id],
                "avg_execution_time_ms": round(avg_time, 1),
                "max_execution_time_ms": round(max_time, 1),
                "sample_count": len(times),
            })

        result.sort(key=lambda x: x["avg_execution_time_ms"], reverse=True)
        return result

    def _compute_most_failing_invariants(
        self, executions: list[HistoryExecutionRecord],
    ) -> list[dict[str, Any]]:
        """
        Find invariants that fail most frequently.

        Returns invariants sorted by failure count descending.
        """
        fail_counts: dict[str, int] = {}
        inv_meta: dict[str, dict[str, Any]] = {}

        for exec_rec in executions:
            for inv in exec_rec.invariants:
                inv_id = inv.invariant_id
                if inv_id not in fail_counts:
                    fail_counts[inv_id] = 0
                    inv_meta[inv_id] = {
                        "invariant_id": inv_id,
                        "title": inv.title,
                        "module": inv.module or "unknown",
                        "severity": inv.severity,
                        "category": inv.category,
                    }
                if inv.result == "fail":
                    fail_counts[inv_id] += 1

        # Filter to only those with failures
        result = []
        for inv_id, count in fail_counts.items():
            if count == 0:
                continue
            # Count total executions for this invariant
            total = sum(
                1 for e in executions
                for i in e.invariants
                if i.invariant_id == inv_id
            )
            fail_rate = (count / max(total, 1)) * 100
            result.append({
                **inv_meta[inv_id],
                "fail_count": count,
                "total_executions": total,
                "fail_rate_pct": round(fail_rate, 1),
            })

        result.sort(key=lambda x: x["fail_count"], reverse=True)
        return result

    @staticmethod
    def _to_unix_timestamp(iso_timestamp: str) -> float:
        """Convert an ISO-8601 timestamp to a Unix timestamp (seconds)."""
        try:
            dt = datetime.fromisoformat(iso_timestamp)
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0
