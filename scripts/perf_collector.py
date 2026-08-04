"""Performance measurement collector for Operion ERP.

Usage in a running app::

    from scripts.perf_collector import collect_measurements, generate_report

    report = collect_measurements(main_window, scenario="sequential_nav")
    generate_report(report, "perf_report_nav.json")
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ui.performance_timer import reset_timings, timing_report, TimingSummary

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def collect_measurements(
    window,
    scenario: str = "sequential_nav",
    settle_seconds: float = 3.0,
) -> dict[str, Any]:
    """Run a measurement scenario and return results.
    
    Scenarios:
        - "sequential_nav": Navigate to each view in order, wait, then report.
        - "rapid_switch": Switch between views rapidly to test animation/layout.
        - "stay_alive": Just record timings for 8+ hours (for leak detection).
    """
    reset_timings()
    
    if scenario == "sequential_nav":
        _run_sequential_nav(window, settle_seconds)
    elif scenario == "rapid_switch":
        _run_rapid_switch(window)
    elif scenario == "stay_alive":
        logger.info("Stay-alive mode - timings accumulate until manual report dump")
    else:
        raise ValueError(f"Unknown scenario: {scenario}")
    
    return _build_report(scenario)


def _run_sequential_nav(window, settle_seconds: float = 3.0):
    """Navigate through every view in the sidebar, waiting for settle."""
    nav_keys = [
        "overview", "analytics", "calculator", "route_planner",
        "dispatch_board", "tracking", "fleet", "driver_manager",
        "clients", "documents", "maintenance", "maintenance_control",
        "tachograph", "invoices", "history", "route_history",
        "copilot", "migration_center", "settings",
    ]
    
    for key in nav_keys:
        logger.info("[PERF] Navigating to: %s", key)
        t0 = time.perf_counter()
        
        # Navigate via the existing _switch_module method
        if hasattr(window, '_switch_module'):
            window._switch_module(key)
        elif hasattr(window, 'navigate'):
            window.navigate(key)
        elif hasattr(window, 'nav') and hasattr(window.nav, 'select'):
            window.nav.select(key)
        
        # Process Qt events and wait for rendering
        _process_events()
        time.sleep(settle_seconds)
        
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("[PERF] %s: total_nav=%.1fms", key, elapsed)


def _run_rapid_switch(window):
    """Switch between views rapidly to stress animation/layout."""
    nav_keys = [
        "overview", "fleet", "dispatch_board", "route_planner", 
        "analytics", "history", "invoices", "fleet",
        "tracking", "clients", "settings", "overview",
    ]
    
    for i in range(3):  # 3 rounds
        logger.info("[PERF] Rapid switch round %d/3", i + 1)
        for key in nav_keys:
            t0 = time.perf_counter()
            if hasattr(window, '_switch_module'):
                window._switch_module(key)
            _process_events()
            time.sleep(0.3)  # 300ms between switches
        
        time.sleep(2.0)  # settle between rounds


def _process_events():
    """Process pending Qt events."""
    from PySide6.QtCore import QCoreApplication
    for _ in range(5):
        QCoreApplication.processEvents()


def _build_report(scenario: str) -> dict[str, Any]:
    """Build a comprehensive report from accumulated timings."""
    summaries = timing_report()
    
    report = {
        "scenario": scenario,
        "timestamp": datetime.now().isoformat(),
        "total_measurements": sum(s.count for s in summaries),
        "unique_labels": len(summaries),
        "timings": [
            {
                "label": s.label,
                "count": s.count,
                "avg_ms": round(s.avg_ms, 2),
                "min_ms": round(s.min_ms, 2),
                "max_ms": round(s.max_ms, 2),
                "p50_ms": round(s.p50_ms, 2),
                "p95_ms": round(s.p95_ms, 2),
                "p99_ms": round(s.p99_ms, 2),
                "total_ms": round(s.total_ms, 2),
            }
            for s in summaries
        ],
        "slowest": _top_slowest(summaries, 20),
        "slowest_queries": _slowest_queries(summaries),
    }
    return report


def _top_slowest(summaries: list[TimingSummary], n: int = 20) -> list[dict]:
    """Return the n slowest average timings."""
    sorted_s = sorted(summaries, key=lambda s: s.avg_ms, reverse=True)
    return [
        {"label": s.label, "avg_ms": round(s.avg_ms, 2), "max_ms": round(s.max_ms, 2)}
        for s in sorted_s[:n]
    ]


def _slowest_queries(summaries: list[TimingSummary]) -> list[dict]:
    """Return the slowest database queries."""
    db_queries = [s for s in summaries if s.label.startswith("db.")]
    sorted_q = sorted(db_queries, key=lambda s: s.avg_ms, reverse=True)
    return [
        {"query": s.label[3:], "avg_ms": round(s.avg_ms, 2), "count": s.count}
        for s in sorted_q[:20]
    ]


def generate_report(report: dict[str, Any], filename: str | None = None) -> str:
    """Save report to JSON and return the file path."""
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"perf_report_{ts}.json"
    
    path = REPORTS_DIR / filename
    path.write_text(json.dumps(report, indent=2, default=str))
    logger.info("[PERF] Report saved to %s", path)
    
    # Also generate a human-readable markdown summary
    md_path = path.with_suffix(".md")
    _write_markdown(report, md_path)
    
    return str(path)


def _write_markdown(report: dict, path: Path):
    """Write a human-readable markdown report."""
    lines = [
        f"# Performance Report: {report['scenario']}",
        f"**Timestamp**: {report['timestamp']}",
        f"**Total measurements**: {report['total_measurements']}",
        f"**Unique labels**: {report['unique_labels']}",
        "",
        "## Top 20 Slowest Functions",
        "| # | Label | Avg (ms) | Max (ms) |",
        "|---|-------|----------|----------|",
    ]
    for i, item in enumerate(report.get("slowest", []), 1):
        lines.append(f"| {i} | {item['label']} | {item['avg_ms']} | {item['max_ms']} |")
    
    lines.extend(["", "## Top 20 Slowest SQL Queries"])
    if report.get("slowest_queries"):
        lines.append("| # | Query | Avg (ms) | Count |")
        lines.append("|---|-------|----------|-------|")
        for i, item in enumerate(report["slowest_queries"], 1):
            query_short = item["query"][:80]
            lines.append(f"| {i} | {query_short} | {item['avg_ms']} | {item['count']} |")
    else:
        lines.append("*No database queries timed.*")
    
    lines.append("")
    lines.append("## All Timings")
    lines.append("| Label | Count | Avg (ms) | Min (ms) | Max (ms) | P50 | P95 |")
    lines.append("|-------|-------|----------|----------|----------|-----|-----|")
    for t in sorted(report.get("timings", []), key=lambda x: x["avg_ms"], reverse=True):
        lines.append(
            f"| {t['label']} | {t['count']} | {t['avg_ms']} | "
            f"{t['min_ms']} | {t['max_ms']} | {t['p50_ms']} | {t['p95_ms']} |"
        )
    
    path.write_text("\n".join(lines), encoding="utf-8")
