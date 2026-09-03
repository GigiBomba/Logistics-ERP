"""Tests for ``workflow_struggle_job`` (§18, §34.9).

The job aggregates the §34.9 abandonment signal from ``copilot_audit_log``
— conversations that started a tool execution but never finished — per
active company, and writes a ``workflow_struggle`` insight when a workflow
crosses ``STRUGGLE_THRESHOLD``.

Data-source note: the UI ``StruggleDetector``
(``ui/copilot/controllers/struggle_detector.py:180-181``) emits
``struggle_detected(workflow_id, tooltip_key)`` and logs
"Struggle detected: screen=... workflow=..." client-side; it is not persisted
to a dedicated table.  The backend-recorded analogue this job reads is the
same ``copilot_audit_log`` abandonment signal the §34.9 observability panel
computes (started-but-never-finished conversations).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_tenant_context():
    """Reset the tenant context after each test — the job calls
    ``set_company_context`` which must not leak into other tests."""
    from database.tenant_context import clear_context
    yield
    clear_context()


@pytest.fixture
def db(tmp_path):
    """Temp-file SQLite DB with the copilot tables the job reads/writes.

    The job calls ``db.close()`` in its ``finally`` block, which resets the
    connection pool — so the DB must live on disk (a ``:memory:`` database
    would be destroyed by that close).  ``DatabaseManager`` creates the core
    ERP schema on construction; the ``copilot_*`` tables come from Alembic
    migrations and are created here explicitly (mirroring
    ``test_copilot_repository_cleanup.py``).
    """
    from database.db_manager import DatabaseManager

    d = DatabaseManager(str(tmp_path / "test.db"))
    for cid in (1, 2):
        d.conn.execute(
            "INSERT OR IGNORE INTO companies "
            "(id, company_name, subscription_tier, is_active) "
            "VALUES (?, ?, 'enterprise', 1)",
            (cid, f"Company-{cid}"),
        )
    d.conn.execute("""CREATE TABLE IF NOT EXISTS copilot_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id),
        user_id INTEGER,
        conversation_id TEXT,
        plan_id TEXT,
        step_id TEXT,
        tool_name TEXT,
        tool_version TEXT,
        parameters TEXT,
        permission_checked TEXT,
        permission_granted INTEGER,
        confidence_score REAL,
        confirmation_level INTEGER,
        status TEXT,
        result TEXT,
        error TEXT,
        model_used TEXT,
        provider_id TEXT,
        prompt_version TEXT,
        execution_time_ms INTEGER,
        started_at TEXT,
        finished_at TEXT,
        created_at TEXT,
        corrects_audit_id TEXT,
        action TEXT,
        entity_type TEXT,
        entity_id TEXT,
        old_value TEXT,
        new_value TEXT,
        performed_by TEXT
    )""")
    d.conn.execute("""CREATE TABLE IF NOT EXISTS copilot_insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        insight_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'low',
        status TEXT NOT NULL DEFAULT 'new',
        created_at TEXT,
        read_at TEXT,
        dismissed_at TEXT
    )""")
    # Unique index the insight repo dedup relies on (INSERT OR IGNORE).
    d.conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_copilot_insights_dedup "
        "ON copilot_insights(company_id, insight_type, payload)"
    )
    d.conn.commit()
    yield d
    d.close()


def _seed_audit(db, company_id: int, conversation_id: str, tool_name: str,
                status: str = "running", action: str | None = None,
                created_at: str | None = None) -> None:
    if created_at is None:
        # The job's window is `now - STRUGGLE_WINDOW_DAYS` (7 days).  A
        # hardcoded absolute timestamp silently falls out of the window once
        # the wall clock passes it (every positive assertion collapsed to
        # "0 insights created" on 2026-08-27 when the 2026-08-20 seed went
        # stale).  Seed relative to now so the rows are always in-window.
        created_at = (datetime.now() - timedelta(days=1)).isoformat()
    db.conn.execute(
        "INSERT INTO copilot_audit_log "
        "(company_id, conversation_id, tool_name, status, action, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (company_id, conversation_id, tool_name, status, action, created_at),
    )
    db.conn.commit()


def _insights(db, company_id: int | None = None):
    if company_id is None:
        rows = db.rows_to_dicts(
            db.conn.execute("SELECT * FROM copilot_insights").fetchall()
        )
    else:
        rows = db.rows_to_dicts(
            db.conn.execute(
                "SELECT * FROM copilot_insights WHERE company_id = ?",
                (company_id,),
            ).fetchall()
        )
    for r in rows:
        if isinstance(r.get("payload"), str):
            r["payload"] = json.loads(r["payload"])
    return rows


def _run_job(db):
    """Run ``workflow_struggle_job`` against a provided in-memory DB."""
    from backend.celery_app.tasks.insight_tasks import workflow_struggle_job

    with (
        patch("backend.db.DatabaseManager", return_value=db),
        patch(
            "repositories.company_repository.CompanyRepository.get_active_ids",
            return_value=[1, 2],
        ),
    ):
        return workflow_struggle_job()


class TestWorkflowStruggleJobContract:
    """Signature and importability contract — mirrors the other insight jobs."""

    def test_job_importable(self):
        from backend.celery_app.tasks.insight_tasks import workflow_struggle_job
        assert workflow_struggle_job is not None

    def test_job_has_celery_decorator(self):
        from backend.celery_app.tasks.insight_tasks import workflow_struggle_job
        assert hasattr(workflow_struggle_job, "delay")
        assert callable(workflow_struggle_job.delay)

    def test_job_returns_insights_created(self):
        """Job returns the standard ``{insights_created: int}`` shape."""
        from backend.celery_app.tasks.insight_tasks import workflow_struggle_job

        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchall.return_value = []

        with (
            patch("backend.db.DatabaseManager", return_value=mock_db),
            patch(
                "repositories.company_repository.CompanyRepository.get_active_ids",
                return_value=[42],
            ),
        ):
            result = workflow_struggle_job()
        assert isinstance(result, dict)
        assert "insights_created" in result
        assert isinstance(result["insights_created"], int)


class TestWorkflowStruggleDetection:
    """Real in-memory DB: aggregation of abandoned conversations."""

    def test_creates_insight_when_threshold_crossed(self, db):
        """3 abandoned conversations for the same tool → 1 insight (count 3)."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_THRESHOLD

        for i in range(STRUGGLE_THRESHOLD):
            _seed_audit(db, 1, f"conv-abandon-{i}", "maintenance.schedule")

        result = _run_job(db)
        assert result["insights_created"] == 1

        rows = _insights(db, company_id=1)
        assert len(rows) == 1
        assert rows[0]["insight_type"] == "workflow_struggle"
        assert rows[0]["severity"] == "medium"
        assert rows[0]["payload"]["workflow_id"] == "maintenance.schedule"
        assert rows[0]["payload"]["tool_name"] == "maintenance.schedule"
        assert rows[0]["payload"]["abandoned_count"] == STRUGGLE_THRESHOLD
        assert rows[0]["payload"]["window_days"] == 7

    def test_high_severity_above_high_threshold(self, db):
        """≥ STRUGGLE_HIGH_THRESHOLD abandoned conversations → severity high."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_HIGH_THRESHOLD

        for i in range(STRUGGLE_HIGH_THRESHOLD):
            _seed_audit(db, 1, f"conv-hi-{i}", "dispatch.create")

        result = _run_job(db)
        assert result["insights_created"] == 1
        rows = _insights(db, company_id=1)
        assert rows[0]["severity"] == "high"
        assert rows[0]["payload"]["abandoned_count"] == STRUGGLE_HIGH_THRESHOLD

    def test_below_threshold_creates_no_insight(self, db):
        """1–2 abandoned conversations must not cross the threshold."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_THRESHOLD

        for i in range(STRUGGLE_THRESHOLD - 1):
            _seed_audit(db, 1, f"conv-low-{i}", "invoice.draft")

        result = _run_job(db)
        assert result["insights_created"] == 0
        assert _insights(db) == []

    def test_completed_conversations_not_counted(self, db):
        """A started-then-finished conversation is NOT abandoned."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_THRESHOLD

        for i in range(STRUGGLE_THRESHOLD):
            _seed_audit(db, 1, f"conv-finished-{i}", "route.calculate",
                        status="succeeded")

        result = _run_job(db)
        assert result["insights_created"] == 0

    def test_mixed_abandoned_and_finished_counts_only_abandoned(self, db):
        """2 abandoned + 1 finished for the same tool → count is 2 (no insight)."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_THRESHOLD

        _seed_audit(db, 1, "conv-mix-ab-1", "driver.check_hours")
        _seed_audit(db, 1, "conv-mix-ab-2", "driver.check_hours")
        _seed_audit(db, 1, "conv-mix-ok", "driver.check_hours",
                    status="succeeded")

        result = _run_job(db)
        assert result["insights_created"] == 0

        # Bump past the threshold with a third abandoned one.
        _seed_audit(db, 1, "conv-mix-ab-3", "driver.check_hours")
        result = _run_job(db)
        assert result["insights_created"] == 1
        rows = _insights(db, company_id=1)
        assert rows[0]["payload"]["abandoned_count"] == 3

    def test_action_column_schema_also_detected(self, db):
        """Rows written with ``action='tool_execution_start'`` (Postgres/
        Alembic schema) are detected as abandoned too."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_THRESHOLD

        for i in range(STRUGGLE_THRESHOLD):
            _seed_audit(db, 1, f"conv-action-{i}", "document.search",
                        status=None, action="tool_execution_start")

        result = _run_job(db)
        assert result["insights_created"] == 1

    def test_tenant_isolation(self, db):
        """A company's pass only writes insights for that company."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_THRESHOLD

        for i in range(STRUGGLE_THRESHOLD):
            _seed_audit(db, 1, f"conv-a-{i}", "vehicle.search")
        for i in range(STRUGGLE_THRESHOLD):
            _seed_audit(db, 2, f"conv-b-{i}", "vehicle.search")

        result = _run_job(db)
        assert result["insights_created"] == 2

        rows_a = _insights(db, company_id=1)
        rows_b = _insights(db, company_id=2)
        assert len(rows_a) == 1
        assert len(rows_b) == 1
        assert all(r["company_id"] == 1 for r in rows_a)
        assert all(r["company_id"] == 2 for r in rows_b)

    def test_job_is_idempotent_for_unchanged_signal(self, db):
        """Re-running with the same signal must not duplicate insight rows."""
        from backend.celery_app.tasks.insight_tasks import STRUGGLE_THRESHOLD

        for i in range(STRUGGLE_THRESHOLD):
            _seed_audit(db, 1, f"conv-dup-{i}", "trip.calculate_profitability")

        _run_job(db)
        _run_job(db)

        rows = _insights(db, company_id=1)
        assert len(rows) == 1, "unique (company_id, insight_type, payload) must dedup"


class TestWorkflowStruggleScheduling:
    """The job is registered in the Celery beat schedule (§18)."""

    def test_schedule_registers_workflow_struggle_job(self):
        from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE

        entry = CELERY_BEAT_SCHEDULE.get("workflow-struggle-daily")
        assert entry is not None, "workflow-struggle-daily missing from beat schedule"
        assert entry["task"] == (
            "backend.celery_app.tasks.insight_tasks.workflow_struggle_job"
        )