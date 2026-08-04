"""
Business Invariant Framework — Core Data Models

Defines the types used throughout the invariant system:
invariant definitions, execution context, results, reports.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class Severity(enum.IntEnum):
    """Impact severity if invariant is violated."""

    LOW = 10
    MEDIUM = 20
    HIGH = 30
    CRITICAL = 40

    def label(self) -> str:
        return self.name.title()

    @classmethod
    def from_str(cls, s: str) -> "Severity":
        normalized = s.strip().upper()
        for member in cls:
            if member.name == normalized:
                return member
            if member.label().upper() == normalized:
                return member
        raise ValueError(f"Unknown severity: {s!r}")


class ExecutionFrequency(enum.Enum):
    """How often an invariant should be validated."""

    COMMIT = "on_every_commit"
    PR = "on_pull_request"
    NIGHTLY = "nightly"
    WEEKLY = "weekly"
    RELEASE = "before_release"
    AFTER_MIGRATION = "after_migration"
    AFTER_AI_PATCH = "after_ai_patch"

    def label(self) -> str:
        labels = {
            "on_every_commit": "Every Commit",
            "on_pull_request": "Pull Request",
            "nightly": "Nightly",
            "weekly": "Weekly",
            "before_release": "Before Release",
            "after_migration": "After Migration",
            "after_ai_patch": "After AI Patch",
        }
        return labels.get(self.value, self.value)


class ExecutionScope(enum.Enum):
    """Scope of data to validate."""

    SCHEMA = "schema"
    DATA_INTEGRITY = "data_integrity"
    FINANCIAL = "financial"
    WORKFLOW = "workflow"
    PERMISSION = "permission"
    CONSISTENCY = "consistency"


class InvariantCategory(enum.Enum):
    """Business domain category."""

    FINANCIAL = "financial"
    FLEET = "fleet"
    DRIVERS = "drivers"
    TRIPS = "trips"
    ROUTES = "routes"
    DOCUMENTS = "documents"
    DISPATCH = "dispatch"
    AUTH = "auth"
    MULTITENANT = "multitenant"
    DATABASE = "database"
    AI_ARGO = "ai_argo"
    FREIGHT_EXCHANGE = "freight_exchange"
    ANALYTICS = "analytics"
    WORKFLOWS = "workflows"
    GENERAL = "general"

    def label(self) -> str:
        return self.name.replace("_", " ").title()


class InvariantStatus(enum.Enum):
    """Result status of a single invariant check."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


# ──────────────────────────────────────────────
# Core Data Classes
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class InvariantMeta:
    """Declarative metadata attached to an invariant check function."""

    id: str
    title: str
    description: str
    category: InvariantCategory
    modules: list[str]
    severity: Severity
    execution: list[ExecutionFrequency]
    rationale: str = ""
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class InvariantDefinition:
    """
    Full definition of a business invariant.

    Combines the static metadata with the runtime validation callable.
    """

    meta: InvariantMeta
    check_fn: Callable[["InvariantContext"], "InvariantResult"]

    @property
    def id(self) -> str:
        return self.meta.id

    @property
    def title(self) -> str:
        return self.meta.title

    @property
    def severity(self) -> Severity:
        return self.meta.severity


@dataclass
class InvariantContext:
    """
    Runtime context passed to every invariant check function.

    Carries all the dependencies a check needs: database connections,
    configuration, environment flags, and the scope of execution.
    """

    db: Optional[Any] = None
    db_type: str = "sqlite"
    config: dict[str, Any] = field(default_factory=dict)
    company_id: Optional[int] = None
    user_id: Optional[int] = None
    execution_frequency: Optional[ExecutionFrequency] = None
    scope: Optional[ExecutionScope] = None
    env: dict[str, str] = field(default_factory=dict)
    dry_run: bool = False

    # Allow arbitrary extra context
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class InvariantResult:
    """
    Result of executing a single invariant check.

    Includes pass/fail status, diagnostic details, and timing.
    """

    invariant_id: str
    status: InvariantStatus
    expected: str = ""
    actual: str = ""
    message: str = ""
    root_cause: str = ""
    suggested_fix: str = ""
    affected_modules: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == InvariantStatus.PASS

    @property
    def failed(self) -> bool:
        return self.status == InvariantStatus.FAIL

    @property
    def errored(self) -> bool:
        return self.status == InvariantStatus.ERROR


@dataclass
class InvariantReport:
    """
    Complete report covering an invariant execution run.

    Aggregates results, summary statistics, and risk assessment.
    """

    run_id: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    results: list[InvariantResult] = field(default_factory=list)
    critical_failures: list[InvariantResult] = field(default_factory=list)
    affected_modules: set[str] = field(default_factory=set)
    environment: str = ""

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return self.passed / (self.total - self.skipped) if (self.total - self.skipped) > 0 else 0.0

    @property
    def has_critical_failures(self) -> bool:
        return len(self.critical_failures) > 0

    @property
    def risk_level(self) -> str:
        if self.has_critical_failures:
            return "CRITICAL"
        if self.failed > 0:
            return "HIGH"
        if self.errors > 0:
            return "MEDIUM"
        return "LOW"

    def summary_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "success_rate": round(self.success_rate, 4),
            "risk_level": self.risk_level,
            "critical_failures": len(self.critical_failures),
            "affected_modules": sorted(self.affected_modules),
            "environment": self.environment,
        }


# ──────────────────────────────────────────────
# Helper: Severity shorthands
# ──────────────────────────────────────────────

CRITICAL = Severity.CRITICAL
HIGH = Severity.HIGH
MEDIUM = Severity.MEDIUM
LOW = Severity.LOW

COMMIT = ExecutionFrequency.COMMIT
PR = ExecutionFrequency.PR
NIGHTLY = ExecutionFrequency.NIGHTLY
WEEKLY = ExecutionFrequency.WEEKLY
RELEASE = ExecutionFrequency.RELEASE
AFTER_MIGRATION = ExecutionFrequency.AFTER_MIGRATION
AFTER_AI_PATCH = ExecutionFrequency.AFTER_AI_PATCH
