"""Performance-focused tests for the Trans.eu Celery tasks.

Covers the approved performance fixes (audit of trans_eu_tasks.py):
  C1a — ONE event loop per task run in trans_eu_sync_active_freights
        (was: a fresh ``asyncio.new_event_loop()`` per freight, every 10 min).
  C1b — per-freight ``asyncio.wait_for`` timeout so a hung freight can't
        stall the whole 10-minute cycle (timeout → log + skip that freight).
  C1c — idempotent check-then-set status update (skip UPDATE when the stored
        status already equals the new status).
  C2  — ONE event loop per task run in trans_eu_process_failed_webhooks and
        trans_eu_health_check (was: loop per row / per company).

The adapter + repository are mocked; ``asyncio.new_event_loop`` is patched to
count how many event loops a single task run creates.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.test_helpers import InMemoryDB


def _install_loop_counter():
    """Patch ``asyncio.new_event_loop`` so tests can count loops per task run.

    Returns ``(created_loops, patcher)`` — ``created_loops`` collects every
    real event loop the code under test asks for; ``patcher`` is the context
    manager that installs the counting factory.
    """
    created = []
    real_new_event_loop = asyncio.new_event_loop

    def counting_factory():
        loop = real_new_event_loop()
        created.append(loop)
        return loop

    return created, patch("asyncio.new_event_loop", counting_factory)


@pytest.fixture
def db():
    from database.tenant_context import clear_context
    d = InMemoryDB()
    yield d
    clear_context()
    d.close()


@pytest.fixture
def freight_tables(db):
    """Minimal Trans.eu tables needed by the celery task tests."""
    db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_freight_offers (
        id TEXT PRIMARY KEY, company_id INTEGER, user_id INTEGER,
        trans_eu_freight_id INTEGER, status TEXT, origin TEXT,
        destination TEXT, operion_trip_id INTEGER,
        updated_at TEXT
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
    for t in ["trans_eu_freight_offers", "trans_eu_webhook_events_failed"]:
        db.conn.execute(f"DROP TABLE IF EXISTS {t}")
    db.conn.commit()


# ── Sync active freights ────────────────────────────────────────────────


def _make_sync_mocks(freight_ids, *, companies=None, get_load_result=None, hang=False):
    """Build mocked offer repo / connection manager / adapter for the sync task."""
    offer_repo = MagicMock()
    offer_repo.get_distinct_company_ids_by_status.return_value = (
        companies if companies is not None else [{"company_id": 1}]
    )
    offer_repo.get_freight_ids_by_company_and_status.return_value = [
        {"trans_eu_freight_id": fid} for fid in freight_ids
    ]
    offer_repo.update_status.return_value = 1

    conn_mgr = MagicMock()
    conn_mgr.get_active_session_sync.return_value = SimpleNamespace(
        access_token_encrypted="tok",
    )

    adapter = MagicMock()
    if hang:
        async def _hang(*args, **kwargs):
            await asyncio.sleep(3600)

        adapter.get_load = _hang
    else:
        adapter.get_load = AsyncMock(return_value=get_load_result)

    return offer_repo, conn_mgr, adapter


def _run_sync_task(db, offer_repo, conn_mgr, adapter):
    """Invoke trans_eu_sync_active_freights with mocked deps."""
    from backend.celery_app.tasks import trans_eu_tasks as mod
    from backend.celery_app.tasks.trans_eu_tasks import trans_eu_sync_active_freights

    with patch.object(mod, "DatabaseManager", return_value=db):
        with patch.object(mod, "TransEuFreightOfferRepository", return_value=offer_repo):
            with patch(
                "services.freight_exchange.connection_manager.ConnectionManagerService",
                return_value=conn_mgr,
            ):
                with patch("services.freight_exchange.registry.get_adapter", return_value=adapter):
                    return trans_eu_sync_active_freights()


class TestSyncActiveFreightsPerf:
    def test_single_event_loop_across_many_freights(self, db, freight_tables):
        """C1a: one loop per run, even with N freights; closed once in finally."""
        offer_repo, conn_mgr, adapter = _make_sync_mocks(
            [101, 102, 103],
            get_load_result=SimpleNamespace(raw_payload={"status": "in_progress"}),
        )

        created, patcher = _install_loop_counter()
        with patcher:
            result = _run_sync_task(db, offer_repo, conn_mgr, adapter)

        assert result["synced"] == 3
        assert adapter.get_load.await_count == 3
        assert len(created) == 1, "must create exactly ONE event loop per task run"
        assert created[0].is_closed(), "event loop must be closed once in a finally"

    def test_single_event_loop_across_multiple_companies(self, db, freight_tables):
        """C1a: one loop per run, even across several companies."""
        offer_repo, conn_mgr, adapter = _make_sync_mocks(
            [101],
            companies=[{"company_id": 1}, {"company_id": 2}],
            get_load_result=SimpleNamespace(raw_payload={"status": "in_progress"}),
        )
        offer_repo.get_freight_ids_by_company_and_status.side_effect = (
            lambda cid, statuses: [{"trans_eu_freight_id": cid * 100 + 1}]
        )

        created, patcher = _install_loop_counter()
        with patcher:
            result = _run_sync_task(db, offer_repo, conn_mgr, adapter)

        assert result["synced"] == 2
        assert result["companies_checked"] == 2
        assert len(created) == 1, "must create exactly ONE event loop per task run"

    def test_hung_freight_times_out_and_is_skipped(self, db, freight_tables):
        """C1b: a hung freight times out; the task logs + skips it and completes."""
        offer_repo, conn_mgr, adapter = _make_sync_mocks([101], hang=True)

        created, patcher = _install_loop_counter()
        with patcher:
            with patch(
                "backend.celery_app.tasks.trans_eu_tasks.TRANS_EU_SYNC_FREIGHT_TIMEOUT_SECONDS",
                0.05,
            ):
                with patch("backend.celery_app.tasks.trans_eu_tasks.logger") as mock_logger:
                    result = _run_sync_task(db, offer_repo, conn_mgr, adapter)

        assert result["synced"] == 0
        assert result["companies_checked"] == 1
        assert offer_repo.update_status.call_count == 0
        assert len(created) == 1
        mock_logger.warning.assert_called_once()

    def test_status_update_skipped_when_unchanged(self, db, freight_tables):
        """C1c: stored status == new status → no redundant UPDATE (idempotent retry)."""
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, trans_eu_freight_id, status) VALUES ('f1', 1, 101, 'draft')"
        )
        db.conn.commit()

        offer_repo, conn_mgr, adapter = _make_sync_mocks(
            [101],
            get_load_result=SimpleNamespace(raw_payload={"status": "draft"}),
        )

        result = _run_sync_task(db, offer_repo, conn_mgr, adapter)

        assert result["synced"] == 0
        offer_repo.update_status.assert_not_called()

    def test_status_update_called_when_changed(self, db, freight_tables):
        """C1c: stored status differs → UPDATE issued exactly once."""
        db.conn.execute(
            "INSERT INTO trans_eu_freight_offers "
            "(id, company_id, trans_eu_freight_id, status) VALUES ('f1', 1, 101, 'draft')"
        )
        db.conn.commit()

        offer_repo, conn_mgr, adapter = _make_sync_mocks(
            [101],
            get_load_result=SimpleNamespace(raw_payload={"status": "in_progress"}),
        )

        result = _run_sync_task(db, offer_repo, conn_mgr, adapter)

        assert result["synced"] == 1
        offer_repo.update_status.assert_called_once_with(1, "in_progress", "draft")


# ── Process failed webhooks ─────────────────────────────────────────────


class TestProcessFailedWebhooksPerf:
    def test_single_event_loop_for_many_rows(self, db, freight_tables):
        """C2: one loop per run instead of asyncio.run() per event row."""
        now = datetime.now(timezone.utc).isoformat()
        db.conn.execute(
            "INSERT INTO trans_eu_webhook_events_failed "
            "(id, company_id, trans_eu_event_id, event_name, payload, "
            "attempt_count, next_retry_at, status) "
            "VALUES ('dlq1', 1, 'evt1', 'test.event', '{}', 0, ?, 'pending'), "
            "('dlq2', 2, 'evt2', 'test.event', '{}', 0, ?, 'pending')",
            (now, now),
        )
        db.conn.commit()

        mock_service = MagicMock()
        mock_service.process_webhook = AsyncMock(return_value={"status": "processed"})

        from backend.celery_app.tasks import trans_eu_tasks as mod
        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_process_failed_webhooks

        created, patcher = _install_loop_counter()
        with patcher:
            with patch.object(mod, "DatabaseManager", return_value=db):
                with patch(
                    "services.trans_eu.webhook_ingestion.WebhookIngestionService",
                    return_value=mock_service,
                ):
                    result = trans_eu_process_failed_webhooks()

        assert result["processed"] == 2
        assert result["total"] == 2
        assert mock_service.process_webhook.await_count == 2
        assert len(created) == 1, "must create exactly ONE event loop per task run"


# ── Health check ────────────────────────────────────────────────────────


class TestHealthCheckPerf:
    def test_single_event_loop_for_many_companies(self, db):
        """C2: one loop per run instead of a loop per company."""
        db.conn.execute(
            "INSERT INTO freight_exchange_connections "
            "(id, company_id, provider_id, credentials_encrypted, status) "
            "VALUES ('hc1', 1, 'trans_eu', 'cred', 'connected'), "
            "('hc2', 2, 'trans_eu', 'cred', 'connected')"
        )
        db.conn.commit()

        conn_mgr = MagicMock()
        conn_mgr.test_connection = AsyncMock(return_value=True)

        from backend.celery_app.tasks import trans_eu_tasks as mod
        from backend.celery_app.tasks.trans_eu_tasks import trans_eu_health_check

        created, patcher = _install_loop_counter()
        with patcher:
            with patch.object(mod, "DatabaseManager", return_value=db):
                with patch(
                    "services.freight_exchange.connection_manager.ConnectionManagerService",
                    return_value=conn_mgr,
                ):
                    result = trans_eu_health_check()

        assert result["checked"] == 2
        assert result["total"] == 2
        assert conn_mgr.test_connection.await_count == 2
        assert len(created) == 1, "must create exactly ONE event loop per task run"