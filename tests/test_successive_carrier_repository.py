"""Tests for repositories.successive_carrier_repository — CRUD + replace.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.successive_carrier_repository import SuccessiveCarrierRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> SuccessiveCarrierRepository:
    return SuccessiveCarrierRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _carrier(db: InMemoryDB, **kw) -> int:
    d = dict(
        trip_id=1,
        sequence_order=1,
        carrier_name="Sub Carrier A",
        carrier_address="Addr 1",
        carrier_country="RO",
        vehicle_plate="B-111-AAA",
        trailer_plate="B-222-BBB",
        driver_name="John",
        from_location="Bucharest",
        to_location="Budapest",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(
        f"INSERT INTO successive_carriers ({cols}) VALUES ({vals})",
        list(d.values()),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Get by trip ──────────────────────────────────────────────────────


class TestGetByTrip:
    def test_get_by_trip_returns_ordered_by_sequence(self, db, repo):
        _carrier(db, trip_id=50, sequence_order=2, carrier_name="Second")
        _carrier(db, trip_id=50, sequence_order=1, carrier_name="First")
        _carrier(db, trip_id=50, sequence_order=3, carrier_name="Third")
        rows = repo.get_by_trip(50)
        assert len(rows) == 3
        names = [r["carrier_name"] for r in rows]
        assert names == ["First", "Second", "Third"]

    def test_get_by_trip_returns_empty_list(self, repo):
        assert repo.get_by_trip(999) == []


# ── Create ───────────────────────────────────────────────────────────


class TestCreate:
    def test_create_inserts_row(self, repo):
        cid = repo.create(
            {
                "trip_id": 10,
                "sequence_order": 1,
                "carrier_name": "New Carrier",
                "carrier_address": "",
                "carrier_country": "HU",
                "vehicle_plate": "",
                "trailer_plate": "",
                "driver_name": "",
                "from_location": "",
                "to_location": "",
            }
        )
        assert cid > 0
        row = repo.db.conn.execute(
            "SELECT * FROM successive_carriers WHERE id = ?", (cid,)
        ).fetchone()
        assert row is not None
        assert row["carrier_name"] == "New Carrier"
        assert row["trip_id"] == 10


# ── Update ───────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_changes_fields(self, db, repo):
        cid = _carrier(db, carrier_name="Old Name", vehicle_plate="OLD-01")
        repo.update(cid, {"carrier_name": "Updated Name", "vehicle_plate": "NEW-01"})
        row = db.conn.execute(
            "SELECT * FROM successive_carriers WHERE id = ?", (cid,)
        ).fetchone()
        assert row["carrier_name"] == "Updated Name"
        assert row["vehicle_plate"] == "NEW-01"


# ── Delete ───────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_removes_single_record(self, db, repo):
        cid = _carrier(db, trip_id=20, carrier_name="ToDelete")
        repo.delete(cid)
        row = db.conn.execute(
            "SELECT * FROM successive_carriers WHERE id = ?", (cid,)
        ).fetchone()
        assert row is None

    def test_delete_by_trip_removes_all(self, db, repo):
        _carrier(db, trip_id=30, sequence_order=1, carrier_name="A")
        _carrier(db, trip_id=30, sequence_order=2, carrier_name="B")
        _carrier(db, trip_id=30, sequence_order=3, carrier_name="C")
        repo.delete_by_trip(30)
        remaining = db.conn.execute(
            "SELECT * FROM successive_carriers WHERE trip_id = 30"
        ).fetchall()
        assert len(remaining) == 0


# ── Replace for trip ─────────────────────────────────────────────────


class TestReplaceForTrip:
    def test_replace_for_trip_replaces_all(self, db, repo):
        _carrier(db, trip_id=40, sequence_order=1, carrier_name="Old A")
        _carrier(db, trip_id=40, sequence_order=2, carrier_name="Old B")
        new_carriers = [
            {"carrier_name": "New X", "carrier_address": "Addr X", "carrier_country": "DE",
             "vehicle_plate": "", "trailer_plate": "", "driver_name": "",
             "from_location": "", "to_location": ""},
            {"carrier_name": "New Y", "carrier_address": "Addr Y", "carrier_country": "FR",
             "vehicle_plate": "", "trailer_plate": "", "driver_name": "",
             "from_location": "", "to_location": ""},
            {"carrier_name": "New Z", "carrier_address": "Addr Z", "carrier_country": "IT",
             "vehicle_plate": "", "trailer_plate": "", "driver_name": "",
             "from_location": "", "to_location": ""},
        ]
        repo.replace_for_trip(40, new_carriers)
        rows = repo.get_by_trip(40)
        assert len(rows) == 3
        names = [r["carrier_name"] for r in rows]
        assert names == ["New X", "New Y", "New Z"]
        # Sequence order should be 1, 2, 3
        seqs = [r["sequence_order"] for r in rows]
        assert seqs == [1, 2, 3]

    def test_replace_for_trip_empty_list_clears_all(self, db, repo):
        _carrier(db, trip_id=50, sequence_order=1, carrier_name="ToClear")
        _carrier(db, trip_id=50, sequence_order=2, carrier_name="AlsoClear")
        repo.replace_for_trip(50, [])
        rows = repo.get_by_trip(50)
        assert rows == []
