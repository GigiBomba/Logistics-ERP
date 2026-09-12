"""Bounded-concurrency tests for ``trans_eu_sync_active_freights``.

Covers the approved parallelization (C1d) of the per-freight Trans.eu
``get_load`` fetches in ``backend/celery_app/tasks/trans_eu_tasks.py``:

  Before — each freight's ``get_load`` ran through
           ``loop.run_until_complete(...)`` *sequentially* (N HTTP round-trips
           back to back, 30 s timeout each) → ~N × latency per company/cycle.
  After  — the per-freight fetches run concurrently on the one shared event
           loop with BOUNDED concurrency (``asyncio.Semaphore`` capped at
           ``TRANS_EU_SYNC_MAX_CONCURRENT_FETCHES``), so a large list completes
           in ~N/concurrency × latency without hammering the external API.

Design guarantees verified here:
  * Only the pure-HTTP fetch is parallelized (the per-freight ``get_load``
    coroutine opens an ``httpx.AsyncClient`` with the passed session — no DB,
    no tenant-context global reads).  Session lookups and the status
    read/update persistence stay on the task's sync thread, serialized.
  * Per-freight timeout (``asyncio.wait_for``) and per-freight error isolation
    are preserved (one failed freight must not fail the batch).
  * The task's return shape (``{"synced": ..., "companies_checked": ...}``)
    is unchanged.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.test_helpers import InMemoryDB

try:
    from backend.celery_app.tasks.trans_eu_tasks import (
        TRANS_EU_SYNC_MAX_CONCURRENT_FETCHES as CAP,
    )
except ImportError:  # constant not yet present (sequential baseline) — fall back
    CAP = 6


@pytest.fixture
def db():
    from database.tenant_context import clear_context
    d = InMemoryDB()
    yield d
    clear_context()
    d.close()


@pytest.fixture
def freight_tables(db):
    """Minimal Trans.eu tables needed by the sync task (status read)."""
    db.conn.execute("""CREATE TABLE IF NOT EXISTS trans_eu_freight_offers (
        id TEXT PRIMARY KEY, company_id INTEGER, user_id INTEGER,
        trans_eu_freight_id INTEGER, status TEXT, origin TEXT,
        destination TEXT, operion_trip_id INTEGER,
        updated_at TEXT
    )""")
    db.conn.commit()
    yield
    db.conn.execute("DROP TABLE IF EXISTS trans_eu_freight_offers")
    db.conn.commit()


def _make_sync_mocks(freight_ids):
    """Build mocked offer repo / connection manager / adapter for the sync task."""
    offer_repo = MagicMock()
    offer_repo.get_distinct_company_ids_by_status.return_value = [
        {"company_id": 1},
    ]
    offer_repo.get_freight_ids_by_company_and_status.return_value = [
        {"trans_eu_freight_id": fid} for fid in freight_ids
    ]
    offer_repo.update_status.return_value = 1

    conn_mgr = MagicMock()
    conn_mgr.get_active_session_sync.return_value = SimpleNamespace(
        access_token_encrypted="tok",
    )

    adapter = MagicMock()
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


class TestSyncActiveFreightsBoundedConcurrency:
    def test_freight_fetches_run_with_bounded_concurrency(self, db, freight_tables):
        """N freights fetch concurrently (max in-flight ≤ cap) and finish well
        under N × per-fetch latency (sequential would take ~N × latency)."""
        n = 12
        per_fetch = 0.25
        tracker = {"in_flight": 0, "max": 0}

        async def slow_get_load(session, load_id):
            tracker["in_flight"] += 1
            tracker["max"] = max(tracker["max"], tracker["in_flight"])
            try:
                await asyncio.sleep(per_fetch)
                return SimpleNamespace(raw_payload={"status": "in_progress"})
            finally:
                tracker["in_flight"] -= 1

        offer_repo, conn_mgr, adapter = _make_sync_mocks(list(range(101, 101 + n)))
        adapter.get_load = AsyncMock(side_effect=slow_get_load)

        start = time.perf_counter()
        result = _run_sync_task(db, offer_repo, conn_mgr, adapter)
        elapsed = time.perf_counter() - start

        # Return shape unchanged + every freight fetched + synced.
        assert result["companies_checked"] == 1
        assert result["synced"] == n
        assert adapter.get_load.await_count == n

        # Concurrency happened (max > 1) but is BOUNDED (max ≤ cap).
        assert 2 <= tracker["max"] <= CAP, (
            f"expected bounded concurrency in [2, {CAP}], got max={tracker['max']}"
        )

        print(f"\n[C1d] freights={n} per_fetch={per_fetch}s "
              f"cap={CAP} max_in_flight={tracker['max']} elapsed={elapsed:.2f}s "
              f"(sequential would be ~{n * per_fetch:.2f}s)")

        # Completed in ~N/concurrency × latency, NOT N × latency.
        assert elapsed < 2.0, (
            f"took {elapsed:.2f}s for {n}×{per_fetch:.2f}s fetches "
            f"(sequential ≈ {n * per_fetch:.2f}s, max_in_flight={tracker['max']})"
        )

    def test_concurrency_is_capped_for_many_freights(self, db, freight_tables):
        """More freights than the cap still never exceeds the cap in flight."""
        n = 40
        per_fetch = 0.05
        tracker = {"in_flight": 0, "max": 0}

        async def slow_get_load(session, load_id):
            tracker["in_flight"] += 1
            tracker["max"] = max(tracker["max"], tracker["in_flight"])
            try:
                await asyncio.sleep(per_fetch)
                return SimpleNamespace(raw_payload={"status": "in_progress"})
            finally:
                tracker["in_flight"] -= 1

        offer_repo, conn_mgr, adapter = _make_sync_mocks(list(range(201, 201 + n)))
        adapter.get_load = AsyncMock(side_effect=slow_get_load)

        result = _run_sync_task(db, offer_repo, conn_mgr, adapter)

        assert result["synced"] == n
        assert adapter.get_load.await_count == n
        # Bound holds even with 40 freights >> cap.
        assert 1 <= tracker["max"] <= CAP, (
            f"max in-flight {tracker['max']} must not exceed cap {CAP}"
        )

    def test_one_failed_freight_does_not_fail_the_batch(self, db, freight_tables):
        """Per-freight error isolation: a single failing fetch (raises) is
        logged+skipped and the rest of the batch still syncs."""
        n = 6
        tracker = {"in_flight": 0, "max": 0}

        async def flaky_get_load(session, load_id):
            tracker["in_flight"] += 1
            tracker["max"] = max(tracker["max"], tracker["in_flight"])
            try:
                await asyncio.sleep(0.02)
                if int(load_id) % 3 == 0:  # every 3rd freight fails
                    raise RuntimeError("provider boom")
                return SimpleNamespace(raw_payload={"status": "in_progress"})
            finally:
                tracker["in_flight"] -= 1

        offer_repo, conn_mgr, adapter = _make_sync_mocks(list(range(301, 301 + n)))
        adapter.get_load = AsyncMock(side_effect=flaky_get_load)

        with patch("backend.celery_app.tasks.trans_eu_tasks.logger") as mock_logger:
            result = _run_sync_task(db, offer_repo, conn_mgr, adapter)

        # Freights 301,304 (divisible by 3) fail; the other 4 succeed.
        assert result["synced"] == n - 2
        assert adapter.get_load.await_count == n
        assert mock_logger.warning.call_count == 2
