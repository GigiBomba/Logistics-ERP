"""Parse Locust CSV stats and assert performance thresholds.

Usage:
    python tests/loadtest/assert_thresholds.py ci-load_stats.csv

Returns exit code 0 if all thresholds pass, 1 if any fail.
"""
from __future__ import annotations


import csv
import re
import sys


# Thresholds: {name_pattern: {"p95_ms": max_ms, "error_pct": max_error_percent}}
THRESHOLDS = {
    "login":               {"p95_ms": 500,  "error_pct": 1.0},
    "refresh":             {"p95_ms": 500,  "error_pct": 1.0},
    "list_trips":          {"p95_ms": 500,  "error_pct": 1.0},
    "get_trip":            {"p95_ms": 300,  "error_pct": 1.0},
    "create_trip":         {"p95_ms": 1000, "error_pct": 2.0},
    "list_clients":        {"p95_ms": 500,  "error_pct": 1.0},
    "get_client":          {"p95_ms": 300,  "error_pct": 1.0},
    "list_drivers":        {"p95_ms": 500,  "error_pct": 1.0},
    "list_fleet":          {"p95_ms": 500,  "error_pct": 1.0},
    "create_client":       {"p95_ms": 1000, "error_pct": 2.0},
    "list_documents":      {"p95_ms": 500,  "error_pct": 1.0},
    "upload_document":     {"p95_ms": 3000, "error_pct": 5.0},
    "generate_invoice":    {"p95_ms": 3000, "error_pct": 5.0},
    "export_pdf":          {"p95_ms": 5000, "error_pct": 5.0},

    # Dispatch endpoints
    "assign_truck":        {"p95_ms": 500,  "error_pct": 2.0},
    "assign_driver":       {"p95_ms": 500,  "error_pct": 2.0},
    "transition_trip":     {"p95_ms": 500,  "error_pct": 2.0},
    "dispatch_board":      {"p95_ms": 1000, "error_pct": 2.0},
    "complete_trip":       {"p95_ms": 500,  "error_pct": 2.0},
    "workflow_create_trip": {"p95_ms": 1000, "error_pct": 3.0},
    "workflow_assign_truck": {"p95_ms": 500, "error_pct": 2.0},
    "workflow_transition":  {"p95_ms": 500, "error_pct": 2.0},
    "workflow_complete":    {"p95_ms": 500, "error_pct": 2.0},
    "workflow_board_load":  {"p95_ms": 1000, "error_pct": 2.0},
    "workflow_board_filter": {"p95_ms": 500, "error_pct": 2.0},
}


def parse_locust_csv(csv_path: str) -> dict:
    """Parse Locust CSV and return dict of {name: {p95_ms: int, error_pct: float}}."""
    results = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip("/").replace("/", "_")
            if not name:
                continue
            try:
                p95 = int(float(row.get("95%", 0)))
            except (ValueError, TypeError):
                p95 = 0
            error_str = row.get("Error Rate", "0%").strip().rstrip("%")
            try:
                error_pct = float(error_str) if error_str else 0.0
            except ValueError:
                error_pct = 0.0
            results[name] = {"p95_ms": p95, "error_pct": error_pct}
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python assert_thresholds.py <locust_stats.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    results = parse_locust_csv(csv_path)
    failures = []

    for endpoint, threshold in THRESHOLDS.items():
        # Find matching result (exact or substring match)
        matched = False
        for name, metrics in results.items():
            if endpoint in name:
                matched = True
                if metrics["p95_ms"] > threshold["p95_ms"]:
                    failures.append(
                        f"  ❌ {endpoint}: p95={metrics['p95_ms']}ms > {threshold['p95_ms']}ms"
                    )
                if metrics["error_pct"] > threshold["error_pct"]:
                    failures.append(
                        f"  ❌ {endpoint}: errors={metrics['error_pct']}% > {threshold['error_pct']}%"
                    )
                break
        if not matched:
            failures.append(f"  ⚠️  {endpoint}: no matching data in CSV (endpoint may not have been hit)")

    if failures:
        print("❌ Performance thresholds exceeded:")
        for f in failures:
            print(f)
        sys.exit(1)
    else:
        print("✅ All performance thresholds passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
