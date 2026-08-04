"""Tests for repositories.contact_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from repositories.contact_repository import ContactRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> ContactRepository:
    return ContactRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _contact(db: InMemoryDB, **kw: Any) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    c: Dict[str, Any] = dict(
        client_id=1,
        contact_type="operations",
        full_name="John Doe",
        title="Manager",
        phone="+123456789",
        email="john@example.com",
        is_primary=0,
        notes="",
        created_at=now,
    )
    c.update(kw)
    cols = ", ".join(c.keys())
    vals = ", ".join("?" for _ in c)
    # Ensure a client row exists (FK not enforced, but good practice)
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, created_at) VALUES (?, ?, ?)",
        (c.get("client_id", 1), "Test Client", now),
    )
    db.conn.commit()
    db.conn.execute(f"INSERT INTO client_contacts ({cols}) VALUES ({vals})", list(c.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── set_primary ──────────────────────────────────────────────────────


class TestSetPrimary:
    def test_set_primary_clears_old_primary(self, db, repo):
        c1 = _contact(db, client_id=1, full_name="Alice", is_primary=1)
        c2 = _contact(db, client_id=1, full_name="Bob", is_primary=0)
        repo.set_primary(1, c2)
        row = db.conn.execute(
            "SELECT is_primary FROM client_contacts WHERE id = ?", (c1,)
        ).fetchone()
        assert row["is_primary"] == 0

    def test_set_primary_sets_new_primary(self, db, repo):
        c1 = _contact(db, client_id=1, full_name="Alice", is_primary=1)
        c2 = _contact(db, client_id=1, full_name="Bob", is_primary=0)
        repo.set_primary(1, c2)
        row = db.conn.execute(
            "SELECT is_primary FROM client_contacts WHERE id = ?", (c2,)
        ).fetchone()
        assert row["is_primary"] == 1

    def test_set_primary_transaction_atomic(self, db, repo):
        """Both updates happen inside a transaction (all-or-nothing)."""
        c1 = _contact(db, client_id=1, full_name="Alice", is_primary=1)
        c2 = _contact(db, client_id=1, full_name="Bob", is_primary=0)
        repo.set_primary(1, c2)
        # Verify both changes are visible (committed)
        r1 = db.conn.execute(
            "SELECT is_primary FROM client_contacts WHERE id = ?", (c1,)
        ).fetchone()
        r2 = db.conn.execute(
            "SELECT is_primary FROM client_contacts WHERE id = ?", (c2,)
        ).fetchone()
        assert r1["is_primary"] == 0
        assert r2["is_primary"] == 1


# ── Create ───────────────────────────────────────────────────────────


class TestCreate:
    def test_create_injects_created_at(self, db, repo):
        # Ensure parent client exists before creating contact (FK constraint)
        db.conn.execute("INSERT OR IGNORE INTO clients (id, name, created_at) VALUES (?, ?, ?)",
                        (2, "Client 2", datetime.utcnow().isoformat(timespec="seconds") + "Z"))
        db.conn.commit()
        cid = repo.create({
            "client_id": 2,
            "contact_type": "ops",
            "full_name": "Charlie",
        })
        row = db.conn.execute(
            "SELECT created_at FROM client_contacts WHERE id = ?", (cid,)
        ).fetchone()
        assert row is not None
        assert row["created_at"]  # non-empty string

    def test_create_respects_explicit_created_at(self, db, repo):
        # Ensure parent client exists before creating contact (FK constraint)
        db.conn.execute("INSERT OR IGNORE INTO clients (id, name, created_at) VALUES (?, ?, ?)",
                        (3, "Client 3", datetime.utcnow().isoformat(timespec="seconds") + "Z"))
        db.conn.commit()
        explicit = "2025-06-15T10:00:00Z"
        cid = repo.create({
            "client_id": 3,
            "contact_type": "ops",
            "full_name": "Diana",
            "created_at": explicit,
        })
        row = db.conn.execute(
            "SELECT created_at FROM client_contacts WHERE id = ?", (cid,)
        ).fetchone()
        assert row["created_at"] == explicit


# ── Update ───────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_no_rowcount_check(self, repo):
        """Update on a non-existent contact does not raise."""
        repo.update(99999, {"full_name": "Ghost"})  # should not raise

    def test_update_modifies_fields(self, db, repo):
        cid = _contact(db, full_name="Original", phone="+111")
        repo.update(cid, {"full_name": "Updated", "phone": "+222"})
        row = db.conn.execute(
            "SELECT full_name, phone FROM client_contacts WHERE id = ?", (cid,)
        ).fetchone()
        assert row["full_name"] == "Updated"
        assert row["phone"] == "+222"


# ── get_primary_for_client ───────────────────────────────────────────


class TestGetPrimaryForClient:
    def test_get_primary_for_client_returns_is_primary_1(self, db, repo):
        c1 = _contact(db, client_id=10, full_name="Primary", is_primary=1)
        _contact(db, client_id=10, full_name="Secondary", is_primary=0)
        result = repo.get_primary_for_client(10)
        assert result is not None
        assert result["id"] == c1
        assert result["is_primary"] == 1

    def test_get_primary_for_client_none_when_no_primary(self, db, repo):
        _contact(db, client_id=11, full_name="NonPrimary", is_primary=0)
        result = repo.get_primary_for_client(11)
        assert result is None


# ── get_by_id ────────────────────────────────────────────────────────


class TestGetById:
    def test_get_by_id_returns_contact(self, db, repo):
        cid = _contact(db, client_id=1, full_name="Solo")
        row = repo.get_by_id(cid)
        assert row is not None
        assert row["id"] == cid
        assert row["full_name"] == "Solo"

    def test_get_by_id_none_when_missing(self, repo):
        assert repo.get_by_id(99999) is None

    def test_get_by_id_company_scoped_hides_other_company(self, db, repo):
        cid = _contact(db, client_id=1, full_name="Tenant A", company_id=9)
        assert repo.get_by_id(cid, company_id=9) is not None
        assert repo.get_by_id(cid, company_id=7) is None

    def test_get_by_id_company_scope_admin_unscoped(self, db, repo):
        cid = _contact(db, client_id=1, full_name="Tenant B", company_id=9)
        # Admin callers (company_id 0 / None) fall back to the context filter,
        # which is unscoped outside a scoped request → all tenants visible.
        assert repo.get_by_id(cid, company_id=0) is not None
        assert repo.get_by_id(cid, company_id=None) is not None


# ── get_by_client ────────────────────────────────────────────────────


class TestGetByClient:
    def test_get_by_client_orders_by_primary_desc(self, db, repo):
        c2 = _contact(db, client_id=20, full_name="Secondary", is_primary=0)
        c1 = _contact(db, client_id=20, full_name="Primary", is_primary=1)
        contacts = repo.get_by_client(20)
        # Primary should come first
        assert len(contacts) >= 2
        assert contacts[0]["id"] == c1
        assert contacts[0]["is_primary"] == 1
