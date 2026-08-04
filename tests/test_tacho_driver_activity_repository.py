"""Tests for repositories.tacho_driver_activity_repository — CRUD + queries.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import date

from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> TachoDriverActivityRepository:
    return TachoDriverActivityRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _ensure_parents(db: InMemoryDB, import_id: int = 1, driver_id: int = 1) -> None:
    """Create parent records needed for FK constraints."""
    db.conn.execute(
        "INSERT OR IGNORE INTO tacho_imports (id, file_name, file_type, file_hash, imported_at, parse_status) "
        "VALUES (?, 'test.ddd', 'DDD', 'abc', datetime('now'), 'ok')",
        (import_id,),
    )
    db.conn.execute(
        "INSERT OR IGNORE INTO drivers (id, name, is_active, created_at, updated_at) "
        "VALUES (?, 'Test Driver', 1, datetime('now'), datetime('now'))",
        (driver_id,),
    )
    db.conn.commit()


def _ensure_import(db: InMemoryDB, import_id: int = 1) -> None:
    """Create a parent tacho_imports record for FK constraints."""
    db.conn.execute(
        "INSERT OR IGNORE INTO tacho_imports (id, file_name, file_type, file_hash, imported_at, parse_status) "
        "VALUES (?, 'test.ddd', 'DDD', 'abc', datetime('now'), 'ok')",
        (import_id,),
    )
    db.conn.commit()


def _activity(db: InMemoryDB, **kw) -> int:
    d = dict(
        import_id=1,
        driver_id=1,
        activity_date="2026-06-15",
        driving_minutes=480,
        work_minutes=120,
        rest_minutes=360,
        avail_minutes=0,
        distance_km=500.0,
        violations=None,
        country_codes="RO,HU",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(
        f"INSERT INTO tacho_driver_activity ({cols}) VALUES ({vals})",
        list(d.values()),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Create ───────────────────────────────────────────────────────────


class TestCreate:
    def test_create_returns_id(self, db, repo):
        _ensure_parents(db, import_id=1, driver_id=42)
        aid = repo.create(
            {
                "import_id": 1,
                "driver_id": 42,
                "activity_date": "2026-06-15",
                "driving_minutes": 300,
                "work_minutes": 60,
                "rest_minutes": 480,
                "avail_minutes": 0,
                "distance_km": 350.0,
                "violations": None,
                "country_codes": "RO",
            }
        )
        assert aid > 0
        row = repo.db.conn.execute(
            "SELECT * FROM tacho_driver_activity WHERE id = ?", (aid,)
        ).fetchone()
        assert row is not None
        assert row["driver_id"] == 42

    def test_create_invalid_column_raises_valueerror(self, repo):
        with pytest.raises(ValueError, match="Invalid column"):
            repo.create(
                {
                    "import_id": 1,
                    "driver_id": 1,
                    "activity_date": "2026-06-15",
                    "driving_minutes": 0,
                    "no_such_column": "boom",
                }
            )

    def test_create_injects_company_id_for_scoped_user(self, db, repo):
        """When the DB has a company context, company_id is injected into the row."""
        # Add company_id column to tacho_driver_activity (not present in base schema)
        try:
            db.conn.execute(
                "ALTER TABLE tacho_driver_activity ADD COLUMN company_id INTEGER"
            )
        except Exception:
            pass  # already exists

        from database.tenant_context import set_request_context, clear_context

        _ensure_parents(db, import_id=1, driver_id=7)
        set_request_context(company_id=5, role="user")

        try:
            aid = repo.create(
                {
                    "import_id": 1,
                    "driver_id": 7,
                    "activity_date": "2026-06-15",
                    "driving_minutes": 200,
                    "work_minutes": 0,
                    "rest_minutes": 600,
                    "avail_minutes": 0,
                    "distance_km": 250.0,
                    "violations": None,
                    "country_codes": "DE",
                }
            )
            assert aid > 0
            row = db.conn.execute(
                "SELECT * FROM tacho_driver_activity WHERE id = ?", (aid,)
            ).fetchone()
            assert row["company_id"] == 5
        finally:
            clear_context()


# ── Get by driver ────────────────────────────────────────────────────


class TestGetByDriver:
    def test_get_by_driver_returns_correct_rows(self, db, repo):
        _ensure_parents(db, driver_id=10, import_id=1)
        _ensure_parents(db, driver_id=20, import_id=1)
        _activity(db, driver_id=10, activity_date="2026-07-01", driving_minutes=400)
        _activity(db, driver_id=10, activity_date="2026-07-02", driving_minutes=450)
        _activity(db, driver_id=20, activity_date="2026-07-01", driving_minutes=300)

        rows = repo.get_by_driver(10, date_from=date(2026, 1, 1))
        assert len(rows) == 2
        assert all(r["driver_id"] == 10 for r in rows)

    def test_get_by_driver_respects_from_date(self, db, repo):
        _ensure_parents(db, driver_id=10, import_id=1)
        _activity(db, driver_id=10, activity_date="2026-06-01", driving_minutes=100)
        _activity(db, driver_id=10, activity_date="2026-07-01", driving_minutes=200)
        _activity(db, driver_id=10, activity_date="2026-08-01", driving_minutes=300)

        rows = repo.get_by_driver(10, date_from=date(2026, 7, 1))
        assert len(rows) == 2  # July and August
        dates = sorted(r["activity_date"] for r in rows)
        assert dates == ["2026-07-01", "2026-08-01"]

    def test_get_by_driver_returns_empty_when_no_match(self, repo):
        rows = repo.get_by_driver(999, date_from=date(2020, 1, 1))
        assert rows == []


# ── Get by import ────────────────────────────────────────────────────


class TestGetByImport:
    def test_get_by_import_returns_correct_rows(self, db, repo):
        _ensure_parents(db, import_id=100, driver_id=1)
        _ensure_parents(db, import_id=100, driver_id=2)
        _ensure_parents(db, import_id=200, driver_id=1)
        _activity(db, import_id=100, driver_id=1, activity_date="2026-07-01")
        _activity(db, import_id=100, driver_id=2, activity_date="2026-07-02")
        _activity(db, import_id=200, driver_id=1, activity_date="2026-07-01")

        rows = repo.get_by_import(100)
        assert len(rows) == 2
        assert all(r["import_id"] == 100 for r in rows)


# ── Delete by import ─────────────────────────────────────────────────


class TestDeleteByImport:
    def test_delete_by_import_removes_all(self, db, repo):
        _ensure_parents(db, import_id=300, driver_id=1)
        _ensure_parents(db, import_id=300, driver_id=2)
        _ensure_parents(db, import_id=301, driver_id=1)
        _activity(db, import_id=300, driver_id=1, activity_date="2026-07-01")
        _activity(db, import_id=300, driver_id=2, activity_date="2026-07-02")
        _activity(db, import_id=301, driver_id=1, activity_date="2026-07-03")

        repo.delete_by_import(300)
        remaining = db.conn.execute(
            "SELECT * FROM tacho_driver_activity WHERE import_id = 300"
        ).fetchall()
        assert len(remaining) == 0
        # Other import's data should still exist
        other = db.conn.execute(
            "SELECT * FROM tacho_driver_activity WHERE import_id = 301"
        ).fetchall()
        assert len(other) == 1
