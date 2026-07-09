"""Compare load test results against baseline and detect regressions.

Usage:
    python tests/loadtest/regression_detection.py <new_results.csv>
"""

import csv
import json
import sys
from pathlib import Path


BASELINE_PATH = Path(__file__).parent / "benchmarks" / "baseline.json"
REGRESSION_THRESHOLD = 1.5  # 50% slower = regression


def load_baseline():
    with open(BASELINE_PATH) as f:
        return json.load(f)


def parse_results(csv_path):
    results = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            name = row.get("Name", "").strip("/")
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
        print("Usage: python regression_detection.py <locust_stats.csv>")
        sys.exit(1)

    baseline = load_baseline()
    current = parse_results(sys.argv[1])
    regressions = []

    for endpoint, expected in baseline.items():
        for name, metrics in current.items():
            if endpoint in name:
                if metrics["p95_ms"] > expected["p95_ms"] * REGRESSION_THRESHOLD:
                    change_pct = ((metrics["p95_ms"] - expected["p95_ms"]) / expected["p95_ms"]) * 100
                    regressions.append(
                        f"  ❌ {endpoint}: {metrics['p95_ms']}ms (+{change_pct:.0f}%) vs baseline {expected['p95_ms']}ms"
                    )
                break

    if regressions:
        print("❌ Performance regressions detected:")
        for r in regressions:
            print(r)
        sys.exit(1)
    else:
        print("✅ No performance regressions detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
