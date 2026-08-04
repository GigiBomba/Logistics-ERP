"""Tests for repositories.invoice_repository — query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.invoice_repository import InvoiceRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> InvoiceRepository:
    return InvoiceRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _client(db: InMemoryDB, **kw) -> int:
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
        created_at="2026-01-01T00:00:00Z",
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


def _invoice(db: InMemoryDB, **kw) -> int:
    d = dict(
        trip_id=1,
        invoice_number="INV-2026-0001",
        issue_date="2026-06-15",
        due_date="2026-07-15",
        total_amount=5000.00,
        status="Unpaid",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO invoices ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Get by ID ────────────────────────────────────────────────────────


class TestGetById:
    def test_returns_invoice(self, db, repo):
        tid = _trip(db)
        inv_id = _invoice(db, trip_id=tid)
        row = repo.get_by_id(inv_id)
        assert row is not None
        assert row["id"] == inv_id
        assert row["trip_id"] == tid

    def test_returns_none_for_missing(self, repo):
        assert repo.get_by_id(99999) is None

    def test_returns_correct_amount(self, db, repo):
        tid = _trip(db)
        _invoice(db, trip_id=tid, total_amount=1234.56)
        row = repo.get_by_id(1)
        assert row is not None
        assert row["total_amount"] == 1234.56


# ── Get by Trip ID ───────────────────────────────────────────────────


class TestGetByTripId:
    def test_returns_invoice_for_trip(self, db, repo):
        tid = _trip(db)
        _invoice(db, trip_id=tid)
        row = repo.get_by_trip_id(tid)
        assert row is not None
        assert row["trip_id"] == tid

    def test_returns_none_when_no_invoice(self, repo):
        assert repo.get_by_trip_id(99999) is None


# ── Get by Number ────────────────────────────────────────────────────


class TestGetByNumber:
    def test_exact_match(self, db, repo):
        tid = _trip(db)
        _invoice(db, trip_id=tid, invoice_number="INV-2026-0001")
        row = repo.get_by_number("INV-2026-0001")
        assert row is not None
        assert row["invoice_number"] == "INV-2026-0001"

    def test_none_for_unknown_number(self, repo):
        assert repo.get_by_number("NONEXISTENT") is None


# ── Get by Client ID ─────────────────────────────────────────────────


class TestGetByClientId:
    def test_returns_client_invoices(self, db, repo):
        cid = _client(db, name="Client A")
        tid = _trip(db, client_id=cid, client_name="Client A")
        _invoice(db, trip_id=tid)
        results = repo.get_by_client_id(cid)
        assert len(results) >= 1
        assert results[0]["trip_id"] == tid

    def test_empty_for_client_without_invoices(self, db, repo):
        cid = _client(db, name="Empty Client")
        _trip(db, client_id=cid, client_name="Empty Client")
        results = repo.get_by_client_id(cid)
        assert results == []


# ── Outstanding balance ──────────────────────────────────────────────


class TestGetOutstandingBalance:
    def test_calculates_balance(self, db, repo):
        cid = _client(db)
        tid1 = _trip(db, client_id=cid)
        tid2 = _trip(db, client_id=cid)
        _invoice(db, trip_id=tid1, invoice_number="INV-2026-0001", total_amount=1000.00, status="Unpaid")
        _invoice(db, trip_id=tid2, invoice_number="INV-2026-0002", total_amount=2500.00, status="Unpaid")
        balance = repo.get_outstanding_balance(cid)
        assert balance == 3500.0

    def test_zero_when_all_paid(self, db, repo):
        cid = _client(db)
        tid = _trip(db, client_id=cid)
        _invoice(db, trip_id=tid, total_amount=1000.00, status="Paid")
        balance = repo.get_outstanding_balance(cid)
        assert balance == 0.0


# ── Get by Status ────────────────────────────────────────────────────


class TestGetByStatus:
    def test_filters_by_status(self, db, repo):
        tid1 = _trip(db)
        tid2 = _trip(db)
        _invoice(db, trip_id=tid1, invoice_number="INV-2026-0001", status="Unpaid")
        _invoice(db, trip_id=tid2, invoice_number="INV-2026-0002", status="Paid")
        unpaid = repo.get_by_status("Unpaid")
        assert len(unpaid) == 1
        assert unpaid[0]["status"] == "Unpaid"


# ── Get all ──────────────────────────────────────────────────────────


class TestGetAll:
    def test_returns_all_with_limit(self, db, repo):
        for i in range(5):
            tid = _trip(db, truck_number=f"TRK-{i}")
            _invoice(db, trip_id=tid, invoice_number=f"INV-2026-{i+1:04d}")
        results = repo.get_all(limit=3)
        assert len(results) == 3


# ── Invoice count ────────────────────────────────────────────────────


class TestGetInvoiceCount:
    def test_counts_correctly(self, db, repo):
        cid = _client(db)
        tid1 = _trip(db, client_id=cid)
        tid2 = _trip(db, client_id=cid)
        _invoice(db, trip_id=tid1, invoice_number="INV-2026-0001")
        _invoice(db, trip_id=tid2, invoice_number="INV-2026-0002")
        assert repo.get_invoice_count(cid) == 2

    def test_zero_for_no_invoices(self, db, repo):
        cid = _client(db)
        _trip(db, client_id=cid)
        assert repo.get_invoice_count(cid) == 0


# ── Next number ──────────────────────────────────────────────────────


class TestGetNextNumber:
    def test_formats_year_seq(self, db, repo):
        tid = _trip(db)
        nxt1 = repo.get_next_number()
        assert nxt1.startswith("INV-2026-")
        _invoice(db, trip_id=tid, invoice_number=nxt1)
        nxt2 = repo.get_next_number()
        assert nxt2.startswith("INV-2026-")
        # Second call should give a different (incremented) number
        seq1 = int(nxt1.split("-")[-1])
        seq2 = int(nxt2.split("-")[-1])
        assert seq2 == seq1 + 1
