"""Stress tests: analytics queries over large datasets (10k+ trips)."""
from __future__ import annotations

import time
from typing import Any

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


def _seed_trips(db, count: int = 10000) -> None:
    """Insert *count* trip rows into the in-memory database."""
    import random
    from datetime import datetime, timedelta

    trucks = [f"TRUCK-{i}" for i in range(1, 51)]
    drivers = [f"Driver-{i}" for i in range(1, 31)]
    clients = [f"Client-{i}" for i in range(1, 21)]
    statuses = ["Delivered", "Completed", "In Progress", "Planned", "Paid"]
    countries = ["DE", "FR", "NL", "BE", "AT", "CH", "IT", "ES", "PL", "CZ"]

    base_date = datetime(2025, 1, 1)
    batch_size = 500

    rows: list[tuple[Any, ...]] = []
    for i in range(count):
        truck = random.choice(trucks)
        driver = random.choice(drivers)
        client = random.choice(clients)
        status = random.choice(statuses)
        country = random.choice(countries)
        distance = random.uniform(100, 2500)
        revenue = random.uniform(500, 8000)
        fuel = random.uniform(100, 1500)
        toll = random.uniform(20, 400)
        salary = random.uniform(100, 800)
        profit = revenue - fuel - toll - salary - random.uniform(0, 500)
        start = base_date + timedelta(days=random.randint(0, 540), hours=random.randint(0, 23))
        end = start + timedelta(days=random.randint(1, 5))
        created = start - timedelta(days=random.randint(0, 3))

        rows.append((
            i + 1, created.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"),
            truck, driver, client, round(distance, 2), round(revenue, 2),
            round(revenue / distance, 4) if distance > 0 else 0,
            round(profit, 2), start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
            "", round(fuel, 2), round(toll, 2), round(salary, 2),
            "EUR", status, country, country, 0, "",
            "", "", "", 0, 0, 0, 21.0, "",
            "", "", "", "", "", "", "", "", "", "",
            "", "", "", "", "", "", "", "",
        ))

        if len(rows) >= batch_size or i == count - 1:
            placeholders = ",".join("(" + ",".join("?" for _ in range(48)) + ")" for _ in rows)
            flat_params = [v for row in rows for v in row]
            db.conn.execute(
                f"INSERT INTO trips VALUES {placeholders}",
                flat_params,
            )
            db.conn.commit()
            rows.clear()


class TestStressLargeDataset:
    """Stress tests for analytics over large datasets."""

    @pytest.fixture
    def db_with_10k_trips(self):
        db = make_db()
        _seed_trips(db, 10000)
        return db

    # ── test 1: Analytics over large dataset ────────────────────────────

    def test_analytics_over_large_dataset(self, db_with_10k_trips):
        """Seed 10k trips, hit /analytics/financial with real SQL — verify < 5s."""
        from services.analytics_service import AnalyticsService

        svc = AnalyticsService(db_with_10k_trips)

        start = time.monotonic()
        result = svc.get_financial()
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, (
            f"get_financial over 10k trips took {elapsed:.2f}s (expected < 5s)"
        )
        # Verify we got some data back
        assert isinstance(result, list)

    # ── test 2: All analytics endpoints over large dataset ──────────────

    def test_analytics_all_endpoints_large_dataset(self, db_with_10k_trips):
        """Hit all analytics endpoints on 10k-trip DB — verify each < 10s."""
        from services.analytics_service import AnalyticsService

        svc = AnalyticsService(db_with_10k_trips)
        # Invalidate caches between calls to force real DB queries
        svc.invalidate()

        endpoints = [
            ("get_financial", lambda: svc.get_financial()),
            ("get_revenue_by_client", lambda: svc.get_revenue_by_client()),
            ("get_revenue_by_country", lambda: svc.get_revenue_by_country()),
            ("get_route_profitability", lambda: svc.get_route_profitability()),
            ("get_client_analytics", lambda: svc.get_client_analytics()),
            ("get_fleet", lambda: svc.get_fleet()),
            ("get_driver", lambda: svc.get_driver()),
            ("get_monthly_financial", lambda: svc.get_monthly_financial()),
            ("get_truck_utilization", lambda: svc.get_truck_utilization()),
            ("get_trip_status_distribution", lambda: svc.get_trip_status_distribution()),
            ("get_cost_breakdown", lambda: svc.get_cost_breakdown()),
            ("get_monthly_trip_volume", lambda: svc.get_monthly_trip_volume()),
            ("get_profit_per_km_by_country", lambda: svc.get_profit_per_km_by_country()),
            ("get_revenue_concentration", lambda: svc.get_revenue_concentration()),
            ("get_driver_profit_per_km", lambda: svc.get_driver_profit_per_km()),
        ]

        failures = []
        for name, call_fn in endpoints:
            svc.invalidate()  # reset cache so each call hits DB
            start = time.monotonic()
            try:
                result = call_fn()
            except Exception as e:
                elapsed = time.monotonic() - start
                failures.append((name, elapsed, str(e)))
                continue
            elapsed = time.monotonic() - start
            if elapsed >= 10.0:
                failures.append((name, elapsed, "exceeded 10s threshold"))

        assert len(failures) == 0, (
            f"Analytics endpoint failures over large dataset:\n"
            + "\n".join(f"  {n}: {e:.2f}s — {d}" for n, e, d in failures)
        )
