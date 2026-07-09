"""Tests for repositories.receipt_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.receipt_repository import ReceiptRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> ReceiptRepository:
    return ReceiptRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _receipt(db: InMemoryDB, **kw) -> int:
    from datetime import datetime
    now = datetime.now().isoformat()
    d = dict(
        receipt_number="RCT-2026-000001",
        receipt_type="customer_payment",
        issue_date="2026-06-01",
        payment_date="2026-06-15",
        currency="EUR",
        company_name="Test Corp",
        company_address="123 Main St",
        company_vat="VAT123",
        company_reg="REG123",
        company_phone="+123456789",
        company_email="corp@test.com",
        received_from_name="John Doe",
        received_from_address="456 Oak Ave",
        received_from_vat="VAT456",
        received_from_reg="REG456",
        received_from_contact="+987654321",
        received_by_name="Jane Smith",
        received_by_address="789 Pine Rd",
        received_by_vat="VAT789",
        received_by_reg="REG789",
        received_by_contact="+555123456",
        payment_method="bank_transfer",
        reference_number="REF-001",
        transaction_id="TXN-001",
        bank_reference="BANK-REF-001",
        invoice_reference="INV-2026-0001",
        related_trip_id=None,
        driver_id=None,
        vehicle_id=None,
        trailer_id=None,
        purpose="Payment for trip",
        amount=1000.00,
        vat_rate=19.0,
        vat_amount=190.00,
        total=1190.00,
        amount_words="One thousand one hundred ninety",
        notes="Test receipt",
        status="Draft",
        logo_path="",
        signature_path="",
        stamp_path="",
        attachments_json="[]",
        employee_name="",
        department="",
        expense_category="",
        mileage=0.0,
        fuel=0.0,
        accommodation=0.0,
        meals=0.0,
        parking=0.0,
        tolls=0.0,
        other_expense=0.0,
        pickup_location="",
        delivery_location="",
        route="",
        dispatcher="",
        language="en",
        created_at=now,
        updated_at=now,
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO receipts ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Create ───────────────────────────────────────────────────────────


class TestCreate:
    def test_creates_and_returns_id(self, db, repo):
        rcp_id = repo.create(receipt_number="RCT-2026-000001")
        assert rcp_id is not None and rcp_id > 0
        row = db.conn.execute(
            "SELECT * FROM receipts WHERE id = ?", (rcp_id,)
        ).fetchone()
        assert row is not None

    def test_stores_all_fields(self, repo):
        rcp_id = repo.create(
            receipt_number="RCT-2026-000002",
            receipt_type="expense",
            amount=500.00,
            vat_rate=19.0,
            total=595.00,
            currency="USD",
            notes="Expense receipt",
        )
        assert rcp_id is not None
        row = repo.get_by_id(rcp_id)
        assert row["receipt_number"] == "RCT-2026-000002"
        assert row["receipt_type"] == "expense"
        assert row["amount"] == 500.00
        assert row["currency"] == "USD"

    def test_defaults_status_to_draft(self, repo):
        rcp_id = repo.create(receipt_number="RCT-2026-000003")
        assert rcp_id is not None
        row = repo.get_by_id(rcp_id)
        assert row["status"] == "Draft"


# ── Get by ID ────────────────────────────────────────────────────────


class TestGetById:
    def test_returns_receipt(self, db, repo):
        rcp_id = _receipt(db, receipt_number="RCT-2026-000010")
        row = repo.get_by_id(rcp_id)
        assert row is not None
        assert row["id"] == rcp_id

    def test_none_for_missing(self, repo):
        assert repo.get_by_id(99999) is None


# ── Get by Number ────────────────────────────────────────────────────


class TestGetByNumber:
    def test_exact_match(self, db, repo):
        _receipt(db, receipt_number="RCT-2026-000020")
        row = repo.get_by_number("RCT-2026-000020")
        assert row is not None
        assert row["receipt_number"] == "RCT-2026-000020"

    def test_none_for_unknown(self, repo):
        assert repo.get_by_number("NONEXISTENT") is None


# ── Get all ──────────────────────────────────────────────────────────


class TestGetAll:
    def test_returns_all_paginated(self, db, repo):
        for i in range(5):
            _receipt(db, receipt_number=f"RCT-2026-{i+1:06d}")
        results = repo.get_all(limit=3, offset=0)
        assert len(results) == 3

    def test_empty_db(self, repo):
        assert repo.get_all() == []


# ── Get by Status ────────────────────────────────────────────────────


class TestGetByStatus:
    def test_filters_by_status(self, db, repo):
        _receipt(db, receipt_number="RCT-2026-000030", status="Draft")
        _receipt(db, receipt_number="RCT-2026-000031", status="Paid")
        _receipt(db, receipt_number="RCT-2026-000032", status="Draft")
        drafts = repo.get_by_status("Draft")
        assert len(drafts) == 2
        paid = repo.get_by_status("Paid")
        assert len(paid) == 1


# ── Update ───────────────────────────────────────────────────────────


class TestUpdate:
    def test_updates_fields(self, db, repo):
        rcp_id = _receipt(db, receipt_number="RCT-2026-000040", notes="Old note")
        success = repo.update(rcp_id, notes="Updated note", amount=999.00)
        assert success is True
        row = repo.get_by_id(rcp_id)
        assert row["notes"] == "Updated note"
        assert row["amount"] == 999.00

    def test_update_invalid_column_raises(self, repo):
        rcp_id = repo.create(receipt_number="RCT-2026-000050")
        with pytest.raises(ValueError, match="Invalid column"):
            repo.update(rcp_id, nonexistent_column="value")


# ── Delete ───────────────────────────────────────────────────────────


class TestDelete:
    def test_removes_receipt(self, db, repo):
        rcp_id = _receipt(db, receipt_number="RCT-2026-000060")
        assert repo.delete(rcp_id) is True
        assert repo.get_by_id(rcp_id) is None


# ── Search by Trip ───────────────────────────────────────────────────


class TestSearchByTrip:
    def test_finds_by_trip_id(self, db, repo):
        _receipt(db, receipt_number="RCT-2026-000070", related_trip_id=42)
        _receipt(db, receipt_number="RCT-2026-000071", related_trip_id=42)
        _receipt(db, receipt_number="RCT-2026-000072", related_trip_id=99)
        results = repo.search_by_trip(42)
        assert len(results) == 2
        assert all(r["related_trip_id"] == 42 for r in results)
