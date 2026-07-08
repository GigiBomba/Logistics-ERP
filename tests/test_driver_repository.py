"""Tests for repositories.driver_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from repositories.driver_repository import DriverRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> DriverRepository:
    return DriverRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _driver(db: InMemoryDB, **kw) -> int:
    now = datetime.now().isoformat()
    d: Dict[str, Any] = dict(
        name="John Doe",
        phone="+123456",
        email="john@example.com",
        license_number="LIC-123",
        license_category="B",
        license_expiry="2027-01-01",
        medical_expiry="2027-06-01",
        hire_date="2025-01-01",
        monthly_salary=3000.0,
        notes="",
        is_active=1,
        created_at=now,
        updated_at=now,
        passport_number="",
        passport_expiry="",
        adr_certificate="",
        adr_certificate_expiry="",
        driver_card_number="",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO drivers ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── CRUD ─────────────────────────────────────────────────────────────


class TestCreate:
    def test_creates_and_returns_id(self, db, repo):
        did = repo.create({
            "name": "Alice Smith",
            "phone": "+111",
            "email": "alice@test.com",
            "license_number": "LIC-001",
        })
        assert did > 0
        row = db.conn.execute("SELECT * FROM drivers WHERE id = ?", (did,)).fetchone()
        assert row is not None
        assert row["name"] == "Alice Smith"

    def test_sets_created_and_updated(self, repo):
        did = repo.create({"name": "Timestamps Test"})
        row = repo.get_by_id(did)
        assert row["created_at"] != ""
        assert row["updated_at"] != ""

    def test_strips_id_from_data(self, repo):
        did = repo.create({"id": 999, "name": "NoIdOverride"})
        assert did != 999  # autoincrement
        assert repo.get_by_id(did) is not None


class TestGetById:
    def test_returns_driver(self, db, repo):
        did = _driver(db, name="Findable")
        row = repo.get_by_id(did)
        assert row is not None
        assert row["name"] == "Findable"

    def test_none_for_missing(self, repo):
        assert repo.get_by_id(99999) is None


class TestGetByIdWithAdr:
    def test_returns_adr_fields(self, db, repo):
        did = _driver(db, name="ADR Driver", adr_certificate_expiry="2027-12-31")
        row = repo.get_by_id_with_adr(did)
        assert row is not None
        assert row["name"] == "ADR Driver"
        assert row["adr_certificate_expiry"] == "2027-12-31"

    def test_none_for_missing(self, repo):
        assert repo.get_by_id_with_adr(99999) is None


class TestGetAll:
    def test_empty_db(self, repo):
        assert repo.get_all() == []

    def test_returns_sorted_by_name(self, db, repo):
        _driver(db, name="Zoe")
        _driver(db, name="Alice")
        _driver(db, name="Bob")
        results = repo.get_all()
        names = [r["name"] for r in results]
        assert names == ["Alice", "Bob", "Zoe"]

    def test_pagination(self, db, repo):
        for i in range(10):
            _driver(db, name=f"Driver {i}")
        page1 = repo.get_all(limit=3, offset=0)
        assert len(page1) == 3
        page2 = repo.get_all(limit=3, offset=3)
        assert len(page2) == 3
        ids1 = {r["id"] for r in page1}
        ids2 = {r["id"] for r in page2}
        assert ids1.isdisjoint(ids2)


class TestUpdate:
    def test_updates_fields(self, db, repo):
        did = _driver(db, name="Old Name", phone="+000")
        repo.update(did, {"name": "New Name", "phone": "+999"})
        row = repo.get_by_id(did)
        assert row["name"] == "New Name"
        assert row["phone"] == "+999"

    def test_sets_updated_at(self, db, repo):
        did = _driver(db)
        old_updated = repo.get_by_id(did)["updated_at"]
        repo.update(did, {"name": "Updated"})
        new_updated = repo.get_by_id(did)["updated_at"]
        assert new_updated != old_updated

    def test_rejects_invalid_column(self, repo):
        with pytest.raises(ValueError, match="Invalid column"):
            repo.update(1, {"nonexistent": "x"})


class TestDelete:
    def test_removes_driver(self, db, repo):
        did = _driver(db)
        repo.delete(did)
        assert repo.get_by_id(did) is None

    def test_delete_nonexistent_does_not_raise(self, repo):
        repo.delete(99999)


# ── Domain queries ───────────────────────────────────────────────────


class TestGetActiveDrivers:
    def test_returns_only_active(self, db, repo):
        _driver(db, name="Active One", is_active=1)
        _driver(db, name="Inactive One", is_active=0)
        _driver(db, name="Active Two", is_active=1)
        active = repo.get_active_drivers()
        assert len(active) == 2
        assert all(d["is_active"] == 1 for d in active)

    def test_empty_when_all_inactive(self, db, repo):
        _driver(db, name="Inactive", is_active=0)
        assert repo.get_active_drivers() == []


class TestSearchByName:
    def test_fuzzy_match(self, db, repo):
        _driver(db, name="Jonathan Smith")
        results = repo.search_by_name("Jon")
        assert len(results) == 1
        assert results[0]["name"] == "Jonathan Smith"

    def test_no_match(self, repo):
        assert repo.search_by_name("NoSuchDriver") == []


class TestGetByCardNumber:
    def test_finds_by_card(self, db, repo):
        _driver(db, name="Card Holder", driver_card_number="CARD-001")
        row = repo.get_by_card_number("CARD-001")
        assert row is not None
        assert row["name"] == "Card Holder"

    def test_none_for_missing_card(self, repo):
        assert repo.get_by_card_number("NONEXISTENT") is None


class TestGetByNameFuzzy:
    def test_like_match(self, db, repo):
        _driver(db, name="Christopher Lee")
        row = repo.get_by_name_fuzzy("Chris")
        assert row is not None
        assert row["name"] == "Christopher Lee"

    def test_none_when_no_match(self, repo):
        assert repo.get_by_name_fuzzy("NoMatch") is None


class TestCountActive:
    def test_counts_active(self, db, repo):
        _driver(db, is_active=1)
        _driver(db, is_active=1)
        _driver(db, is_active=0)
        assert repo.count_active() == 2

    def test_zero_when_none(self, repo):
        assert repo.count_active() == 0


# ── Expiry queries ───────────────────────────────────────────────────


class TestGetExpiringLicenses:
    def test_returns_drivers_within_window(self, db, repo):
        future = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        far_future = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        _driver(db, name="Expiring Soon", license_expiry=future, is_active=1)
        _driver(db, name="Not Expiring", license_expiry=far_future, is_active=1)
        _driver(db, name="Inactive Expiring", license_expiry=future, is_active=0)
        results = repo.get_expiring_licenses(30)
        names = {r["name"] for r in results}
        assert "Expiring Soon" in names
        assert "Not Expiring" not in names
        assert "Inactive Expiring" not in names

    def test_empty_when_none_expiring(self, repo):
        assert repo.get_expiring_licenses(30) == []


class TestGetExpiredLicenses:
    def test_returns_expired(self, db, repo):
        past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        _driver(db, name="Expired", license_expiry=past, is_active=1)
        results = repo.get_expired_licenses()
        assert len(results) == 1

    def test_excludes_future(self, db, repo):
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        _driver(db, name="Future", license_expiry=future, is_active=1)
        assert repo.get_expired_licenses() == []


class TestGetExpiringMedical:
    def test_returns_within_window(self, db, repo):
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        _driver(db, name="Medical Soon", medical_expiry=future, is_active=1)
        results = repo.get_expiring_medical(30)
        assert len(results) == 1


class TestGetExpiredMedical:
    def test_returns_expired(self, db, repo):
        past = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        _driver(db, name="Expired Medical", medical_expiry=past, is_active=1)
        results = repo.get_expired_medical()
        assert len(results) == 1


class TestUpdateLicenseExpiry:
    def test_updates_expiry(self, db, repo):
        did = _driver(db, license_expiry="2026-01-01")
        repo.update_license_expiry(did, "2028-01-01")
        row = repo.get_by_id(did)
        assert row["license_expiry"] == "2028-01-01"
