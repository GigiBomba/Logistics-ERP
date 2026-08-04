"""
Business Invariant Framework — Registry & Execution Engine

Maintains the global registry of invariants and provides
the engine that executes them, collects results, and produces reports.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Callable, Optional

from business_invariants.models import (
    ExecutionFrequency,
    InvariantContext,
    InvariantDefinition,
    InvariantMeta,
    InvariantReport,
    InvariantResult,
    InvariantStatus,
    Severity,
)


class InvariantRegistry:
    """
    Thread-safe registry of all business invariants.

    Maintains the canonical list of InvariantDefinitions and
    provides filtering by category, severity, execution frequency, etc.
    """

    _global_instance: Optional["InvariantRegistry"] = None

    def __init__(self) -> None:
        self._definitions: dict[str, InvariantDefinition] = {}

    # ── Global singleton ──────────────────────────────────

    @classmethod
    def get_global(cls) -> "InvariantRegistry":
        """Return or create the global registry singleton."""
        if cls._global_instance is None:
            cls._global_instance = cls()
        return cls._global_instance

    @classmethod
    def reset_global(cls) -> None:
        """Clear the global registry (useful in tests)."""
        cls._global_instance = None

    # ── Registration ──────────────────────────────────────

    def register(
        self,
        meta: InvariantMeta,
        check_fn: Callable[["InvariantContext"], "InvariantResult"],
    ) -> InvariantDefinition:
        """Register an invariant definition."""
        if meta.id in self._definitions:
            raise ValueError(
                f"Invariant {meta.id!r} is already registered. "
                f"Existing: {self._definitions[meta.id].title!r}"
            )
        definition = InvariantDefinition(meta=meta, check_fn=check_fn)
        self._definitions[meta.id] = definition
        return definition

    def register_definition(self, definition: InvariantDefinition) -> InvariantDefinition:
        """Register a pre-built InvariantDefinition."""
        if definition.id in self._definitions:
            raise ValueError(f"Invariant {definition.id!r} is already registered.")
        self._definitions[definition.id] = definition
        return definition

    # ── Lookup ────────────────────────────────────────────

    def get(self, invariant_id: str) -> Optional[InvariantDefinition]:
        return self._definitions.get(invariant_id)

    def get_all(self) -> list[InvariantDefinition]:
        return list(self._definitions.values())

    def count(self) -> int:
        return len(self._definitions)

    # ── Filtering ─────────────────────────────────────────

    def filter(
        self,
        categories: Optional[set[str]] = None,
        severities: Optional[set[str]] = None,
        frequencies: Optional[set[ExecutionFrequency]] = None,
        min_severity: Optional[Severity] = None,
        tags: Optional[set[str]] = None,
        modules: Optional[set[str]] = None,
        ids: Optional[set[str]] = None,
    ) -> list[InvariantDefinition]:
        """
        Return definitions matching ALL specified filters.

        Parameters
        ----------
        categories: Only invariants in these categories
        severities: Only invariants with these severity names
        frequencies: Only invariants runnable at these frequencies
        min_severity: Only invariants at this severity or higher
        tags: Only invariants with ANY of these tags
        modules: Only invariants affecting ANY of these modules
        ids: Only invariants with these specific IDs
        """
        results: list[InvariantDefinition] = []

        for defn in self._definitions.values():
            meta = defn.meta

            if categories and meta.category.value not in categories:
                continue
            if severities and meta.severity.name not in severities:
                continue
            if min_severity and meta.severity < min_severity:
                continue
            if frequencies and not any(f in meta.execution for f in frequencies):
                continue
            if tags and not any(t in meta.tags for t in tags):
                continue
            if modules and not any(m in meta.modules for m in modules):
                continue
            if ids and meta.id not in ids:
                continue

            results.append(defn)

        # Sort by severity (most critical first), then by ID
        results.sort(key=lambda d: (-d.meta.severity.value, d.meta.id))
        return results

    def filter_by_frequency(self, frequency: ExecutionFrequency) -> list[InvariantDefinition]:
        """Return all invariants that should run at the given frequency."""
        return self.filter(frequencies={frequency})

    # ── Dependency ordering ───────────────────────────────

    def topological_sort(self, selected: list[InvariantDefinition]) -> list[InvariantDefinition]:
        """
        Topological sort so dependencies run before dependents.
        Unspecified dependencies are excluded from the result.
        """
        selected_ids = {d.id for d in selected}
        selected_map = {d.id: d for d in selected}

        visited: set[str] = set()
        sorted_list: list[InvariantDefinition] = []

        def visit(defn_id: str) -> None:
            if defn_id in visited:
                return
            visited.add(defn_id)
            defn = selected_map.get(defn_id)
            if defn is None:
                return
            for dep_id in defn.meta.dependencies:
                if dep_id in selected_ids:
                    visit(dep_id)
            sorted_list.append(defn)

        for defn in selected:
            visit(defn.id)

        return sorted_list


class InvariantEngine:
    """
    Orchestrates the execution of business invariants.

    Usage::

        engine = InvariantEngine()
        ctx = InvariantContext(db=db_connection)
        report = engine.run_all(ctx)
        print(report.summary_dict())
    """

    def __init__(self, registry: Optional[InvariantRegistry] = None) -> None:
        self.registry = registry or InvariantRegistry.get_global()

    # ── Running ───────────────────────────────────────────

    def run(
        self,
        ctx: InvariantContext,
        invariant_ids: Optional[set[str]] = None,
    ) -> InvariantReport:
        """
        Run specific invariants by ID.

        Parameters
        ----------
        ctx: Runtime context
        invariant_ids: Set of invariant IDs to run (None = all registered)
        """
        if invariant_ids:
            definitions = [d for d in self.registry.get_all() if d.id in invariant_ids]
            definitions.sort(key=lambda d: (-d.meta.severity.value, d.meta.id))
        else:
            definitions = self.registry.get_all()

        definitions = self.registry.topological_sort(definitions)
        return self._execute(definitions, ctx)

    def run_filtered(
        self,
        ctx: InvariantContext,
        categories: Optional[set[str]] = None,
        severities: Optional[set[str]] = None,
        frequencies: Optional[set[ExecutionFrequency]] = None,
        min_severity: Optional[Severity] = None,
        tags: Optional[set[str]] = None,
        modules: Optional[set[str]] = None,
    ) -> InvariantReport:
        """
        Run invariants matching the given filters.
        """
        definitions = self.registry.filter(
            categories=categories,
            severities=severities,
            frequencies=frequencies,
            min_severity=min_severity,
            tags=tags,
            modules=modules,
        )
        definitions = self.registry.topological_sort(definitions)
        return self._execute(definitions, ctx)

    def run_all(self, ctx: InvariantContext) -> InvariantReport:
        """Run all registered invariants."""
        definitions = self.registry.get_all()
        definitions = self.registry.topological_sort(definitions)
        return self._execute(definitions, ctx)

    def run_for_frequency(
        self,
        frequency: ExecutionFrequency,
        ctx: InvariantContext,
    ) -> InvariantReport:
        """Run invariants matching a specific execution frequency."""
        ctx.execution_frequency = frequency
        return self.run_filtered(ctx, frequencies={frequency})

    # ── Internal ──────────────────────────────────────────

    def _execute(
        self,
        definitions: list[InvariantDefinition],
        ctx: InvariantContext,
    ) -> InvariantReport:
        report = InvariantReport(
            run_id=f"inv-{uuid.uuid4().hex[:12]}",
            started_at=datetime.utcnow(),
        )
        results: list[InvariantResult] = []
        critical_failures: list[InvariantResult] = []
        affected_modules: set[str] = set()

        start = time.perf_counter()

        for defn in definitions:
            # Check dependencies
            deps_satisfied = True
            for dep_id in defn.meta.dependencies:
                dep_result = next(
                    (r for r in results if r.invariant_id == dep_id), None
                )
                if dep_result and dep_result.failed:
                    deps_satisfied = False
                    result = InvariantResult(
                        invariant_id=defn.id,
                        status=InvariantStatus.SKIPPED,
                        message=f"Dependency {dep_id} failed — skipping",
                        affected_modules=list(defn.meta.modules),
                    )
                    results.append(result)
                    report.skipped += 1
                    break

            if not deps_satisfied:
                continue

            # Execute
            t0 = time.perf_counter()
            try:
                result = defn.check_fn(ctx)
            except Exception as exc:
                t1 = time.perf_counter()
                result = InvariantResult(
                    invariant_id=defn.id,
                    status=InvariantStatus.ERROR,
                    message=f"Invariant raised an exception: {exc}",
                    root_cause=str(exc),
                    affected_modules=list(defn.meta.modules),
                    duration_ms=(t1 - t0) * 1000,
                )

            result.duration_ms = (time.perf_counter() - t0) * 1000
            if not result.affected_modules:
                result.affected_modules = list(defn.meta.modules)

            results.append(result)
            affected_modules.update(result.affected_modules)

            if result.passed:
                report.passed += 1
            elif result.failed:
                report.failed += 1
                if defn.meta.severity == Severity.CRITICAL:
                    critical_failures.append(result)
            elif result.errored:
                report.errors += 1
            else:
                report.skipped += 1

        report.duration_ms = (time.perf_counter() - start) * 1000
        report.completed_at = datetime.utcnow()
        report.results = results
        report.critical_failures = critical_failures
        report.affected_modules = affected_modules
        report.total = report.passed + report.failed + report.errors + report.skipped

        return report
