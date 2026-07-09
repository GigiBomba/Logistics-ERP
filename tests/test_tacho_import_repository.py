"""Tests for repositories.tacho_import_repository.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.tacho_import_repository import TachoImportRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> TachoImportRepository:
    return TachoImportRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _import_row(db: InMemoryDB, **kw) -> int:
    """Insert a minimal tacho_imports row and return its id."""
    d = dict(
        file_name="test.ddd",
        file_type="DDD",
        file_hash="abc123",
        imported_at="2026-01-01T00:00:00",
        parse_status="ok",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO tacho_imports ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Create ──────────────────────────────────────────────────────────


class TestCreate:
    def test_create_rejects_invalid_columns(self, repo):
        """Unknown columns raise ValueError."""
        with pytest.raises(ValueError, match="Invalid column"):
            repo.create({"file_name": "x.ddd", "bogus_col": "boom"})

    def test_create_returns_id(self, repo):
        """create() returns a positive integer id."""
        iid = repo.create({
            "file_name": "test.ddd",
            "file_type": "DDD",
            "file_hash": "hash-001",
            "imported_at": "2026-06-01T12:00:00",
            "parse_status": "ok",
        })
        assert iid > 0

    def test_create_persists_fields(self, db, repo):
        """Inserted row is readable back with matching values."""
        iid = repo.create({
            "file_name": "persist.ddd",
            "file_type": "DDD",
            "file_hash": "hash-002",
            "imported_at": "2026-06-02T12:00:00",
            "parse_status": "ok",
            "notes": "test notes",
        })
        row = db.conn.execute(
            "SELECT * FROM tacho_imports WHERE id = ?", (iid,)
        ).fetchone()
        assert row is not None
        assert row["file_name"] == "persist.ddd"
        assert row["file_hash"] == "hash-002"
        assert row["notes"] == "test notes"


# ── Get by hash ────────────────────────────────────────────────────


class TestGetByHash:
    def test_get_by_hash_finds_exact_match(self, db, repo):
        _import_row(db, file_hash="exact-hash", file_name="found.ddd")
        result = repo.get_by_hash("exact-hash")
        assert result is not None
        assert result["file_hash"] == "exact-hash"

    def test_get_by_hash_returns_none_for_unknown(self, db, repo):
        _import_row(db, file_hash="some-hash")
        result = repo.get_by_hash("nonexistent")
        assert result is None

    def test_get_by_hash_deduplicates_latest(self, db, repo):
        """When multiple rows share the same hash, return the one with the highest id."""
        _import_row(db, file_hash="dup-hash", file_name="old.ddd", imported_at="2026-01-01")
        _import_row(db, file_hash="dup-hash", file_name="new.ddd", imported_at="2026-06-01")
        result = repo.get_by_hash("dup-hash")
        assert result is not None
        assert result["file_name"] == "new.ddd"


# ── Get recent ──────────────────────────────────────────────────────


class TestGetRecent:
    def test_get_recent_respects_limit(self, db, repo):
        for i in range(5):
            _import_row(db, file_hash=f"h{i}", file_name=f"f{i}.ddd",
                        imported_at=f"2026-06-{i+1:02d}T00:00:00")
        results = repo.get_recent(limit=3)
        assert len(results) == 3

    def test_get_recent_orders_by_imported_at_desc(self, db, repo):
        _import_row(db, file_hash="h1", file_name="old.ddd", imported_at="2026-01-01T00:00:00")
        _import_row(db, file_hash="h2", file_name="new.ddd", imported_at="2026-06-01T00:00:00")
        results = repo.get_recent(limit=10)
        assert len(results) >= 2
        assert results[0]["file_name"] == "new.ddd"
        assert results[1]["file_name"] == "old.ddd"
