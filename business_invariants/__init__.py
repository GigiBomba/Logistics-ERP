"""
Operion Business Invariant Framework

Ensures that future development, AI-generated code, refactors, database migrations,
and autonomous bug fixes can never silently break the business logic of Operion ERP.

This is NOT a test suite. It defines the fundamental truths of the business
that must always remain valid, regardless of implementation details.
"""

from business_invariants.models import (
    ExecutionFrequency,
    ExecutionScope,
    InvariantCategory,
    InvariantContext,
    InvariantDefinition,
    InvariantResult,
    InvariantReport,
    InvariantStatus,
    Severity,
)
from business_invariants.engine import InvariantRegistry, InvariantEngine
from business_invariants.decorators import invariant

__all__ = [
    "ExecutionFrequency",
    "ExecutionScope",
    "InvariantCategory",
    "InvariantContext",
    "InvariantDefinition",
    "InvariantResult",
    "InvariantReport",
    "InvariantStatus",
    "Severity",
    "InvariantRegistry",
    "InvariantEngine",
    "invariant",
]
