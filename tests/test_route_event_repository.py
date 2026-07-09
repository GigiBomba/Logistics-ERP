"""Tests for repositories.route_event_repository — CRUD + orphan cleanup.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.route_event_repository import RouteEventRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> RouteEventRepository:
    return RouteEventRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _route_history(db: InMemoryDB, **kw) -> int:
    """Seed a row in route_history_v2 and return its id."""
    d = dict(
        route_fingerprint="fp-test",
        metadata_version=1,
        created_at="2026-07-01T00:00:00",
        last_calculated_at="2026-07-01T00:00:00",
        calculation_count=1,
        stops_json="[]",
        geometry_encoding="zlib-json",
        is_committed=1,
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(
        f"INSERT INTO route_history_v2 ({cols}) VALUES ({vals})",
        list(d.values()),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _route_event(db: InMemoryDB, **kw) -> int:
    """Seed a row in route_events and return its id."""
    d = dict(
        route_id=None,
        event_type="created",
        payload_json="{}",
        created_at="2026-07-01T00:00:00",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(
        f"INSERT INTO route_events ({cols}) VALUES ({vals})",
        list(d.values()),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Create ───────────────────────────────────────────────────────────


class TestCreate:
    def test_create_with_valid_route_id_returns_id(self, db, repo):
        rh_id = _route_history(db)
        event_id = repo.create(
            route_id=rh_id,
            event_type="calculated",
            payload_json='{"duration": 120}',
            created_at="2026-07-01T12:00:00",
        )
        assert event_id > 0
        row = db.conn.execute(
            "SELECT * FROM route_events WHERE id = ?", (event_id,)
        ).fetchone()
        assert row is not None
        assert row["route_id"] == rh_id
        assert row["event_type"] == "calculated"

    def test_create_with_null_route_id_returns_id(self, repo):
        event_id = repo.create(
            route_id=None,
            event_type="comment",
            payload_json='{"note": "manual entry"}',
            created_at="2026-07-01T12:00:00",
        )
        assert event_id > 0
        row = repo.db.conn.execute(
            "SELECT * FROM route_events WHERE id = ?", (event_id,)
        ).fetchone()
        assert row is not None
        assert row["route_id"] is None

    def test_create_invalid_column_raises_valueerror(self, repo):
        # create() has explicit kwargs, not **kwargs; test via _validate_columns directly
        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns(
                {"route_id": None, "event_type": "test", "bogus_field": "crash"}
            )


# ── Delete orphans ──────────────────────────────────────────────────


class TestDeleteOrphans:
    def test_delete_orphans_admin_removes_stale_refs(self, db, repo):
        """Events referencing a non-existent route_history_v2 row are removed."""
        _route_event(db, route_id=999, event_type="orphan")
        count = repo.delete_orphans()
        assert count == 1
        remaining = db.conn.execute(
            "SELECT * FROM route_events WHERE event_type = 'orphan'"
        ).fetchall()
        assert len(remaining) == 0

    def test_delete_orphans_admin_preserves_valid_refs(self, db, repo):
        """Events referencing an existing route_history_v2 row are kept."""
        rh_id = _route_history(db)
        _route_event(db, route_id=rh_id, event_type="valid")
        count = repo.delete_orphans()
        assert count == 0
        row = db.conn.execute(
            "SELECT * FROM route_events WHERE event_type = 'valid'"
        ).fetchone()
        assert row is not None

    def test_delete_orphans_scoped_respects_company_filter(self, db, repo):
        """When scoped, only events belonging to the user's company are removed."""
        # Add company_id column (in real app this is added via migration)
        try:
            db.conn.execute("ALTER TABLE route_events ADD COLUMN company_id INTEGER")
        except Exception:
            pass  # already exists

        # Seed a route_history row (will be used to validate route_id exists)
        rh_id = _route_history(db)

        # Set scoped context
        db.user_company_id = 10
        db.user_role = "user"

        # Event with company_id=10 (matches scope) and route_id=999 (orphan)
        _route_event(db, route_id=999, event_type="orphan-scoped", company_id=10)
        # Event with company_id=20 (different company) and route_id=999 (orphan)
        _route_event(db, route_id=999, event_type="orphan-other", company_id=20)
        # Event with company_id=10 and valid route_id (should be preserved)
        _route_event(db, route_id=rh_id, event_type="valid-scoped", company_id=10)

        count = repo.delete_orphans()
        # Only the orphan event with company_id=10 should be deleted
        assert count == 1

        remaining = db.conn.execute(
            "SELECT event_type FROM route_events ORDER BY id"
        ).fetchall()
        remaining_types = [r["event_type"] for r in remaining]
        assert "orphan-scoped" not in remaining_types  # deleted
        assert "orphan-other" in remaining_types       # different company
        assert "valid-scoped" in remaining_types       # valid route_id
