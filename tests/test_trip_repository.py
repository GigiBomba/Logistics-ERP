"""Tests for repositories.trip_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from repositories.trip_repository import TripRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> TripRepository:
    return TripRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _trip(db: InMemoryDB, **kw) -> int:
    """Seed a trip row, bypassing FK enforcement so we don't need parent
    rows (trucks, drivers, clients) for every test that doesn't test FK."""
    db.conn.execute("PRAGMA foreign_keys=OFF")
    d: Dict[str, Any] = dict(
        created_at="2026-06-01",
        truck_number="TRK-100",
        driver_name="Alice",
        client_name="ACME Corp",
        distance_km=500.0,
        total_price_eur=2500.0,
        net_profit=800.0,
        status="completed",
        delivery_country="DE",
        loading_country="FR",
        extra_costs=0,
        fuel_cost=0,
        toll_cost=0,
        salary_cost=0,
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO trips ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    db.conn.execute("PRAGMA foreign_keys=ON")
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _truck(db: InMemoryDB, **kw) -> int:
    """Seed a truck row with an explicit tenant (for JOIN-scoping tests)."""
    t: Dict[str, Any] = dict(
        plate_number="ISO-TRK",
        model="Volvo FH",
        manufacturer="Volvo",
    )
    t.update(kw)
    cols = ", ".join(t.keys())
    vals = ", ".join("?" for _ in t)
    db.conn.execute(f"INSERT INTO trucks ({cols}) VALUES ({vals})", list(t.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _invoice(db: InMemoryDB, trip_id: int, invoice_number: str, company_id: int) -> None:
    """Seed an invoice row linked to a trip with an explicit tenant."""
    db.conn.execute(
        "INSERT INTO invoices (trip_id, invoice_number, total_amount, status, company_id) "
        "VALUES (?, ?, 100.0, 'paid', ?)",
        (trip_id, invoice_number, company_id),
    )
    db.conn.commit()


# ── CRUD ─────────────────────────────────────────────────────────────


class TestCreateTrip:
    def test_creates_and_returns_id(self, db, repo):
        tid = repo.create({
            "created_at": "2026-06-10",
            "truck_number": "TRK-1",
            "driver_name": "Bob",
            "client_name": "Beta Inc",
            "distance_km": 300,
            "total_price_eur": 1500,
            "net_profit": 400,
            "status": "planned",
        })
        row = db.get_trip_by_id(tid)
        assert row is not None
        assert row["client_name"] == "Beta Inc"
        assert row["truck_number"] == "TRK-1"


class TestGetById:
    def test_returns_trip(self, db, repo):
        tid = _trip(db, client_name="FindMe")
        row = repo.get_by_id(tid)
        assert row is not None
        assert row["client_name"] == "FindMe"

    def test_returns_none_for_missing(self, repo):
        assert repo.get_by_id(99999) is None


class TestGetAll:
    def test_empty_db(self, repo):
        assert repo.get_all() == []

    def test_returns_all_trips(self, db, repo):
        _trip(db)
        _trip(db)
        _trip(db)
        all_t = repo.get_all()
        assert len(all_t) == 3

    def test_pagination(self, db, repo):
        for i in range(10):
            _trip(db, truck_number=f"TRK-{i}")
        page1 = repo.get_all(limit=3, offset=0)
        assert len(page1) == 3
        page2 = repo.get_all(limit=3, offset=3)
        assert len(page2) == 3
        # ensure different pages return different rows
        ids1 = {r["id"] for r in page1}
        ids2 = {r["id"] for r in page2}
        assert ids1.isdisjoint(ids2)


class TestUpdate:
    def test_updates_fields(self, db, repo):
        tid = _trip(db, status="planned")
        repo.update(tid, {"status": "in_transit", "truck_number": "TRK-NEW"})
        row = repo.get_by_id(tid)
        assert row["status"] == "in_transit"
        assert row["truck_number"] == "TRK-NEW"

    def test_update_unknown_column_raises(self, repo):
        with pytest.raises(ValueError, match="Invalid column"):
            repo.update(1, {"invalid_col": "x"})


class TestDelete:
    def test_removes_trip(self, db, repo):
        tid = _trip(db)
        repo.delete(tid)
        assert repo.get_by_id(tid) is None

    def test_delete_nonexistent_does_not_raise(self, repo):
        repo.delete(99999)  # should not crash


# ── Query methods ────────────────────────────────────────────────────


class TestGetFiltered:
    def test_search_by_client_name(self, db, repo):
        _trip(db, client_name="Alpha Corp")
        _trip(db, client_name="Beta Ltd")
        results = repo.get_filtered(search="Alpha")
        assert len(results) == 1
        assert results[0]["client_name"] == "Alpha Corp"

    def test_search_by_driver_name(self, db, repo):
        _trip(db, driver_name="Charlie")
        _trip(db, driver_name="Diana")
        results = repo.get_filtered(search="Diana")
        assert len(results) == 1

    def test_filter_by_truck(self, db, repo):
        _trip(db, truck_number="TRK-A")
        _trip(db, truck_number="TRK-B")
        _trip(db, truck_number="TRK-A")
        results = repo.get_filtered(truck="TRK-A")
        assert len(results) == 2

    def test_filter_by_status(self, db, repo):
        _trip(db, status="completed")
        _trip(db, status="planned")
        _trip(db, status="completed")
        results = repo.get_filtered(status="completed")
        assert len(results) == 2

    def test_combined_filters(self, db, repo):
        _trip(db, client_name="X", truck_number="T1", status="done")
        _trip(db, client_name="X", truck_number="T2", status="planned")
        _trip(db, client_name="Y", truck_number="T1", status="done")
        results = repo.get_filtered(search="X", truck="T1", status="done")
        assert len(results) == 1

    def test_empty_results(self, repo):
        assert repo.get_filtered(search="NoMatch") == []


class TestGetByStatus:
    def test_returns_matching(self, db, repo):
        _trip(db, status="completed")
        _trip(db, status="planned")
        _trip(db, status="completed")
        results = repo.get_by_status("completed")
        assert len(results) == 2

    def test_returns_empty_for_unused_status(self, repo):
        assert repo.get_by_status("nonexistent") == []


class TestGetByStatuses:
    def test_multiple_statuses(self, db, repo):
        _trip(db, status="completed")
        _trip(db, status="planned")
        _trip(db, status="in_transit")
        results = repo.get_by_statuses(["completed", "planned"])
        assert len(results) == 2


class TestGetByStatusesLimit:
    def test_limit_caps_rows(self, db, repo):
        for _ in range(5):
            _trip(db, status="planned")
        results = repo.get_by_statuses(["planned"], limit=2)
        assert len(results) == 2

    def test_no_limit_returns_all(self, db, repo):
        for _ in range(3):
            _trip(db, status="planned")
        results = repo.get_by_statuses(["planned"])
        assert len(results) == 3


class TestGetByDateRange:
    def test_returns_in_range(self, db, repo):
        _trip(db, created_at="2026-01-01")
        _trip(db, created_at="2026-02-15")
        _trip(db, created_at="2026-03-20")
        results = repo.get_by_date_range("2026-02-01", "2026-03-01")
        assert len(results) == 1
        assert results[0]["created_at"] == "2026-02-15"

    def test_empty_range(self, repo):
        assert repo.get_by_date_range("2020-01-01", "2020-01-31") == []


class TestGetByTruckNumber:
    def test_returns_matching(self, db, repo):
        _trip(db, truck_number="TRK-A")
        _trip(db, truck_number="TRK-B")
        _trip(db, truck_number="TRK-A")
        results = repo.get_by_truck_number("TRK-A")
        assert len(results) == 2


class TestGetByDriverId:
    def test_returns_matching(self, db, repo):
        _trip(db, driver_id=1)
        _trip(db, driver_id=2)
        _trip(db, driver_id=1)
        results = repo.get_by_driver_id(1)
        assert len(results) == 2


class TestGetByIds:
    def test_returns_batch(self, db, repo):
        t1 = _trip(db)
        t2 = _trip(db)
        _trip(db)
        results = repo.get_by_ids([t1, t2])
        assert len(results) == 2

    def test_empty_list(self, repo):
        assert repo.get_by_ids([]) == []


class TestGetLastActivity:
    def test_returns_last_date(self, db, repo):
        _trip(db, truck_id=1, created_at="2026-01-01")
        _trip(db, truck_id=1, created_at="2026-03-15")
        _trip(db, truck_id=2, created_at="2026-02-01")
        last = repo.get_last_activity_by_truck_id(1)
        assert last == "2026-03-15"

    def test_no_activity(self, repo):
        assert repo.get_last_activity_by_truck_id(999) is None


class TestGetLastActivityByTruckNumber:
    def test_returns_last_date(self, db, repo):
        _trip(db, truck_number="TRK-1", created_at="2026-01-01")
        _trip(db, truck_number="TRK-1", created_at="2026-05-20")
        last = repo.get_last_activity("TRK-1")
        assert last == "2026-05-20"

    def test_none_for_missing(self, repo):
        assert repo.get_last_activity("NONEXISTENT") is None


class TestGetDailyProfit:
    def test_returns_daily_profit(self, db, repo):
        _trip(db, start_date="2026-01-01", net_profit=100, status="completed")
        _trip(db, start_date="2026-01-01", net_profit=200, status="completed")
        _trip(db, start_date="2026-01-02", net_profit=300, status="delivered")
        result = repo.get_daily_profit("2026-01-01", "2026-01-02")
        assert len(result) == 2
        day_map = dict(result)
        assert day_map["2026-01-01"] == 300.0
        assert day_map["2026-01-02"] == 300.0

    def test_filters_non_delivered_statuses(self, db, repo):
        _trip(db, start_date="2026-01-01", net_profit=500, status="planned")
        result = repo.get_daily_profit("2026-01-01", "2026-01-31")
        assert result == []


class TestGetActiveExcludingStatuses:
    def test_excludes_given_statuses(self, db, repo):
        _trip(db, status="planned")
        _trip(db, status="in_transit")
        _trip(db, status="completed")
        _trip(db, status="")
        active = repo.get_active_excluding_statuses(["completed", "done", "paid"])
        statuses = {r["status"] for r in active}
        assert "completed" not in statuses
        assert len(active) >= 2  # planned + empty


class TestGetNextCmrSequence:
    def test_first_sequence(self, repo):
        number, seq = repo.get_next_cmr_sequence(2026)
        assert seq == 1
        assert number == "CMR-2026-000001"

    def test_increments_sequence(self, repo):
        repo.get_next_cmr_sequence(2026)
        number, seq = repo.get_next_cmr_sequence(2026)
        assert seq == 2
        assert number == "CMR-2026-000002"


class TestGetDocumentsAttached:
    def test_returns_parsed_list(self, db, repo):
        tid = _trip(db, documents_attached='[1, 2, 3]')
        result = repo.get_documents_attached(tid)
        assert result == [1, 2, 3]

    def test_empty_when_null(self, db, repo):
        tid = _trip(db, documents_attached=None)
        assert repo.get_documents_attached(tid) == []

    def test_empty_when_missing(self, repo):
        assert repo.get_documents_attached(99999) == []


class TestUpdateCmrFields:
    def test_updates_cmr_fields(self, db, repo):
        tid = _trip(db)
        repo.update_cmr_fields(tid, "CMR-2026-000042", 42)
        row = repo.get_by_id(tid)
        assert row["cmr_number"] == "CMR-2026-000042"
        assert row["cmr_sequence"] == 42
        assert row["cmr_status"] == "generated"


class TestGetByCmrNumber:
    def test_finds_by_cmr(self, db, repo):
        _trip(db, cmr_number="CMR-2026-000001")
        _trip(db, cmr_number="CMR-2026-000002")
        results = repo.get_by_cmr_number("CMR-2026-000001")
        assert len(results) == 1


class TestGetByCmrNumberTenantIsolation:
    """``get_by_cmr_number`` must never return another company's trip."""

    def test_cmr_number_explicit_company_id(self, db, repo):
        _trip(db, cmr_number="CMR-2026-000001", company_id=1)
        _trip(db, cmr_number="CMR-2026-000001", company_id=2)
        results = repo.get_by_cmr_number("CMR-2026-000001", company_id=1)
        assert len(results) == 1
        assert results[0]["company_id"] == 1
        results_b = repo.get_by_cmr_number("CMR-2026-000001", company_id=2)
        assert len(results_b) == 1
        assert results_b[0]["company_id"] == 2

    def test_cmr_number_context_scoped(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        _trip(db, cmr_number="CMR-2026-000001", company_id=1)
        _trip(db, cmr_number="CMR-2026-000001", company_id=2)
        results = repo.get_by_cmr_number("CMR-2026-000001")
        assert len(results) == 1
        assert results[0]["company_id"] == 1


class TestGetByTruckPlate:
    def test_finds_by_truck_number(self, db, repo):
        _trip(db, truck_number="PLATE-123")
        results = repo.get_by_truck_plate("PLATE-123")
        assert len(results) == 1


class TestGetByDriverName:
    def test_fuzzy_match(self, db, repo):
        _trip(db, driver_name="John Smith")
        results = repo.get_by_driver_name("john")
        assert len(results) == 1

    def test_no_match(self, repo):
        assert repo.get_by_driver_name("nobody") == []


# ── Tenant isolation: JOINs must scope BOTH sides ─────────────────────


class TestGetByTruckPlateTenantIsolation:
    """``get_by_truck_plate`` LEFT JOINs trips → trucks: the trucks side must
    be company-scoped so a company-B truck plate never surfaces company-A trips."""

    def test_cross_tenant_truck_plate_not_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        tid_b = _truck(db, plate_number="PLT-B", company_id=2)
        _trip(db, truck_id=tid_b, truck_number="TRK-A", company_id=1)
        assert repo.get_by_truck_plate("PLT-B") == []

    def test_same_company_truck_plate_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        tid_a = _truck(db, plate_number="PLT-A", company_id=1)
        _trip(db, truck_id=tid_a, truck_number="TRK-A", company_id=1)
        results = repo.get_by_truck_plate("PLT-A")
        assert len(results) == 1


class TestGetByInvoiceViaTripInvoiceTenantIsolation:
    """``get_by_invoice_via_trip_invoice`` JOINs trips → invoices: the
    invoices side must be company-scoped too."""

    def test_cross_tenant_invoice_not_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        _trip(db, company_id=1)
        trip_x = _trip(db, company_id=1)
        # Company 1 trip whose linked invoice row is owned by company 2 —
        # the invoices side of the JOIN must reject it.
        _invoice(db, trip_id=trip_x, invoice_number="INV-B", company_id=2)
        assert repo.get_by_invoice_via_trip_invoice("INV-B") == []

    def test_same_company_invoice_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        trip_a = _trip(db, company_id=1)
        _invoice(db, trip_id=trip_a, invoice_number="INV-2", company_id=1)
        results = repo.get_by_invoice_via_trip_invoice("INV-2")
        assert len(results) == 1
        assert results[0]["id"] == trip_a


class TestGetTopTrucksByRevenueTenantIsolation:
    """``get_top_trucks_by_revenue`` LEFT JOINs trips → trucks: a company-B
    truck must never contribute revenue to a company-A top-trucks list."""

    def test_cross_tenant_truck_not_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        tid_a = _truck(db, plate_number="PLT-A", company_id=1)
        tid_b = _truck(db, plate_number="PLT-B", company_id=2)
        _trip(db, truck_id=tid_a, start_date="2026-01-10", status="delivered",
              total_price_eur=1000, company_id=1)
        _trip(db, truck_id=tid_b, start_date="2026-01-10", status="delivered",
              total_price_eur=9000, company_id=2)
        results = repo.get_top_trucks_by_revenue("2026-01-01", "2026-01-31", limit=4, company_id=1)
        assert len(results) == 1
        assert results[0]["truck_number"] == "PLT-A"
        assert results[0]["revenue"] == 1000
