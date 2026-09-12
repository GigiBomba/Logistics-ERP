"""Tests for repositories.driver_truck_assignment_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from repositories.driver_truck_assignment_repository import (
    DriverTruckAssignmentRepository,
)
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> DriverTruckAssignmentRepository:
    return DriverTruckAssignmentRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _driver(db: InMemoryDB, **kw: Any) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    d: Dict[str, Any] = dict(
        name="Test Driver",
        phone="+111",
        email="driver@test.com",
        created_at=now,
        updated_at=now,
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO drivers ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _truck(db: InMemoryDB, **kw: Any) -> int:
    t: Dict[str, Any] = dict(
        plate_number="AB-123-CD",
        model="Volvo FH",
        manufacturer="Volvo",
    )
    t.update(kw)
    cols = ", ".join(t.keys())
    vals = ", ".join("?" for _ in t)
    db.conn.execute(f"INSERT INTO trucks ({cols}) VALUES ({vals})", list(t.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _assignment(db: InMemoryDB, driver_id: int, truck_id: int) -> None:
    db.conn.execute(
        "INSERT OR REPLACE INTO driver_truck_assignments "
        "(driver_id, truck_id, assigned_at) VALUES (?, ?, datetime('now'))",
        (driver_id, truck_id),
    )
    db.conn.commit()


# ── Assign ───────────────────────────────────────────────────────────


class TestAssign:
    def test_assign_inserts_new_assignment(self, db, repo):
        did = _driver(db)
        tid = _truck(db)
        repo.assign(did, tid)
        row = db.conn.execute(
            "SELECT * FROM driver_truck_assignments WHERE driver_id = ?", (did,)
        ).fetchone()
        assert row is not None
        assert row["truck_id"] == tid

    def test_assign_upserts_existing_driver(self, db, repo):
        did = _driver(db)
        t1 = _truck(db, plate_number="TRUCK-1")
        t2 = _truck(db, plate_number="TRUCK-2")
        repo.assign(did, t1)
        repo.assign(did, t2)
        rows = db.conn.execute(
            "SELECT * FROM driver_truck_assignments WHERE driver_id = ?", (did,)
        ).fetchall()
        assert len(rows) == 1  # upsert — no duplicate rows
        assert rows[0]["truck_id"] == t2


# ── Swap ─────────────────────────────────────────────────────────────


class TestSwap:
    def test_swap_exchanges_trucks(self, db, repo):
        d1 = _driver(db, name="Driver A")
        d2 = _driver(db, name="Driver B")
        t1 = _truck(db, plate_number="TRUCK-A")
        t2 = _truck(db, plate_number="TRUCK-B")
        _assignment(db, d1, t1)
        _assignment(db, d2, t2)

        repo.swap(d1, t1, d2, t2)

        r1 = db.conn.execute(
            "SELECT truck_id FROM driver_truck_assignments WHERE driver_id = ?", (d1,)
        ).fetchone()
        r2 = db.conn.execute(
            "SELECT truck_id FROM driver_truck_assignments WHERE driver_id = ?", (d2,)
        ).fetchone()
        assert r1["truck_id"] == t2
        assert r2["truck_id"] == t1

    def test_swap_transaction_atomic(self, db, repo):
        d1 = _driver(db, name="Driver X")
        d2 = _driver(db, name="Driver Y")
        t1 = _truck(db, plate_number="TRUCK-X")
        t2 = _truck(db, plate_number="TRUCK-Y")
        _assignment(db, d1, t1)
        _assignment(db, d2, t2)

        repo.swap(d1, t1, d2, t2)

        # Both changes should be visible (committed)
        r1 = db.conn.execute(
            "SELECT truck_id FROM driver_truck_assignments WHERE driver_id = ?", (d1,)
        ).fetchone()
        r2 = db.conn.execute(
            "SELECT truck_id FROM driver_truck_assignments WHERE driver_id = ?", (d2,)
        ).fetchone()
        assert r1 is not None
        assert r2 is not None
        assert r1["truck_id"] == t2
        assert r2["truck_id"] == t1


# ── get_truck_plate_for_driver ───────────────────────────────────────


class TestGetTruckPlateForDriver:
    def test_get_truck_plate_for_driver_returns_plate(self, db, repo):
        did = _driver(db)
        tid = _truck(db, plate_number="PLT-001")
        _assignment(db, did, tid)
        plate = repo.get_truck_plate_for_driver(did)
        assert plate == "PLT-001"

    def test_get_truck_plate_for_driver_returns_empty_string_when_none(self, repo):
        plate = repo.get_truck_plate_for_driver(9999)
        assert plate == ""

    def test_get_truck_plate_for_driver_none_plate_becomes_empty_string(self, db, repo):
        did = _driver(db)
        tid = _truck(db, plate_number=None)
        _assignment(db, did, tid)
        plate = repo.get_truck_plate_for_driver(did)
        assert plate == ""


# ── get_driver_name_for_truck ────────────────────────────────────────


class TestGetDriverNameForTruck:
    def test_get_driver_name_for_truck_returns_name(self, db, repo):
        did = _driver(db, name="John Smith")
        tid = _truck(db)
        _assignment(db, did, tid)
        name = repo.get_driver_name_for_truck(tid)
        assert name == "John Smith"


# ── Unassign ─────────────────────────────────────────────────────────


class TestUnassign:
    def test_unassign_driver_removes_row(self, db, repo):
        did = _driver(db)
        tid = _truck(db)
        _assignment(db, did, tid)
        repo.unassign_driver(did)
        row = db.conn.execute(
            "SELECT * FROM driver_truck_assignments WHERE driver_id = ?", (did,)
        ).fetchone()
        assert row is None

    def test_unassign_truck_removes_row(self, db, repo):
        did = _driver(db)
        tid = _truck(db)
        _assignment(db, did, tid)
        repo.unassign_truck(tid)
        row = db.conn.execute(
            "SELECT * FROM driver_truck_assignments WHERE truck_id = ?", (tid,)
        ).fetchone()
        assert row is None


# ── get_driver_id_for_truck ──────────────────────────────────────────


class TestGetDriverIdForTruck:
    def test_get_driver_id_for_truck_returns_none(self, repo):
        result = repo.get_driver_id_for_truck(9999)
        assert result is None


# ── Tenant isolation: JOINs must scope BOTH sides ─────────────────────


def _assignment_with_company(db: InMemoryDB, driver_id: int, truck_id: int, company_id: int) -> None:
    """Seed an assignment with an explicit tenant, bypassing the repo (whose
    ``assign`` would stamp the caller's own company_id)."""
    db.conn.execute(
        "INSERT OR REPLACE INTO driver_truck_assignments "
        "(driver_id, truck_id, assigned_at, active, company_id) "
        "VALUES (?, ?, datetime('now'), 1, ?)",
        (driver_id, truck_id, company_id),
    )
    db.conn.commit()


class TestTenantIsolation:
    """A company-A query must never surface trucks/drivers owned by company B."""

    def test_get_truck_plate_for_driver_cross_tenant_truck_not_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        did = _driver(db, name="Alice", company_id=1)
        tid_b = _truck(db, plate_number="PLT-B", company_id=2)
        _assignment_with_company(db, did, tid_b, company_id=1)
        # The assignment belongs to company 1 but points at a company 2 truck —
        # the trucks side of the JOIN must reject it.
        assert repo.get_truck_plate_for_driver(did) == ""

    def test_get_truck_plate_for_driver_same_company_truck_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        did = _driver(db, name="Alice", company_id=1)
        tid_a = _truck(db, plate_number="PLT-A", company_id=1)
        _assignment_with_company(db, did, tid_a, company_id=1)
        assert repo.get_truck_plate_for_driver(did) == "PLT-A"

    def test_get_plates_by_driver_ids_cross_tenant_truck_not_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        did_a = _driver(db, name="Alice", company_id=1)
        did_b = _driver(db, name="Bob", company_id=1)
        tid_a = _truck(db, plate_number="PLT-A", company_id=1)
        tid_b = _truck(db, plate_number="PLT-B", company_id=2)
        _assignment_with_company(db, did_a, tid_a, company_id=1)
        _assignment_with_company(db, did_b, tid_b, company_id=1)
        plates = repo.get_plates_by_driver_ids([did_a, did_b])
        # Only the company-1 truck plate may be returned.
        assert plates == {did_a: "PLT-A"}

    def test_get_driver_names_for_trucks_cross_tenant_not_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        did_a = _driver(db, name="Alice", company_id=1)
        did_b = _driver(db, name="Bob", company_id=2)
        tid_a = _truck(db, plate_number="ISO-A", company_id=1)
        tid_b = _truck(db, plate_number="ISO-B", company_id=2)
        _assignment_with_company(db, did_a, tid_a, company_id=1)
        _assignment_with_company(db, did_b, tid_b, company_id=2)
        names = repo.get_driver_names_for_trucks([tid_a, tid_b])
        # Company B's truck/driver must not leak into company A's mapping.
        assert names == {tid_a: "Alice"}

    def test_get_driver_names_for_trucks_explicit_company_id(self, db, repo):
        # No tenant context set — the explicit company_id scopes the query.
        did_a = _driver(db, name="Alice", company_id=1)
        did_b = _driver(db, name="Bob", company_id=2)
        tid_a = _truck(db, plate_number="ISO-A", company_id=1)
        tid_b = _truck(db, plate_number="ISO-B", company_id=2)
        _assignment_with_company(db, did_a, tid_a, company_id=1)
        _assignment_with_company(db, did_b, tid_b, company_id=2)
        names = repo.get_driver_names_for_trucks([tid_a, tid_b], company_id=1)
        assert names == {tid_a: "Alice"}
        names_b = repo.get_driver_names_for_trucks([tid_a, tid_b], company_id=2)
        assert names_b == {tid_b: "Bob"}

    def test_get_driver_name_for_truck_cross_tenant_driver_not_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        did_b = _driver(db, name="Bob", company_id=2)
        tid_a = _truck(db, plate_number="ISO-A", company_id=1)
        _assignment_with_company(db, did_b, tid_a, company_id=1)
        # Company 1 assignment referencing a company 2 driver — the drivers
        # side of the JOIN must reject it.
        assert repo.get_driver_name_for_truck(tid_a) == ""

    def test_get_driver_name_for_truck_same_company_driver_returned(self, db, repo):
        from database.tenant_context import set_request_context
        set_request_context(1, "dispatcher")
        did_a = _driver(db, name="Alice", company_id=1)
        tid_a = _truck(db, plate_number="ISO-A", company_id=1)
        _assignment_with_company(db, did_a, tid_a, company_id=1)
        assert repo.get_driver_name_for_truck(tid_a) == "Alice"
