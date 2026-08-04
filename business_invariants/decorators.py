"""
Business Invariant Framework — Decorators

Provides the @invariant decorator for declarative invariant definition.
"""

from __future__ import annotations

import functools
from typing import Callable, Optional

from business_invariants.models import (
    ExecutionFrequency,
    InvariantCategory,
    InvariantContext,
    InvariantMeta,
    InvariantResult,
    Severity,
)
from business_invariants.engine import InvariantRegistry


def invariant(
    id: str,
    title: str,
    description: str,
    category: InvariantCategory | str,
    modules: list[str] | None = None,
    severity: Severity | str = Severity.MEDIUM,
    execution: list[ExecutionFrequency | str] | None = None,
    rationale: str = "",
    dependencies: list[str] | None = None,
    tags: list[str] | None = None,
    registry: Optional[InvariantRegistry] = None,
):
    """
    Decorator that registers a function as a business invariant check.

    Usage::

        @invariant(
            id="FIN-001",
            title="Invoice subtotal + VAT = total",
            description="For every invoice, total_gross must equal subtotal_net + total_vat",
            category=InvariantCategory.FINANCIAL,
            modules=["invoicing"],
            severity=Severity.CRITICAL,
            execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.NIGHTLY],
        )
        def check_invoice_totals(ctx: InvariantContext) -> InvariantResult:
            ...

    Parameters
    ----------
    id: Unique identifier (e.g., "FIN-001")
    title: Human-readable title
    description: Detailed explanation of what is being checked
    category: Business domain category
    modules: Affected module names
    severity: Impact severity if violated
    execution: When this invariant should run
    rationale: Business justification
    dependencies: IDs of invariants that must pass first
    tags: Free-form tags for filtering
    registry: Registry to register with (uses global if None)
    """
    if modules is None:
        modules = []
    if execution is None:
        execution = [ExecutionFrequency.COMMIT]
    if dependencies is None:
        dependencies = []
    if tags is None:
        tags = []

    # Normalize category
    if isinstance(category, str):
        category = InvariantCategory(category)

    # Normalize severity
    if isinstance(severity, str):
        severity = Severity.from_str(severity)

    # Normalize execution frequencies
    normalized_execution: list[ExecutionFrequency] = []
    for freq in execution:
        if isinstance(freq, str):
            normalized_execution.append(ExecutionFrequency(freq))
        else:
            normalized_execution.append(freq)

    meta = InvariantMeta(
        id=id,
        title=title,
        description=description,
        category=category,
        modules=modules,
        severity=severity,
        execution=normalized_execution,
        rationale=rationale,
        dependencies=dependencies,
        tags=tags,
    )

    def decorator(
        fn: Callable[[InvariantContext], InvariantResult],
    ) -> Callable[[InvariantContext], InvariantResult]:
        reg = registry or InvariantRegistry.get_global()

        @functools.wraps(fn)
        def wrapper(ctx: InvariantContext) -> InvariantResult:
            return fn(ctx)

        reg.register(meta=meta, check_fn=wrapper)
        return wrapper

    return decorator
