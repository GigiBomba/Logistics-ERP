#!/usr/bin/env python
"""Constitutional Readiness Scorecard — Report Generator.

Runs the Workflow Integrity Test Suite via pytest subprocess, parses the
junit XML output, computes the 10-dimension Constitutional Readiness Score,
detects threshold breaches per quality tier, and generates machine-readable
JSON + human-readable Markdown reports.

Usage:
    python tests/workflow_integrity/telemetry/report_generator.py --tier gold
    python tests/workflow_integrity/telemetry/report_generator.py --tier gold --json
    python tests/workflow_integrity/telemetry/report_generator.py --tier platinum -o report.json
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parents[3]
SUITE_DIR = ROOT / "tests" / "workflow_integrity"

# 10 Constitutional Dimensions: name → (weight, file pattern for attribution)
DIMENSIONS: Dict[str, Dict[str, Any]] = {
    "Workflow Integrity":     {"weight": 0.15, "pattern": r"(golden_flows/|test_golden_workflows\.py)"},
    "Data Integrity":         {"weight": 0.12, "pattern": r"(test_state_machine_trip\.py|test_state_machine_dispatch\.py)"},
    "Financial Integrity":    {"weight": 0.12, "pattern": r"(test_financial_invariants|test_invoice_payment)"},
    "Tenant Isolation":       {"weight": 0.10, "pattern": r"(test_argo_multitenant_invariants)"},
    "AI Safety":              {"weight": 0.10, "pattern": r"(argo/|test_state_machine_argo)"},
    "Historical Immutability":{"weight": 0.08, "pattern": r"(test_historical_immutability)"},
    "Offline Consistency":    {"weight": 0.08, "pattern": r"(parity/|test_conflict_resolution)"},
    "Chaos Resilience":       {"weight": 0.10, "pattern": r"(reliability/|test_chaos_workflow)"},
    "Observability":          {"weight": 0.08, "pattern": r"(telemetry/)"},
    "Governance":             {"weight": 0.07, "pattern": r"(test_governance|test_quality_gates)"},
}

# Per-tier thresholds: (min_overall_pass_rate, min_dim_pass_rate, max_skips_allowed)
TIER_THRESHOLDS: Dict[str, tuple[float, float, Optional[int]]] = {
    "Bronze":   (0.60, 0.50, None),
    "Silver":   (0.70, 0.60, None),
    "Gold":     (0.80, 0.70, None),
    "Platinum": (0.95, 0.85, 0),
}

TIER_SCORE_MAP: Dict[str, float] = {
    "Platinum": 0.95,
    "Gold":     0.80,
    "Silver":   0.70,
    "Bronze":   0.0,
}


# ═════════════════════════════════════════════════════════════════════════════
# Data models
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class DimensionResult:
    """Pass/fail/skip breakdown for one constitutional dimension."""
    name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 1.0


@dataclass
class TestResults:
    """Aggregate test-suite results with dimension breakdown."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 1.0


@dataclass
class DimensionScore:
    """Weighted contribution of one dimension to the total score."""
    name: str
    weight: float
    pass_rate: float
    weighted_score: float


@dataclass
class Breach:
    """A quality-gate threshold breach."""
    metric: str
    threshold: float
    actual: float
    tier: str
    severity: str  # "blocking" | "warning"


@dataclass
class Scorecard:
    """The complete Constitutional Readiness Scorecard."""
    total_score: float
    tier: str
    dimensions: Dict[str, DimensionScore]
    test_results: TestResults
    timestamp: str
    duration_seconds: float
    breaches: List[Breach] = field(default_factory=list)


# ═════════════════════════════════════════════════════════════════════════════
# ReportGenerator
# ═════════════════════════════════════════════════════════════════════════════


class ReportGenerator:
    """Orchestrates suite execution, scoring, breach detection, and reporting."""

    def run_suite(self) -> TestResults:
        """Run the suite via pytest subprocess, capturing junitxml.

        Runs with ``--override-ini=addopts=`` to suppress xdist parallelism
        in the subprocess and avoid worker manager issues.
        """
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
            xml_path = Path(tmp.name)

        start = time.time()
        exit_code, stdout, stderr = self._invoke_pytest(xml_path)
        elapsed = time.time() - start

        raw_cases = self._parse_junit(xml_path)
        try:
            xml_path.unlink(missing_ok=True)
        except OSError:
            pass

        # Create dimension buckets
        dim_results: Dict[str, DimensionResult] = {
            name: DimensionResult(name=name) for name in DIMENSIONS
        }

        # Count totals from junit cases
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        for case in raw_cases:
            total += 1
            if case["status"] == "passed":
                passed += 1
            elif case["status"] == "skipped":
                skipped += 1
            else:
                failed += 1

            # Attribute to dimension
            dim = self._match_dimension(case["classname"])
            if dim:
                dr = dim_results[dim]
                dr.total += 1
                if case["status"] == "passed":
                    dr.passed += 1
                elif case["status"] == "skipped":
                    dr.skipped += 1
                else:
                    dr.failed += 1

        # If junit parsing produced zero results, fall back to summary line parse
        if total == 0:
            total, passed, failed, skipped = self._parse_pytest_summary_line(stderr)

        return TestResults(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=elapsed,
            dimensions=dim_results,
        )

    def compute_score(self, results: TestResults) -> Scorecard:
        """Weight the per-dimension pass rates into a 0–1 Constitutional Readiness Score."""
        dim_scores: Dict[str, DimensionScore] = {}
        total_weighted = 0.0

        for dim_name, dim_cfg in DIMENSIONS.items():
            dr = results.dimensions.get(dim_name, DimensionResult(name=dim_name))
            weight = dim_cfg["weight"]
            ws = dr.pass_rate * weight
            dim_scores[dim_name] = DimensionScore(
                name=dim_name, weight=weight, pass_rate=dr.pass_rate, weighted_score=ws,
            )
            total_weighted += ws

        return Scorecard(
            total_score=round(total_weighted, 4),
            tier=self._score_to_tier(total_weighted),
            dimensions=dim_scores,
            test_results=results,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_seconds=results.duration_seconds,
        )

    def detect_breaches(self, scorecard: Scorecard, tier: Optional[str] = None) -> List[Breach]:
        """Return every threshold breach for *tier* (or scorecard's own tier)."""
        tier = tier or scorecard.tier
        breaches: List[Breach] = []

        threshold = TIER_THRESHOLDS.get(tier)
        if threshold is None:
            return breaches

        min_overall, min_dim, max_skips = threshold

        overall_pr = scorecard.test_results.pass_rate
        if overall_pr < min_overall:
            breaches.append(Breach(
                metric="overall_pass_rate",
                threshold=min_overall, actual=round(overall_pr, 4),
                tier=tier, severity="blocking",
            ))

        for dim_name, ds in scorecard.dimensions.items():
            if ds.pass_rate < min_dim:
                breaches.append(Breach(
                    metric=f"dimension.{dim_name}.pass_rate",
                    threshold=min_dim, actual=round(ds.pass_rate, 4),
                    tier=tier,
                    severity="blocking" if ds.pass_rate < min_dim - 0.05 else "warning",
                ))

        if max_skips is not None and scorecard.test_results.skipped > max_skips:
            breaches.append(Breach(
                metric="skipped_tests",
                threshold=float(max_skips),
                actual=float(scorecard.test_results.skipped),
                tier=tier, severity="blocking",
            ))

        return breaches

    def generate_json_report(self, scorecard: Scorecard, breaches: Optional[List[Breach]] = None) -> dict:
        """Produce a machine-readable JSON report."""
        breaches = breaches or scorecard.breaches
        r = scorecard.test_results
        return {
            "report_type": "constitutional_readiness_scorecard",
            "timestamp": scorecard.timestamp,
            "duration_seconds": round(scorecard.duration_seconds, 2),
            "summary": {
                "total": r.total, "passed": r.passed, "failed": r.failed,
                "skipped": r.skipped, "pass_rate": round(r.pass_rate, 4),
            },
            "score": scorecard.total_score,
            "quality_tier": scorecard.tier,
            "dimensions": {
                dim_name: {
                    "weight": ds.weight,
                    "pass_rate": round(ds.pass_rate, 4),
                    "weighted_score": round(ds.weighted_score, 4),
                }
                for dim_name, ds in scorecard.dimensions.items()
            },
            "breaches": [
                {"metric": b.metric, "threshold": b.threshold, "actual": b.actual,
                 "tier": b.tier, "severity": b.severity}
                for b in breaches
            ],
        }

    def generate_markdown_scorecard(self, scorecard: Scorecard, breaches: Optional[List[Breach]] = None) -> str:
        """Produce a human-readable Markdown scorecard."""
        breaches = breaches or scorecard.breaches
        r = scorecard.test_results

        lines: List[str] = [
            "# Constitutional Readiness Scorecard",
            "",
            f"- **Generated**: {scorecard.timestamp}",
            f"- **Quality Tier**: **{scorecard.tier}**",
            f"- **Overall Score**: `{scorecard.total_score:.4f}`",
            f"- **Pass Rate**: {r.pass_rate:.1%} ({r.passed}/{r.total})",
            f"- **Duration**: {scorecard.duration_seconds:.1f}s",
            "",
            "## Dimension Breakdown",
            "",
            "| Dimension               | Weight | Pass Rate | Weighted |",
            "|-------------------------|--------|-----------|----------|",
        ]

        for dim_name in DIMENSIONS:
            ds = scorecard.dimensions.get(dim_name)
            if ds is None:
                continue
            icon = "+" if ds.pass_rate >= 0.90 else ("~" if ds.pass_rate >= 0.70 else "!")
            lines.append(
                f"| {icon} {dim_name:<25s} | {ds.weight:>5.0%}  | {ds.pass_rate:>8.1%}  | {ds.weighted_score:>7.4f} |"
            )

        lines.append("")
        lines.append(f"**Weighted Total**: `{scorecard.total_score:.4f}`")
        lines.append("")

        if breaches:
            blocking = [b for b in breaches if b.severity == "blocking"]
            warnings = [b for b in breaches if b.severity == "warning"]

            lines.append("## Breaches")
            lines.append("")
            if blocking:
                lines.append("### BLOCKING")
                for b in blocking:
                    lines.append(f"- `{b.metric}`: {b.actual:.2%} < threshold {b.threshold:.0%} [{b.tier}]")
                lines.append("")
            if warnings:
                lines.append("### WARNINGS")
                for b in warnings:
                    lines.append(f"- `{b.metric}`: {b.actual:.2%} < threshold {b.threshold:.0%} [{b.tier}]")
                lines.append("")
        else:
            lines.append("## Breaches: None detected")
            lines.append("")

        lines.extend([
            "## Tiers",
            "",
            "| Tier     | Min Score | Min Dim | Max Skips |",
            "|----------|-----------|---------|-----------|",
            "| Platinum | 95%       | 85%     | 0         |",
            "| Gold     | 80%       | 70%     | -         |",
            "| Silver   | 70%       | 60%     | -         |",
            "| Bronze   | 60%       | 50%     | -         |",
            "",
            "## Methodology",
            "",
            "The Constitutional Readiness Score is a weighted average across 10 dimensions.",
            "Each dimension is scored 0–1 from its test pass rate, multiplied by its weight.",
            "The quality tier is determined by the weighted total score.",
        ])

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════
    # Internals
    # ═══════════════════════════════════════════════════════════════════

    def _invoke_pytest(self, xml_path: Path) -> tuple[int, str, str]:
        """Run pytest subprocess with junitxml output."""
        cmd = [
            sys.executable, "-m", "pytest",
            str(SUITE_DIR),
            f"--junitxml={xml_path}",
            "--override-ini=addopts=",
            "-W", "ignore",
            "-q",
            "--no-header",
        ]
        env = dict(os.environ)
        env["OPERION_ENCRYPTION_KEY"] = "test-key-12345"
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
            cwd=str(ROOT),
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _parse_junit(self, xml_path: Path) -> List[Dict[str, str]]:
        """Parse junitxml into a list of {classname, name, status} dicts."""
        cases: List[Dict[str, str]] = []
        if not xml_path.exists():
            return cases
        try:
            tree = ET.parse(str(xml_path))
            root = tree.getroot()
        except ET.ParseError:
            return cases

        for testcase in root.iter("testcase"):
            classname = testcase.attrib.get("classname", "")
            name = testcase.attrib.get("name", "")
            if testcase.find("failure") is not None or testcase.find("error") is not None:
                status = "failed"
            elif testcase.find("skipped") is not None:
                status = "skipped"
            else:
                status = "passed"
            cases.append({"classname": classname, "name": name, "status": status})

        return cases

    def _parse_pytest_summary_line(self, stderr: str) -> tuple[int, int, int, int]:
        """Parse the pytest summary line like '401 passed in 78.17s'."""
        total = passed = failed = skipped = 0
        for line in stderr.split("\n"):
            line = line.strip()
            # e.g. "401 passed in 78.17s"
            m = re.match(r"(\d+)\s+passed", line)
            if m:
                passed = int(m.group(1))
                total += passed
            # e.g. "1 failed" or "1 failed, 400 passed"
            m = re.findall(r"(\d+)\s+failed", line)
            if m:
                failed = sum(int(x) for x in m)
                total += failed
            m = re.findall(r"(\d+)\s+skipped", line)
            if m:
                skipped = sum(int(x) for x in m)
                total += skipped
        return total, passed, failed, skipped

    def _match_dimension(self, classname: str) -> Optional[str]:
        """Return the dimension name matching *classname*, or None."""
        if not classname:
            return None
        for dim_name, dim_cfg in DIMENSIONS.items():
            if re.search(dim_cfg["pattern"], classname):
                return dim_name
        return None

    @staticmethod
    def _score_to_tier(score: float) -> str:
        for tier, threshold in sorted(TIER_SCORE_MAP.items(), key=lambda kv: -kv[1]):
            if score >= threshold:
                return tier
        return "Bronze"


# ═════════════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═════════════════════════════════════════════════════════════════════════════


def run_report(tier: Optional[str] = None) -> str:
    """Run the full pipeline and return a Markdown scorecard."""
    gen = ReportGenerator()
    results = gen.run_suite()
    card = gen.compute_score(results)
    breaches = gen.detect_breaches(card, tier=tier)
    card.breaches = breaches
    return gen.generate_markdown_scorecard(card, breaches)


def run_report_json(tier: Optional[str] = None) -> dict:
    """Run the full pipeline and return a JSON-serialisable dict."""
    gen = ReportGenerator()
    results = gen.run_suite()
    card = gen.compute_score(results)
    breaches = gen.detect_breaches(card, tier=tier)
    card.breaches = breaches
    return gen.generate_json_report(card, breaches)


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Constitutional Readiness Scorecard Generator"
    )
    parser.add_argument(
        "--tier", choices=["bronze", "silver", "gold", "platinum"],
        default=None,
        help="Quality tier for breach detection (default: auto-detect)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit JSON to stdout instead of Markdown",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Write report to file (encoding: UTF-8)",
    )
    args = parser.parse_args()

    tier = args.tier.capitalize() if args.tier else None

    print("Running Workflow Integrity Suite...", file=sys.stderr)
    gen = ReportGenerator()
    results = gen.run_suite()
    print(f"  {results.passed} passed, {results.failed} failed, {results.skipped} skipped in {results.duration_seconds:.1f}s", file=sys.stderr)

    print("Computing Constitutional Readiness Score...", file=sys.stderr)
    card = gen.compute_score(results)

    print(f"Detecting breaches for tier: {tier or card.tier}...", file=sys.stderr)
    breaches = gen.detect_breaches(card, tier=tier)
    card.breaches = breaches

    if args.json:
        output = json.dumps(gen.generate_json_report(card, breaches), indent=2)
    else:
        output = gen.generate_markdown_scorecard(card, breaches)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        # Use sys.stdout.buffer.write for safe UTF-8 output on Windows
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # Python 3.7+
        except (AttributeError, OSError):
            pass
        print(output)

    blocking = [b for b in breaches if b.severity == "blocking"]
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
