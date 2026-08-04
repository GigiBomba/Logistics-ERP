"""
Invariant History — Markdown Report Generator

Produces production-quality Markdown reports for the Invariant History System.
Reports are written to ``docs/Invariant_History_Report.md`` and used by
Operion Ops Console for stakeholder review.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from invariant_history.models import (
    DashboardData,
    HistoryExecutionRecord,
    ModuleReliability,
    RegressionReport,
    ReleaseComparison,
    StabilityIndex,
    TrendResult,
)


# ── Helpers ─────────────────────────────────────────────

def _int_change(value: int) -> str:
    """Format an integer change with a + sign for positive values."""
    if value > 0:
        return f"+{value}"
    if value < 0:
        return str(value)
    return "0"

def _trend_icon(direction: str) -> str:
    """Return an emoji icon for a trend direction."""
    if direction == "improving":
        return "📈"
    if direction == "degrading":
        return "📉"
    return "➡️"


class ReportGenerator:
    """Generates Invariant_History_Report.md and related Markdown documents."""

    # ── Full Report ──────────────────────────────────────

    def generate_full_report(
        self,
        stability: StabilityIndex,
        pass_rate_trend: TrendResult,
        critical_failures_trend: TrendResult,
        execution_time_trend: TrendResult,
        slowest_invariants: list[dict[str, Any]],
        most_failing_invariants: list[dict[str, Any]],
        module_reliabilities: list[ModuleReliability],
        regressions: RegressionReport,
        execution_count: int,
        period_days: int,
    ) -> str:
        """
        Generate a complete Markdown report with sections:

        1. Executive Summary
        2. Historical Overview
        3. Trend Analysis
        4. Reliability Rankings
        5. Regression Analysis
        6. Performance Trends
        7. Module Health
        8. Recommendations
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        sections: list[str] = []

        # ── Header ───────────────────────────────────
        sections.append(f"""# Invariant History Report

> **Generated:** {now}  \
> **Period:** Last {period_days} days  \
> **Executions analyzed:** {execution_count}

---
""")

        # ── 1. Executive Summary ─────────────────────
        sections.append(self._section_executive_summary(stability, regressions))
        sections.append("\n---\n")

        # ── 2. Historical Overview ───────────────────
        sections.append(self._section_historical_overview(stability, execution_count, period_days))
        sections.append("\n---\n")

        # ── 3. Trend Analysis ────────────────────────
        sections.append(self._section_trend_analysis(
            pass_rate_trend, critical_failures_trend, execution_time_trend,
        ))
        sections.append("\n---\n")

        # ── 4. Reliability Rankings ─────────────────
        sections.append(self._section_reliability_rankings(module_reliabilities))
        sections.append("\n---\n")

        # ── 5. Regression Analysis ───────────────────
        sections.append(self._section_regression_analysis(regressions))
        sections.append("\n---\n")

        # ── 6. Performance Trends ────────────────────
        sections.append(self._section_performance_trends(
            slowest_invariants, most_failing_invariants, execution_time_trend,
        ))
        sections.append("\n---\n")

        # ── 7. Module Health ─────────────────────────
        sections.append(self._section_module_health(module_reliabilities))
        sections.append("\n---\n")

        # ── 8. Recommendations ───────────────────────
        sections.append(self._section_recommendations(
            stability, regressions, module_reliabilities,
        ))

        return "\n\n".join(sections)

    # ── Executive Summary ─────────────────────────────────

    def _section_executive_summary(
        self, stability: StabilityIndex, regressions: RegressionReport,
    ) -> str:
        score = stability.score
        if score >= 90:
            rating = "🟢 Excellent"
        elif score >= 75:
            rating = "🟡 Good"
        elif score >= 50:
            rating = "🟠 Fair"
        else:
            rating = "🔴 Poor"

        regression_count = (
            len(regressions.pass_to_fail)
            + len(regressions.execution_time_spikes)
            + len(regressions.reliability_decreases)
        )
        module_count = len(stability.modules)

        return f"""## 1. Executive Summary

| Metric | Value |
|--------|-------|
| **Stability Index** | {score:.1f}/100 ({rating}) |
| **Pass Rate** | {stability.pass_rate:.1f}% |
| **Critical Failure Rate** | {stability.critical_failure_rate:.1f}% |
| **Modules Tracked** | {module_count} |
| **Avg Execution Time** | {stability.avg_execution_time_ms:.0f} ms |
| **Module Reliability Avg** | {stability.module_reliability_avg:.1f}% |
| **Regressions Detected** | {regression_count} |

**Summary:** The invariant system is currently operating at a stability index of
**{score:.1f}/100** with a pass rate of **{stability.pass_rate:.1f}%**.
{self._summary_narrative(stability, regressions)}"""

    def _summary_narrative(
        self, stability: StabilityIndex, regressions: RegressionReport,
    ) -> str:
        parts: list[str] = []
        score = stability.score

        if score >= 90:
            parts.append("System health is excellent with no significant concerns.")
        elif score >= 75:
            parts.append("System health is good but there are areas for improvement.")
        elif score >= 50:
            parts.append("System health is fair — several areas require attention.")
        else:
            parts.append("System health is poor — immediate action is recommended.")

        if regressions.pass_to_fail:
            count = len(regressions.pass_to_fail)
            parts.append(
                f"**{count}** invariant(s) transitioned from pass to fail."
            )
        if regressions.execution_time_spikes:
            count = len(regressions.execution_time_spikes)
            parts.append(
                f"**{count}** invariant(s) show significant execution time increases."
            )
        if regressions.reliability_decreases:
            count = len(regressions.reliability_decreases)
            parts.append(
                f"**{count}** module(s) experienced reliability drops exceeding 5%."
            )

        return " ".join(parts)

    # ── Historical Overview ───────────────────────────────

    def _section_historical_overview(
        self, stability: StabilityIndex, execution_count: int, period_days: int,
    ) -> str:
        return f"""## 2. Historical Overview

| Attribute | Value |
|-----------|-------|
| **Reporting Period** | {stability.period_start} → {stability.period_end} |
| **Duration** | {period_days} days |
| **Total Executions** | {execution_count} |
| **Sample Size (Stability)** | {stability.sample_size} |
| **Overall Pass Rate** | {stability.pass_rate:.1f}% |
| **Critical Failure Rate** | {stability.critical_failure_rate:.1f}% |
| **System Stability** | {stability.score:.1f}/100 |
| **Avg Execution Duration** | {stability.avg_execution_time_ms:.0f} ms |
| **Avg Module Reliability** | {stability.module_reliability_avg:.1f}% |

This section provides a high-level view of invariant execution activity over the
reporting period. A total of **{execution_count}** executions were analyzed across
**{period_days}** days, encompassing **{stability.sample_size}** invariant evaluations."""

    # ── Trend Analysis ───────────────────────────────────

    def _section_trend_analysis(
        self,
        pass_rate_trend: TrendResult,
        critical_failures_trend: TrendResult,
        execution_time_trend: TrendResult,
    ) -> str:
        def _trend_icon(direction: str) -> str:
            if direction == "improving":
                return "📈"
            if direction == "degrading":
                return "📉"
            return "➡️"

        def _trend_table(tr: TrendResult) -> str:
            return (
                f"| Min | Max | Avg | Samples | Direction | Change |\n"
                f"|-----|-----|-----|---------|-----------|--------|\n"
                f"| {tr.min_value:.2f} | {tr.max_value:.2f} | {tr.avg_value:.2f} | "
                f"{tr.sample_count} | {_trend_icon(tr.trend_direction)} {tr.trend_direction.title()} | "
                f"{tr.change_pct:+.1f}% |"
            )

        return f"""## 3. Trend Analysis

### 3.1 Pass Rate Trend

{_trend_table(pass_rate_trend)}

### 3.2 Critical Failures Trend

{_trend_table(critical_failures_trend)}

### 3.3 Execution Time Trend

{_trend_table(execution_time_trend)}

### Interpretation

| Trend | Signal |
|-------|--------|
| **Pass Rate** | {self._interpret_trend(pass_rate_trend, higher_is_better=True)} |
| **Critical Failures** | {self._interpret_trend(critical_failures_trend, higher_is_better=False)} |
| **Execution Time** | {self._interpret_trend(execution_time_trend, higher_is_better=False)} |"""

    def _interpret_trend(self, tr: TrendResult, higher_is_better: bool) -> str:
        if tr.sample_count < 2:
            return "Insufficient data for trend analysis."
        if tr.trend_direction == "stable":
            return f"No significant change ({tr.change_pct:+.1f}%). Pattern is consistent."
        improving = tr.trend_direction == "improving"
        if higher_is_better:
            if improving:
                return f"Positive trend (+{tr.change_pct:.1f}%). Performance is improving."
            return f"Negative trend ({tr.change_pct:.1f}%). Attention recommended."
        else:
            if improving:
                return f"Favorable trend ({tr.change_pct:.1f}%). Metric is decreasing."
            return f"Concerning trend (+{abs(tr.change_pct):.1f}%). Metric is rising."

    # ── Reliability Rankings ─────────────────────────────

    def _section_reliability_rankings(self, modules: list[ModuleReliability]) -> str:
        if not modules:
            return "## 4. Reliability Rankings\n\nNo module reliability data available."

        sorted_modules = sorted(modules, key=lambda m: m.reliability_pct, reverse=True)

        rows: list[str] = []
        for i, mod in enumerate(sorted_modules, 1):
            trend_ch = "↑" if mod.trend == "improving" else "↓" if mod.trend == "degrading" else "→"
            rows.append(
                f"| {i} | {mod.module} | {mod.reliability_pct:.1f}% | "
                f"{mod.total_invariants} | {mod.passed} | {mod.failed} | "
                f"{trend_ch} {mod.trend} |"
            )

        header = (
            "## 4. Reliability Rankings\n\n"
            "Modules ranked by reliability percentage (higher is better).\n\n"
            "| Rank | Module | Reliability | Invariants | Passed | Failed | Trend |\n"
            "|------|--------|-------------|------------|--------|--------|-------|\n"
        )

        return header + "\n".join(rows)

    # ── Regression Analysis ──────────────────────────────

    def _section_regression_analysis(self, regression: RegressionReport) -> str:
        sections: list[str] = ["## 5. Regression Analysis\n"]

        if (
            not regression.new_failures
            and not regression.pass_to_fail
            and not regression.execution_time_spikes
            and not regression.reliability_decreases
        ):
            sections.append("✅ **No regressions detected** in the analyzed period.\n")
            return "\n".join(sections)

        # 5.1 Pass-to-Fail Regressions
        if regression.pass_to_fail:
            sections.append(self._regression_table(
                "### 5.1 Pass-to-Fail Regressions",
                "Invariants that changed from PASS to FAIL",
                ["Invariant ID", "Title", "Module", "Severity", "Failure Reason"],
                regression.pass_to_fail,
                ["invariant_id", "title", "module", "severity", "failure_reason"],
            ))

        # 5.2 New Failures
        if regression.new_failures:
            sections.append(self._regression_table(
                "### 5.2 New Failures",
                "Invariants that are failing for the first time",
                ["Invariant ID", "Title", "Module", "Severity", "Failure Reason"],
                regression.new_failures,
                ["invariant_id", "title", "module", "severity", "failure_reason"],
            ))

        # 5.3 Execution Time Spikes
        if regression.execution_time_spikes:
            sections.append(self._regression_table(
                "### 5.3 Execution Time Spikes",
                "Invariants where execution time increased by more than 100%",
                ["Invariant ID", "Title", "Module", "Previous (ms)", "Current (ms)", "Increase"],
                regression.execution_time_spikes,
                ["invariant_id", "title", "module", "previous_time_ms", "current_time_ms", "increase_pct"],
                value_formatters={"increase_pct": lambda v: f"{v}%"},
            ))

        # 5.4 Reliability Decreases
        if regression.reliability_decreases:
            sections.append(self._regression_table(
                "### 5.4 Module Reliability Decreases",
                "Modules where reliability dropped more than 5%",
                ["Module", "Baseline", "Target", "Change"],
                regression.reliability_decreases,
                ["module", "baseline_reliability_pct", "target_reliability_pct", "change_pct"],
                value_formatters={
                    "baseline_reliability_pct": lambda v: f"{v}%",
                    "target_reliability_pct": lambda v: f"{v}%",
                    "change_pct": lambda v: f"{v}%",
                },
            ))

        # 5.5 New / Removed Invariants
        if regression.new_invariants:
            items = "\n".join(f"- `{inv}`" for inv in regression.new_invariants)
            sections.append(f"### 5.5 New Invariants\n\n{items}\n")
        if regression.removed_invariants:
            items = "\n".join(f"- `{inv}`" for inv in regression.removed_invariants)
            sections.append(f"### 5.6 Removed Invariants\n\n{items}\n")

        return "\n".join(sections)

    def _regression_table(
        self,
        heading: str,
        description: str,
        columns: list[str],
        items: list[dict[str, Any]],
        keys: list[str],
        value_formatters: dict[str, Callable[[Any], str]] | None = None,
    ) -> str:
        if not items:
            return ""

        fmtrs = value_formatters or {}
        header_row = "| " + " | ".join(columns) + " |"
        sep_row = "| " + " | ".join("---" for _ in columns) + " |"
        data_rows: list[str] = []

        for item in items:
            vals: list[str] = []
            for key in keys:
                raw = item.get(key, "")
                if isinstance(raw, float):
                    raw = round(raw, 2)
                if key in fmtrs:
                    vals.append(str(fmtrs[key](raw)))
                else:
                    vals.append(str(raw))
            data_rows.append("| " + " | ".join(vals) + " |")

        return f"{heading}\n\n> {description}\n\n{header_row}\n{sep_row}\n" + "\n".join(data_rows) + "\n"

    # ── Performance Trends ──────────────────────────────

    def _section_performance_trends(
        self,
        slowest_invariants: list[dict[str, Any]],
        most_failing_invariants: list[dict[str, Any]],
        execution_time_trend: TrendResult,
    ) -> str:
        sections: list[str] = ["## 6. Performance Trends\n"]

        # Slowest invariants
        if slowest_invariants:
            rows: list[str] = []
            for i, inv in enumerate(slowest_invariants[:10], 1):
                rows.append(
                    f"| {i} | {inv.get('invariant_id', '')} | {inv.get('title', '')} | "
                    f"{inv.get('module', '')} | {inv.get('execution_time_ms', 0):.0f} |"
                )
            sections.append(
                "### 6.1 Slowest Invariants\n\n"
                "| Rank | Invariant ID | Title | Module | Time (ms) |\n"
                "|------|-------------|-------|--------|----------|\n"
                + "\n".join(rows) + "\n"
            )

        # Most failing invariants
        if most_failing_invariants:
            rows = []
            for i, inv in enumerate(most_failing_invariants[:10], 1):
                rows.append(
                    f"| {i} | {inv.get('invariant_id', '')} | {inv.get('title', '')} | "
                    f"{inv.get('module', '')} | {inv.get('fail_count', inv.get('failed', 0))} | "
                    f"{inv.get('severity', '')} |"
                )
            sections.append(
                "### 6.2 Most Failing Invariants\n\n"
                "| Rank | Invariant ID | Title | Module | Failures | Severity |\n"
                "|------|-------------|-------|--------|----------|----------|\n"
                + "\n".join(rows) + "\n"
            )

        # Execution time trend summary
        if execution_time_trend.sample_count > 0:
            sections.append(
                "### 6.3 Execution Time Summary\n\n"
                f"| Metric | Value |\n"
                f"|--------|-------|\n"
                f"| Minimum | {execution_time_trend.min_value:.0f} ms |\n"
                f"| Maximum | {execution_time_trend.max_value:.0f} ms |\n"
                f"| Average | {execution_time_trend.avg_value:.0f} ms |\n"
                f"| Samples | {execution_time_trend.sample_count} |\n"
                f"| Trend | {execution_time_trend.trend_direction.title()} "
                f"({execution_time_trend.change_pct:+.1f}%) |\n"
            )

        return "\n".join(sections)

    # ── Module Health ────────────────────────────────────

    def _section_module_health(self, modules: list[ModuleReliability]) -> str:
        if not modules:
            return "## 7. Module Health\n\nNo module data available."

        sections: list[str] = [
            "## 7. Module Health\n",
            "Detailed per-module breakdown of invariant reliability and execution metrics.\n",
        ]

        for mod in sorted(modules, key=lambda m: m.reliability_pct):
            trend_ch = "↑" if mod.trend == "improving" else "↓" if mod.trend == "degrading" else "→"
            last_fail = mod.last_failure or "N/A"

            sections.append(f"""### {mod.module}

| Metric | Value |
|--------|-------|
| **Reliability** | {mod.reliability_pct:.1f}% |
| **Total Invariants** | {mod.total_invariants} |
| **Passed** | {mod.passed} |
| **Failed** | {mod.failed} |
| **Trend** | {trend_ch} {mod.trend} |
| **Last Failure** | {last_fail} |
| **Avg Execution Time** | {mod.avg_execution_time_ms:.0f} ms |

""")

        return "\n".join(sections)

    # ── Recommendations ──────────────────────────────────

    def _section_recommendations(
        self,
        stability: StabilityIndex,
        regressions: RegressionReport,
        modules: list[ModuleReliability],
    ) -> str:
        recommendations: list[str] = ["## 8. Recommendations\n"]

        score = stability.score

        if score < 50:
            recommendations.append("- **🔴 Critical:** System stability is below 50%. "
                                   "Conduct an immediate review of all failing invariants.")
        elif score < 75:
            recommendations.append("- **🟡 Warning:** Stability is below 75%. "
                                   "Review the top failing modules and address regressions.")
        else:
            recommendations.append("- **🟢 Good:** Stability is above 75%. "
                                   "Continue monitoring and addressing issues proactively.")

        if regressions.pass_to_fail:
            recs = "\n".join(
                f"  - Investigate `{r.get('invariant_id', '')}` in module "
                f"`{r.get('module', 'unknown')}` ({r.get('failure_reason', 'no reason given')})"
                for r in regressions.pass_to_fail[:5]
            )
            recommendations.append(
                f"\n- **Pass-to-Fail Regressions:** Review the following regressions:\n{recs}"
            )

        if regressions.execution_time_spikes:
            recs = "\n".join(
                f"  - `{r.get('invariant_id', '')}` time increased by "
                f"{r.get('increase_pct', 0)}%"
                for r in regressions.execution_time_spikes[:5]
            )
            recommendations.append(
                f"\n- **Performance Regressions:** Investigate execution time spikes:\n{recs}"
            )

        if regressions.reliability_decreases:
            recs = "\n".join(
                f"  - `{r.get('module', '')}` dropped from "
                f"{r.get('baseline_reliability_pct', 0)}% to "
                f"{r.get('target_reliability_pct', 0)}%"
                for r in regressions.reliability_decreases[:5]
            )
            recommendations.append(
                f"\n- **Reliability Decreases:** Address modules with declining reliability:\n{recs}"
            )

        # Recommend focusing on bottom modules
        bottom_modules = sorted(modules, key=lambda m: m.reliability_pct)[:3]
        if bottom_modules and bottom_modules[0].reliability_pct < 80:
            mods = ", ".join(f"`{m.module}` ({m.reliability_pct:.1f}%)" for m in bottom_modules)
            recommendations.append(
                f"\n- **Focus Areas:** Prioritize improvements in the least reliable modules: {mods}."
            )

        return "\n".join(recommendations)

    # ── Release Comparison Report ─────────────────────────

    def generate_release_comparison_report(
        self, comp: ReleaseComparison,
    ) -> str:
        """Markdown report comparing two releases."""
        reg = comp.regressions
        pass_change = f"{comp.pass_rate_change:+.1f}%"
        time_change = f"{comp.execution_time_change_pct:+.1f}%"

        pass_icon = "🟢" if comp.pass_rate_change >= 0 else "🔴"
        time_icon = "🟢" if comp.execution_time_change_pct <= 0 else "🔴"
        stab_icon = "🟢" if comp.stability_change >= 0 else "🔴"

        sections: list[str] = [
            "# Release Comparison Report\n",
            f"> **Baseline:** `{comp.baseline_id}` — {comp.baseline_version} ({comp.baseline_timestamp})  \n"
            f"> **Target:** `{comp.target_id}` — {comp.target_version} ({comp.target_timestamp})  \n",
            "---\n",
            "## Comparison Summary\n",
            f"| Metric | Change |\n"
            f"|--------|--------|\n"
            f"| Pass Rate | {pass_icon} {pass_change} |\n"
            f"| Failure Count | {_int_change(comp.failure_count_change)} |\n"
            f"| Critical Failures | {_int_change(comp.critical_failure_change)} |\n"
            f"| Execution Time | {time_icon} {time_change} |\n"
            f"| Reliability | {comp.reliability_change:+.1f}% |\n"
            f"| Stability | {stab_icon} {comp.stability_change:+.1f} points |\n",
            "---\n",
            "## Regressions\n",
        ]

        if (
            not reg.new_failures
            and not reg.pass_to_fail
            and not reg.execution_time_spikes
            and not reg.reliability_decreases
            and not reg.new_invariants
            and not reg.removed_invariants
        ):
            sections.append("✅ **No regressions detected** between these releases.\n")
        else:
            if reg.pass_to_fail:
                items = "\n".join(
                    f"- `{r.get('invariant_id', '')}` — {r.get('failure_reason', 'no reason')}"
                    for r in reg.pass_to_fail
                )
                sections.append(f"### Pass-to-Fail ({len(reg.pass_to_fail)})\n\n{items}\n")
            if reg.execution_time_spikes:
                items = "\n".join(
                    f"- `{r.get('invariant_id', '')}` — {r.get('increase_pct', 0)}% increase"
                    for r in reg.execution_time_spikes
                )
                sections.append(f"### Execution Time Spikes ({len(reg.execution_time_spikes)})\n\n{items}\n")
            if reg.reliability_decreases:
                items = "\n".join(
                    f"- `{r.get('module', '')}` — {r.get('change_pct', 0)}% change"
                    for r in reg.reliability_decreases
                )
                sections.append(f"### Reliability Decreases ({len(reg.reliability_decreases)})\n\n{items}\n")
            if reg.new_invariants:
                items = "\n".join(f"- `{inv}`" for inv in reg.new_invariants)
                sections.append(f"### New Invariants ({len(reg.new_invariants)})\n\n{items}\n")
            if reg.removed_invariants:
                items = "\n".join(f"- `{inv}`" for inv in reg.removed_invariants)
                sections.append(f"### Removed Invariants ({len(reg.removed_invariants)})\n\n{items}\n")

        return "\n".join(sections)

    # ── Regression Alert ─────────────────────────────────

    def generate_regression_alert(self, regression: RegressionReport) -> str:
        """Compact alert message for detected regressions."""
        total = (
            len(regression.pass_to_fail)
            + len(regression.execution_time_spikes)
            + len(regression.reliability_decreases)
        )

        if total == 0:
            return "✅ **Invariant Regression Check:** No regressions detected."

        lines: list[str] = [
            "⚠️ **Invariant Regression Alert**",
            "",
            f"| Category | Count |",
            f"|----------|-------|",
        ]

        if regression.pass_to_fail:
            lines.append(f"| Pass-to-Fail | {len(regression.pass_to_fail)} |")
        if regression.execution_time_spikes:
            lines.append(f"| Execution Time Spikes | {len(regression.execution_time_spikes)} |")
        if regression.reliability_decreases:
            lines.append(f"| Reliability Decreases | {len(regression.reliability_decreases)} |")
        if regression.new_failures:
            lines.append(f"| First-Time Failures | {len(regression.new_failures)} |")

        if regression.pass_to_fail:
            lines.append("")
            lines.append("**Top Pass-to-Fail:**")
            for r in regression.pass_to_fail[:3]:
                lines.append(
                    f"- `{r.get('invariant_id', '')}` — {r.get('failure_reason', 'no reason')}"
                )

        if regression.execution_time_spikes:
            lines.append("")
            lines.append("**Top Time Spikes:**")
            for r in regression.execution_time_spikes[:3]:
                lines.append(
                    f"- `{r.get('invariant_id', '')}` — {r.get('increase_pct', 0)}% increase"
                )

        return "\n".join(lines)
