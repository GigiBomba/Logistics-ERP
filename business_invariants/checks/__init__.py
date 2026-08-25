"""
All business invariant check functions live in this package.

Each module registers invariants via the @invariant decorator.
Modules are auto-discovered by the CLI and test runner.

To add a new invariant:
    1. Identify the business truth and its metadata (id, title, severity, etc.)
    2. Add the check function in the appropriate category module
    3. Decorate with @invariant(...) — all metadata is declared in the decorator
    4. Import the module in business_invariants/cli.py:_load_checks()
    5. Done — the invariant is auto-registered on import
"""
from __future__ import annotations


from business_invariants.checks import (
    financial,
    fleet,
    drivers,
    trips,
    routes,
    documents,
    dispatch,
    auth_security,
    multitenant,
    database,
    ai_argo,
    freight_exchange,
    analytics,
    workflows,
)

__all__ = [
    "financial",
    "fleet",
    "drivers",
    "trips",
    "routes",
    "documents",
    "dispatch",
    "auth_security",
    "multitenant",
    "database",
    "ai_argo",
    "freight_exchange",
    "analytics",
    "workflows",
]
