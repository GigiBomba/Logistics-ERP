"""Tests for repositories.payment_profile_repository — CRUD + query methods."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from repositories.payment_profile_repository import PaymentProfileRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    imdb = InMemoryDB()
    _ensure_payment_profiles_table(imdb)
    return imdb


@pytest.fixture
def repo(db) -> PaymentProfileRepository:
    return PaymentProfileRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _ensure_payment_profiles_table(db: InMemoryDB):
    """Create payment_profiles table if it doesn't exist in the schema."""
    db.conn.execute("""
        CREATE TABLE IF NOT EXISTS payment_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_name TEXT NOT NULL,
            recipient_type TEXT NOT NULL DEFAULT 'custom'
                CHECK (recipient_type IN ('custom', 'government', 'supplier', 'contractor', 'other')),
            bank_name TEXT DEFAULT '',
            bank_account TEXT DEFAULT '',
            bank_code TEXT DEFAULT '',
            bank_bic TEXT DEFAULT '',
            iban TEXT DEFAULT '',
            payment_reference TEXT DEFAULT '',
            contact_name TEXT DEFAULT '',
            contact_email TEXT DEFAULT '',
            contact_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            company_id INTEGER
        )
    """)
    db.conn.commit()


def _profile(db: InMemoryDB, **kw) -> int:
    now = datetime.utcnow().isoformat()
    d: Dict[str, Any] = dict(
        profile_name="Test Supplier Ltd",
        recipient_type="supplier",
        bank_name="Test Bank",
        bank_account="1234567890",
        bank_code="BARC12345",
        bank_bic="BARCGB22",
        iban="GB29NWBK60161331926819",
        payment_reference="INV-001",
        contact_name="John Contact",
        contact_email="john@supplier.com",
        contact_phone="+44012345678",
        notes="Test notes",
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO payment_profiles ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── CRUD ─────────────────────────────────────────────────────────────


class TestCreate:
    def test_create_returns_id(self, repo):
        now = datetime.utcnow().isoformat()
        profile_id = repo.create({
            "profile_name": "New Corp",
            "recipient_type": "custom",
            "bank_account": "0987654321",
            "created_at": now,
            "updated_at": now,
        })
        assert profile_id > 0

    def test_create_persists(self, repo, db):
        now = datetime.utcnow().isoformat()
        pid = repo.create({
            "profile_name": "Persist Corp",
            "bank_account": "1111111",
            "recipient_type": "custom",
            "created_at": now,
            "updated_at": now,
        })
        profile = repo.get_by_id(pid)
        assert profile is not None
        assert profile["profile_name"] == "Persist Corp"

    def test_create_invalid_column_raises(self, repo):
        with pytest.raises(ValueError, match="Invalid column"):
            repo.create({"invalid_col": "test"})


class TestGetById:
    def test_get_existing(self, repo, db):
        pid = _profile(db)
        profile = repo.get_by_id(pid)
        assert profile is not None
        assert profile["profile_name"] == "Test Supplier Ltd"
        assert profile["recipient_type"] == "supplier"

    def test_get_non_existent(self, repo):
        assert repo.get_by_id(99999) is None

    def test_get_zero(self, repo):
        assert repo.get_by_id(0) is None


class TestGetAll:
    def test_returns_list(self, repo, db):
        _profile(db)
        items = repo.get_all()
        assert isinstance(items, list)
        assert len(items) >= 1

    def test_excludes_inactive(self, repo, db):
        _profile(db, profile_name="Active", is_active=1)
        _profile(db, profile_name="Inactive", is_active=0)
        items = repo.get_all(include_inactive=False)
        names = [i["profile_name"] for i in items]
        assert "Active" in names
        assert "Inactive" not in names

    def test_includes_inactive_when_requested(self, repo, db):
        _profile(db, profile_name="Active", is_active=1)
        _profile(db, profile_name="Inactive", is_active=0)
        items = repo.get_all(include_inactive=True)
        names = [i["profile_name"] for i in items]
        assert "Active" in names
        assert "Inactive" in names


class TestSearch:
    def test_search_by_name(self, repo, db):
        _profile(db, profile_name="UniqueSupplier XYZ")
        items = repo.search("UniqueSupplier")
        assert len(items) >= 1
        assert items[0]["profile_name"] == "UniqueSupplier XYZ"

    def test_search_no_match(self, repo, db):
        _profile(db)
        items = repo.search("NonExistentName")
        assert len(items) == 0


class TestGetActiveByType:
    def test_filters_by_type(self, repo, db):
        _profile(db, profile_name="Gov One", recipient_type="government")
        _profile(db, profile_name="Sup One", recipient_type="supplier")
        items = repo.get_active_by_type("government")
        assert all(i["recipient_type"] == "government" for i in items)

    def test_excludes_inactive(self, repo, db):
        _profile(db, profile_name="Active Gov", recipient_type="government", is_active=1)
        _profile(db, profile_name="Inactive Gov", recipient_type="government", is_active=0)
        items = repo.get_active_by_type("government")
        names = [i["profile_name"] for i in items]
        assert "Active Gov" in names
        assert "Inactive Gov" not in names


class TestUpdate:
    def test_update_name(self, repo, db):
        pid = _profile(db, profile_name="Original")
        repo.update(pid, {"profile_name": "Updated", "updated_at": datetime.utcnow().isoformat()})
        profile = repo.get_by_id(pid)
        assert profile["profile_name"] == "Updated"

    def test_update_invalid_column_raises(self, repo):
        with pytest.raises(ValueError, match="Invalid column"):
            repo.update(1, {"bad_column": "val"})


class TestDelete:
    def test_delete_removes_record(self, repo, db):
        pid = _profile(db)
        repo.delete(pid)
        assert repo.get_by_id(pid) is None

    def test_delete_non_existent_does_not_raise(self, repo):
        # should not raise
        repo.delete(99999)
