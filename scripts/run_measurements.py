"""Run performance measurements and generate reports.

Usage::

    python scripts/run_measurements.py --scenario sequential_nav
    python scripts/run_measurements.py --scenario rapid_switch
    python scripts/run_measurements.py --scenario stay_alive --duration 28800  # 8 hours

Environment variables:
    OPERION_PERF_LOG=1  — Enable performance logging
    OPERION_DB=test_group1.db  — Use test database
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("OPERION_PERF_LOG", "1")
os.environ.setdefault("OPERION_DB", "test_group1.db")

from scripts.perf_collector import collect_measurements, generate_report, REPORTS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_measurements")


def main():
    parser = argparse.ArgumentParser(description="Run Operion performance measurements")
    parser.add_argument(
        "--scenario", 
        default="sequential_nav",
        choices=["sequential_nav", "rapid_switch", "stay_alive"],
        help="Measurement scenario to run",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=3600,
        help="Duration in seconds for stay_alive scenario (default: 1 hour)",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Output report filename (default: auto-generated)",
    )
    args = parser.parse_args()

    logger.info("Starting Operion performance measurement: %s", args.scenario)

    # ── Initialize application ─────────────────────────────────────
    try:
        from main import run_app
        app, window = run_app(return_window=True)
    except ImportError:
        logger.error("Cannot import run_app from main.py")
        logger.error("Make sure you're running from the project root")
        sys.exit(1)
    except Exception as e:
        logger.error("Failed to start application: %s", e)
        sys.exit(1)

    # ── Let UI settle ──────────────────────────────────────────────
    logger.info("Application started, waiting 3s for UI to settle...")
    from PySide6.QtCore import QCoreApplication
    for _ in range(30):
        QCoreApplication.processEvents()
        time.sleep(0.1)
    
    # ── Run measurement scenario ───────────────────────────────────
    try:
        if args.scenario == "stay_alive":
            logger.info(
                "Stay-alive mode — measurements collect for %d seconds",
                args.duration,
            )
            time.sleep(args.duration)
            report = collect_measurements(window, "stay_alive")
        else:
            report = collect_measurements(window, args.scenario)
    except Exception as e:
        logger.exception("Measurement scenario failed: %s")
        report = {"error": str(e), "scenario": args.scenario}

    # ── Generate report ────────────────────────────────────────────
    report_path = generate_report(report, args.report)
    logger.info("Report saved to: %s", report_path)

    # ── Print summary to console ───────────────────────────────────
    if "error" not in report:
        print(f"\n{'='*60}")
        print(f"PERFORMANCE MEASUREMENT COMPLETE")
        print(f"{'='*60}")
        print(f"Scenario: {report['scenario']}")
        print(f"Total measurements: {report['total_measurements']}")
        print(f"Unique labels: {report['unique_labels']}")
        print(f"\nTop 5 slowest:")
        for item in report.get("slowest", [])[:5]:
            print(f"  {item['label']}: {item['avg_ms']}ms avg / {item['max_ms']}ms max")
        print(f"\nFull report: {report_path}")
        print(f"{'='*60}\n")

    # ── Cleanup ────────────────────────────────────────────────────
    try:
        window.close()
    except Exception:
        pass
    try:
        app.quit()
    except Exception:
        pass

    return 0 if "error" not in report else 1


if __name__ == "__main__":
    sys.exit(main())
