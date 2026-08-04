#!/usr/bin/env python
"""Threshold Calibrator — benchmarks golden workflows and suggests calibrated thresholds.

Usage:
    python scripts/calibrate_thresholds.py
    python scripts/calibrate_thresholds.py --runs 20 --json -o calibration.json
"""

from __future__ import annotations

import json
import os
import sys
import time
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class BenchmarkResult:
    """Result of benchmarking a single workflow."""
    name: str
    measurements_s: list[float] = field(default_factory=list)

    @property
    def min_s(self) -> float:
        return min(self.measurements_s) if self.measurements_s else 0.0

    @property
    def max_s(self) -> float:
        return max(self.measurements_s) if self.measurements_s else 0.0

    @property
    def avg_s(self) -> float:
        return statistics.mean(self.measurements_s) if self.measurements_s else 0.0

    @property
    def p95_s(self) -> float:
        if len(self.measurements_s) < 2:
            return self.avg_s
        sorted_m = sorted(self.measurements_s)
        idx = int(len(sorted_m) * 0.95)
        return sorted_m[min(idx, len(sorted_m) - 1)]

    @property
    def p99_s(self) -> float:
        if len(self.measurements_s) < 2:
            return self.avg_s
        sorted_m = sorted(self.measurements_s)
        idx = int(len(sorted_m) * 0.99)
        return sorted_m[min(idx, len(sorted_m) - 1)]


@dataclass
class ThresholdSuggestion:
    """A suggested threshold value for a workflow."""
    name: str
    current_threshold: float
    measured_p95: float
    suggested_threshold: float
    unit: str = "seconds"
    rationale: str = ""


@dataclass
class CalibrationReport:
    """Complete calibration report."""
    timestamp: str = ""
    benchmarks: list[BenchmarkResult] = field(default_factory=list)
    suggestions: list[ThresholdSuggestion] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class ThresholdCalibrator:
    """Benchmarks workflows and calibrates thresholds."""

    def __init__(self, runs: int = 10):
        self.runs = max(3, runs)
        self.results: list[BenchmarkResult] = []

    def benchmark_workflow(self, name: str, fn: callable) -> BenchmarkResult:
        """Run a workflow function multiple times and record durations."""
        result = BenchmarkResult(name=name)
        for i in range(self.runs):
            start = time.perf_counter()
            try:
                fn()
            except Exception as e:
                print(f"  [WARN] Run {i+1}/{self.runs} failed: {e}", file=sys.stderr)
                continue
            elapsed = time.perf_counter() - start
            result.measurements_s.append(elapsed)
            if i > 0:
                sys.stdout.write(f"\r  {name}: run {i+1}/{self.runs} — {elapsed:.3f}s{' ' * 10}")
                sys.stdout.flush()
        sys.stdout.write(f"\r  {name}: done — p50={result.avg_s:.3f}s p95={result.p95_s:.3f}s{' ' * 20}\n")
        sys.stdout.flush()
        return result

    def run_all(self) -> list[BenchmarkResult]:
        """Benchmark all golden workflows."""
        results = []
        print(f"\nRunning {self.runs} iterations per workflow...\n", file=sys.stderr)

        results.append(self.benchmark_workflow(
            "trip_creation_planned",
            self._benchmark_trip_creation,
        ))
        results.append(self.benchmark_workflow(
            "status_transition",
            self._benchmark_status_transition,
        ))
        results.append(self.benchmark_workflow(
            "invoice_creation",
            self._benchmark_invoice_creation,
        ))
        results.append(self.benchmark_workflow(
            "dispatch_assign",
            self._benchmark_dispatch,
        ))

        self.results = results
        return results

    def _make_db(self):
        """Create a fresh in-memory DB for benchmarking."""
        sys.path.insert(0, str(REPO_ROOT))
        from tests.test_helpers import make_db
        return make_db()

    def _make_env(self, db):
        """Create a WorkflowEnvironment for the given DB."""
        from services.trip_service import TripService
        from services.invoicing.service import InvoiceService
        from services.operations.event_bus import EventBus
        from services.operations.alert_manager import AlertManager
        from services.operations.operations_engine import OperationsEngine
        from tests.workflow_integrity.fixtures.workflow_environment import WorkflowEnvironment

        bus = EventBus()
        if hasattr(bus, "_instance"):
            bus.__class__._instance = None
        bus = EventBus()
        bus.reset()

        ts = TripService(db)
        am = AlertManager(db)
        engine = OperationsEngine.create(db=db, event_bus=bus, alert_mgr=am, trip_service=ts)
        return WorkflowEnvironment(
            db=db, trip_service=ts, invoice_service=InvoiceService(db),
            event_bus=bus, alert_manager=am, operations_engine=engine,
        )

    def _benchmark_trip_creation(self):
        db = self._make_db()
        try:
            env = self._make_env(db)
            company_id = env.seed_company("Benchmark Co")
            client_id = env.seed_client("Benchmark Client")
            env.create_trip(client_id=client_id, status="Planned")
        finally:
            db.conn.close()

    def _benchmark_status_transition(self):
        db = self._make_db()
        try:
            env = self._make_env(db)
            company_id = env.seed_company("Benchmark Co")
            client_id = env.seed_client("Benchmark Client")
            trip_id = env.create_trip(client_id=client_id, status="Planned")
            env.transition_status(trip_id, "Loading")
            env.transition_status(trip_id, "In Transit")
        finally:
            db.conn.close()

    def _benchmark_invoice_creation(self):
        from models.invoice_models import InvoiceCreate, InvoiceLineItem
        from datetime import date
        db = self._make_db()
        try:
            env = self._make_env(db)
            company_id = env.seed_company("Benchmark Co")
            client_id = env.seed_client("Benchmark Client")
            trip_id = env.create_trip(client_id=client_id, status="Delivered")
            env.invoice_service.create(InvoiceCreate(
                client_id=client_id, trip_id=trip_id,
                invoice_date=date.today().isoformat(),
                due_date=date(2026, 8, 20).isoformat(),
                line_items=[InvoiceLineItem(description="Transport", quantity=1, unit_price=1000.0, vat_rate=19.0)],
            ))
        finally:
            db.conn.close()

    def _benchmark_dispatch(self):
        db = self._make_db()
        try:
            env = self._make_env(db)
            company_id = env.seed_company("Benchmark Co")
            client_id = env.seed_client("Benchmark Client")
            trip_id = env.create_trip(client_id=client_id, status="Planned")
            truck_id = env.seed_truck("BN-01-BENCH")
            driver_id = env.seed_driver(company_id, "Bench Driver")
            from services.dispatch_service.dispatch_service import DispatchService
            from services.conflict_service import TripConflictService
            from repositories.fleet_repository import FleetRepository
            from repositories.driver_repository import DriverRepository
            from services.operations.event_bus import EventBus
            from services.operations.alert_manager import AlertManager
            ds = DispatchService(
                trip_service=env.trip_service,
                fleet_repo=FleetRepository(db),
                driver_repo=DriverRepository(db),
                conflict_service=TripConflictService(db),
                event_bus=EventBus(),
                alert_manager=AlertManager(db),
            )
            ds.assign_truck(trip_id, truck_id)
        finally:
            db.conn.close()

    def suggest_thresholds(self, results: list[BenchmarkResult]) -> list[ThresholdSuggestion]:
        """Compute suggested thresholds from benchmark results."""
        suggestions = []
        for r in results:
            if len(r.measurements_s) < 3:
                continue
            current = {
                "trip_creation_planned": 5.0,
                "status_transition": 5.0,
                "invoice_creation": 5.0,
                "dispatch_assign": 5.0,
            }.get(r.name, 5.0)

            suggested = max(round(r.p95_s * 1.5, 2), 0.5)

            rationale = f"P95 measured: {r.p95_s:.3f}s × 1.5 safety buffer = {suggested:.2f}s"
            if r.p95_s > current:
                rationale += f" (EXCEEDS current threshold of {current}s — consider raising)"

            suggestions.append(ThresholdSuggestion(
                name=r.name,
                current_threshold=current,
                measured_p95=r.p95_s,
                suggested_threshold=suggested,
                rationale=rationale,
            ))
        return suggestions

    def generate_report(self, results: list[BenchmarkResult],
                        suggestions: list[ThresholdSuggestion]) -> CalibrationReport:
        return CalibrationReport(
            timestamp=datetime.now().isoformat(),
            benchmarks=results,
            suggestions=suggestions,
            summary={
                "workflows_benchmarked": len(results),
                "total_runs": sum(len(r.measurements_s) for r in results),
                "thresholds_suggested": len(suggestions),
            },
        )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Calibrate workflow thresholds")
    parser.add_argument("--runs", type=int, default=10, help="Number of benchmark iterations")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-o", "--output", type=str, help="Output file path")
    args = parser.parse_args()

    calibrator = ThresholdCalibrator(runs=args.runs)
    results = calibrator.run_all()
    suggestions = calibrator.suggest_thresholds(results)
    report = calibrator.generate_report(results, suggestions)

    # Print suggestions
    print("\n=== Threshold Suggestions ===\n")
    for s in suggestions:
        status = "⚠️ EXCEEDS CURRENT" if s.measured_p95 > s.current_threshold else "✅ WITHIN CURRENT"
        print(f"  {s.name}:")
        print(f"    Current:    {s.current_threshold:.2f}s")
        print(f"    Measured:   {s.measured_p95:.3f}s (P95)")
        print(f"    Suggested:  {s.suggested_threshold:.2f}s")
        print(f"    Status:     {status}")
        print()

    if args.json or args.output:
        data = {
            "timestamp": report.timestamp,
            "benchmarks": {
                r.name: {
                    "min": round(r.min_s, 3),
                    "max": round(r.max_s, 3),
                    "avg": round(r.avg_s, 3),
                    "p95": round(r.p95_s, 3),
                    "p99": round(r.p99_s, 3),
                    "n": len(r.measurements_s),
                }
                for r in results
            },
            "suggestions": [
                {"name": s.name, "current": s.current_threshold, "measured_p95": round(s.measured_p95, 3),
                 "suggested": s.suggested_threshold, "rationale": s.rationale}
                for s in suggestions
            ],
        }
        json_str = json.dumps(data, indent=2)
        if args.output:
            Path(args.output).write_text(json_str)
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
