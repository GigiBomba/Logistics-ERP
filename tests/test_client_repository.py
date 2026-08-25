"""Tests for repositories.client_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.client_repository import ClientRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    d = InMemoryDB()
    # Add client_id column to trips table if missing (needed by repository queries)
    try:
        d.conn.execute("ALTER TABLE trips ADD COLUMN client_id INTEGER REFERENCES clients(id)")
        d.conn.commit()
    except Exception:
        pass
    return d


@pytest.fixture
def repo(db) -> ClientRepository:
    return ClientRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _client(db: InMemoryDB, **kw) -> int:
    from datetime import datetime
    d = dict(
        name="Test Client",
        contact_person="John",
        phone="+123",
        email="john@test.com",
        address="123 Street",
        vat_number="RO123",
        currency_preference="EUR",
        notes="",
        is_active=1,
        created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        updated_at="",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO clients ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _trip(db: InMemoryDB, **kw) -> int:
    d = dict(
        created_at="2026-06-01",
        truck_number="TRK-1",
        driver_name="Alice",
        client_name="Test Client",
        distance_km=500,
        total_price_eur=2500,
        net_profit=800,
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
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── CRUD ─────────────────────────────────────────────────────────────


class TestCreate:
    def test_creates_and_returns_id(self, db, repo):
        cid = repo.create({
            "name": "New Client Inc",
            "contact_person": "Jane",
            "phone": "+456",
            "email": "jane@newclient.com",
            "is_active": 1,
        })
        assert cid > 0
        row = db.conn.execute("SELECT * FROM clients WHERE id = ?", (cid,)).fetchone()
        assert row is not None
        assert row["name"] == "New Client Inc"

    def test_defaults_is_active(self, repo):
        cid = repo.create({"name": "Default Active"})
        row = repo.get_by_id(cid)
        assert row["is_active"] == 1


class TestGetById:
    def test_returns_client(self, db, repo):
        cid = _client(db, name="Findable")
        row = repo.get_by_id(cid)
        assert row is not None
        assert row["name"] == "Findable"

    def test_none_for_missing(self, repo):
        assert repo.get_by_id(99999) is None


class TestGetAll:
    def test_empty_db(self, repo):
        assert repo.get_all() == []

    def test_active_only_by_default(self, db, repo):
        _client(db, name="Active One", is_active=1)
        _client(db, name="Inactive One", is_active=0)
        results = repo.get_all()
        assert len(results) == 1
        assert results[0]["name"] == "Active One"

    def test_include_inactive(self, db, repo):
        _client(db, name="Active One", is_active=1)
        _client(db, name="Inactive One", is_active=0)
        results = repo.get_all(include_inactive=True)
        assert len(results) == 2

    def test_respects_limit(self, db, repo):
        for i in range(5):
            _client(db, name=f"Client {i}")
        results = repo.get_all(limit=3)
        assert len(results) == 3


class TestUpdate:
    def test_updates_fields(self, db, repo):
        cid = _client(db, name="Old Name")
        repo.update(cid, {"name": "New Name", "phone": "+999"})
        row = repo.get_by_id(cid)
        assert row["name"] == "New Name"
        assert row["phone"] == "+999"
        assert row["updated_at"] != ""  # set by update()


class TestDeactivate:
    def test_sets_inactive(self, db, repo):
        cid = _client(db, is_active=1)
        repo.deactivate(cid)
        row = repo.get_by_id(cid)
        assert row["is_active"] == 0


# ── Query methods ────────────────────────────────────────────────────


class TestGetByName:
    def test_exact_match(self, db, repo):
        cid = _client(db, name="Exact Match Ltd")
        row = repo.get_by_name("Exact Match Ltd")
        assert row is not None
        assert row["id"] == cid

    def test_no_match(self, repo):
        assert repo.get_by_name("No Such Client") is None


class TestSearchByName:
    def test_exact_match_first(self, db, repo):
        _client(db, name="Alpha Corp")
        results = repo.search_by_name("Alpha Corp")
        assert len(results) >= 1
        assert results[0]["name"] == "Alpha Corp"

    def test_fuzzy_fallback(self, db, repo):
        _client(db, name="Enterprise Ltd")
        results = repo.search_by_name("enterprise", fuzzy=True)
        assert len(results) >= 1

    def test_no_fuzzy_when_disabled(self, db, repo):
        _client(db, name="Enterprise Ltd")
        results = repo.search_by_name("enterpir", fuzzy=False)
        assert len(results) == 0

    def test_empty_query(self, repo):
        assert repo.search_by_name("") == []


class TestSearch:
    def test_like_search(self, db, repo):
        _client(db, name="Smith Transport")
        _client(db, name="Jones Logistics")
        results = repo.search("trans")
        assert len(results) == 1

    def test_empty_results(self, repo):
        assert repo.search("NoMatch") == []


class TestSearchAdvanced:
    def test_searches_multiple_columns(self, db, repo):
        _client(db, name="ABC Corp", email="contact@abc.com")
        results = repo.search_advanced("abc")
        assert len(results) >= 1

    def test_search_by_phone(self, db, repo):
        _client(db, name="Phone Client", phone="+4077777777")
        results = repo.search_advanced("7777")
        assert len(results) >= 1

    def test_include_inactive(self, db, repo):
        _client(db, name="Hidden", is_active=0)
        assert repo.search_advanced("Hidden") == []
        results = repo.search_advanced("Hidden", include_inactive=True)
        assert len(results) == 1

    def test_excludes_soft_deleted(self, db, repo):
        """R2: search_advanced must exclude soft-deleted clients."""
        _client(db, name="Deleted Client")
        cid = _client(db, name="Deleted Client 2")
        repo.soft_delete(cid)
        results = repo.search_advanced("Deleted Client")
        assert all(r["id"] != cid for r in results)


class TestGetInvoices:
    def test_excludes_soft_deleted_invoice(self, db, repo):
        """R2: get_invoices must exclude soft-deleted invoices."""
        cid = _client(db, name="Invoice Client")
        tid1 = _trip(db, client_id=cid, client_name="Invoice Client")
        tid2 = _trip(db, client_id=cid, client_name="Invoice Client")
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status) VALUES (?, ?, '2026-06-15', '2026-07-15', 1000.00, 'Unpaid')",
            (tid1, "INV-2026-0001"),
        )
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status) VALUES (?, ?, '2026-06-15', '2026-07-15', 2000.00, 'Unpaid')",
            (tid2, "INV-2026-0002"),
        )
        db.conn.commit()
        gone_id = db.conn.execute(
            "SELECT id FROM invoices WHERE invoice_number = 'INV-2026-0002'"
        ).fetchone()["id"]
        db.conn.execute(
            "UPDATE invoices SET deleted_at = '2026-08-01T00:00:00Z' WHERE id = ?",
            (gone_id,),
        )
        db.conn.commit()
        rows = repo.get_invoices(cid)
        ids = {r["id"] for r in rows}
        assert gone_id not in ids
        assert len(rows) == 1


class TestGetTripCount:
    def test_counts_trips(self, db, repo):
        cid = _client(db)
        _client(db, id=999, name="Other Client")  # ensure FK target exists
        _trip(db, client_id=cid)
        _trip(db, client_id=cid)
        _trip(db, client_id=999)
        assert repo.get_trip_count(cid) == 2

    def test_zero_for_no_trips(self, db, repo):
        cid = _client(db)
        assert repo.get_trip_count(cid) == 0


class TestGetTrips:
    def test_returns_client_trips(self, db, repo):
        cid = _client(db)
        _trip(db, client_id=cid)
        _trip(db, client_id=cid)
        trips = repo.get_trips(cid)
        assert len(trips) == 2

    def test_pagination(self, db, repo):
        cid = _client(db)
        for _ in range(5):
            _trip(db, client_id=cid)
        page = repo.get_trips(cid, limit=2, offset=0)
        assert len(page) == 2


class TestGetTripsStatusCounts:
    def test_counts_by_status(self, db, repo):
        cid = _client(db)
        _trip(db, client_id=cid, status="completed")
        _trip(db, client_id=cid, status="completed")
        _trip(db, client_id=cid, status="planned")
        counts = repo.get_trips_status_counts(cid)
        assert counts.get("completed") == 2
        assert counts.get("planned") == 1


class TestGetRevenueSummary:
    def test_returns_aggregates(self, db, repo):
        cid = _client(db)
        _trip(db, client_id=cid, total_price_eur=2000, net_profit=500, distance_km=400)
        _trip(db, client_id=cid, total_price_eur=3000, net_profit=800, distance_km=600)
        summary = repo.get_revenue_summary(cid)
        assert summary["total_trips"] == 2
        assert summary["total_revenue"] == 5000.0
        assert summary["total_profit"] == 1300.0
        assert summary["total_km"] == 1000.0

    def test_no_trips(self, db, repo):
        cid = _client(db)
        summary = repo.get_revenue_summary(cid)
        assert summary["total_trips"] == 0


class TestGetRevenueHistory:
    def test_monthly_breakdown(self, db, repo):
        cid = _client(db)
        _trip(db, client_id=cid, start_date="2026-01-15", total_price_eur=1000, net_profit=200, distance_km=300)
        _trip(db, client_id=cid, start_date="2026-02-10", total_price_eur=2000, net_profit=400, distance_km=500)
        history = repo.get_revenue_history(cid, months=12)
        # Verify total revenue across all months
        total_revenue = sum(h["revenue"] for h in history)
        assert total_revenue == 3000

    def test_empty_history(self, db, repo):
        cid = _client(db)
        assert repo.get_revenue_history(cid) == []


class TestGetTopByRevenue:
    def test_returns_top_clients(self, db, repo):
        c1 = _client(db, name="Top Client")
        c2 = _client(db, name="Small Client")
        _trip(db, client_id=c1, total_price_eur=10000, status="completed")
        _trip(db, client_id=c1, total_price_eur=5000, status="completed")
        _trip(db, client_id=c2, total_price_eur=2000, status="completed")
        top = repo.get_top_by_revenue(limit=2)
        assert len(top) == 2
        assert top[0]["name"] == "Top Client"
        assert top[0]["total_revenue"] == 15000.0

    def test_excludes_cancelled(self, db, repo):
        cid = _client(db, name="Cancelled Co")
        _trip(db, client_id=cid, total_price_eur=9999, status="Cancelled")
        top = repo.get_top_by_revenue()
        assert cid not in {r["id"] for r in top}


class TestGetClientEmailByName:
    def test_returns_email(self, db, repo):
        _client(db, name="Email Co", email="info@emailco.com")
        email = repo.get_client_email_by_name("Email Co")
        assert email == "info@emailco.com"

    def test_none_when_missing(self, repo):
        assert repo.get_client_email_by_name("NoSuch") is None
