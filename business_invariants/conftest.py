"""
Pytest integration for the Business Invariant Framework.

This conftest auto-discovers and registers all invariants as pytest tests.
Usage:
    pytest business_invariants/ -v
    pytest business_invariants/ -v -k "FIN-001 or DRV-003"

Each invariant runs as a normal pytest test with proper pass/fail semantics.
"""

from __future__ import annotations

import pytest

from business_invariants.config import default_invariant_config
from business_invariants.engine import InvariantRegistry
from business_invariants.models import (
    InvariantContext,
    InvariantStatus,
    Severity,
)
from business_invariants.reporter import ConsoleReporter


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom CLI options for the invariant framework."""
    parser.addoption(
        "--invariant-db",
        action="store",
        default=None,
        help="Database connection string for runtime invariant checks",
    )
    parser.addoption(
        "--invariant-frequency",
        action="store",
        default=None,
        help="Only run invariants matching this execution frequency",
    )
    parser.addoption(
        "--invariant-severity",
        action="store",
        default=None,
        help="Minimum severity threshold (LOW, MEDIUM, HIGH, CRITICAL)",
    )
    parser.addoption(
        "--invariant-category",
        action="store",
        default=None,
        help="Only run invariants in this category",
    )


def pytest_collect_file(file_path, parent):
    """Hook to discover invariant definition files as tests."""
    # This is handled by test_invariants.py which loads from registry
    return None


# ── Shared fixtures ──────────────────────────────────


@pytest.fixture(scope="session")
def invariant_registry() -> InvariantRegistry:
    """Return the global (fully loaded) invariant registry."""
    # Import all check modules to ensure registration
    import business_invariants.checks  # noqa: F401

    return InvariantRegistry.get_global()


@pytest.fixture(scope="function")
def invariant_context(request: pytest.FixtureRequest) -> InvariantContext:
    """Build the runtime context for invariant checks."""
    db = getattr(request, "_invariant_db", None)
    db_type = "sqlite" if db is None else "postgresql"
    return InvariantContext(
        db=db,
        db_type=db_type,
        config=default_invariant_config(),
        extra={
            "pytest_request": request,
            "node_id": request.node.nodeid if hasattr(request, "node") else "",
        },
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize test_invariant_check with all registered invariants."""
    if "invariant_def" not in metafunc.fixturenames:
        return

    # Load checks
    import business_invariants.checks  # noqa: F401

    registry = InvariantRegistry.get_global()
    definitions = registry.get_all()

    # Apply CLI filters
    freq = metafunc.config.getoption("--invariant-frequency")
    sev = metafunc.config.getoption("--invariant-severity")
    cat = metafunc.config.getoption("--invariant-category")

    filtered = []
    for d in definitions:
        if freq and not any(f.value == freq for f in d.meta.execution):
            continue
        if sev:
            min_sev = Severity.from_str(sev)
            if d.meta.severity < min_sev:
                continue
        if cat and d.meta.category.value != cat:
            continue
        filtered.append(d)

    metafunc.parametrize(
        "invariant_def",
        filtered,
        ids=[d.id for d in filtered],
        scope="function",
    )
