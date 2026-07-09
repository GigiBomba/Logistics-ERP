"""Tests for repositories.alert_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from repositories.alert_repository import AlertRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> AlertRepository:
    return AlertRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _alert_tuple(
    alert_id: str = "alert-001",
    alert_type: str = "maintenance",
    severity: str = "warning",
    title: str = "Test Alert",
    message: str = "Something needs attention",
    truck_id: str = "TRK-1",
    trip_id: int = None,
    created_at: str = None,
    resolved: int = 0,
    resolved_at: str = None,
    metadata_json: str = None,
):
    if created_at is None:
        created_at = datetime.now().isoformat()
    return (
        alert_id, alert_type, severity, title, message,
        truck_id, trip_id, created_at, resolved, resolved_at, metadata_json,
    )


# ── Create (single) ──────────────────────────────────────────────────


class TestCreate:
    def test_creates_single_alert(self, db, repo):
        repo.create(
            id="alert-001",
            alert_type="maintenance",
            severity="warning",
            title="Oil change due",
            message="Truck TRK-1 needs oil change",
            truck_id="TRK-1",
            trip_id=None,
            created_at=datetime.now().isoformat(),
            resolved=0,
            resolved_at=None,
            metadata_json=None,
        )
        row = db.conn.execute(
            "SELECT * FROM alerts WHERE id = ?", ("alert-001",)
        ).fetchone()
        assert row is not None
        assert row["title"] == "Oil change due"
        assert row["resolved"] == 0

    def test_upserts_on_duplicate_id(self, db, repo):
        now = datetime.now().isoformat()
        repo.create(
            id="alert-dup", alert_type="type_a", severity="low",
            title="Original", message="First", truck_id=None,
            trip_id=None, created_at=now, resolved=0,
            resolved_at=None, metadata_json=None,
        )
        repo.create(
            id="alert-dup", alert_type="type_b", severity="high",
            title="Replaced", message="Second", truck_id=None,
            trip_id=None, created_at=now, resolved=0,
            resolved_at=None, metadata_json=None,
        )
        row = db.conn.execute(
            "SELECT * FROM alerts WHERE id = ?", ("alert-dup",)
        ).fetchone()
        assert row["title"] == "Replaced"
        assert row["severity"] == "high"


# ── Create batch ─────────────────────────────────────────────────────


class TestCreateBatch:
    def test_bulk_inserts_all(self, db, repo):
        alerts = [
            _alert_tuple("batch-001", title="Alert 1"),
            _alert_tuple("batch-002", title="Alert 2"),
            _alert_tuple("batch-003", title="Alert 3"),
        ]
        count = repo.create_batch(alerts)
        assert count == 3
        rows = db.conn.execute(
            "SELECT * FROM alerts ORDER BY id"
        ).fetchall()
        assert len(rows) == 3

    def test_uses_insert_or_ignore(self, db, repo):
        now = datetime.now().isoformat()
        # Seed one alert first
        repo.create(
            id="ignore-test", alert_type="existing", severity="low",
            title="Keep me", message="", truck_id=None,
            trip_id=None, created_at=now, resolved=0,
            resolved_at=None, metadata_json=None,
        )
        # Batch with a duplicate id — should be ignored, not replaced
        alerts = [
            _alert_tuple("ignore-test", title="Should be ignored"),
            _alert_tuple("batch-new", title="New alert"),
        ]
        count = repo.create_batch(alerts)
        assert count == 2  # still counts the attempt
        rows = db.conn.execute(
            "SELECT * FROM alerts ORDER BY id"
        ).fetchall()
        assert len(rows) == 2
        # Original alert should keep its title
        orig = db.conn.execute(
            "SELECT * FROM alerts WHERE id = ?", ("ignore-test",)
        ).fetchone()
        assert orig["title"] == "Keep me"


# ── Get unresolved ───────────────────────────────────────────────────


class TestGetUnresolved:
    def test_returns_only_unresolved(self, db, repo):
        now = datetime.now().isoformat()
        repo.create(
            id="unres-1", alert_type="a", severity="low",
            title="Unresolved", message="", truck_id=None,
            trip_id=None, created_at=now, resolved=0,
            resolved_at=None, metadata_json=None,
        )
        repo.create(
            id="res-1", alert_type="a", severity="low",
            title="Resolved", message="", truck_id=None,
            trip_id=None, created_at=now, resolved=1,
            resolved_at=now, metadata_json=None,
        )
        results = repo.get_unresolved()
        assert len(results) == 1
        assert results[0]["id"] == "unres-1"

    def test_empty_when_all_resolved(self, db, repo):
        now = datetime.now().isoformat()
        repo.create(
            id="all-res-1", alert_type="a", severity="low",
            title="Done", message="", truck_id=None,
            trip_id=None, created_at=now, resolved=1,
            resolved_at=now, metadata_json=None,
        )
        assert repo.get_unresolved() == []


# ── Resolve ──────────────────────────────────────────────────────────


class TestResolve:
    def test_marks_as_resolved(self, db, repo):
        now = datetime.now().isoformat()
        repo.create(
            id="to-resolve", alert_type="a", severity="low",
            title="Fix me", message="", truck_id=None,
            trip_id=None, created_at=now, resolved=0,
            resolved_at=None, metadata_json=None,
        )
        repo.resolve("to-resolve", resolved_at=now)
        row = db.conn.execute(
            "SELECT * FROM alerts WHERE id = ?", ("to-resolve",)
        ).fetchone()
        assert row["resolved"] == 1
        assert row["resolved_at"] == now

    def test_noop_for_missing_alert(self, repo):
        # Should not raise
        repo.resolve("does-not-exist", resolved_at="2026-07-01T00:00:00")


# ── Cleanup old ──────────────────────────────────────────────────────


class TestCleanupOld:
    def test_deletes_old_resolved(self, db, repo):
        old = (datetime.now() - timedelta(days=200)).isoformat()
        now = datetime.now().isoformat()
        repo.create(
            id="old-resolved", alert_type="a", severity="low",
            title="Old", message="", truck_id=None,
            trip_id=None, created_at=old, resolved=1,
            resolved_at=old, metadata_json=None,
        )
        repo.create(
            id="new-unresolved", alert_type="a", severity="low",
            title="New", message="", truck_id=None,
            trip_id=None, created_at=now, resolved=0,
            resolved_at=None, metadata_json=None,
        )
        deleted = repo.cleanup_old(days=90)
        assert deleted == 1
        remaining = db.conn.execute(
            "SELECT id FROM alerts ORDER BY id"
        ).fetchall()
        ids = [r["id"] for r in remaining]
        assert "new-unresolved" in ids
        assert "old-resolved" not in ids

    def test_keeps_unresolved(self, db, repo):
        old = (datetime.now() - timedelta(days=200)).isoformat()
        repo.create(
            id="old-unresolved", alert_type="a", severity="low",
            title="Old but unresolved", message="", truck_id=None,
            trip_id=None, created_at=old, resolved=0,
            resolved_at=None, metadata_json=None,
        )
        deleted = repo.cleanup_old(days=90)
        assert deleted == 0
        row = db.conn.execute(
            "SELECT * FROM alerts WHERE id = ?", ("old-unresolved",)
        ).fetchone()
        assert row is not None
