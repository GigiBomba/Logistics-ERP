"""Scale validation — blueprint Appendix A, Phase 6.2 (the implementable part).

Validates the suite's repository/analytics read paths against a synthetic
10,000-trip dataset: bulk ingestion integrity (exact row count, no duplicate
ids, bounded seed time) and financial aggregation correctness at volume
(counts/sums consistent with the raw table, bounded query time).

Scope note: blueprint Phase 6 is a *future roadmap* item. 6.1 (threshold
calibration) and 6.3 (one-week operational certification) are non-code
procedures documented in ``tests/workflow_integrity/reports/README.md``
("Phase 6 — calibration & certification"). This module delivers the 6.2 scale
entry point and keeps the roadmap framing intact.

The module never runs in the default suite: it carries ``pytest.mark.scale``
(and ``slow``) and every test self-skips unless ``-m scale`` is explicitly
requested. Run it with:

    python -m pytest tests\\workflow_integrity\\scale -m scale
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta

import pytest

from repositories.trip_repository import TripRepository
from services.analytics_service import AnalyticsService


pytestmark = [pytest.mark.scale, pytest.mark.slow]


# ═════════════════════════════════════════════════════════════════════════════
# Deterministic synthetic dataset — identical 10k trips on every run.
# ═════════════════════════════════════════════════════════════════════════════

TRIP_COUNT = 10_000
_SEED_BATCH = 1_000
_RNG = random.Random(2026)  # fixed seed → reproducible validation dataset
_BASE_DATE = datetime(2025, 1, 1)

_TRUCKS = [f"TRUCK-{i:02d}" for i in range(1, 51)]
_DRIVERS = [f"Driver-{i:02d}" for i in range(1, 31)]
_CLIENTS = [f"Client-{i:02d}" for i in range(1, 21)]
_STATUSES = ["Delivered", "Completed", "In Transit", "Planned", "Paid"]
_COUNTRIES = ["RO", "DE", "FR", "NL", "BE", "AT", "HU", "IT", "PL", "CZ"]

# Explicit subset of TripRepository.COLUMNS — the repository allowlist is the
# source of truth, so a schema drift here fails loudly instead of silently.
_SEED_COLUMNS = [
    "id", "created_at", "truck_number", "driver_name", "client_name",
    "distance_km", "total_price_eur", "rate_per_km", "gross_per_km", "net_profit",
    "start_date", "end_date", "extra_costs", "fuel_cost", "toll_cost",
    "salary_cost", "currency", "status", "loading_country", "delivery_country",
]
assert set(_SEED_COLUMNS) <= set(TripRepository.COLUMNS), (
    "Seed columns drifted from TripRepository.COLUMNS"
)


def _trip_row(i: int) -> tuple:
    """One deterministic synthetic trip row matching ``_SEED_COLUMNS``.

    Financial consistency is baked in: ``net_profit`` is exactly
    ``price - fuel - toll - salary - extra`` so the aggregate comparisons in
    the query test are meaningful (they still compare against the raw table,
    not against these formulas).
    """
    distance = round(_RNG.uniform(100.0, 2500.0), 2)
    price = round(_RNG.uniform(500.0, 8000.0), 2)
    fuel = round(_RNG.uniform(100.0, 1500.0), 2)
    toll = round(_RNG.uniform(20.0, 400.0), 2)
    salary = round(_RNG.uniform(100.0, 800.0), 2)
    extra = round(_RNG.uniform(0.0, 200.0), 2)
    profit = round(price - fuel - toll - salary - extra, 2)
    rate_per_km = round(price / distance, 4) if distance > 0 else 0.0
    gross_per_km = round(profit / distance, 4) if distance > 0 else 0.0

    start = _BASE_DATE + timedelta(days=_RNG.randint(0, 364), hours=_RNG.randint(0, 23))
    end = start + timedelta(days=_RNG.randint(1, 5))
    created = start - timedelta(days=_RNG.randint(0, 3))

    return (
        i,
        created.strftime("%Y-%m-%d %H:%M:%S"),
        _RNG.choice(_TRUCKS), _RNG.choice(_DRIVERS), _RNG.choice(_CLIENTS),
        distance, price, rate_per_km, gross_per_km, profit,
        start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
        extra, fuel, toll, salary,
        "EUR", _RNG.choice(_STATUSES), _RNG.choice(_COUNTRIES),
        _RNG.choice(_COUNTRIES),
    )


def _seed_trips(db, count: int = TRIP_COUNT) -> None:
    """Bulk-insert *count* trips via the repository bulk path.

    Mirrors the repository bulk-insert pattern (see ``pipeline_repository``):
    one transaction, ``db.executemany`` per batch, a single commit at the end.
    """
    cols = ", ".join(_SEED_COLUMNS)
    placeholders = ", ".join("?" for _ in _SEED_COLUMNS)
    query = f"INSERT INTO trips ({cols}) VALUES ({placeholders})"

    repo = TripRepository(db)
    with repo.transaction():
        batch: list[tuple] = []
        for i in range(1, count + 1):
            batch.append(_trip_row(i))
            if len(batch) >= _SEED_BATCH:
                db.executemany(query, batch)
                batch.clear()
        if batch:
            db.executemany(query, batch)


# ═════════════════════════════════════════════════════════════════════════════
# Default-suite protection: skip unless ``-m scale`` was explicitly requested.
# ═════════════════════════════════════════════════════════════════════════════

def _scale_requested(config: pytest.Config) -> bool:
    """True when the active ``-m`` expression explicitly selects ``scale``."""
    expr = getattr(config.option, "markexpr", "") or ""
    return "scale" in expr.split()


@pytest.fixture(autouse=True)
def _require_explicit_scale_selection(request: pytest.FixtureRequest) -> None:
    """Skip the whole module unless the operator asked for ``-m scale``.

    Mirrors the suite's heavy-test convention (see the ``slow`` marker): the
    scale module is never part of the default run.
    """
    if not _scale_requested(request.config):
        pytest.skip("Scale-validation tests run only when explicitly selected with '-m scale'")


# ═════════════════════════════════════════════════════════════════════════════
# 6.2 — Test A: 10k-trip seed (bulk ingestion integrity + seed budget)
# ═════════════════════════════════════════════════════════════════════════════

class TestScaleSeed:
    """Phase 6.2 — bulk ingestion of a 10,000-trip dataset."""

    def test_seed_10k_trips_within_budget(self, db) -> None:
        started = time.monotonic()
        _seed_trips(db, TRIP_COUNT)
        elapsed = time.monotonic() - started

        assert elapsed < 180.0, (
            f"Seeding {TRIP_COUNT} trips took {elapsed:.1f}s (budget: < 180s)"
        )

        row = db.conn.execute(
            "SELECT COUNT(*) AS total, COUNT(DISTINCT id) AS distinct_ids FROM trips"
        ).fetchone()
        assert row["total"] == TRIP_COUNT, (
            f"Expected {TRIP_COUNT} seeded trips, found {row['total']}"
        )
        assert row["distinct_ids"] == TRIP_COUNT, (
            f"Duplicate trip ids in the seeded dataset: "
            f"{TRIP_COUNT - row['distinct_ids']} collisions"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 6.2 — Test B: query at scale (read paths stay correct and fast)
# ═════════════════════════════════════════════════════════════════════════════

class TestScaleQueries:
    """Phase 6.2 — repository/analytics read paths at 10k-trip volume."""

    def test_listing_and_financial_aggregate_at_scale(self, db) -> None:
        _seed_trips(db, TRIP_COUNT)

        # Source-of-truth sums straight from the table the aggregates read.
        raw = db.conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(total_price_eur) AS revenue, SUM(net_profit) AS profit "
            "FROM trips"
        ).fetchone()
        assert raw["total"] == TRIP_COUNT, (
            f"Expected {TRIP_COUNT} trips in the table, found {raw['total']}"
        )

        # Read path 1 — repository trip listing.
        repo = TripRepository(db)
        listing_started = time.monotonic()
        trips = repo.get_all(limit=TRIP_COUNT + 500)
        listing_elapsed = time.monotonic() - listing_started
        assert len(trips) == TRIP_COUNT, (
            f"Trip listing returned {len(trips)} rows, expected {TRIP_COUNT}"
        )
        assert listing_elapsed < 60.0, (
            f"Trip listing at 10k scale took {listing_elapsed:.1f}s (budget: < 60s)"
        )

        # Read path 2 — financial aggregate consumed by the scorecard.
        analytics = AnalyticsService(db)
        aggregate_started = time.monotonic()
        monthly = analytics.get_financial()
        aggregate_elapsed = time.monotonic() - aggregate_started
        assert aggregate_elapsed < 60.0, (
            f"Financial aggregate at 10k scale took {aggregate_elapsed:.1f}s "
            f"(budget: < 60s)"
        )

        revenue = sum(float(r["revenue"] or 0) for r in monthly)
        profit = sum(float(r["profit"] or 0) for r in monthly)
        assert revenue == pytest.approx(float(raw["revenue"]), rel=1e-6, abs=0.01), (
            f"Aggregate revenue {revenue} != raw table revenue {raw['revenue']}"
        )
        assert profit == pytest.approx(float(raw["profit"]), rel=1e-6, abs=0.01), (
            f"Aggregate profit {profit} != raw table profit {raw['profit']}"
        )