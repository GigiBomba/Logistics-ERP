"""
Business Invariant Framework — Reporters

Produces human-readable and machine-readable reports.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import IO, TextIO

from business_invariants.models import (
    InvariantReport,
    InvariantResult,
    InvariantStatus,
    Severity,
)


def _severity_icon(severity: Severity) -> str:
    icons = {Severity.CRITICAL: "🛑", Severity.HIGH: "🔴", Severity.MEDIUM: "🟡", Severity.LOW: "🟢"}
    return icons.get(severity, "⚪")


def _status_icon(status: InvariantStatus) -> str:
    icons = {
        InvariantStatus.PASS: "✅",
        InvariantStatus.FAIL: "❌",
        InvariantStatus.ERROR: "⚠️",
        InvariantStatus.SKIPPED: "⏭️",
    }
    return icons.get(status, "❓")


class ConsoleReporter:
    """Human-readable console output."""

    def __init__(self, stream: TextIO = sys.stdout) -> None:
        self.stream = stream

    def report(self, report: InvariantReport) -> None:
        self._print_header(report)
        self._print_summary(report)
        if report.failed > 0 or report.errors > 0:
            self._print_failures(report)
        self._print_footer(report)

    def _print_header(self, report: InvariantReport) -> None:
        env = f" [{report.environment}]" if report.environment else ""
        self.stream.write(f"\n{'=' * 72}\n")
        self.stream.write(f"  OPERION BUSINESS INVARIANT REPORT{env}\n")
        self.stream.write(f"  Run ID: {report.run_id}\n")
        self.stream.write(f"  Started: {report.started_at.isoformat()}\n")
        self.stream.write(f"{'=' * 72}\n\n")

    def _print_summary(self, report: InvariantReport) -> None:
        self.stream.write(f"  Summary:\n")
        self.stream.write(f"    Total:     {report.total:4d}\n")
        self.stream.write(f"    Passed:    {report.passed:4d}\n")
        self.stream.write(f"    Failed:    {report.failed:4d}\n")
        self.stream.write(f"    Errors:    {report.errors:4d}\n")
        self.stream.write(f"    Skipped:   {report.skipped:4d}\n")
        self.stream.write(f"    Duration:  {report.duration_ms:.1f} ms\n")
        self.stream.write(f"    Risk:      {report.risk_level}\n")
        self.stream.write(f"    Rate:      {report.success_rate:.1%}\n\n")

    def _print_failures(self, report: InvariantReport) -> None:
        self.stream.write(f"  Failures & Errors:\n")
        self.stream.write(f"  {'─' * 68}\n")
        for result in report.results:
            if result.failed or result.errored:
                self._print_result(result)

    def _print_result(self, result: InvariantResult) -> None:
        icon = _status_icon(result.status)
        self.stream.write(f"\n  {icon} [{result.invariant_id}]\n")
        self.stream.write(f"     Expected: {result.expected}\n")
        self.stream.write(f"     Actual:   {result.actual}\n")
        if result.message:
            self.stream.write(f"     Message:  {result.message}\n")
        if result.root_cause:
            self.stream.write(f"     Cause:    {result.root_cause}\n")
        if result.suggested_fix:
            self.stream.write(f"     Fix:      {result.suggested_fix}\n")
        self.stream.write(f"     Modules:  {', '.join(result.affected_modules)}\n")

        if result.duration_ms > 0:
            self.stream.write(f"     Duration: {result.duration_ms:.1f} ms\n")

    def _print_footer(self, report: InvariantReport) -> None:
        self.stream.write(f"\n{'=' * 72}\n")
        if report.has_critical_failures:
            self.stream.write(
                f"  ❌ DEPLOYMENT BLOCKED — {len(report.critical_failures)} critical "
                f"invariant(s) failed\n"
            )
        elif report.failed > 0:
            self.stream.write(f"  ⚠️  {report.failed} non-critical invariant(s) failed — review required\n")
        else:
            self.stream.write(f"  ✅ All invariants passed\n")
        self.stream.write(f"{'=' * 72}\n\n")


class JsonReporter:
    """Machine-readable JSON output."""

    def report(self, report: InvariantReport) -> str:
        return json.dumps(self._to_dict(report), indent=2, default=str)

    def _to_dict(self, report: InvariantReport) -> dict:
        return {
            "run_id": report.run_id,
            "started_at": report.started_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            "duration_ms": report.duration_ms,
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "errors": report.errors,
            "skipped": report.skipped,
            "success_rate": round(report.success_rate, 4),
            "risk_level": report.risk_level,
            "critical_failures_count": len(report.critical_failures),
            "affected_modules": sorted(report.affected_modules),
            "results": [
                {
                    "invariant_id": r.invariant_id,
                    "status": r.status.value,
                    "expected": r.expected,
                    "actual": r.actual,
                    "message": r.message,
                    "root_cause": r.root_cause,
                    "suggested_fix": r.suggested_fix,
                    "affected_modules": r.affected_modules,
                    "duration_ms": round(r.duration_ms, 1),
                }
                for r in report.results
            ],
        }


class MarkdownReporter:
    """Report as Markdown (suitable for PR comments, docs)."""

    def report(self, report: InvariantReport) -> str:
        lines: list[str] = []
        lines.append(f"# Operion Business Invariant Report\n")
        lines.append(f"- **Run ID:** {report.run_id}")
        lines.append(f"- **Environment:** {report.environment or 'default'}")
        lines.append(f"- **Started:** {report.started_at.isoformat()}")
        lines.append(f"- **Duration:** {report.duration_ms:.1f} ms")
        lines.append(f"- **Risk Level:** {report.risk_level}")
        lines.append("")

        lines.append("## Summary\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total | {report.total} |")
        lines.append(f"| ✅ Passed | {report.passed} |")
        lines.append(f"| ❌ Failed | {report.failed} |")
        lines.append(f"| ⚠️ Errors | {report.errors} |")
        lines.append(f"| ⏭️ Skipped | {report.skipped} |")
        lines.append(f"| Success Rate | {report.success_rate:.1%} |")
        lines.append("")

        if report.failed > 0 or report.errors > 0:
            lines.append("## Failures & Errors\n")
            for result in report.results:
                if result.failed or result.errored:
                    icon = _status_icon(result.status)
                    lines.append(f"### {icon} {result.invariant_id}\n")
                    lines.append(f"- **Status:** {result.status.value}")
                    lines.append(f"- **Expected:** {result.expected}")
                    lines.append(f"- **Actual:** {result.actual}")
                    if result.message:
                        lines.append(f"- **Message:** {result.message}")
                    if result.root_cause:
                        lines.append(f"- **Root Cause:** {result.root_cause}")
                    if result.suggested_fix:
                        lines.append(f"- **Suggested Fix:** {result.suggested_fix}")
                    lines.append(f"- **Modules:** {', '.join(result.affected_modules)}")
                    lines.append("")

        if report.has_critical_failures:
            lines.append("## 🛑 Deployment Blocked\n")
            lines.append(
                f"{len(report.critical_failures)} critical invariant(s) failed. "
                f"Deployment is blocked until resolved.\n"
            )

        return "\n".join(lines)
