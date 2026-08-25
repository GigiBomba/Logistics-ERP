"""
Invariant History & Trend Analysis System

Transforms the Business Invariant Framework into a historical reliability monitoring
system. Every execution produces a permanent historical record, enabling trend analysis,
stability scoring, regression detection, and release comparison.

Requires the `business_invariants` package.
"""
from __future__ import annotations


from invariant_history.models import (
    ExecutionTrigger,
    HistoryExecutionRecord,
    HistoryInvariantRecord,
    HistoryQuery,
    HistoryPage,
    StabilityIndex,
    ModuleReliability,
    TrendPoint,
    TrendResult,
    RegressionReport,
    ReleaseComparison,
    DashboardData,
)
from invariant_history.storage import HistoryStorage
from invariant_history.trends import TrendEngine
from invariant_history.stability import StabilityScorer
from invariant_history.regression import RegressionDetector
from invariant_history.reports import ReportGenerator
from invariant_history.dashboards import DashboardBuilder
from invariant_history.ai_interface import AIQueryInterface

__all__ = [
    "ExecutionTrigger",
    "HistoryExecutionRecord",
    "HistoryInvariantRecord",
    "HistoryQuery",
    "HistoryPage",
    "StabilityIndex",
    "ModuleReliability",
    "TrendPoint",
    "TrendResult",
    "RegressionReport",
    "ReleaseComparison",
    "DashboardData",
    "HistoryStorage",
    "TrendEngine",
    "StabilityScorer",
    "RegressionDetector",
    "ReportGenerator",
    "DashboardBuilder",
    "AIQueryInterface",
]
