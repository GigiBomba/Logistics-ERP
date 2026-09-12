"""Phase-3 evidence tests for the approved low-risk performance fixes.

Each test demonstrates the before/after metric for one fix:

  * Fix 1 — ``DriverTruckService.list_drivers`` enrichment is constant-query
    (was 2N+1 per-driver lookups).
  * Fix 2 — ``DispatchService.get_dispatch_board_data`` resolves all routes
    in one batched query (was N sequential ``get_by_id`` calls).
  * Fix 3 — ``FleetService.search`` pushes query/status filters to SQL
    (was: load up to 200 rows then filter in Python).
  * Fix 4 — ``get_recent_trips_for_matching`` fetch is bounded by SQL LIMIT.
  * Fix 5 — ``get_trips_by_date_proximity`` fetch is bounded by SQL LIMIT
    (was: materialise every row in the window, then sort in Python).
  * Fix 6 — ``CostEngineService`` fetches the truck once per estimate
    (was: two identical ``get_by_id`` calls).
  * Fix 7 — ``STATUS_TO_COLUMN`` / ``COLUMN_KEYS`` defined once in
    ``services/dispatch_service/constants.py`` and imported everywhere.

Queries are counted by wrapping ``BaseRepository._execute_query`` — the
single funnel every repository SELECT/INSERT/UPDATE/DELETE passes through —
so the counts reflect real SQL statements, not mock call counts.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from repositories import BaseRepository
from repositories.route_repository import RouteRepository
from repositories.trip_repository import TripRepository
from services.cost_engine import CostEngineService
from services.dispatch_service.constants import STATUS_TO_COLUMN
from services.dispatch_service.dispatch_service import DispatchService
from services.driver_truck_service import DriverTruckService
from services.fleet_service import FleetService
from services.trip_service import TripService
from models.cost_models import CostEstimateRequest
from models.vehicle_models import VehicleSearchRequest
from tests.test_helpers import make_db


# ── Query / row counting helper ──────────────────────────────────────────


class _CountingCursor:
    """Proxy cursor that tallies rows materialised via ``fetchall``/``fetchone``."""

    def __init__(self, cursor, stats):
        self._cursor = cursor
        self._stats = stats

    def fetchall(self):
        rows = self._cursor.fetchall()
        self._stats["rows"] += len(rows)
        return rows

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is not None:
            self._stats["rows"] += 1
        return row

    def __getattr__(self, name):
        return getattr(self._cursor, name)


@contextmanager
def _count_queries():
    """Count repo SQL statements and rows materialised on any repository."""
    stats = {"queries": 0, "rows": 0}
    original = BaseRepository._execute_query

    def counting_execute_query(self, query, params=()):
        stats["queries"] += 1
        return _CountingCursor(original(self, query, params), stats)

    with patch.object(BaseRepository, "_execute_query", counting_execute_query):
        yield stats


# ── Fix 1: DriverTruckService.list_drivers (N+1 → constant) ──────────────


def _seed_driver_trucks(db, n=30):
    """Seed ``n`` drivers, each assigned to their own truck.

    ``DriverResult`` requires columns the ``drivers`` table does not store
    (pre-existing model/DB mismatch) — those are backfilled via SQL so the
    typed enrichment can run against the real query path.
    """
    db.conn.execute("ALTER TABLE drivers ADD COLUMN hours_worked REAL DEFAULT 0")
    db.conn.execute("ALTER TABLE drivers ADD COLUMN max_hours_per_day REAL DEFAULT 9")
    db.conn.execute("ALTER TABLE drivers ADD COLUMN status TEXT DEFAULT 'active'")
    db.conn.commit()
    svc = DriverTruckService(db)
    for i in range(n):
        did = svc._driver_repo.create({
            "name": f"Driver {i}", "email": f"d{i}@test.local", "phone": "+40",
            "license_number": f"L{i}", "is_active": 1,
            "created_at": "2026-01-01", "updated_at": "2026-01-01",
        })
        db.conn.execute(
            "UPDATE drivers SET hours_worked = 1.0, max_hours_per_day = 9.0, status = 'active' "
            "WHERE id = ?", (did,),
        )
        tid = svc._fleet_repo.create({
            "plate_number": f"B-{i:03d}", "model": "FH",
            "manufacturer": "Volvo", "active_status": 1,
        })
        svc._repo.assign(did, tid)
    db.conn.commit()
    return svc


class TestFix1ListDriversQueryCount:
    def test_list_drivers_enrichment_is_constant_queries(self):
        db = make_db()
        svc = _seed_driver_trucks(db, n=30)

        # BEFORE: the old per-driver enrichment pattern (get_all + per driver
        # get_by_driver + fleet get_by_id) issues 2N+1 queries.
        with _count_queries() as before:
            for d in svc._driver_repo.get_all():
                assignment = svc._repo.get_by_driver(d["id"])
                if assignment:
                    svc._fleet_repo.get_by_id(assignment["truck_id"])
        assert before["queries"] == 2 * 30 + 1, before

        # AFTER: batched list_drivers — constant query count, independent of N.
        with _count_queries() as after:
            result = svc.list_drivers()
        assert result.success is True
        assert len(result.data) == 30
        # drivers.get_all + assignments.get_all + plates batch + truck validity
        # batch = 4 queries total.
        assert after["queries"] == 4, after
        # Output shape preserved: every driver carries its truck enrichment.
        assert all(d.current_truck_id is not None for d in result.data)
        assert all(d.current_truck_plate.startswith("B-") for d in result.data)

    def test_list_drivers_missing_truck_not_reported(self):
        """A driver without an assignment keeps the empty-truck shape."""
        db = make_db()
        svc = _seed_driver_trucks(db, n=5)
        unassigned = svc._driver_repo.create({
            "name": "No Truck", "email": "nt@test.local", "phone": "+40",
            "license_number": "L0", "is_active": 1,
            "created_at": "2026-01-01", "updated_at": "2026-01-01",
        })
        db.conn.execute(
            "UPDATE drivers SET hours_worked = 1.0, max_hours_per_day = 9.0, status = 'active' "
            "WHERE id = ?", (unassigned,),
        )
        db.conn.commit()

        result = svc.list_drivers()
        assert result.success is True
        no_truck = [d for d in result.data if d.name == "No Truck"]
        assert len(no_truck) == 1
        assert no_truck[0].current_truck_id is None
        assert no_truck[0].current_truck_plate == ""


# ── Fix 2: DispatchService.get_dispatch_board_data (N+1 → 1 batched query) ──


def _seed_dispatch_board(db, n=10):
    trip_repo = TripRepository(db)
    route_repo = RouteRepository(db)
    route_ids = []
    for i in range(n):
        rid = route_repo.create({
            "route_fingerprint": f"fp-{i}",
            "created_at": "2026-01-01T00:00:00Z",
            "last_calculated_at": "2026-01-01T00:00:00Z",
            "stops_json": "[]",
            "geometry_encoding": "zlib-json",
            "route_summary_json": json.dumps({
                "origin": f"City{i}", "destination": f"Town{i}",
            }),
        })
        route_ids.append(rid)
        trip_repo.create({
            "status": "Planned",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "route_history_v2_id": rid,
            "created_at": "2026-01-01",
        })
    return trip_repo, route_repo


class TestFix2DispatchBoardQueryCount:
    def test_board_data_resolves_all_routes_in_one_query(self):
        db = make_db()
        trip_repo, route_repo = _seed_dispatch_board(db, n=10)

        class FakeTripService:
            _trip_repo = trip_repo
            _route_repo = route_repo

        svc = DispatchService(
            trip_service=FakeTripService(),
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=MagicMock(),
        )

        with _count_queries() as stats:
            response = svc.get_dispatch_board_data()

        assert len(response.column_trips["Planned"]) == 10
        for card in response.column_trips["Planned"]:
            assert card["origin"].startswith("City")
            assert card["destination"].startswith("Town")
        # get_by_statuses (1) + batched get_routes_by_ids (1) — constant,
        # NOT 1 + N per-trip get_by_id lookups.
        assert stats["queries"] == 2, stats


# ── Fix 2b: GET /dispatch/board endpoint (16 status queries + N route → 2) ───


def _seed_board_endpoint(db, n):
    """Seed ``n`` Planned trips (each with a route) for company 1."""
    trip_repo = TripRepository(db)
    route_repo = RouteRepository(db)
    for i in range(n):
        rid = route_repo.create({
            "route_fingerprint": f"ep-fp-{i}",
            "created_at": "2026-01-01T00:00:00Z",
            "last_calculated_at": "2026-01-01T00:00:00Z",
            "stops_json": "[]",
            "geometry_encoding": "zlib-json",
            "route_summary_json": json.dumps({
                "origin": f"City{i}", "destination": f"Town{i}",
            }),
        })
        trip_repo.create({
            "status": "Planned",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "route_history_v2_id": rid,
            "created_at": "2026-01-01",
            "company_id": 1,  # endpoint queries are company-scoped (JWT)
        })
    return trip_repo, route_repo


def _hit_board_endpoint(service, company_id: int = 1,
                        delivered_window_days: int = 30, limit: int = 200):
    """Call ``get_dispatch_board`` exactly as FastAPI would (same thread).

    The endpoint is a plain sync function; invoking it directly keeps the
    test on the thread that owns the ``:memory:`` SQLite connection — an
    HTTP TestClient runs in a worker thread whose per-thread ``:memory:``
    connection would be empty.  The query profile is identical to the HTTP
    path (auth and the service dependency add no DB statements).
    """
    from backend.api.v1.dispatch import get_dispatch_board
    return get_dispatch_board(
        current_user={
            "id": 1, "email": "test@test.com", "role": "dispatcher",
            "company_id": company_id,
        },
        delivered_window_days=delivered_window_days,
        limit=limit,
        service=service,
    )


class TestFix2bDispatchBoardEndpointQueryCount:
    def test_board_endpoint_constant_queries(self):
        db = make_db()
        trip_repo, route_repo = _seed_board_endpoint(db, n=30)
        service = TripService(db)

        # BEFORE: the old endpoint loop — one company-scoped get_filtered per
        # status (16 statuses) plus one route get_by_id per trip (N).
        with _count_queries() as before:
            seen: set[int] = set()
            for raw_status in STATUS_TO_COLUMN:
                trips = service.get_filtered(
                    search="", status=raw_status, limit=200, company_id=1,
                )
                for trip in trips or []:
                    trip_id = trip.get("id")
                    if trip_id is None or trip_id in seen:
                        continue
                    seen.add(trip_id)
                    route_id = trip.get("route_history_v2_id")
                    if route_id:
                        route_repo.get_by_id(int(route_id))
        assert before["queries"] == 16 + 30, before

        # AFTER: the endpoint issues exactly 2 queries — 1 batched trip fetch
        # + 1 batched route fetch — constant, independent of trip count.
        with _count_queries() as after:
            data = _hit_board_endpoint(service)
        assert data["columns"]["Planned"] == 30
        assert data["columns"]["Loading"] == 0
        assert len(data["trips"]) == 30
        assert after["queries"] == 2, after
        # Response shape preserved: origin/destination resolved from the
        # batched route map.
        for card in data["trips"]:
            assert card["origin"].startswith("City")
            assert card["destination"].startswith("Town")

    def test_board_endpoint_still_constant_with_more_trips(self):
        """2x the trips must not add queries (N+1 would grow to 16 + 60)."""
        db = make_db()
        _seed_board_endpoint(db, n=60)
        service = TripService(db)

        with _count_queries() as after:
            data = _hit_board_endpoint(service)
        assert data["columns"]["Planned"] == 60
        assert len(data["trips"]) == 60
        assert after["queries"] == 2, after


# ── Fix 3: FleetService.search (Python filter → SQL filter) ────────────────


def _seed_fleet(db, n=500):
    svc = FleetService(db)
    for i in range(n):
        svc._fleet_repo.create({
            "plate_number": f"B-{i:03d}",
            "model": "FH",
            "manufacturer": "Volvo",
            "status": "active" if i % 2 == 0 else "inactive",
            "active_status": 1 if i % 2 == 0 else 0,
        })
    return svc


class TestFix3FleetSearchSqlPushdown:
    def test_search_filters_in_sql_not_in_python(self):
        db = make_db()
        svc = _seed_fleet(db, n=500)

        # BEFORE: old behaviour — load the first page of ALL trucks (200) via
        # get_all, then filter in Python.  Matches living past row 200 are
        # invisible to the client-side filter.
        with _count_queries() as before_stats:
            before_rows = svc._fleet_repo.get_all()
            before_matches = [
                r for r in before_rows
                if "b-4" in r.get("plate_number", "").lower()
            ]
        assert before_stats["rows"] == 200, before_stats  # capped page fetch
        assert before_matches == [], "old filter missed rows past the 200 cap"

        # AFTER: the query/status filters run in SQL — only the 100 matching
        # rows (B-400..B-499) are materialised, and all of them are returned.
        with _count_queries() as after_stats:
            result = svc.search(VehicleSearchRequest(query="B-4"))
        assert result.success is True
        assert len(result.data) == 100
        assert after_stats["rows"] == 100, after_stats

    def test_search_status_filter_matches_old_case_insensitive_semantics(self):
        db = make_db()
        svc = _seed_fleet(db, n=200)

        # Old Python filter: r.get("status","").lower() == status.lower()
        with _count_queries() as stats:
            result = svc.search(VehicleSearchRequest(status="ACTIVE"))
        assert result.success is True
        assert len(result.data) == 100
        assert all(v.status == "active" for v in result.data)
        # Only the 100 matching rows are fetched from the DB.
        assert stats["rows"] == 100, stats


# ── Fix 4: get_recent_trips_for_matching (SQL LIMIT present) ───────────────


def _seed_trips(db, n=600, days_back_max=5):
    """Seed ``n`` trips with start dates in the last ``days_back_max`` days.

    ``get_recent_trips_for_matching`` looks at the trailing 30-day window, so
    the seed dates must be relative to *today*.
    """
    from datetime import datetime, timedelta
    trip_repo = TripRepository(db)
    today = datetime.now()
    for i in range(n):
        date_str = (today - timedelta(days=i % max(days_back_max, 1))).strftime("%Y-%m-%d")
        trip_repo.create({
            "status": "Planned",
            "start_date": date_str,
            "end_date": date_str,
            "created_at": date_str,
        })
    return trip_repo


class TestFix4RecentTripsForMatchingBounded:
    def test_fetch_is_bounded_by_sql_limit(self):
        db = make_db()
        trip_repo = _seed_trips(db, n=600)

        # 600 rows fall inside the 30-day window, yet the SQL ``LIMIT ?``
        # (present in get_recent_trips_for_matching) materialises only 50.
        with _count_queries() as stats:
            rows = trip_repo.get_recent_trips_for_matching(
                days_back=30, limit=50,
            )
        assert len(rows) == 50
        assert stats["rows"] == 50, stats


# ── Fix 5: get_trips_by_date_proximity (bounded fetch + Python sort) ───────


class TestFix5DateProximityBounded:
    def _proximity(self, row, anchor_iso):
        from datetime import datetime
        anchor = datetime.strptime(anchor_iso, "%Y-%m-%d")
        row_date = datetime.strptime(str(row["start_date"])[:10], "%Y-%m-%d")
        return abs((row_date - anchor).total_seconds())

    def test_fetch_bounded_and_ordering_preserved(self):
        db = make_db()
        target = "2026-06-15"
        # 600 trips spread across the ±14-day window around the target.
        trip_repo = TripRepository(db)
        for i in range(600):
            offset_days = (i % 29) - 14  # -14..+14
            day = 15 + offset_days
            date_str = f"2026-06-{day:02d}"
            trip_repo.create({
                "status": "Planned",
                "start_date": date_str,
                "end_date": date_str,
                "created_at": date_str,
            })

        with _count_queries() as stats:
            rows = trip_repo.get_trips_by_date_proximity(
                target_date=target, window_days=14, limit=25,
            )
        assert len(rows) == 25
        # Only the 25-row SQL page is materialised (was: all 600 window rows).
        assert stats["rows"] == 25, stats
        # Same return fields as before (full trip rows).
        assert all("id" in r and "status" in r and "start_date" in r for r in rows)
        # Ordering semantics preserved: sorted by date proximity ascending.
        proximities = [self._proximity(r, target) for r in rows]
        assert proximities == sorted(proximities)

    def test_invalid_target_falls_back_to_recent(self):
        db = make_db()
        trip_repo = _seed_trips(db, n=20)
        # Unparseable target dates delegate to get_recent_trips_for_matching()
        # (pre-existing fallback — the window rows are bounded by its SQL LIMIT).
        rows = trip_repo.get_trips_by_date_proximity("not-a-date", limit=5)
        assert rows == trip_repo.get_recent_trips_for_matching()
        assert len(rows) == 20


# ── Fix 6: CostEngineService (single truck fetch) ──────────────────────────


class TestFix6SingleTruckFetch:
    def test_estimate_fetches_truck_once(self):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "manufacturer": "Volvo",
            "model": "FH",
            "plate_number": "B-123",
            "fuel_consumption": 35,
        }
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo,
        )
        # No consumption in the request → both consumption resolution and
        # truck_info need the truck row.  It must be fetched exactly once.
        request = CostEstimateRequest(distance_km=100, truck_id=1)
        result = engine.estimate(request)
        assert result.success is True
        assert result.data.truck_info == "Volvo FH (B-123)"
        # Consumption came from the same fetched row: 100 * 35 / 100 * 1.5.
        assert result.data.breakdown.fuel_cost == 52.5
        assert mock_repo.get_by_id.call_count == 1, mock_repo.get_by_id.call_count
        mock_repo.get_by_id.assert_called_once_with(1)

    def test_estimate_does_not_fetch_when_no_truck_id(self):
        mock_repo = MagicMock()
        engine = CostEngineService(
            fuel_price_eur_per_liter=1.5, fleet_repo=mock_repo,
        )
        request = CostEstimateRequest(distance_km=100)
        result = engine.estimate(request)
        assert result.success is True
        assert result.data.truck_info == ""
        mock_repo.get_by_id.assert_not_called()


# ── Fix 7: STATUS_TO_COLUMN single source of truth ─────────────────────────


class TestFix7StatusColumnSingleSource:
    def test_both_consumers_import_the_same_constants(self):
        from services.dispatch_service import constants
        from services.dispatch_service.dispatch_service import (
            COLUMN_KEYS as SVC_COLUMN_KEYS,
            STATUS_TO_COLUMN as SVC_STATUS_TO_COLUMN,
        )
        from backend.api.v1 import dispatch as api_dispatch

        # Identity — not a re-defined copy — proves there is no duplication.
        assert SVC_STATUS_TO_COLUMN is constants.STATUS_TO_COLUMN
        assert SVC_COLUMN_KEYS is constants.COLUMN_KEYS
        assert api_dispatch.STATUS_TO_COLUMN is constants.STATUS_TO_COLUMN
        assert api_dispatch.COLUMN_KEYS is constants.COLUMN_KEYS
        # Mapping contents unchanged (regression guard).
        assert constants.STATUS_TO_COLUMN["InTransit"] == "In Transit"
        assert constants.STATUS_TO_COLUMN["Completed"] == "Delivered"
        assert constants.COLUMN_KEYS == [
            "Planned", "Loading", "In Transit", "Delivered", "Cancelled",
        ]