"""Tests for Celery maintenance tasks — data retention cleanup.

Uses CELERY_ALWAYS_EAGER=True so tasks run synchronously in the test process.
Environment variables are set BEFORE any celery import to avoid real Redis.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

# Force eager mode and memory backend BEFORE any celery imports
os.environ.setdefault("CELERY_ALWAYS_EAGER", "true")
os.environ.setdefault("CELERY_EAGER_PROPAGATES_EXCEPTIONS", "true")
os.environ.setdefault("OPERION_CELERY_BROKER", "memory://")
os.environ.setdefault("OPERION_CELERY_RESULT", "cache+memory://")
os.environ.setdefault("OPERION_REDIS_URL", "memory://")

from backend.celery_app.tasks.maintenance_tasks import cleanup_expired_data


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def _mock_backend_settings():
    """Mock BackendSettings (at its real location) to avoid reading .env.

    Patches ``backend.config.BackendSettings`` because the task imports
    ``BackendSettings`` lazily via ``from backend.config import BackendSettings``
    inside the function body — so we intercept at the source.
    """
    with patch("backend.config.BackendSettings") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.db_path = ":memory:"
        mock_cls.return_value = mock_instance
        yield mock_cls, mock_instance


@pytest.fixture
def _mock_db():
    """Mock DatabaseManager (at its real location) to avoid real I/O.

    Patches ``backend.db.DatabaseManager`` (which re-exports
    ``database.db_manager.DatabaseManager``) because the task imports it
    lazily inside the function body.  Also stubs the per-company iteration
    (``CompanyRepository.get_active_ids``) to a single active company so the
    task's tenant-scoped delete loop runs.
    """
    from database.tenant_context import clear_context

    with (
        patch("backend.db.DatabaseManager") as mock_cls,
        patch(
            "repositories.company_repository.CompanyRepository.get_active_ids",
            return_value=[1],
        ),
    ):
        mock_instance = MagicMock()
        mock_instance.conn = MagicMock()
        mock_instance.conn.execute.return_value.rowcount = 10
        mock_cls.return_value = mock_instance
        try:
            yield mock_cls, mock_instance
        finally:
            # The task sets the tenant context (set_company_context); clear it
            # so it does not leak into unrelated tests in the same process.
            clear_context()


# ── cleanup_expired_data ─────────────────────────────────────────────────────


class TestCleanupExpiredData:
    """Tests for the cleanup_expired_data Celery task — happy path, edge cases,
    error propagation, and resource cleanup."""

    # ── Happy path ───────────────────────────────────────────────────────

    def test_successful_cleanup_returns_deleted_count(
        self, _mock_backend_settings, _mock_db
    ):
        """Happy path: task deletes GPS records and returns the count."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 42

        result = cleanup_expired_data()

        assert result == {"gps_records_deleted": 42}
        mock_db.conn.execute.assert_called_once()
        mock_db.conn.commit.assert_called_once()

    def test_calls_database_manager_with_config_db_path(
        self, _mock_backend_settings, _mock_db
    ):
        """Task passes BackendSettings().db_path to DatabaseManager."""
        _mock_settings_cls, mock_settings_instance = _mock_backend_settings
        _mock_db_cls, mock_db = _mock_db

        mock_settings_instance.db_path = "data/test_retention.db"

        cleanup_expired_data()

        _mock_db_cls.assert_called_once_with("data/test_retention.db")

    def test_instantiates_backend_settings(
        self, _mock_backend_settings, _mock_db
    ):
        """Task creates a BackendSettings instance."""
        _mock_settings_cls, mock_settings_instance = _mock_backend_settings
        _mock_db_cls, mock_db = _mock_db

        cleanup_expired_data()

        _mock_settings_cls.assert_called_once()

    def test_executes_correct_delete_sql(self, _mock_backend_settings, _mock_db):
        """The SQL deletes from gps_telemetry with recorded_at < cutoff."""
        _mock_db_cls, mock_db = _mock_db

        cleanup_expired_data()

        call_args = mock_db.conn.execute.call_args[0]
        sql = call_args[0]
        assert sql.strip().startswith("DELETE FROM gps_telemetry")
        assert "recorded_at < ?" in sql

    def test_cutoff_is_approximately_90_days_ago(
        self, _mock_backend_settings, _mock_db
    ):
        """The cutoff parameter passed to SQL is ~90 days in the past."""
        _mock_db_cls, mock_db = _mock_db

        cleanup_expired_data()

        call_args = mock_db.conn.execute.call_args[0]
        cutoff_str = call_args[1][0]
        cutoff_dt = datetime.fromisoformat(cutoff_str)
        expected = datetime.now() - timedelta(days=90)
        diff_seconds = abs((cutoff_dt - expected).total_seconds())
        assert diff_seconds < 5, (
            f"Cutoff {cutoff_str} differs from expected by {diff_seconds:.1f}s"
        )

    def test_cutoff_isoformat_with_time(
        self, _mock_backend_settings, _mock_db
    ):
        """The cutoff is an ISO-formatted datetime string (includes time)."""
        _mock_db_cls, mock_db = _mock_db

        cleanup_expired_data()

        call_args = mock_db.conn.execute.call_args[0]
        cutoff_str = call_args[1][0]
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", cutoff_str
        ), f"Expected ISO datetime, got: {cutoff_str}"

    # ── Zero records ────────────────────────────────────────────────────

    def test_no_records_to_delete_returns_zero(
        self, _mock_backend_settings, _mock_db
    ):
        """Edge case: no GPS records match the retention cutoff."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 0

        result = cleanup_expired_data()

        assert result == {"gps_records_deleted": 0}
        mock_db.conn.execute.assert_called_once()
        mock_db.conn.commit.assert_called_once()

    # ── Error propagation ───────────────────────────────────────────────

    def test_exception_on_db_execute_propagates(
        self, _mock_backend_settings, _mock_db
    ):
        """Task does not catch DB execute exceptions — they propagate to Celery."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            cleanup_expired_data()

    def test_exception_on_db_commit_propagates(
        self, _mock_backend_settings, _mock_db
    ):
        """Task does not catch DB commit exceptions — they propagate to Celery."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 5
        mock_db.conn.commit.side_effect = RuntimeError("Commit failed")

        with pytest.raises(RuntimeError, match="Commit failed"):
            cleanup_expired_data()

    def test_exception_on_settings_construction_propagates(
        self, _mock_db
    ):
        """If BackendSettings() fails the exception propagates."""
        with patch(
            "backend.config.BackendSettings",
            side_effect=RuntimeError("Config load failed"),
        ):
            with pytest.raises(RuntimeError, match="Config load failed"):
                cleanup_expired_data()

    def test_exception_on_db_construction_propagates(
        self, _mock_backend_settings
    ):
        """If DatabaseManager() fails the exception propagates."""
        with patch(
            "backend.db.DatabaseManager",
            side_effect=RuntimeError("Cannot open database"),
        ):
            with pytest.raises(RuntimeError, match="Cannot open database"):
                cleanup_expired_data()

    # ── Resource cleanup (finally block) ────────────────────────────────

    def test_db_is_closed_after_success(
        self, _mock_backend_settings, _mock_db
    ):
        """Database connection is closed in the finally block on success."""
        _mock_db_cls, mock_db = _mock_db

        cleanup_expired_data()

        mock_db.close.assert_called_once()

    def test_db_is_closed_after_exception(
        self, _mock_backend_settings, _mock_db
    ):
        """Database connection is closed in the finally block even on error."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.side_effect = RuntimeError("Kaboom")

        with pytest.raises(RuntimeError):
            cleanup_expired_data()

        mock_db.close.assert_called_once()

    def test_db_is_closed_after_commit_exception(
        self, _mock_backend_settings, _mock_db
    ):
        """Database connection is closed when commit fails."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 5
        mock_db.conn.commit.side_effect = RuntimeError("Commit failed")

        with pytest.raises(RuntimeError):
            cleanup_expired_data()

        mock_db.close.assert_called_once()

    # ── Logging behaviour ───────────────────────────────────────────────

    def test_logs_info_when_records_deleted(
        self, _mock_backend_settings, _mock_db, caplog
    ):
        """Task logs an info message when records are deleted."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 7
        caplog.set_level(logging.INFO)

        cleanup_expired_data()

        assert any(
            "deleted 7 GPS records older than 90 days" in msg
            for msg in caplog.messages
        )

    def test_does_not_log_when_no_records(
        self, _mock_backend_settings, _mock_db, caplog
    ):
        """Task does not log the info message when zero records are deleted."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 0
        caplog.set_level(logging.INFO)

        cleanup_expired_data()

        assert not any(
            "GPS records" in msg for msg in caplog.messages
        )

    # ── Multiple invocations ────────────────────────────────────────────

    def test_can_be_called_multiple_times(
        self, _mock_backend_settings, _mock_db
    ):
        """Task is stateless and can be invoked repeatedly."""
        _mock_db_cls, mock_db = _mock_db

        mock_db.conn.execute.return_value.rowcount = 3
        r1 = cleanup_expired_data()
        assert r1 == {"gps_records_deleted": 3}

        mock_db.conn.execute.return_value.rowcount = 0
        r2 = cleanup_expired_data()
        assert r2 == {"gps_records_deleted": 0}

        mock_db.conn.execute.return_value.rowcount = 15
        r3 = cleanup_expired_data()
        assert r3 == {"gps_records_deleted": 15}

    # ── Per-company tenant scoping (blocker 5) ──────────────────────────

    def test_deletes_per_active_company(
        self, _mock_backend_settings, _mock_db
    ):
        """The task loops over active companies, scoping each delete."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 4

        with patch(
            "repositories.company_repository.CompanyRepository.get_active_ids",
            return_value=[1, 2, 3],
        ):
            result = cleanup_expired_data()

        assert result == {"gps_records_deleted": 12}
        # One DELETE per active company, each scoped by company_id.
        sqls = [call.args[0] for call in mock_db.conn.execute.call_args_list]
        assert len(sqls) == 3
        for sql in sqls:
            assert "company_id = ?" in sql
        params = [call.args[1] for call in mock_db.conn.execute.call_args_list]
        assert [p[-1] for p in params] == [1, 2, 3]

    def test_skips_admin_scope_company_zero(
        self, _mock_backend_settings, _mock_db
    ):
        """company_id 0 (admin/global scope) is never deleted."""
        _mock_db_cls, mock_db = _mock_db
        mock_db.conn.execute.return_value.rowcount = 2

        with patch(
            "repositories.company_repository.CompanyRepository.get_active_ids",
            return_value=[0, 1],
        ):
            result = cleanup_expired_data()

        assert result == {"gps_records_deleted": 2}
        sqls = [call.args[0] for call in mock_db.conn.execute.call_args_list]
        assert len(sqls) == 1, "id 0 must be skipped"
        assert "company_id = ?" in sqls[0]
        assert mock_db.conn.execute.call_args_list[0].args[1][-1] == 1


class TestCleanupExpiredDataRegistration:
    """Verifies the task is correctly registered in the Celery app,
    has the expected signature, and appears in the beat schedule."""

    def test_task_name_matches_expected(self):
        """Task name includes the full module path."""
        expected = (
            "backend.celery_app.tasks.maintenance_tasks.cleanup_expired_data"
        )
        assert cleanup_expired_data.name == expected

    def test_task_registered_in_celery_app(self):
        """Task is registered in the Celery app's task registry."""
        from backend.celery_app.celery import celery_app

        assert cleanup_expired_data.name in celery_app.tasks

    def test_task_signature_no_bind_no_args(self):
        """Task is not a bind task and accepts no arguments."""
        import inspect

        sig = inspect.signature(cleanup_expired_data)
        params = list(sig.parameters.keys())
        assert "self" not in params
        assert params == [], f"Expected no parameters, got: {params}"

    def test_task_is_callable_directly(self):
        """Task can be called as a plain function (no Celery worker needed)."""
        # We can't test actual execution without mocks here, but the
        # function object itself is callable.
        assert callable(cleanup_expired_data)

    def test_task_type_is_task(self):
        """The decorated object is a Celery Task instance."""
        from celery import Task

        assert isinstance(cleanup_expired_data, Task)

    # ── Beat schedule ───────────────────────────────────────────────────

    def test_beat_schedule_entry_exists(self):
        """The task appears in the Celery beat schedule."""
        from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE

        assert "cleanup-expired-data" in CELERY_BEAT_SCHEDULE

    def test_beat_schedule_references_correct_task(self):
        """Beat schedule entry points to the exact task name."""
        from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE

        entry = CELERY_BEAT_SCHEDULE["cleanup-expired-data"]
        assert entry["task"] == cleanup_expired_data.name

    def test_beat_schedule_schedule_type(self):
        """Schedule uses a crontab instance (runs daily at 3 AM)."""
        from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE
        from celery.schedules import crontab

        entry = CELERY_BEAT_SCHEDULE["cleanup-expired-data"]
        assert isinstance(entry["schedule"], crontab)

    def test_beat_schedule_has_task_key(self):
        """Each schedule entry has the required 'task' key."""
        from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE

        entry = CELERY_BEAT_SCHEDULE["cleanup-expired-data"]
        assert "task" in entry
        assert isinstance(entry["task"], str)


class TestCleanupExpiredDataIntegration:
    """Minimal integration checks — ensuring the task module loads
    cleanly and the task can be resolved by name."""

    def test_module_imports_without_error(self):
        """The maintenance_tasks module imports cleanly."""
        import importlib

        mod = importlib.import_module(
            "backend.celery_app.tasks.maintenance_tasks"
        )
        assert hasattr(mod, "cleanup_expired_data")

    def test_task_resolvable_by_name(self):
        """Celery can resolve the task from its registered name."""
        from backend.celery_app.celery import celery_app

        resolved = celery_app.tasks[cleanup_expired_data.name]
        # Celery may return a different proxy object, so compare names
        assert resolved.name == cleanup_expired_data.name

    def test_beat_schedule_entries_match_registered_tasks(self):
        """All maintenance beat-schedule entries reference tasks that
        actually exist in the Celery app registry."""
        from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE

        maintenance_keys = {
            k for k in CELERY_BEAT_SCHEDULE if "cleanup" in k
        }
        assert maintenance_keys, "No maintenance entries found in schedule"

        for key in maintenance_keys:
            entry = CELERY_BEAT_SCHEDULE[key]
            task_path = entry["task"]
            # The task should be resolvable (i.e., the module is importable
            # and the attribute exists)
            module_path, _, task_name = task_path.rpartition(".")
            import importlib

            mod = importlib.import_module(module_path)
            assert hasattr(mod, task_name), (
                f"Beat schedule references {task_path} but "
                f"{module_path} has no attribute {task_name}"
            )
