"""Tenant-scoped cleanup + insight dedup tests for copilot repositories.

Blocker 5: ``delete_older_than`` must accept an explicit ``company_id`` and
scope the DELETE so foreign-company rows survive.
Blocker 6: ``CopilotInsightRepository.create`` must be idempotent against the
``idx_copilot_insights_dedup`` unique index (double insert → 1 row).
"""

from __future__ import annotations

import json

import pytest

from tests.test_helpers import InMemoryDB


@pytest.fixture
def db():
    from database.tenant_context import clear_context

    d = InMemoryDB()
    d.conn.execute("""CREATE TABLE IF NOT EXISTS copilot_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT,
        action TEXT,
        entity_type TEXT,
        entity_id TEXT,
        old_value TEXT,
        new_value TEXT,
        performed_by TEXT,
        company_id INTEGER,
        created_at TEXT
    )""")
    d.conn.execute("""CREATE TABLE IF NOT EXISTS conversation_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT,
        summary TEXT,
        model TEXT,
        token_count INTEGER,
        company_id INTEGER,
        created_at TEXT
    )""")
    d.conn.execute("""CREATE TABLE IF NOT EXISTS copilot_reasoning_graphs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT,
        graph_json TEXT,
        company_id INTEGER,
        created_at TEXT
    )""")
    d.conn.execute("""CREATE TABLE IF NOT EXISTS copilot_insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        insight_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'low',
        status TEXT NOT NULL DEFAULT 'new',
        created_at TEXT
    )""")
    d.conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_copilot_insights_dedup "
        "ON copilot_insights(company_id, insight_type, payload)"
    )
    d.conn.commit()
    yield d
    clear_context()
    d.close()


def _insert_audit(db, company_id: int, created_at: str) -> None:
    db.conn.execute(
        "INSERT INTO copilot_audit_log (conversation_id, action, company_id, created_at) "
        "VALUES (?, 'test', ?, ?)",
        (f"conv-{company_id}-{created_at}", company_id, created_at),
    )
    db.conn.commit()


class TestCopilotDeleteOlderThanScoping:
    def test_deletes_only_requested_company(self, db):
        """company-scoped delete must leave foreign-company rows untouched."""
        from repositories.copilot_repository import CopilotAuditRepository

        _insert_audit(db, 1, "2020-01-01T00:00:00")
        _insert_audit(db, 2, "2020-01-01T00:00:00")

        deleted = CopilotAuditRepository(db).delete_older_than(
            "2021-01-01T00:00:00", company_id=1
        )

        assert deleted == 1
        remaining = db.rows_to_dicts(
            db.conn.execute("SELECT company_id FROM copilot_audit_log").fetchall()
        )
        assert [r["company_id"] for r in remaining] == [2]

    def test_default_none_keeps_context_behaviour(self, db):
        """company_id=None keeps the old context-based behaviour (delete all)."""
        from database.tenant_context import clear_context
        from repositories.copilot_repository import CopilotAuditRepository

        clear_context()
        _insert_audit(db, 1, "2020-01-01T00:00:00")
        _insert_audit(db, 2, "2020-01-01T00:00:00")

        deleted = CopilotAuditRepository(db).delete_older_than("2021-01-01T00:00:00")

        assert deleted == 2

    def test_delete_older_than_scoped_all_four_repos(self, db):
        """Every copilot repo's delete_older_than honours company_id."""
        from repositories.copilot_repository import (
            ConversationSummaryRepository,
            CopilotInsightRepository,
            CopilotReasoningGraphRepository,
        )

        _insert_audit(db, 1, "2020-01-01T00:00:00")
        _insert_audit(db, 2, "2020-01-01T00:00:00")

        for created in ("2020-01-01T00:00:00",):
            db.conn.execute(
                "INSERT INTO conversation_summary (conversation_id, summary, company_id, created_at) "
                "VALUES (?, 's', ?, ?)",
                (f"cs-{created}", 1, created),
            )
        db.conn.execute(
            "INSERT INTO copilot_insights (company_id, insight_type, payload, created_at) "
            "VALUES (1, 'test', '{}', '2020-01-01T00:00:00')"
        )
        db.conn.execute(
            "INSERT INTO copilot_reasoning_graphs (conversation_id, graph_json, company_id, created_at) "
            "VALUES ('rg-1', '{}', 1, '2020-01-01T00:00:00')"
        )
        db.conn.commit()

        assert ConversationSummaryRepository(db).delete_older_than(
            "2021-01-01T00:00:00", company_id=1
        ) == 1
        assert CopilotInsightRepository(db).delete_older_than(
            "2021-01-01T00:00:00", company_id=1
        ) == 1
        assert CopilotReasoningGraphRepository(db).delete_older_than(
            "2021-01-01T00:00:00", company_id=1
        ) == 1


class TestCopilotInsightDedup:
    def test_double_insert_yields_one_row(self, db):
        """Retry after partial progress must not duplicate an insight."""
        from repositories.copilot_repository import CopilotInsightRepository

        repo = CopilotInsightRepository(db)
        payload = json.dumps({"truck_id": 7, "maint_type": "oil"})
        first = repo.create({
            "company_id": 1,
            "insight_type": "maintenance_forecast",
            "severity": "medium",
            "payload": payload,
        })
        second = repo.create({
            "company_id": 1,
            "insight_type": "maintenance_forecast",
            "severity": "medium",
            "payload": payload,
        })

        rows = db.rows_to_dicts(
            db.conn.execute("SELECT * FROM copilot_insights").fetchall()
        )
        assert len(rows) == 1, "unique index must suppress the duplicate"

    def test_distinct_payloads_both_kept(self, db):
        """Legitimate distinct insights (different payload) are not suppressed."""
        from repositories.copilot_repository import CopilotInsightRepository

        repo = CopilotInsightRepository(db)
        repo.create({
            "company_id": 1,
            "insight_type": "maintenance_forecast",
            "severity": "medium",
            "payload": json.dumps({"truck_id": 7}),
        })
        repo.create({
            "company_id": 1,
            "insight_type": "maintenance_forecast",
            "severity": "medium",
            "payload": json.dumps({"truck_id": 8}),
        })

        rows = db.rows_to_dicts(
            db.conn.execute("SELECT * FROM copilot_insights").fetchall()
        )
        assert len(rows) == 2
