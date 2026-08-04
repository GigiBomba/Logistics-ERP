"""
Invariant History — Data Models

Every execution record, invariant record, query, trend, dashboard model.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class ExecutionTrigger(enum.Enum):
    """What triggered the invariant execution."""

    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    NIGHTLY = "nightly"
    RELEASE = "release"
    AI_PATCH = "ai_patch"
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CI = "ci"

    @classmethod
    def from_frequency(cls, freq_str: str) -> "ExecutionTrigger":
        mapping = {
            "on_every_commit": cls.COMMIT,
            "on_pull_request": cls.PULL_REQUEST,
            "nightly": cls.NIGHTLY,
            "weekly": cls.SCHEDULED,
            "before_release": cls.RELEASE,
            "after_migration": cls.MANUAL,
            "after_ai_patch": cls.AI_PATCH,
        }
        return mapping.get(freq_str, cls.MANUAL)


# ──────────────────────────────────────────────
# History Records
# ──────────────────────────────────────────────


@dataclass
class HistoryInvariantRecord:
    """Record of a single invariant execution within a run."""

    invariant_id: str
    title: str
    category: str
    severity: str
    execution_time_ms: float
    result: str  # "pass" | "fail" | "warning"
    failure_reason: str = ""
    module: str = ""
    affected_files: list[str] = field(default_factory=list)
    execution_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class HistoryExecutionRecord:
    """Record of one complete invariant framework execution."""

    execution_id: str
    timestamp: str  # ISO-8601
    git_commit_hash: str = ""
    git_branch: str = ""
    application_version: str = ""
    build_number: str = ""
    environment: str = ""
    execution_trigger: str = "manual"
    execution_duration_ms: float = 0.0
    total_invariants: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    critical_failures: int = 0
    risk_level: str = "LOW"
    invariants: list[HistoryInvariantRecord] = field(default_factory=list)
    affected_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "timestamp": self.timestamp,
            "git_commit_hash": self.git_commit_hash,
            "git_branch": self.git_branch,
            "application_version": self.application_version,
            "build_number": self.build_number,
            "environment": self.environment,
            "execution_trigger": self.execution_trigger,
            "execution_duration_ms": self.execution_duration_ms,
            "total_invariants": self.total_invariants,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "critical_failures": self.critical_failures,
            "risk_level": self.risk_level,
            "invariants": [i.__dict__ for i in self.invariants],
            "affected_modules": self.affected_modules,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HistoryExecutionRecord":
        invariants = [HistoryInvariantRecord(**i) for i in d.get("invariants", [])]
        d = {k: v for k, v in d.items() if k != "invariants"}
        record = cls(**d)
        record.invariants = invariants
        return record


# ──────────────────────────────────────────────
# Query & Pagination
# ──────────────────────────────────────────────


@dataclass
class HistoryQuery:
    """Filter for querying execution history."""

    limit: int = 100
    offset: int = 0
    trigger: Optional[str] = None
    environment: Optional[str] = None
    min_severity: Optional[str] = None
    module: Optional[str] = None
    invariant_id: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None
    version: Optional[str] = None
    branch: Optional[str] = None
    only_failures: bool = False
    only_critical: bool = False


@dataclass
class HistoryPage:
    """Paginated query result."""

    items: list[HistoryExecutionRecord]
    total: int
    offset: int
    limit: int
    has_more: bool


# ──────────────────────────────────────────────
# Trend Analysis
# ──────────────────────────────────────────────


@dataclass
class TrendPoint:
    """A single data point in a trend line."""

    label: str  # execution_id or date
    value: float
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendResult:
    """Result of a trend analysis query."""

    metric: str
    points: list[TrendPoint]
    period_start: str
    period_end: str
    sample_count: int
    min_value: float = 0.0
    max_value: float = 0.0
    avg_value: float = 0.0
    trend_direction: str = "stable"  # "improving" | "degrading" | "stable"
    change_pct: float = 0.0


# ──────────────────────────────────────────────
# Stability
# ──────────────────────────────────────────────


@dataclass
class ModuleReliability:
    """Reliability score for a single module."""

    module: str
    reliability_pct: float  # 0-100
    total_executions: int = 0
    total_invariants: int = 0
    passed: int = 0
    failed: int = 0
    trend: str = "stable"
    last_failure: Optional[str] = None
    avg_execution_time_ms: float = 0.0


@dataclass
class StabilityIndex:
    """Overall system stability score (0-100)."""

    score: float
    pass_rate: float
    critical_failure_rate: float
    avg_execution_time_ms: float
    module_reliability_avg: float
    regression_count: int
    sample_size: int
    period_start: str
    period_end: str
    modules: list[ModuleReliability] = field(default_factory=list)


# ──────────────────────────────────────────────
# Regression
# ──────────────────────────────────────────────


@dataclass
class RegressionReport:
    """Report of detected regressions in a comparison."""

    new_failures: list[dict[str, Any]] = field(default_factory=list)
    pass_to_fail: list[dict[str, Any]] = field(default_factory=list)
    execution_time_spikes: list[dict[str, Any]] = field(default_factory=list)
    reliability_decreases: list[dict[str, Any]] = field(default_factory=list)
    new_invariants: list[str] = field(default_factory=list)
    removed_invariants: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Release Comparison
# ──────────────────────────────────────────────


@dataclass
class ReleaseComparison:
    """Comparison between two releases/executions."""

    baseline_id: str
    baseline_version: str
    baseline_timestamp: str
    target_id: str
    target_version: str
    target_timestamp: str
    pass_rate_change: float = 0.0
    failure_count_change: int = 0
    execution_time_change_pct: float = 0.0
    critical_failure_change: int = 0
    reliability_change: float = 0.0
    stability_change: float = 0.0
    regressions: RegressionReport = field(default_factory=RegressionReport)


# ──────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────


@dataclass
class DashboardData:
    """Complete dashboard data for visualization."""

    stability: StabilityIndex
    pass_rate_trend: TrendResult
    critical_failures_trend: TrendResult
    execution_time_trend: TrendResult
    slowest_invariants: list[dict[str, Any]]
    most_failing_invariants: list[dict[str, Any]]
    module_reliabilities: list[ModuleReliability]
    recent_regressions: RegressionReport
    top_stable_modules: list[dict[str, Any]]
    top_unstable_modules: list[dict[str, Any]]
    last_execution: Optional[HistoryExecutionRecord] = None
    execution_count: int = 0
    period_days: int = 30
