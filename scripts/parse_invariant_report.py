#!/usr/bin/env python3
"""
Parse an invariant report JSON and output summary + GitHub Actions annotations.

Usage:
    python scripts/parse_invariant_report.py invariants-report.json
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: parse_invariant_report.py <report.json>")
        return 1

    report_path = sys.argv[1]
    if not os.path.exists(report_path):
        print(f"Report not found: {report_path}")
        return 1

    with open(report_path) as f:
        report = json.load(f)

    total = report.get("total", 0)
    passed = report.get("passed", 0)
    failed = report.get("failed", 0)
    errors = report.get("errors", 0)
    skipped = report.get("skipped", 0)
    rate = report.get("success_rate", 0.0)
    risk = report.get("risk_level", "UNKNOWN")
    critical_count = report.get("critical_failures_count", 0)

    # Console output
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | "
          f"Errors: {errors} | Skipped: {skipped}")
    print(f"Success Rate: {rate:.1%} | Risk Level: {risk} | "
          f"Critical Failures: {critical_count}")

    # Set GitHub Actions step outputs
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"total={total}\n")
            f.write(f"passed={passed}\n")
            f.write(f"failed={failed}\n")
            f.write(f"errors={errors}\n")
            f.write(f"skipped={skipped}\n")
            f.write(f"success_rate={rate}\n")
            f.write(f"risk_level={risk}\n")
            f.write(f"critical_failures={critical_count}\n")

    # Print per-result details for failures
    if failed > 0 or errors > 0:
        print(f"\nFailed/Errored Invariants:")
        print(f"{'─' * 72}")
        for r in report.get("results", []):
            status = r.get("status", "")
            if status in ("fail", "error"):
                inv_id = r.get("invariant_id", "???")
                msg = r.get("message", "")
                expected = r.get("expected", "")
                actual = r.get("actual", "")
                cause = r.get("root_cause", "")
                fix = r.get("suggested_fix", "")

                print(f"\n  [{inv_id}] {status.upper()}")
                if expected:
                    print(f"    Expected: {expected}")
                if actual:
                    print(f"    Actual:   {actual}")
                if msg:
                    print(f"    Message:  {msg}")
                if cause:
                    print(f"    Cause:    {cause}")
                if fix:
                    print(f"    Fix:      {fix}")

    # Generate GitHub Actions step summary
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "w") as f:
            f.write("## Business Invariant Report\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            f.write(f"| Total | {total} |\n")
            f.write(f"| Passed | {passed} |\n")
            f.write(f"| Failed | {failed} |\n")
            f.write(f"| Errors | {errors} |\n")
            f.write(f"| Skipped | {skipped} |\n")
            f.write(f"| Success Rate | {rate:.1%} |\n")
            f.write(f"| Risk Level | {risk} |\n")
            f.write(f"| Critical Failures | {critical_count} |\n")

            if critical_count > 0:
                f.write("\n### ❌ Deployment Blocked\n\n")
                f.write(f"{critical_count} critical invariant(s) failed. "
                        f"Deployment is blocked until resolved.\n\n")
                for r in report.get("results", []):
                    if r.get("status") == "fail":
                        inv_id = r.get("invariant_id", "???")
                        msg = r.get("message", "")
                        f.write(f"- **{inv_id}**: {msg}\n")

            if failed > 0 and critical_count == 0:
                f.write("\n### ⚠️ Review Recommended\n\n")
                f.write(f"{failed} non-critical invariant(s) failed — "
                        f"review before proceeding.\n")

    return 0 if critical_count == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
