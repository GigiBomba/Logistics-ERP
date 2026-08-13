"""
Business Invariant Framework — CLI Entry Point

Usage:
    python -m business_invariants run                  # Run all invariants
    python -m business_invariants run --frequency pr   # Run PR-frequency invariants
    python -m business_invariants list                 # List all invariants
    python -m business_invariants run --ids FIN-001    # Run specific invariants
    python -m business_invariants run --json           # JSON output
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, TextIO

from business_invariants.config import default_invariant_config
from business_invariants.engine import InvariantEngine, InvariantRegistry
from business_invariants.models import (
    ExecutionFrequency,
    InvariantContext,
    Severity,
)
from business_invariants.reporter import ConsoleReporter, JsonReporter


def _load_checks(registry: InvariantRegistry) -> None:
    """Import all check modules so they register with the global registry."""
    # Each import triggers the @invariant decorator which auto-registers
    import business_invariants.checks.financial  # noqa: F401
    import business_invariants.checks.fleet  # noqa: F401
    import business_invariants.checks.drivers  # noqa: F401
    import business_invariants.checks.trips  # noqa: F401
    import business_invariants.checks.routes  # noqa: F401
    import business_invariants.checks.documents  # noqa: F401
    import business_invariants.checks.dispatch  # noqa: F401
    import business_invariants.checks.auth_security  # noqa: F401
    import business_invariants.checks.multitenant  # noqa: F401
    import business_invariants.checks.database  # noqa: F401
    import business_invariants.checks.ai_argo  # noqa: F401
    import business_invariants.checks.freight_exchange  # noqa: F401
    import business_invariants.checks.analytics  # noqa: F401
    import business_invariants.checks.workflows  # noqa: F401


def cmd_run(args: argparse.Namespace) -> int:
    registry = InvariantRegistry.get_global()
    _load_checks(registry)
    engine = InvariantEngine(registry)

    # Expose the process environment to invariant checks (JWT_*, BF_*,
    # OPERION_* etc.) so CI workflows can configure policy via env vars.
    env = dict(os.environ)
    if args.env:
        env["env"] = args.env

    ctx = InvariantContext(
        db_type=args.db_type or "sqlite",
        config=default_invariant_config(),
        env=env,
        company_id=args.company_id,
    )

    if args.ids:
        report = engine.run(ctx, invariant_ids=set(args.ids.split(",")))
    elif args.frequency:
        freq = ExecutionFrequency(args.frequency)
        report = engine.run_for_frequency(freq, ctx)
    elif args.category:
        report = engine.run_filtered(ctx, categories={args.category})
    else:
        report = engine.run_all(ctx)

    if args.json:
        reporter = JsonReporter()
        print(reporter.report(report))
    else:
        reporter = ConsoleReporter()
        reporter.report(report)

    if args.fail_on_critical and report.has_critical_failures:
        return 2
    if args.fail_on_any and report.failed > 0:
        return 1
    if report.has_critical_failures:
        return 2
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    registry = InvariantRegistry.get_global()
    _load_checks(registry)

    invariants = registry.get_all()
    invariants.sort(key=lambda d: (-d.meta.severity.value, d.meta.id))

    print(f"\n  Operion Business Invariants ({len(invariants)} total)\n")
    print(f"  {'ID':<14} {'Severity':<10} {'Category':<20} {'Title'}")
    print(f"  {'-' * 14} {'-' * 10} {'-' * 20} {'-' * 40}")

    for defn in invariants:
        meta = defn.meta
        sev = meta.severity.label().ljust(9)
        cat = meta.category.label().ljust(19)
        print(f"  {meta.id:<14} {sev} {cat} {meta.title}")

    print(f"\n  Total: {len(invariants)} invariants\n")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="business_invariants",
        description="Operion Business Invariant Framework — validate core business truths",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── run ──
    run_parser = subparsers.add_parser("run", help="Run business invariants")
    run_parser.add_argument("--ids", help="Comma-separated invariant IDs to run")
    run_parser.add_argument("--frequency", help="Execution frequency filter")
    run_parser.add_argument("--category", help="Category filter")
    run_parser.add_argument("--db-type", default="sqlite", help="Database type")
    run_parser.add_argument("--env", default="", help="Environment name")
    run_parser.add_argument("--company-id", type=int, default=None, help="Company scope")
    run_parser.add_argument("--json", action="store_true", help="Output as JSON")
    run_parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit code 2 if any CRITICAL invariant fails",
    )
    run_parser.add_argument(
        "--fail-on-any",
        action="store_true",
        help="Exit code 1 if ANY invariant fails",
    )

    # ── list ──
    list_parser = subparsers.add_parser("list", help="List all registered invariants")

    # ── Parse and run ──
    parsed = parser.parse_args(argv)

    if parsed.command == "run":
        return cmd_run(parsed)
    elif parsed.command == "list":
        return cmd_list(parsed)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
