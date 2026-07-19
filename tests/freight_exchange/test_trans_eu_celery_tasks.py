"""Tests for Trans.eu Celery tasks — token refresh, freight sync, webhook retry, health, cleanup.

Covers: all 5 tasks from backend/celery_app/tasks/trans_eu_tasks.py.
Uses InMemoryDB for database interaction. Tasks are called directly
(not via Celery worker) to test business logic.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import json
import pytest
from tests.test_helpers import InMemoryDB


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def freight_tables(db):
    """Create minimal versions of Trans.eu tables for Celery task testing."""
    db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_user_tokens (
        id TEXT PRIMARY KEY, company_id INTEGER, user_id INTEGER,
        access_token_encrypted TEXT, refresh_token_encrypted TEXT,
        scope TEXT, expires_at TEXT, api_key_encrypted TEXT,
        client_id TEXT, client_secret_encrypted TEXT,
        status TEXT, last_refreshed_at TEXT
    )""")
    db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_freight_offers (
        id TEXT PRIMARY KEY, company_id INTEGER, user_id INTEGER,
        trans_eu_freight_id INTEGER, status TEXT, origin TEXT,
        destination TEXT, operion_trip_id INTEGER,
        updated_at TEXT
    )""")
    db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_webhook_events (
        id TEXT PRIMARY KEY, company_id INTEGER,
        trans_eu_event_id TEXT UNIQUE, event_name TEXT,
        occurred_at TEXT, payload TEXT, status TEXT,
        created_at TEXT
    )""")
    db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_webhook_events_failed (
        id TEXT PRIMARY KEY, company_id INTEGER,
        trans_eu_event_id TEXT, event_name TEXT,
        payload TEXT, error_message TEXT, error_type TEXT,
        attempt_count INTEGER DEFAULT 0, max_attempts INTEGER DEFAULT 10,
        next_retry_at TEXT, status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    db.conn.commit()
    yield
    for t in ["trans_eu_user_tokens","trans_eu_freight_offers","trans_eu_webhook_events","trans_eu_webhook_events_failed"]:
        db.conn.execute(f"DROP TABLE IF EXISTS {t}")
    db.conn.commit()


class TestRefreshTokensTask:
    def test_no_expiring_tokens_returns_zero(self, db, freight_tables):
        """No tokens near expiry — nothing to refresh."""
        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_refresh_tokens
        with patch("backend.celery_app.tasks.trans_eu_tasks.DatabaseManager") as MockDB:
            MockDB.return_value = db
            result = trans_eu_refresh_tokens()
            assert result["refreshed"] == 0
            assert result["failed"] == 0

    def test_expiring_token_is_refreshed(self, db, freight_tables):
        """Token expiring within 1 hour triggers refresh."""
        now = datetime.now(timezone.utc)
        expires_soon = datetime.fromtimestamp(now.timestamp() + 600, tz=timezone.utc)  # 10 min from now
        db.conn.execute(
            "INSERT INTO trans_eu_user_tokens VALUES "
            "('tok1', 1, 42, 'old_access', 'old_refresh', '', ?, 'key_enc', '', '', 'active', NULL)",
            (expires_soon.isoformat(),),
        )
        db.conn.commit()

        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_refresh_tokens
        with patch("backend.celery_app.tasks.trans_eu_tasks.DatabaseManager") as MockDB:
            MockDB.return_value = db
            # Mock the entire TransEuClient to avoid async issues with refresh_token
            mock_client = MagicMock()
            mock_client.refresh_token.return_value = {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 21599,
            }
            with patch("services.trans_eu.client.TransEuClient", return_value=mock_client):
                result = trans_eu_refresh_tokens()
                assert result["refreshed"] >= 1


class TestCleanupExpiredSessionsTask:
    def test_deletes_revoked_tokens(self, db, freight_tables):
        """Tokens revoked >30 days ago are deleted."""
        past = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - (31 * 86400), tz=timezone.utc
        )
        db.conn.execute(
            "INSERT INTO trans_eu_user_tokens VALUES "
            "('old_tok', 1, 42, 'enc', 'enc', '', '2000-01-01', 'enc', '', '', 'revoked', ?)",
            (past.isoformat(),),
        )
        db.conn.commit()

        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_cleanup_expired_sessions
        with patch("backend.celery_app.tasks.trans_eu_tasks.DatabaseManager") as MockDB:
            MockDB.return_value = db
            result = trans_eu_cleanup_expired_sessions()
            assert result["tokens_deleted"] >= 1

    def test_active_tokens_not_deleted(self, db, freight_tables):
        """Active tokens are not affected by cleanup."""
        now = datetime.now(timezone.utc)
        db.conn.execute(
            "INSERT INTO trans_eu_user_tokens VALUES "
            "('active_tok', 1, 42, 'enc', 'enc', '', ?, 'enc', '', '', 'active', ?)",
            (now.isoformat(), now.isoformat()),
        )
        db.conn.commit()

        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_cleanup_expired_sessions
        with patch("backend.celery_app.tasks.trans_eu_tasks.DatabaseManager") as MockDB:
            MockDB.return_value = db
            result = trans_eu_cleanup_expired_sessions()
            assert result["tokens_deleted"] == 0


class TestProcessFailedWebhooksTask:
    def test_retries_failed_webhook(self, db, freight_tables):
        """A failed webhook in pending state gets retried."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_webhook_events_failed "
            "(id, company_id, trans_eu_event_id, event_name, payload, "
            "error_message, error_type, attempt_count, next_retry_at, status, created_at) "
            "VALUES ('dlq1', 1, 'evt_fail', 'test.event', '{}', "
            "'error', 'processing', 0, ?, 'pending', ?)",
            (now, now),
        )
        db.conn.commit()

        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_process_failed_webhooks
        with patch("backend.celery_app.tasks.trans_eu_tasks.DatabaseManager") as MockDB:
            MockDB.return_value = db
            # Mock WebhookIngestionService to avoid DB transaction conflicts
            mock_service = MagicMock()
            mock_service.process_webhook = AsyncMock(return_value={"status": "processed"})
            with patch(
                "services.trans_eu.webhook_ingestion.WebhookIngestionService",
                return_value=mock_service,
            ):
                result = trans_eu_process_failed_webhooks()
                assert result["processed"] >= 1


class TestHealthCheckTask:
    def test_returns_zero_when_no_connections(self, db):
        """Health check with no Trans.eu connections."""
        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_health_check
        with patch("backend.celery_app.tasks.trans_eu_tasks.DatabaseManager") as MockDB:
            MockDB.return_value = db
            result = trans_eu_health_check()
            assert result["checked"] == 0
            assert result["total"] == 0


class TestSyncActiveFreightsTask:
    def test_routes_without_active_freights(self, db, freight_tables):
        """Active freight sync with no active freights — no error."""
        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_sync_active_freights
        with patch("backend.celery_app.tasks.trans_eu_tasks.DatabaseManager") as MockDB:
            MockDB.return_value = db
            result = trans_eu_sync_active_freights()
            assert "synced" in result


class TestCeleryTaskImports:
    def test_all_tasks_importable(self):
        from backend.celery_app.tasks.trans_eu_tasks import (
            trans_eu_refresh_tokens,
            trans_eu_sync_active_freights,
            trans_eu_process_failed_webhooks,
            trans_eu_health_check,
            trans_eu_cleanup_expired_sessions,
        )
        names = [
            trans_eu_refresh_tokens.name,
            trans_eu_sync_active_freights.name,
            trans_eu_process_failed_webhooks.name,
            trans_eu_health_check.name,
            trans_eu_cleanup_expired_sessions.name,
        ]
        assert any("refresh" in n for n in names)
        assert any("cleanup" in n for n in names)

    def test_beat_schedule_entries_match_tasks(self):
        from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE
        trans_eu_entries = {k: v for k, v in CELERY_BEAT_SCHEDULE.items() if "trans-eu" in k}
        expected_tasks = [
            "trans_eu_refresh_tokens",
            "trans_eu_sync_active_freights",
            "trans_eu_process_failed_webhooks",
            "trans_eu_health_check",
            "trans_eu_cleanup_expired_sessions",
        ]
        for entry in trans_eu_entries.values():
            task_path = entry["task"]
            found = any(task_name in task_path for task_name in expected_tasks)
            assert found, f"Beat entry references unknown task: {task_path}"
