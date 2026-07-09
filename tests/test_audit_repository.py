"""Tests for repositories.audit_repository — audit event logging.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

import json

from repositories.audit_repository import AuditRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> AuditRepository:
    return AuditRepository(db)


# ── Log event ────────────────────────────────────────────────────────


class TestLogEvent:
    def test_inserts_event(self, db, repo):
        repo.log_event("trip.created", "Trip #42 was created")
        rows = db.conn.execute(
            "SELECT * FROM operation_events ORDER BY created_at DESC"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["event_type"] == "trip.created"

    def test_enforces_max_events(self, db, repo):
        repo.MAX_EVENTS = 3
        for i in range(5):
            repo.log_event("test.event", f"Event {i}")
        rows = db.conn.execute(
            "SELECT * FROM operation_events ORDER BY created_at DESC"
        ).fetchall()
        assert len(rows) <= 3

    def test_inserts_with_custom_id(self, db, repo):
        now = "2026-07-01T12:00:00"
        payload = json.dumps({"event": "custom", "description": "Manual event"})
        repo.log_event_with_details(
            event_id="custom-001",
            event_type="manual.entry",
            data_json=payload,
            created_at=now,
        )
        row = db.conn.execute(
            "SELECT * FROM operation_events WHERE id = ?", ("custom-001",)
        ).fetchone()
        assert row is not None
        assert row["event_type"] == "manual.entry"

    def test_stores_json_payload(self, db, repo):
        repo.log_event("invoice.sent", "Invoice INV-001 sent to client")
        row = db.conn.execute(
            "SELECT * FROM operation_events WHERE event_type = 'invoice.sent'"
        ).fetchone()
        payload = json.loads(row["data_json"])
        assert payload["event"] == "invoice.sent"
        assert payload["description"] == "Invoice INV-001 sent to client"


# ── Get events ───────────────────────────────────────────────────────


class TestGetEvents:
    def test_returns_all_events(self, db, repo):
        repo.log_event("event.a", "First")
        repo.log_event("event.b", "Second")
        results = repo.get_events()
        assert len(results) == 2

    def test_filters_by_prefix(self, db, repo):
        repo.log_event("invoice.created", "Invoice created")
        repo.log_event("invoice.paid", "Invoice paid")
        repo.log_event("trip.created", "Trip created")
        results = repo.get_events(event_type_prefix="invoice")
        assert len(results) == 2
        assert all("invoice" in r["event_type"] for r in results)


# ── Count ────────────────────────────────────────────────────────────


class TestGetEventCount:
    def test_counts_all(self, db, repo):
        repo.log_event("a.x", "A1")
        repo.log_event("a.y", "A2")
        repo.log_event("b.z", "B1")
        assert repo.get_event_count() == 3

    def test_counts_by_prefix(self, db, repo):
        repo.log_event("invoice.created", "Created")
        repo.log_event("invoice.paid", "Paid")
        repo.log_event("trip.started", "Started")
        assert repo.get_event_count(event_type_prefix="invoice") == 2
