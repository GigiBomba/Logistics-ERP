"""Tests for repositories.proforma_repository — CRUD + number generation.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime

from repositories.proforma_repository import ProformaRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> ProformaRepository:
    return ProformaRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _proforma(db: InMemoryDB, **kw) -> int:
    now = datetime.now().isoformat()
    d = dict(
        proforma_number="PROF-2026-0001",
        issue_date="2026-06-01",
        valid_until="2026-07-01",
        client_name="Test Client",
        client_address="123 Street",
        client_vat="RO123",
        client_phone="+40123456789",
        client_email="client@test.com",
        description="Test proforma",
        notes="",
        line_items_json="[]",
        subtotal=1000.0,
        discount_type="",
        discount_value=0.0,
        discount_amount=0.0,
        tax_rate=19.0,
        tax_amount=190.0,
        grand_total=1190.0,
        currency="EUR",
        mode="client",
        status="Draft",
        logo_path="",
        signature_path="",
        stamp_path="",
        company_color="#6366f1",
        created_at=now,
        updated_at=now,
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO proforma_invoices ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Get next number ─────────────────────────────────────────────────


class TestGetNextNumber:
    def test_get_next_number_returns_default_format(self, repo):
        """Default format is PROF-{year}-{seq:04d}."""
        result = repo.get_next_number()
        year = datetime.now().year
        assert result == f"PROF-{year}-0001"

    def test_get_next_number_increments_with_rows(self, db, repo):
        _proforma(db, proforma_number="PROF-2026-0001")
        # Seed the sequence table to simulate existing proforma
        db.conn.execute(
            "INSERT OR REPLACE INTO invoice_number_sequences (series, year, last_number) VALUES (?, ?, ?)",
            ("prof_year_seq", 2026, 1),
        )
        db.conn.commit()
        result = repo.get_next_number()
        year = datetime.now().year
        assert result == f"PROF-{year}-0002"

    def test_get_next_number_custom_format(self, repo):
        """prof_seq format: PROF-{seq:06d}."""
        result = repo.get_next_number(format_key="prof_seq")
        assert result == "PROF-000001"


# ── Create ───────────────────────────────────────────────────────────


class TestCreate:
    def test_create_returns_id(self, repo):
        pid = repo.create(proforma_number="PROF-2026-0010")
        assert pid is not None and pid > 0

    def test_create_duplicate_proforma_number_returns_none(self, repo):
        repo.create(proforma_number="PROF-2026-DUP")
        # Duplicate UNIQUE constraint -> returns None
        result = repo.create(proforma_number="PROF-2026-DUP")
        assert result is None

    def test_create_invalid_column_raises_valueerror(self, repo):
        # create() has explicit kwargs, not **kwargs; test via _validate_columns directly
        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"proforma_number": "X", "nonexistent": "boom"})


# ── Get by ID ────────────────────────────────────────────────────────


class TestGetById:
    def test_get_by_id_deserializes_line_items(self, db, repo):
        line_items = [{"description": "Item A", "quantity": 2, "unit_price": 50.0}]
        pid = repo.create(
            proforma_number="PROF-2026-LI",
            line_items=line_items,
        )
        row = repo.get_by_id(pid)
        assert row is not None
        assert "line_items" in row
        assert row["line_items"] == line_items


# ── Update ───────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_changes_fields_and_updated_at(self, db, repo):
        pid = _proforma(db, proforma_number="PROF-2026-UPD1", notes="Old notes")
        success = repo.update(pid, notes="Updated notes", client_name="New Client")
        assert success is True
        row = repo.get_by_id(pid)
        assert row["notes"] == "Updated notes"
        assert row["client_name"] == "New Client"
        assert "updated_at" in row and row["updated_at"] is not None

    def test_update_unknown_kwargs_ignored(self, db, repo):
        pid = _proforma(db, proforma_number="PROF-2026-IGN")
        # Unknown kwargs are rejected by _validate_columns with ValueError
        with pytest.raises(ValueError, match="Invalid column"):
            repo.update(pid, nonexistent="ignored")


# ── Update status ────────────────────────────────────────────────────


class TestUpdateStatus:
    def test_update_status_delegates_to_update(self, db, repo):
        pid = _proforma(db, proforma_number="PROF-2026-STAT", status="Draft")
        result = repo.update_status(pid, "Sent")
        assert result is True
        row = repo.get_by_id(pid)
        assert row["status"] == "Sent"
