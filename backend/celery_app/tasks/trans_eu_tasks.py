"""Trans.eu Celery tasks — background jobs for token management, freight sync,
webhook processing, health checks, and expired session cleanup.

All tasks are referred to by entries in ``backend/celery_app.schedule``.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from backend.celery_app.celery import celery_app
from backend.config import BackendSettings
from backend.dependencies import set_company_context
from config import Config
from database.db_manager import DatabaseManager
from repositories.trans_eu_repository import (
    TransEuUserTokenRepository,
    TransEuFreightOfferRepository,
    TransEuWebhookEventRepository,
)

logger = logging.getLogger(__name__)

settings = BackendSettings()

# Per-freight timeout for the external Trans.eu ``get_load`` call during
# trans_eu_sync_active_freights.  Bounds a single hung freight so it cannot
# stall the whole 10-minute sync cycle (C1b).
TRANS_EU_SYNC_FREIGHT_TIMEOUT_SECONDS = 30

# C1d: max concurrent in-flight Trans.eu ``get_load`` fetches per task run
# during trans_eu_sync_active_freights.  The per-freight fetches run
# concurrently on the one shared event loop but no more than this many are in
# flight at once, so a large active-freight list completes in ~N/concurrency ×
# latency (instead of N × latency) without hammering the external API.
TRANS_EU_SYNC_MAX_CONCURRENT_FETCHES = 6


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def trans_eu_refresh_tokens(self) -> dict:
    """Scan trans_eu_user_tokens for tokens expiring within 1 hour
    and refresh them proactively.

    Runs every 30 minutes (crontab minute="*/30").
    Task-level retries use exponential backoff (60s, 120s) so a transient
    provider/DB outage self-heals instead of waiting for the next beat.
    Per-token failures stay best-effort (logged + marked for re-auth).
    """
    db = DatabaseManager(Config.DB_PATH)
    try:
        now = datetime.now(timezone.utc)
        cutoff = datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc)

        token_repo = TransEuUserTokenRepository(db)
        rows = token_repo.get_active_expiring_before(cutoff.isoformat())

        refreshed = 0
        failed = 0

        for row in rows:
            try:
                set_company_context(row["company_id"])
                from services.trans_eu.client import TransEuClient

                api_key = row["api_key_encrypted"] or ""
                client = TransEuClient(api_key=api_key)

                tokens = client.refresh_token(
                    refresh_token=row["refresh_token_encrypted"] or "",
                    client_id=row["client_id"] or "",
                    client_secret=row["client_secret_encrypted"] or "",
                )

                # Update tokens
                expires_in = tokens.get("expires_in", 21599)
                new_expires_at = datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + expires_in, tz=timezone.utc,
                )
                token_repo.update(
                    row["id"],
                    access_token_encrypted=tokens["access_token"],
                    refresh_token_encrypted=tokens.get("refresh_token", row["refresh_token_encrypted"]),
                    expires_at=new_expires_at.isoformat(),
                    last_refreshed_at=now.isoformat(),
                    status="active",
                )
                refreshed += 1
                logger.info("Refreshed token for user %d (company %d)", row["user_id"], row["company_id"])

            except Exception as e:
                logger.warning("Token refresh failed for user %d: %s", row["user_id"], e)
                token_repo.mark_needs_reauth(row["id"])
                failed += 1

        return {"refreshed": refreshed, "failed": failed, "total": len(rows)}

    except Exception as e:
        logger.exception("trans_eu_refresh_tokens failed: %s", e)
        # Exponential backoff: 60s on the first retry, 120s on the second.
        raise self.retry(exc=e, countdown=self.default_retry_delay * (2 ** self.request.retries))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def trans_eu_sync_active_freights(self, company_id: int = None,
                                  request_id: str | None = None) -> dict:
    """Webhook fallback: poll Trans.eu for status changes on active freights.

    Runs every 10 minutes (crontab minute="*/10").
    Retries 3 times with 2-minute delay on failure.

    Args:
        company_id: If provided, scope to a single company.
                   Otherwise iterates all companies with active connections.
        request_id: Optional HTTP correlation id for tracing when this task
                    is triggered from a request (defaults to None for the
                    beat-scheduled run).
    """
    logger.info(
        "trans_eu_sync_active_freights: company_id=%s request_id=%s",
        company_id, request_id,
    )
    db = DatabaseManager(Config.DB_PATH)
    # C1a: ONE event loop for the whole task run — reuse it for every freight
    # instead of creating (and tearing down) a new loop per freight every 10 min.
    loop = asyncio.new_event_loop()
    try:
        try:
            offer_repo = TransEuFreightOfferRepository(db)
            exclude_statuses = ["closed", "accepted"]

            if company_id is not None:
                rows = [{"company_id": company_id}]
            else:
                rows = offer_repo.get_distinct_company_ids_by_status(exclude_statuses)

            synced = 0

            # C1d: bounded-concurrency limiter for the per-freight HTTP fetches,
            # shared across every company in this task run.  It is created on the
            # shared loop (via run_until_complete) so it binds to that loop on every
            # supported Python (asyncio.Semaphore must be created while its loop is
            # the running loop to bind correctly on 3.9).
            async def _new_fetch_limiter() -> asyncio.Semaphore:
                return asyncio.Semaphore(TRANS_EU_SYNC_MAX_CONCURRENT_FETCHES)

            fetch_limiter = loop.run_until_complete(_new_fetch_limiter())

            for row in rows:
                cid = row["company_id"]
                set_company_context(cid)

                # Get active freights for this company
                freights = offer_repo.get_freight_ids_by_company_and_status(cid, exclude_statuses)

                # C1d: parallelize the per-freight Trans.eu fetches.  The per-freight
                # coroutine (adapter.get_load) is PURE HTTP — it only opens an httpx
                # client with the passed session, with NO DB reads and NO tenant-context
                # global access.  So all freights of this company are fetched
                # concurrently on the one shared loop, bounded by
                # TRANS_EU_SYNC_MAX_CONCURRENT_FETCHES, and the statuses are then
                # persisted back on this sync thread (serialized).  Session lookup and
                # status persistence never run inside the parallel coroutine.
                from services.freight_exchange.connection_manager import ConnectionManagerService
                from services.freight_exchange.registry import get_adapter

                conn_mgr = ConnectionManagerService(db)
                adapter = get_adapter("trans_eu")

                # Per-freight session lookup + adapter check — same per-freight
                # behaviour as before (missing session/adapter → skip that freight).
                planned = []  # (fid, session) for freights we will fetch
                for freight_row in freights:
                    try:
                        fid = freight_row["trans_eu_freight_id"]
                        session = conn_mgr.get_active_session_sync(cid, "trans_eu")
                        if session is None or adapter is None:
                            continue
                        planned.append((fid, session))
                    except Exception as e:
                        logger.warning("Failed to sync freight %d for company %d: %s", fid, cid, e)

                if not planned:
                    continue

                async def _fetch_freight(adapter, session, fid):
                    # C1b: bounded by a per-freight timeout so one hung freight can't
                    # stall the whole 10-minute cycle. The timeout surfaces as an
                    # exception and is handled per-freight below.
                    async with fetch_limiter:
                        return await asyncio.wait_for(
                            adapter.get_load(session, str(fid)),
                            timeout=TRANS_EU_SYNC_FREIGHT_TIMEOUT_SECONDS,
                        )

                async def _fetch_all_freights():
                    # Concurrent, bounded fetch of every freight; exceptions are
                    # captured per-freight (return_exceptions=True) so one failed
                    # freight can't fail the batch. gather() is created here, while
                    # the loop is running, so every child future binds to *loop*.
                    return await asyncio.gather(
                        *(_fetch_freight(adapter, session, fid) for fid, session in planned),
                        return_exceptions=True,
                    )

                outcomes = loop.run_until_complete(_fetch_all_freights())

                for (fid, _session), outcome in zip(planned, outcomes):
                    try:
                        if isinstance(outcome, Exception):
                            raise outcome
                        result = outcome
                        if result:
                            # Sync status from raw_payload
                            raw = result.raw_payload if hasattr(result, 'raw_payload') else {}
                            new_status = raw.get("status", "")
                            if new_status:
                                # C1c: idempotent check-then-set — only UPDATE when the
                                # stored status actually differs, so retries don't issue
                                # redundant writes. Read is company-scoped (tenant isolation).
                                current = db.conn.execute(
                                    "SELECT status FROM trans_eu_freight_offers "
                                    "WHERE company_id = ? AND trans_eu_freight_id = ?",
                                    (cid, fid),
                                ).fetchone()
                                stored_status = current[0] if current else None
                                if stored_status != new_status:
                                    offer_repo.update_status(cid, new_status, stored_status)
                                    synced += 1
                    except Exception as e:
                        logger.warning("Failed to sync freight %d for company %d: %s", fid, cid, e)

            logger.info(
                "trans_eu_sync_active_freights completed: synced=%d request_id=%s",
                synced, request_id,
            )
            return {"synced": synced, "companies_checked": len(rows)}

        except Exception as e:
            logger.exception("trans_eu_sync_active_freights failed: %s", e)
            raise self.retry(exc=e)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def trans_eu_process_failed_webhooks(self) -> dict:
    """Retry processing failed webhook events from the dead letter queue.

    Runs every 15 minutes (crontab minute="*/15").
    Processes events where next_retry_at <= NOW().
    """
    db = DatabaseManager(Config.DB_PATH)
    # C2: ONE event loop for the whole run — reuse it per event row instead of
    # asyncio.run() churning a fresh loop up to 50 times per cycle.
    loop = asyncio.new_event_loop()
    try:
        try:
            now = datetime.now(timezone.utc).isoformat()
            # TODO: migrate to repo when TransEuWebhookEventFailedRepository is available
            rows = db.conn.execute(
                "SELECT id, company_id, trans_eu_event_id, event_name, payload, "
                "attempt_count "
                "FROM trans_eu_webhook_events_failed "
                "WHERE status IN ('pending', 'retrying') AND next_retry_at <= ? "
                "LIMIT 50",
                (now,),
            ).fetchall()

            processed = 0
            for row in rows:
                try:
                    cid = row["company_id"]
                    set_company_context(cid)
                    event_id = row["trans_eu_event_id"]
                    event_name = row["event_name"]

                    import json
                    payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
                    attempts = row["attempt_count"]

                    from services.trans_eu.webhook_ingestion import WebhookIngestionService
                    service = WebhookIngestionService(db)

                    async def _process():
                        return await service.process_webhook(
                            company_id=cid, event_id=event_id,
                            event_name=event_name,
                            occurred_at=payload.get("occurred_at", ""),
                            payload=payload,
                        )

                    result = loop.run_until_complete(_process())

                    if result.get("status") == "processed":
                        # TODO: migrate to repo
                        db.conn.execute(
                            "UPDATE trans_eu_webhook_events_failed SET status = 'resolved' WHERE id = ?",
                            (row["id"],),
                        )
                    else:
                        raise RuntimeError(result.get("error", "unknown error"))

                    db.conn.commit()
                    processed += 1

                except Exception as e:
                    attempts = row["attempt_count"] + 1
                    if attempts >= 10:
                        # TODO: migrate to repo
                        db.conn.execute(
                            "UPDATE trans_eu_webhook_events_failed SET status = 'failed_permanent' WHERE id = ?",
                            (row["id"],),
                        )
                    else:
                        # Calculate next retry: exponential backoff
                        delays = [60, 120, 240, 480, 960, 1800, 3600, 7200, 14400, 28800]
                        delay = delays[min(attempts, len(delays) - 1)]
                        next_retry = datetime.fromtimestamp(
                            datetime.now(timezone.utc).timestamp() + delay,
                            tz=timezone.utc,
                        )
                        # TODO: migrate to repo
                        db.conn.execute(
                            "UPDATE trans_eu_webhook_events_failed "
                            "SET attempt_count = ?, next_retry_at = ?, status = 'retrying' "
                            "WHERE id = ?",
                            (attempts, next_retry.isoformat(), row["id"]),
                        )
                    db.conn.commit()

            return {"processed": processed, "total": len(rows) if rows else 0}

        except Exception as e:
            logger.exception("trans_eu_process_failed_webhooks failed: %s", e)
            return {"error": str(e)}
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=0)
def trans_eu_health_check(self, company_id: int = None) -> dict:
    """Ping Trans.eu for each company with an active connection.

    Runs every 5 minutes (crontab minute="*/5").
    Updates last_health_check_status for each connection.
    """
    db = DatabaseManager(Config.DB_PATH)
    # C2: ONE event loop for the whole run — reuse it per company instead of
    # creating a new loop per company on every 5-minute cycle.
    loop = asyncio.new_event_loop()
    try:
        try:
            # TODO: migrate to repo when FreightExchangeConnectionRepository is available
            query = (
                "SELECT company_id, provider_id FROM freight_exchange_connections "
                "WHERE provider_id = 'trans_eu' AND status = 'connected'"
            )
            params = []
            if company_id is not None:
                query += " AND company_id = ?"
                params.append(company_id)
            rows = db.conn.execute(query, params).fetchall()

            checked = 0
            for row in rows:
                try:
                    cid = row["company_id"]
                    set_company_context(cid)

                    from services.freight_exchange.connection_manager import ConnectionManagerService
                    conn_mgr = ConnectionManagerService(db)
                    health = loop.run_until_complete(
                        conn_mgr.test_connection(cid, "trans_eu")
                    )

                    if health:
                        checked += 1
                except Exception as e:
                    logger.warning("Health check failed for company %d: %s", cid, e)

            return {"checked": checked, "total": len(rows)}

        except Exception as e:
            logger.exception("trans_eu_health_check failed: %s", e)
            return {"error": str(e)}
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=0)
def trans_eu_cleanup_expired_sessions(self) -> dict:
    """Archive expired/revoked Trans.eu user tokens and old webhook events.

    Runs daily at 03:00 UTC (crontab hour=3, minute=0).

    Cleanup is tenant-scoped: each active company's tokens/events are
    cleaned separately so one run never deletes another tenant's data.
    """
    from database.tenant_context import set_company_context
    from repositories.company_repository import CompanyRepository

    db = DatabaseManager(Config.DB_PATH)
    try:
        # Clean up revoked tokens older than 30 days
        cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - (30 * 86400),
            tz=timezone.utc,
        )

        # Archive old webhook events (> 90 days)
        event_cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - (90 * 86400),
            tz=timezone.utc,
        )

        token_repo = TransEuUserTokenRepository(db)
        event_repo = TransEuWebhookEventRepository(db)
        tokens_deleted = 0
        events_deleted = 0
        for company_id in CompanyRepository(db).get_active_ids():
            if not company_id:
                continue  # skip admin/global scope (id 0)
            set_company_context(company_id)
            tokens_deleted += token_repo.delete_revoked_older_than(
                cutoff.isoformat(), company_id=company_id,
            )
            events_deleted += event_repo.delete_older_than(
                event_cutoff.isoformat(), company_id=company_id,
            )

        return {"tokens_deleted": tokens_deleted, "events_deleted": events_deleted}

    except Exception as e:
        logger.exception("trans_eu_cleanup_expired_sessions failed: %s", e)
        return {"error": str(e)}
