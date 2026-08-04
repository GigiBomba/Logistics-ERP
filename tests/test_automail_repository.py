"""Tests for repositories.automail_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from repositories.automail_repository import AutoMailRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> AutoMailRepository:
    return AutoMailRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _template(db: InMemoryDB, **kw: Any) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    t: Dict[str, Any] = dict(
        name="Test Template",
        subject="Hello {{name}}",
        body_text="Dear {{name}},",
        body_html="",
        variables_json="[]",
        is_default=0,
        created_at=now,
        updated_at=now,
    )
    t.update(kw)
    cols = ", ".join(t.keys())
    vals = ", ".join("?" for _ in t)
    db.conn.execute(f"INSERT INTO automail_templates ({cols}) VALUES ({vals})", list(t.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _schedule(db: InMemoryDB, **kw: Any) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    s: Dict[str, Any] = dict(
        name="Test Schedule",
        trigger_type="before_due",
        days_offset=5,
        template_id=1,
        is_active=1,
        sort_order=0,
        attach_invoice=1,
        attach_cmr=1,
        attach_all_docs=0,
        created_at=now,
        updated_at=now,
    )
    s.update(kw)
    cols = ", ".join(s.keys())
    vals = ", ".join("?" for _ in s)
    db.conn.execute(f"INSERT INTO automail_schedules ({cols}) VALUES ({vals})", list(s.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _email_log(db: InMemoryDB, **kw: Any) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    e: Dict[str, Any] = dict(
        trip_id=None,
        recipient="test@example.com",
        subject="Test Subject",
        timestamp=now,
        status="sent",
    )
    e.update(kw)
    cols = ", ".join(e.keys())
    vals = ", ".join("?" for _ in e)
    db.conn.execute(f"INSERT INTO email_logs ({cols}) VALUES ({vals})", list(e.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Override upsert ──────────────────────────────────────────────────


class TestUpsertOverride:
    def test_upsert_override_insert(self, db, repo):
        repo.upsert_override(
            client_id=100,
            data={"is_disabled": 1, "custom_days_offset": 3, "notes": "new override"},
        )
        row = db.conn.execute(
            "SELECT * FROM automail_client_overrides WHERE client_id = 100"
        ).fetchone()
        assert row is not None
        assert row["client_id"] == 100
        assert row["is_disabled"] == 1
        assert row["custom_days_offset"] == 3

    def test_upsert_override_update(self, db, repo):
        repo.upsert_override(
            client_id=101,
            data={"is_disabled": 1, "notes": "original"},
        )
        repo.upsert_override(
            client_id=101,
            data={"is_disabled": 0, "notes": "updated"},
        )
        rows = db.conn.execute(
            "SELECT * FROM automail_client_overrides WHERE client_id = 101"
        ).fetchall()
        assert len(rows) == 1  # no duplicate row
        assert rows[0]["is_disabled"] == 0
        assert rows[0]["notes"] == "updated"

    def test_upsert_override_rejects_invalid_column(self, repo):
        with pytest.raises(ValueError, match="Invalid column"):
            repo.upsert_override(
                client_id=200,
                data={"nonexistent_column": "boom"},
            )


# ── Reorder schedules ────────────────────────────────────────────────


class TestReorderSchedules:
    def test_reorder_schedules_updates_sort_order(self, db, repo):
        tmpl_id = _template(db)
        id1 = _schedule(db, template_id=tmpl_id, sort_order=0)
        id2 = _schedule(db, template_id=tmpl_id, sort_order=1)
        id3 = _schedule(db, template_id=tmpl_id, sort_order=2)

        repo.reorder_schedules([id3, id1, id2])

        rows = db.conn.execute(
            "SELECT id, sort_order FROM automail_schedules ORDER BY id"
        ).fetchall()
        lookup = {r["id"]: r["sort_order"] for r in rows}
        assert lookup[id3] == 0
        assert lookup[id1] == 1
        assert lookup[id2] == 2

    def test_reorder_schedules_empty_list_noop(self, repo):
        repo.reorder_schedules([])  # should not raise


# ── Create schedule ──────────────────────────────────────────────────


class TestCreateSchedule:
    def test_create_schedule_auto_sort_order(self, db, repo):
        # Clear seeded schedules so sort_order starts from 0
        db.conn.execute("DELETE FROM automail_schedules")
        db.conn.commit()
        tmpl_id = _template(db)
        sid1 = repo.create_schedule({
            "name": "Sched A",
            "trigger_type": "before_due",
            "days_offset": 5,
            "template_id": tmpl_id,
        })
        row1 = db.conn.execute(
            "SELECT sort_order FROM automail_schedules WHERE id = ?", (sid1,)
        ).fetchone()
        assert row1["sort_order"] == 0  # first schedule gets 0

        sid2 = repo.create_schedule({
            "name": "Sched B",
            "trigger_type": "after_due",
            "days_offset": 1,
            "template_id": tmpl_id,
        })
        row2 = db.conn.execute(
            "SELECT sort_order FROM automail_schedules WHERE id = ?", (sid2,)
        ).fetchone()
        assert row2["sort_order"] == 1  # second gets 1

    def test_create_schedule_explicit_sort_order(self, db, repo):
        tmpl_id = _template(db)
        sid = repo.create_schedule({
            "name": "Sched C",
            "trigger_type": "before_due",
            "days_offset": 3,
            "template_id": tmpl_id,
            "sort_order": 42,
        })
        row = db.conn.execute(
            "SELECT sort_order FROM automail_schedules WHERE id = ?", (sid,)
        ).fetchone()
        assert row["sort_order"] == 42


# ── Email history ────────────────────────────────────────────────────


class TestGetEmailHistory:
    def test_get_email_history_basic(self, db, repo):
        e1 = _email_log(db, recipient="a@test.com", subject="Alpha")
        e2 = _email_log(db, recipient="b@test.com", subject="Beta")
        rows, total = repo.get_email_history()
        assert total == 2
        ids = {r["id"] for r in rows}
        assert ids == {e1, e2}

    def test_get_email_history_pagination(self, db, repo):
        ids = []
        for i in range(5):
            ids.append(
                _email_log(db, recipient=f"u{i}@test.com", subject=f"Email {i}")
            )
        page1, total = repo.get_email_history(page=0, page_size=2)
        assert total == 5
        assert len(page1) == 2

        page2, _ = repo.get_email_history(page=1, page_size=2)
        assert len(page2) == 2
        # Ensure pages are different
        p1_ids = {r["id"] for r in page1}
        p2_ids = {r["id"] for r in page2}
        assert p1_ids.isdisjoint(p2_ids)

    def test_get_email_history_search_filter(self, db, repo):
        _email_log(db, recipient="alice@test.com", subject="Invoice January")
        _email_log(db, recipient="bob@test.com", subject="Reminder March")
        rows, total = repo.get_email_history(search="January")
        assert total == 1
        assert rows[0]["subject"] == "Invoice January"

        rows2, total2 = repo.get_email_history(search="nonexistent")
        assert total2 == 0

    def test_get_email_history_status_filter(self, db, repo):
        _email_log(db, status="sent")
        _email_log(db, status="failed")
        rows, total = repo.get_email_history(status_filter="failed")
        assert total == 1
        assert rows[0]["status"] == "failed"


# ── Log email ────────────────────────────────────────────────────────


class TestLogEmail:
    def test_log_email_creates_row(self, db, repo):
        repo.log_email(
            trip_id=None,
            recipient="user@example.com",
            subject="Welcome",
            status="sent",
        )
        row = db.conn.execute(
            "SELECT * FROM email_logs WHERE recipient = ?",
            ("user@example.com",),
        ).fetchone()
        assert row is not None
        assert row["subject"] == "Welcome"
        assert row["status"] == "sent"
