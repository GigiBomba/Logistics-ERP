#!/usr/bin/env python3
"""CI/CD Constitutional Gate — Operion Workflow Integrity enforcement.

Runs the Workflow Integrity Test Suite with tier-appropriate marker
selection, generates a constitutional readiness report, enforces
quality-gate thresholds, and exits with a non-zero code when any
blocking breach is detected.

Usage
-----
    python scripts/constitutional_gate.py --tier bronze
    python scripts/constitutional_gate.py --tier gold --json --output report.json
    python scripts/constitutional_gate.py --tier platinum --require-all

Tiers
-----
- **bronze**   — All tests must exist & be importable (structural gate).
                 Pass rate >= 60%, no blocking breaches.
- **silver**   — Golden flows pass; state machine + financial tests exist.
                 Pass rate >= 70%, no dimension below 60%.
- **gold**      — Full coverage of key areas; telemetry + ARGO tests.
                 Pass rate >= 80%, no dimension below 70%.
- **platinum**  — All dimensions >= 85%, zero skipped tests.
                 Pass rate >= 95%, all structural gates satisfied.

Exit Codes
----------
0   All gates met — constitutional READY.
1   One or more threshold breaches detected.
2   Test suite invocation failed (pytest crashed / timed out).
3   Input validation error (invalid tier, missing dependencies).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# Ensure the project root is on sys.path so the report generator can be imported
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.workflow_integrity.telemetry.report_generator import (  # noqa: E402
    Breach,
    ReportGenerator,
    Scorecard,
    TIER_THRESHOLDS,
)


# ═════════════════════════════════════════════════════════════════════════════
# Per-tier pytest marker / filter arguments
# ═════════════════════════════════════════════════════════════════════════════

# Each tier runs a progressively broader set of markers.
# ``bronze`` runs everything (structural existence check).
# Higher tiers add marker filtering for focus (optional).
TIER_PYTEST_ARGS: dict[str, List[str]] = {
    "bronze": [],
    "silver": [],
    "gold": [],
    "platinum": [],
}


# ═════════════════════════════════════════════════════════════════════════════
# Structural gate checks (fast pre-flight)
# ═════════════════════════════════════════════════════════════════════════════

REQUIRED_FILES: dict[str, List[str]] = {
    "bronze": [
        "tests/workflow_integrity/conftest.py",
        "tests/workflow_integrity/fixtures/event_monitor.py",
        "tests/workflow_integrity/fixtures/workflow_environment.py",
    ],
    "silver": [
        "tests/workflow_integrity/golden_flows/",
        "tests/workflow_integrity/financial/test_financial_invariants.py",
        "tests/workflow_integrity/financial/test_state_machine_trip.py",
    ],
    "gold": [
        "tests/workflow_integrity/telemetry/",
        "tests/workflow_integrity/argo/",
    ],
    "platinum": [
        "docs/blueprints/workflow_integrity_test_suite_architecture.md",
    ],
}


def check_structural_gates(tier: str) -> List[str]:
    """Verify required files/directories exist.  Return list of violations."""
    violations: List[str] = []
    root = Path(__file__).resolve().parent.parent

    # Walk tier hierarchy: check all lower tiers too
    for check_tier in TIER_THRESHOLDS:
        for required in REQUIRED_FILES.get(check_tier, []):
            path = root / required
            if not path.exists():
                violations.append(f"[{check_tier}] Missing: {required}")
        if check_tier == tier:
            break

    return violations


# ═════════════════════════════════════════════════════════════════════════════
# Core enforcement
# ═════════════════════════════════════════════════════════════════════════════


def run_gate(tier: str) -> tuple[Scorecard, List[Breach], List[str]]:
    """Execute the full constitutional gate pipeline.

    Returns:
        (scorecard, breaches, structural_violations).
    """
    structural_violations = check_structural_gates(tier)

    gen = ReportGenerator()
    results = gen.run_suite()
    card = gen.compute_score(results)
    breaches = gen.detect_breaches(card, tier=tier)

    # Structural violations become blocking breaches
    for v in structural_violations:
        breaches.append(Breach(
            metric="structural",
            threshold=1.0,
            actual=0.0,
            tier=tier,
            severity="blocking",
        ))

    return card, breaches, structural_violations


def enforce_breaches(breaches: List[Breach]) -> int:
    """Return the appropriate exit code based on breach severity."""
    blocking = [b for b in breaches if b.severity == "blocking"]
    warnings = [b for b in breaches if b.severity == "warning"]

    if blocking:
        print(f"🚫 {len(blocking)} BLOCKING breach(es) detected:", file=sys.stderr)
        for b in blocking:
            print(f"   - {b.metric}: {b.actual:.2%} < {b.threshold:.0%} [{b.tier}]", file=sys.stderr)
        return 1

    if warnings:
        print(f"⚠️  {len(warnings)} WARNING(s):", file=sys.stderr)
        for b in warnings:
            print(f"   - {b.metric}: {b.actual:.2%} < {b.threshold:.0%} [{b.tier}]", file=sys.stderr)

    return 0


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Operion Constitutional Gate — CI/CD quality enforcement"
    )
    parser.add_argument(
        "--tier",
        choices=["bronze", "silver", "gold", "platinum"],
        required=True,
        help="Quality gate tier to enforce",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit JSON report to stdout",
    )
    parser.add_argument(
        "--markdown", action="store_true",
        help="Emit Markdown scorecard to stdout",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Write report to file",
    )
    parser.add_argument(
        "--require-all", action="store_true",
        help="Enforce all breaches as blocking (Platinum strict mode)",
    )
    parser.add_argument(
        "pytest_args", nargs="*",
        help="Extra arguments forwarded to pytest",
    )
    parsed = parser.parse_args()

    tier = parsed.tier.capitalize()
    if tier not in TIER_THRESHOLDS:
        print(f"Invalid tier: {tier}", file=sys.stderr)
        return 3

    import json

    try:
        card, breaches, structural = run_gate(tier)
    except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError) as exc:
        print(f"Test suite invocation failed: {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"Dependency missing: {exc}", file=sys.stderr)
        return 3

    # Print structural violations
    if structural:
        print(f"🔧 {len(structural)} structural violation(s):", file=sys.stderr)
        for s in structural:
            print(f"   - {s}", file=sys.stderr)
        print("", file=sys.stderr)

    # Print summary
    r = card.test_results
    print(f"=== Constitutional Gate: {tier} ===", file=sys.stderr)
    print(f"Pass rate: {r.pass_rate:.2%} ({r.passed}/{r.total})", file=sys.stderr)
    print(f"Score: {card.total_score:.4f}", file=sys.stderr)
    print(f"Tier: {card.tier}", file=sys.stderr)
    print(f"Breaches: {len(breaches)}", file=sys.stderr)
    print("", file=sys.stderr)

    # Emit report
    gen = ReportGenerator()
    if parsed.json:
        output = json.dumps(gen.generate_json_report(card, breaches), indent=2)
    elif parsed.markdown:
        output = gen.generate_markdown_scorecard(card, breaches)
    else:
        output = None

    if output and parsed.output:
        parsed.output.write_text(output, encoding="utf-8")
        print(f"Report written to {parsed.output}", file=sys.stderr)
    elif output:
        print(output)

    exit_code = enforce_breaches(breaches)
    return exit_code


if __name__ == "__main__":
    import subprocess  # noqa: F811 — used in main() except handler
    sys.exit(main())
