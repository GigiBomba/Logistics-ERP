#!/usr/bin/env python
"""Constitutional Certification — formal certification of the Operion ecosystem.

Runs the full Workflow Integrity Suite, computes the 10-dimension scorecard,
assesses certification level, and generates a certification report.

Usage:
    python scripts/constitutional_certification.py
    python scripts/constitutional_certification.py --require-platinum
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

DIMENSIONS = [
    "Workflow Integrity", "Data Integrity", "Financial Integrity",
    "Tenant Isolation", "AI Safety", "Historical Immutability",
    "Offline Consistency", "Chaos Resilience", "Observability", "Governance",
]

DIMENSION_HINTS = {
    "Workflow Integrity": "Review golden flow test failures — check e2e integration tests",
    "Data Integrity": "Audit state machine transition tests — invariant T-INV violations",
    "Financial Integrity": "Check F1-F10 invariant tests — verify invoice/trip totals match",
    "Tenant Isolation": "Audit MT-INV cross-company queries — verify company_id scoping",
    "AI Safety": "Review ARGO safety boundary tests — check permission checks",
    "Historical Immutability": "Verify finalized records reject edits — check update() guards",
    "Offline Consistency": "Test sync conflict resolution — verify last-write-wins logic",
    "Chaos Resilience": "Run chaos workflow tests — verify DB integrity after failure",
    "Observability": "Check telemetry event coverage — verify workflow.* events publish",
    "Governance": "Review governance rule tests — check G-01 through G-11 compliance",
}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Constitutional Certification")
    parser.add_argument("--require-platinum", action="store_true",
                        help="Require Platinum certification (score >= 95, all dims >= 85%, 0 skips)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-o", "--output", type=str)
    args = parser.parse_args()

    os.environ.setdefault("OPERION_ENCRYPTION_KEY", "cert-key-12345")
    sys.path.insert(0, str(REPO_ROOT))

    from tests.workflow_integrity.telemetry.report_generator import ReportGenerator

    print("Running Workflow Integrity Suite...", file=sys.stderr)
    gen = ReportGenerator()
    results = gen.run_suite()

    print("Computing scorecard...", file=sys.stderr)
    scorecard = gen.compute_score(results)
    breaches = gen.detect_breaches(scorecard, "gold")

    score = scorecard.total_score
    dims = scorecard.dimensions
    min_dim = min((ds.pass_rate * 100 for ds in dims.values()), default=0.0)
    skips = results.skipped

    # Assess level
    if score >= 0.95 and min_dim >= 85.0 and skips == 0:
        level = "certified"
    elif score >= 0.80 and min_dim >= 70.0:
        if args.require_platinum:
            level = "not_yet"
        else:
            level = "conditional"
    else:
        level = "not_yet"

    # Identify gaps
    gaps = []
    for dim in DIMENSIONS:
        ds = dims.get(dim)
        val = (ds.pass_rate * 100) if ds else 0.0
        if val < 70.0:
            gaps.append(f"[CRITICAL] {dim}: {val:.1f}% (needs >= 70%) - {DIMENSION_HINTS.get(dim, '')}")
        elif val < 85.0:
            gaps.append(f"[MAJOR] {dim}: {val:.1f}% (needs >= 85%) - {DIMENSION_HINTS.get(dim, '')}")
        elif val < 95.0:
            gaps.append(f"[MINOR] {dim}: {val:.1f}% (needs >= 95%) - {DIMENSION_HINTS.get(dim, '')}")

    breaches_list = [f"[BREACH] {b.metric}: {b.actual} (threshold: {b.threshold})"
                    for b in breaches]

    # Generate certificate
    result = {
        "level": level,
        "score": round(score * 100, 2),
        "dimensions": {k: round(ds.pass_rate * 100, 2) for k, ds in dims.items()},
        "gaps": gaps,
        "breaches": breaches_list,
        "summary": {
            "passed": results.passed,
            "failed": results.failed,
            "skipped": results.skipped,
            "total": results.total,
            "duration_seconds": round(results.duration_seconds, 1),
        },
        "timestamp": datetime.now().isoformat(),
        "require_platinum": args.require_platinum,
    }

    # Print markdown report (with ASCII fallback for Windows console)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    cert_icon = {"certified": "[PASS]", "conditional": "[WARN]", "not_yet": "[FAIL]"}.get(level, "[?]")
    print(f"\n# Operion Constitutional Certification\n")
    print(f"**Level:** {cert_icon} {level.upper()}")
    print(f"**Score:** {score*100:.1f}/100")
    print(f"**Suite:** {results.passed} passed, {results.failed} failed, "
          f"{results.skipped} skipped ({results.duration_seconds:.1f}s)")
    print(f"\n## Dimension Scores\n")
    print(f"| Dimension | Score | Status |")
    print(f"|-----------|-------|--------|")
    for dim in DIMENSIONS:
        ds = dims.get(dim)
        val = (ds.pass_rate * 100) if ds else 0.0
        status = "Healthy" if val >= 85 else ("At Risk" if val >= 70 else "Critical")
        print(f"| {dim} | {val:.1f}/100 | {status} |")

    if gaps:
        print(f"\n## Gaps\n")
        for g in gaps:
            print(f"- {g}")

    if breaches_list:
        print(f"\n## Breaches\n")
        for b in breaches_list:
            print(f"- {b}")

    verdict = {"certified": "CONSTITUTIONAL QA CERTIFIED",
               "conditional": "CONDITIONALLY CERTIFIED",
               "not_yet": "NOT YET CERTIFIED"}.get(level, "")
    print(f"\n## Verdict\n")
    print(f"**{verdict}**")
    if level == "not_yet" and args.require_platinum:
        print("*Platinum certification was required but not achieved.*")

    # Output JSON
    if args.json or args.output:
        data = json.dumps(result, indent=2)
        if args.output:
            Path(args.output).write_text(data)
            print(f"\nCertificate written to {args.output}", file=sys.stderr)
        else:
            print(data)

    return 1 if level == "not_yet" else 0


if __name__ == "__main__":
    sys.exit(main())
