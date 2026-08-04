"""
Pytest test that discovers and runs all registered business invariants.

This test integrates the Business Invariant Framework with the existing
pytest infrastructure. It discovers all @invariant-decorated functions,
executes them, and reports results as standard pytest test cases.

Usage:
    pytest tests/test_business_invariants.py -v
    pytest tests/test_business_invariants.py -v -k "FIN-001"
    pytest tests/test_business_invariants.py -v --invariant-severity CRITICAL
"""

from __future__ import annotations

import pytest

from business_invariants.config import default_invariant_config
from business_invariants.engine import InvariantRegistry
from business_invariants.models import (
    InvariantContext,
    InvariantDefinition,
    InvariantResult,
    InvariantStatus,
    Severity,
)
from business_invariants.reporter import ConsoleReporter


# ── Fixtures (re-registered here so they're available from tests/) ──


@pytest.fixture(scope="session")
def invariant_registry() -> InvariantRegistry:
    """Return the global (fully loaded) invariant registry."""
    import business_invariants.checks  # noqa: F401
    return InvariantRegistry.get_global()


@pytest.fixture(scope="function")
def invariant_context() -> InvariantContext:
    """Build the runtime context for invariant checks."""
    import os
    return InvariantContext(
        db=None,
        db_type="sqlite",
        config=default_invariant_config(),
        env={
            "JWT_ALGORITHM": os.environ.get("JWT_ALGORITHM", "HS256"),
            "JWT_SECRET": os.environ.get("JWT_SECRET", "a" * 64),
            "BF_ENABLED": os.environ.get("BF_ENABLED", "true"),
            "BF_MAX_ATTEMPTS": os.environ.get("BF_MAX_ATTEMPTS", "5"),
            "BF_WINDOW_MINUTES": os.environ.get("BF_WINDOW_MINUTES", "5"),
            "BF_LOCKOUT_MINUTES": os.environ.get("BF_LOCKOUT_MINUTES", "15"),
        },
        extra={},
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize test_invariant_check with all registered invariants."""
    if "invariant_def" not in metafunc.fixturenames:
        return
    import business_invariants.checks  # noqa: F401
    registry = InvariantRegistry.get_global()
    definitions = registry.get_all()
    metafunc.parametrize(
        "invariant_def",
        definitions,
        ids=[d.id for d in definitions],
        scope="function",
    )


def test_invariant_check(
    invariant_def: InvariantDefinition,
    invariant_context: InvariantContext,
) -> None:
    """
    Execute a single business invariant and assert it passes.
    This test is parametrized by pytest_generate_tests in conftest.py.
    """
    result = invariant_def.check_fn(invariant_context)

    if result.status == InvariantStatus.PASS:
        assert True
    elif result.status == InvariantStatus.FAIL:
        msg = (
            f"[{result.invariant_id}] FAILED\n"
            f"  Expected: {result.expected}\n"
            f"  Actual:   {result.actual}\n"
        )
        if result.root_cause:
            msg += f"  Root cause: {result.root_cause}\n"
        if result.suggested_fix:
            msg += f"  Suggested fix: {result.suggested_fix}\n"
        if result.details:
            msg += f"  Details: {result.details}\n"
        pytest.fail(msg)
    elif result.status == InvariantStatus.ERROR:
        pytest.fail(
            f"[{result.invariant_id}] ERROR: {result.message}\n"
            f"  Root cause: {result.root_cause}"
        )
    elif result.status == InvariantStatus.SKIPPED:
        pytest.skip(f"[{result.invariant_id}] Skipped: {result.message}")


# ── Convenience test classes for grouped runs ──


class TestCriticalInvariants:
    """Run only CRITICAL invariants."""

    @pytest.fixture(params=[
        d for d in InvariantRegistry.get_global().get_all()
        if d.meta.severity == Severity.CRITICAL
    ], ids=lambda d: d.id)
    def critical_invariant(self, request):
        return request.param

    def test_critical_invariant(self, critical_invariant, invariant_context):
        result = critical_invariant.check_fn(invariant_context)
        assert result.passed, (
            f"CRITICAL invariant {critical_invariant.id} failed: {result.message}"
        )


class TestFinancialInvariants:
    """Run only FINANCIAL category invariants."""

    @pytest.fixture(params=[
        d for d in InvariantRegistry.get_global().get_all()
        if d.meta.category.value == "financial"
    ], ids=lambda d: d.id)
    def financial_invariant(self, request):
        return request.param

    def test_financial_invariant(self, financial_invariant, invariant_context):
        result = financial_invariant.check_fn(invariant_context)
        assert result.passed, (
            f"Financial invariant {financial_invariant.id} failed: {result.message}"
        )


# ── Full report generation ──


def test_invariant_report(invariant_registry: InvariantRegistry) -> None:
    """
    Generate and print a full invariant report.
    This test always passes but outputs the complete report for logging.
    """
    import os
    from business_invariants.engine import InvariantEngine

    engine = InvariantEngine(invariant_registry)
    ctx = InvariantContext(
        config=default_invariant_config(),
        env={
            "JWT_ALGORITHM": os.environ.get("JWT_ALGORITHM", "HS256"),
            "JWT_SECRET": os.environ.get("JWT_SECRET", "a" * 64),
            "BF_ENABLED": os.environ.get("BF_ENABLED", "true"),
            "BF_MAX_ATTEMPTS": os.environ.get("BF_MAX_ATTEMPTS", "5"),
            "BF_WINDOW_MINUTES": os.environ.get("BF_WINDOW_MINUTES", "5"),
            "BF_LOCKOUT_MINUTES": os.environ.get("BF_LOCKOUT_MINUTES", "15"),
        },
    )
    report = engine.run_all(ctx)

    reporter = ConsoleReporter()
    reporter.report(report)

    # Print summary to test output
    print(f"\nInvariant Report Summary:")
    print(f"  Total: {report.total} | Passed: {report.passed} | "
          f"Failed: {report.failed} | Errors: {report.errors} | Skipped: {report.skipped}")
    print(f"  Duration: {report.duration_ms:.1f} ms | Risk: {report.risk_level}")

    # Log any failures
    for result in report.results:
        if result.failed:
            print(f"  FAIL: [{result.invariant_id}] {result.message}")
        if result.errored:
            print(f"  ERROR: [{result.invariant_id}] {result.message}")

    # Deployment gate: critical failures should block
    if report.has_critical_failures:
        pytest.fail(
            f"DEPLOYMENT BLOCKED: {len(report.critical_failures)} critical "
            f"invariant(s) failed. See report above."
        )

    # Non-critical failures: warn but don't fail the gate test
    if report.failed > 0:
        import warnings
        warnings.warn(
            f"{report.failed} non-critical invariant(s) failed — review recommended"
        )
