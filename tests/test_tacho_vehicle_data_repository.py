"""Tests for repositories.tacho_vehicle_data_repository.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.tacho_vehicle_data_repository import TachoVehicleDataRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> TachoVehicleDataRepository:
    return TachoVehicleDataRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _truck(db: InMemoryDB, **kw) -> int:
    """Insert a minimal truck row and return its id."""
    d = dict(plate_number="TEST-01", active_status=1)
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO trucks ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _import_row(db: InMemoryDB, **kw) -> int:
    """Insert a minimal tacho_imports row and return its id."""
    d = dict(
        file_name="test.ddd",
        file_type="DDD",
        file_hash="abc",
        imported_at="2026-01-01T00:00:00",
        parse_status="ok",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO tacho_imports ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _ensure_parents(db: InMemoryDB, truck_id: int = 1, import_id: int = 1) -> None:
    """Create parent records needed for FK constraints on tacho_vehicle_data."""
    db.conn.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, active_status) VALUES (?, 'FK-TRUCK', 1)",
        (truck_id,),
    )
    db.conn.execute(
        "INSERT OR IGNORE INTO tacho_imports (id, file_name, file_type, file_hash, imported_at, parse_status) "
        "VALUES (?, 'test.ddd', 'DDD', 'abc', datetime('now'), 'ok')",
        (import_id,),
    )
    db.conn.commit()


def _vehicle_row(db: InMemoryDB, **kw) -> int:
    """Insert a minimal tacho_vehicle_data row and return its id."""
    d = dict(import_id=1, truck_id=1, vu_serial_number="VU-001")
    d.update(kw)
    _ensure_parents(db, truck_id=d.get("truck_id", 1), import_id=d.get("import_id", 1))
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO tacho_vehicle_data ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Create ──────────────────────────────────────────────────────────


class TestCreate:
    def test_create_rejects_invalid_columns(self, repo):
        """Unknown columns raise ValueError."""
        with pytest.raises(ValueError, match="Invalid column"):
            repo.create({"import_id": 1, "truck_id": 1, "bogus_col": "nope"})

    def test_create_persists_data(self, db, repo):
        """Inserted row is readable back with matching values."""
        _ensure_parents(db, truck_id=1, import_id=1)
        iid = repo.create({
            "import_id": 1,
            "truck_id": 1,
            "vu_serial_number": "VU-999",
            "odometer_km": 12345.0,
            "k_factor": 8,
            "w_factor": 4,
            "speed_violations": 2,
        })
        assert iid > 0
        row = db.conn.execute(
            "SELECT * FROM tacho_vehicle_data WHERE id = ?", (iid,)
        ).fetchone()
        assert row is not None
        assert row["vu_serial_number"] == "VU-999"
        assert row["odometer_km"] == 12345.0


# ── Get by truck ────────────────────────────────────────────────────


class TestGetByTruck:
    def test_get_by_truck_filters_correctly(self, db, repo):
        t1 = _truck(db, plate_number="TRUCK-A")
        t2 = _truck(db, plate_number="TRUCK-B")
        imp = _import_row(db)
        _vehicle_row(db, import_id=imp, truck_id=t1, vu_serial_number="VU-A")
        _vehicle_row(db, import_id=imp, truck_id=t2, vu_serial_number="VU-B")

        rows = repo.get_by_truck(t1)
        assert len(rows) == 1
        assert rows[0]["vu_serial_number"] == "VU-A"

    def test_get_by_truck_returns_empty_list(self, db, repo):
        t1 = _truck(db, plate_number="LONELY")
        _truck(db, plate_number="OTHER")
        rows = repo.get_by_truck(t1)
        assert rows == []


# ── Get by import ───────────────────────────────────────────────────


class TestGetByImport:
    def test_get_by_import_returns_correct_row(self, db, repo):
        imp1 = _import_row(db, file_hash="h1")
        imp2 = _import_row(db, file_hash="h2")
        _vehicle_row(db, import_id=imp1, vu_serial_number="VU-1")
        _vehicle_row(db, import_id=imp2, vu_serial_number="VU-2")

        row = repo.get_by_import(imp1)
        assert row is not None
        assert row["vu_serial_number"] == "VU-1"


# ── Get latest by truck ─────────────────────────────────────────────


class TestGetLatestByTruck:
    def test_get_latest_by_truck_picks_max_imported_at(self, db, repo):
        tid = _truck(db)
        imp_old = _import_row(db, file_hash="h1", imported_at="2026-01-01T00:00:00")
        imp_new = _import_row(db, file_hash="h2", imported_at="2026-06-01T00:00:00")
        _vehicle_row(db, import_id=imp_old, truck_id=tid, vu_serial_number="VU-OLD")
        _vehicle_row(db, import_id=imp_new, truck_id=tid, vu_serial_number="VU-NEW")

        row = repo.get_latest_by_truck(tid)
        assert row is not None
        assert row["vu_serial_number"] == "VU-NEW"


# ── Get tacho status data ───────────────────────────────────────────


class TestGetTachoStatusData:
    def test_get_tacho_status_data_joins_trucks(self, db, repo):
        tid = _truck(db, plate_number="STA-01")
        imp = _import_row(db)
        _vehicle_row(db, import_id=imp, truck_id=tid,
                     calibration_date="2026-01-01",
                     calibration_expiry="2026-12-31")

        rows = repo.get_tacho_status_data()
        assert len(rows) == 1
        assert rows[0]["plate_number"] == "STA-01"
        assert rows[0]["truck_id"] == tid
        assert rows[0]["calibration_date"] == "2026-01-01"

    def test_get_tacho_status_data_no_company_filter(self, db, repo):
        """Regression: data from all companies is returned (admin mode)."""
        tid = _truck(db, plate_number="ALL-CO")
        imp = _import_row(db)
        _vehicle_row(db, import_id=imp, truck_id=tid)

        rows = repo.get_tacho_status_data()
        assert len(rows) == 1


# ── Get latest per truck ────────────────────────────────────────────


class TestGetLatestPerTruck:
    def test_get_latest_per_truck_returns_one_per_truck(self, db, repo):
        t1 = _truck(db, plate_number="T1")
        t2 = _truck(db, plate_number="T2")
        imp1 = _import_row(db, file_hash="h1", imported_at="2026-01-01")
        imp2 = _import_row(db, file_hash="h2", imported_at="2026-06-01")
        _vehicle_row(db, import_id=imp1, truck_id=t1, vu_serial_number="VU-T1")
        _vehicle_row(db, import_id=imp2, truck_id=t2, vu_serial_number="VU-T2")
        _vehicle_row(db, import_id=imp2, truck_id=t1, vu_serial_number="VU-T1-LATEST")

        rows = repo.get_latest_per_truck()
        rows_by_truck = {r["truck_id"]: r["vu_serial_number"] for r in rows if r.get("truck_id")}
        assert rows_by_truck[t1] == "VU-T1-LATEST"
        assert rows_by_truck[t2] == "VU-T2"

    def test_get_latest_per_truck_no_company_filter(self, db, repo):
        """Regression: all rows returned without company filter in admin mode."""
        tid = _truck(db, plate_number="REG-TEST")
        imp = _import_row(db)
        _vehicle_row(db, import_id=imp, truck_id=tid)

        rows = repo.get_latest_per_truck()
        assert len(rows) >= 1
