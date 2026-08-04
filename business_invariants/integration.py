"""
Integration bridge: Business Invariant Framework → History System.

This module auto-registers a post-execution hook on InvariantEngine so that
every invariant run is automatically captured into the history system.

No existing framework code is modified. The hook is installed by calling
``auto_integrate()`` which monkey-patches the engine class methods so that
every future invocation of ``run()``, ``run_all()``, ``run_filtered()``,
and ``run_for_frequency()`` records its results into the history system.

Usage::

    # In your application startup:
    from business_invariants.integration import auto_integrate
    storage = auto_integrate()

    # Or with custom storage:
    from invariant_history.storage import HistoryStorage
    storage = HistoryStorage()
    from business_invariants.integration import install_history_hook
    install_history_hook(storage)

    # All subsequent invariant runs are recorded automatically.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Any, Optional

from business_invariants.engine import InvariantEngine
from business_invariants.models import (
    ExecutionFrequency,
    InvariantContext,
    InvariantReport,
    Severity,
)
from invariant_history.models import (
    HistoryExecutionRecord,
    HistoryInvariantRecord,
)
from invariant_history.storage import HistoryStorage


# Module-level singleton
_storage: Optional[HistoryStorage] = None
_hooks_installed: bool = False


def get_git_info() -> tuple[str, str]:
    """Get current git commit hash and branch."""
    commit = ""
    branch = ""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        commit = os.environ.get("GIT_COMMIT", "")
        branch = os.environ.get("GIT_BRANCH", "")
    return commit, branch


def build_history_record(
    report: InvariantReport,
    trigger: str = "manual",
) -> HistoryExecutionRecord:
    """
    Convert an InvariantReport into a HistoryExecutionRecord.

    Parameters
    ----------
    report: The report from InvariantEngine.run*()
    trigger: Execution trigger (commit, pull_request, nightly, etc.)
    """
    git_commit, git_branch = get_git_info()

    invariants: list[HistoryInvariantRecord] = []
    for result in report.results:
        severity = _get_severity_for_invariant(result.invariant_id)
        invariants.append(
            HistoryInvariantRecord(
                invariant_id=result.invariant_id,
                title=result.invariant_id,  # The result doesn't carry title — will improve later
                category="",
                severity=severity,
                execution_time_ms=result.duration_ms,
                result=result.status.value,
                failure_reason=result.message if result.failed else "",
                module=", ".join(result.affected_modules) if result.affected_modules else "",
                affected_files=[],
                execution_context={},
            )
        )

    return HistoryExecutionRecord(
        execution_id=report.run_id,
        timestamp=datetime.utcnow().isoformat(),
        git_commit_hash=git_commit,
        git_branch=git_branch,
        application_version=os.environ.get("APP_VERSION", ""),
        build_number=os.environ.get("BUILD_NUMBER", ""),
        environment=os.environ.get("OPERION_ENV", "development"),
        execution_trigger=trigger,
        execution_duration_ms=report.duration_ms,
        total_invariants=report.total,
        passed=report.passed,
        failed=report.failed,
        warnings=report.errors,
        critical_failures=len(report.critical_failures),
        risk_level=report.risk_level,
        invariants=invariants,
        affected_modules=sorted(report.affected_modules),
    )


def _get_severity_for_invariant(invariant_id: str) -> str:
    """Look up severity from the global registry."""
    try:
        from business_invariants.engine import InvariantRegistry

        reg = InvariantRegistry.get_global()
        defn = reg.get(invariant_id)
        if defn:
            return defn.meta.severity.label()
    except Exception:
        pass
    return "MEDIUM"


def capture_execution(
    report: InvariantReport,
    trigger: str = "manual",
    storage: Optional[HistoryStorage] = None,
) -> HistoryExecutionRecord:
    """
    Capture an invariant execution into the history system.

    This is the primary integration function. Call it after any
    InvariantEngine.run*() call.

    Parameters
    ----------
    report: The report from InvariantEngine.run*()
    trigger: Execution trigger identifier
    storage: History storage instance (uses module singleton if None)
    """
    s = storage or _get_storage()
    record = build_history_record(report, trigger)
    s.store_execution(record)
    return record


# ── Class-level monkey-patching ──────────────────────────

def install_history_hook(
    storage: Optional[HistoryStorage] = None,
    trigger: str = "manual",
) -> HistoryStorage:
    """
    Install a post-execution hook on InvariantEngine.

    After calling this, ALL invariant runs via InvariantEngine will
    automatically be recorded in history.

    This monkey-patches the class methods themselves so that every
    instance of InvariantEngine — existing or future — will have
    the history capture hook.

    Parameters
    ----------
    storage: HistoryStorage instance (creates default if None)
    trigger: Default execution trigger label
    """
    global _storage, _hooks_installed

    s = storage or HistoryStorage()
    _storage = s

    if _hooks_installed:
        return s

    # ── Save originals ──────────────────────────────────
    _original_run_all = InvariantEngine.run_all
    _original_run = InvariantEngine.run
    _original_run_filtered = InvariantEngine.run_filtered
    _original_run_for_frequency = InvariantEngine.run_for_frequency

    # ── Wrappers ────────────────────────────────────────

    def _hooked_run_all(
        self: InvariantEngine,
        ctx: InvariantContext,
    ) -> InvariantReport:
        report = _original_run_all(self, ctx)
        try:
            capture_execution(report, trigger=trigger, storage=s)
        except Exception:
            pass  # Never let history failure break invariants
        return report

    def _hooked_run(
        self: InvariantEngine,
        ctx: InvariantContext,
        invariant_ids: Optional[set[str]] = None,
    ) -> InvariantReport:
        report = _original_run(self, ctx, invariant_ids=invariant_ids)
        try:
            capture_execution(report, trigger=trigger, storage=s)
        except Exception:
            pass
        return report

    def _hooked_run_filtered(
        self: InvariantEngine,
        ctx: InvariantContext,
        categories: Optional[set[str]] = None,
        severities: Optional[set[str]] = None,
        frequencies: Optional[set[ExecutionFrequency]] = None,
        min_severity: Optional[Severity] = None,
        tags: Optional[set[str]] = None,
        modules: Optional[set[str]] = None,
    ) -> InvariantReport:
        report = _original_run_filtered(
            self,
            ctx,
            categories=categories,
            severities=severities,
            frequencies=frequencies,
            min_severity=min_severity,
            tags=tags,
            modules=modules,
        )
        try:
            capture_execution(report, trigger=trigger, storage=s)
        except Exception:
            pass
        return report

    def _hooked_run_for_frequency(
        self: InvariantEngine,
        frequency: ExecutionFrequency,
        ctx: InvariantContext,
    ) -> InvariantReport:
        report = _original_run_for_frequency(self, frequency, ctx)
        try:
            capture_execution(report, trigger=trigger, storage=s)
        except Exception:
            pass
        return report

    # ── Apply patches ───────────────────────────────────
    InvariantEngine.run_all = _hooked_run_all  # type: ignore[assignment]
    InvariantEngine.run = _hooked_run  # type: ignore[assignment]
    InvariantEngine.run_filtered = _hooked_run_filtered  # type: ignore[assignment]
    InvariantEngine.run_for_frequency = _hooked_run_for_frequency  # type: ignore[assignment]

    _hooks_installed = True
    return s


def auto_integrate(
    data_dir: Optional[str] = None,
    trigger: str = "manual",
) -> HistoryStorage:
    """
    One-call setup: create storage, install hook, return storage.

    Call this once at application startup to enable automatic history
    capture for all invariant executions.

    Parameters
    ----------
    data_dir: Optional custom data directory for history storage
    trigger: Default execution trigger label
    """
    s = HistoryStorage(data_dir)
    install_history_hook(s, trigger=trigger)
    return s


def _get_storage() -> HistoryStorage:
    """Return the module-level storage singleton, creating it if needed."""
    global _storage
    if _storage is None:
        _storage = HistoryStorage()
    return _storage
