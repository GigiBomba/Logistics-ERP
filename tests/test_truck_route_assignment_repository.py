"""Tests for repositories.truck_route_assignment_repository.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.truck_route_assignment_repository import TruckRouteAssignmentRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> TruckRouteAssignmentRepository:
    return TruckRouteAssignmentRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _route_history(db: InMemoryDB, **kw) -> int:
    """Insert a minimal route_history_v2 row and return its id."""
    d = dict(
        route_fingerprint="fp-001",
        metadata_version=1,
        created_at="2026-01-01T00:00:00",
        last_calculated_at="2026-01-01T00:00:00",
        stops_json="[]",
        geometry_encoding="zlib-json",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO route_history_v2 ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _assignment(db: InMemoryDB, **kw) -> int:
    """Insert a minimal truck_route_assignments row and return its id."""
    d = dict(
        truck_id="TRK-1",
        route_id=1,
        status="assigned",
        assigned_at="2026-01-01T00:00:00",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO truck_route_assignments ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Assign ──────────────────────────────────────────────────────────


class TestAssign:
    def test_assign_coerces_truck_id_to_str(self, repo):
        """Passing an int truck_id is coerced to str."""
        rid = _route_history(repo.db)
        aid = repo.assign(truck_id=42, route_id=rid)
        row = repo.db.conn.execute(
            "SELECT * FROM truck_route_assignments WHERE id = ?", (aid,)
        ).fetchone()
        assert row["truck_id"] == "42"

    def test_assign_coerces_route_id_to_int(self, repo):
        """Passing a str route_id is coerced to int."""
        rid = _route_history(repo.db)
        aid = repo.assign(truck_id="TRK-1", route_id=str(rid))
        row = repo.db.conn.execute(
            "SELECT * FROM truck_route_assignments WHERE id = ?", (aid,)
        ).fetchone()
        assert row["route_id"] == rid

    def test_assign_returns_id(self, repo):
        rid = _route_history(repo.db)
        aid = repo.assign(truck_id="TRK-1", route_id=rid)
        assert aid > 0

    def test_assign_defaults_status(self, repo):
        rid = _route_history(repo.db)
        aid = repo.assign(truck_id="TRK-1", route_id=rid)
        row = repo.db.conn.execute(
            "SELECT * FROM truck_route_assignments WHERE id = ?", (aid,)
        ).fetchone()
        assert row["status"] == "assigned"


# ── Complete ────────────────────────────────────────────────────────


class TestComplete:
    def test_complete_updates_status_and_timestamp(self, db, repo):
        rid = _route_history(db)
        _assignment(db, route_id=rid, status="active")
        result = repo.complete(route_id=rid, completed_at="2026-06-01T12:00:00")
        assert result is True
        row = db.conn.execute(
            "SELECT * FROM truck_route_assignments WHERE route_id = ?", (rid,)
        ).fetchone()
        assert row["status"] == "completed"
        assert row["completed_at"] == "2026-06-01T12:00:00"

    def test_complete_only_targets_assigned_or_active(self, db, repo):
        rid = _route_history(db)
        _assignment(db, route_id=rid, status="completed")  # already completed
        result = repo.complete(route_id=rid, completed_at="2026-06-01T12:00:00")
        assert result is False

    def test_complete_returns_true_on_success(self, db, repo):
        rid = _route_history(db)
        _assignment(db, route_id=rid, status="assigned")
        result = repo.complete(route_id=rid, completed_at="now")
        assert result is True

    def test_complete_returns_false_when_nothing_matches(self, db, repo):
        result = repo.complete(route_id=999, completed_at="now")
        assert result is False


# ── Get by truck ────────────────────────────────────────────────────


class TestGetByTruck:
    def test_get_by_truck_joins_route_data(self, db, repo):
        rid = _route_history(db, total_distance_km=500.0, duration_min=240.0,
                             profile="fastest")
        _assignment(db, truck_id="TRK-1", route_id=rid)

        rows = repo.get_by_truck("TRK-1")
        assert len(rows) == 1
        assert rows[0]["total_distance_km"] == 500.0
        assert rows[0]["duration_min"] == 240.0
        assert rows[0]["profile"] == "fastest"

    def test_get_by_truck_filters_by_status(self, db, repo):
        rid = _route_history(db)
        _assignment(db, truck_id="TRK-1", route_id=rid, status="assigned")
        rid2 = _route_history(db, route_fingerprint="fp-002")
        _assignment(db, truck_id="TRK-1", route_id=rid2, status="completed")

        rows = repo.get_by_truck("TRK-1", status="assigned")
        assert len(rows) == 1
        assert rows[0]["route_id"] == rid
