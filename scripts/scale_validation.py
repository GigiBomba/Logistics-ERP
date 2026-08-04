#!/usr/bin/env python
"""Scale Validation — generates synthetic data and verifies invariants at volume.

Usage:
    python scripts/scale_validation.py
    python scripts/scale_validation.py --trips 10000 --quick
"""

from __future__ import annotations

import json
import os
import sys
import time
import random
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUSES = ["Planned", "Loading", "In Transit", "Delivered", "Invoiced", "Paid", "Cancelled"]
CURRENCIES = ["EUR", "RON"]
CLIENT_NAMES = ["Dedeman SRL", "Metro Cash & Carry", "Selgros", "Lidl Romania", "Carrefour",
                "Kaufland", "Mega Image", "Profi", "eMAG", "Altex"]

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Scale validation")
    parser.add_argument("--trips", type=int, default=10000)
    parser.add_argument("--companies", type=int, default=10)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-o", "--output", type=str)
    args = parser.parse_args()

    if args.quick:
        args.trips = 1000
        args.companies = 3

    os.environ["OPERION_ENCRYPTION_KEY"] = "scale-validation-key"
    os.environ["OPERION_ENV"] = "testing"
    sys.path.insert(0, str(REPO_ROOT))

    from tests.test_helpers import make_db
    from tests.workflow_integrity.personas.fixtures import (
        seed_company, seed_client, seed_driver, seed_truck, seed_trip, seed_user,
    )
    from services.analytics_service import AnalyticsService

    rng = random.Random(42)
    base_date = date(2025, 1, 1)
    db = make_db()

    start = time.time()
    company_ids, client_ids = [], []

    # Seed companies
    truck_counter = 0
    for i in range(args.companies):
        cid = seed_company(db, company_name=f"Scale Co {i+1}",
                           subscription_tier=rng.choice(["starter", "professional"]))
        company_ids.append(cid)
        seed_user(db, company_id=cid, email=f"admin{i+1}@scale.test", role="dispatcher")
        for _ in range(rng.randint(3, 6)):
            seed_driver(db, company_id=cid, name=f"Driver {i+1}.{rng.randint(1,999)}")
            truck_counter += 1
            seed_truck(db, plate_number=f"B-{100+i}{truck_counter:03d}-SCL",
                       manufacturer=rng.choice(["Volvo","Mercedes","MAN","Scania"]))

    for name in CLIENT_NAMES[:max(5, args.companies)]:
        client_ids.append(seed_client(db, name=name))

    # Generate trips in batches
    print(f"Generating {args.trips:,} trips across {args.companies} companies...", file=sys.stderr)
    for i in range(args.trips):
        cid = rng.choice(company_ids)
        dist = rng.uniform(50, 2500)
        rate = rng.uniform(1.5, 4.0)
        price = round(dist * rate, 2)
        fuel = round(dist * rng.uniform(0.25, 0.40), 2)
        toll = round(dist * rng.uniform(0.05, 0.15), 2)
        salary = round(dist * rng.uniform(0.30, 0.50), 2)
        extra = round(rng.uniform(0, 50), 2)
        profit = round(price - fuel - toll - salary - extra, 2)
        day = rng.randint(1, 365)
        status = rng.choices(STATUSES, weights=[10,8,15,30,15,12,10])[0]

        seed_trip(db,
            company_id=cid, client_id=rng.choice(client_ids),
            client_name="Scale Client",
            driver_name=f"Driver {i % 5 + 1}", truck_number=f"B-{cid}{i % 6}-SCL",
            distance_km=round(dist,1), total_price_eur=price,
            status=status,
            start_date=(base_date + timedelta(days=day)).isoformat(),
            end_date=(base_date + timedelta(days=day + rng.randint(1,5))).isoformat(),
            fuel_cost=fuel, toll_cost=toll, salary_cost=salary,
            extra_costs=extra, net_profit=profit,
            rate_per_km=round(rate,2),
            gross_per_km=round(price/dist,2) if dist>0 else 0,
            currency=rng.choice(CURRENCIES),
        )

        if (i+1) % 2000 == 0:
            print(f"  {i+1:,} trips seeded...", file=sys.stderr)

    gen_time = time.time() - start
    print(f"Seeded {args.trips:,} trips in {gen_time:.1f}s", file=sys.stderr)

    # Verify invariants
    conn = db.conn
    results = {"passed": 0, "failed": 0, "checks": [], "performance": []}

    # F10: Cost breakdown
    bad = conn.execute("""
        SELECT COUNT(*) FROM trips 
        WHERE ABS(net_profit - (total_price_eur - fuel_cost - toll_cost - salary_cost - extra_costs)) > 0.02
    """).fetchone()[0]
    results["checks"].append({"name": "F10_cost_breakdown", "passed": bad == 0, "violations": bad})

    # All non-negative prices
    neg = conn.execute("SELECT COUNT(*) FROM trips WHERE total_price_eur < 0").fetchone()[0]
    results["checks"].append({"name": "non_negative_prices", "passed": neg == 0, "count": neg})

    # Valid statuses
    qmarks = ",".join("?" for _ in STATUSES)
    bad_s = conn.execute(f"SELECT COUNT(*) FROM trips WHERE status NOT IN ({qmarks})", STATUSES).fetchone()[0]
    results["checks"].append({"name": "valid_statuses", "passed": bad_s == 0, "count": bad_s})

    # Trip count
    count = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    results["checks"].append({"name": "trip_count", "passed": count == args.trips,
                              "expected": args.trips, "actual": count})

    # Analytics
    try:
        an = AnalyticsService(db).get_financial()
        results["checks"].append({"name": "analytics_financial", "passed": an is not None})
    except Exception as e:
        results["checks"].append({"name": "analytics_financial", "passed": False, "error": str(e)})

    # Query performance
    for qname, sql in [
        ("COUNT(*)", "SELECT COUNT(*) FROM trips"),
        ("SUM(revenue)", "SELECT SUM(total_price_eur) FROM trips"),
        ("GROUP BY status", "SELECT status, COUNT(*) FROM trips GROUP BY status"),
    ]:
        t0 = time.perf_counter()
        conn.execute(sql).fetchone()
        ms = (time.perf_counter() - t0) * 1000
        results["performance"].append({"query": qname, "duration_ms": round(ms, 1), "passed": ms < 500})

    results["passed"] = sum(1 for c in results["checks"] if c.get("passed", False))
    results["failed"] = sum(1 for c in results["checks"] if not c.get("passed", True))
    results["timestamp"] = datetime.now().isoformat()
    results["duration_seconds"] = round(time.time() - start, 1)

    # Summary
    print(f"\nResults: {results['passed']} passed, {results['failed']} failed", file=sys.stderr)
    for c in results["checks"]:
        icon = "✅" if c["passed"] else "❌"
        print(f"  {icon} {c['name']}", file=sys.stderr)
    for p in results["performance"]:
        icon = "✅" if p["passed"] else "❌"
        print(f"  {icon} {p['query']}: {p['duration_ms']:.0f}ms", file=sys.stderr)

    if args.json or args.output:
        data = json.dumps(results, indent=2)
        if args.output:
            Path(args.output).write_text(data)
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(data)

    return 1 if results["failed"] > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
