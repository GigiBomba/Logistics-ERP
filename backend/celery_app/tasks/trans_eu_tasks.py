"""Trans.eu Celery tasks — background jobs for token management, freight sync,
webhook processing, health checks, and expired session cleanup.

All tasks are referred to by entries in ``backend/celery_app.schedule``.
"""
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


@celery_app.task(bind=True, max_retries=0)
def trans_eu_refresh_tokens(self) -> dict:
    """Scan trans_eu_user_tokens for tokens expiring within 1 hour
    and refresh them proactively.

    Runs every 30 minutes (crontab minute="*/30").
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
        return {"error": str(e)}


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
    try:
        offer_repo = TransEuFreightOfferRepository(db)
        exclude_statuses = ["closed", "accepted"]

        if company_id is not None:
            rows = [{"company_id": company_id}]
        else:
            rows = offer_repo.get_distinct_company_ids_by_status(exclude_statuses)

        synced = 0
        for row in rows:
            cid = row["company_id"]
            set_company_context(cid)

            # Get active freights for this company
            freights = offer_repo.get_freight_ids_by_company_and_status(cid, exclude_statuses)

            for freight_row in freights:
                try:
                    fid = freight_row["trans_eu_freight_id"]
                    # Fetch current status from Trans.eu
                    from services.freight_exchange.connection_manager import ConnectionManagerService
                    from services.freight_exchange.registry import get_adapter

                    conn_mgr = ConnectionManagerService(db)
                    session = conn_mgr.get_active_session_sync(cid, "trans_eu")
                    if session is None:
                        continue

                    adapter = get_adapter("trans_eu")
                    if adapter is None:
                        continue

                    # Use asyncio to run the async get_load in sync context
                    import asyncio
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(
                            adapter.get_load(session, str(fid))
                        )
                    finally:
                        loop.close()

                    if result:
                        # Sync status from raw_payload
                        raw = result.raw_payload if hasattr(result, 'raw_payload') else {}
                        new_status = raw.get("status", "")
                        if new_status:
                            offer_repo.update_status(
                                fid, cid, new_status,
                                datetime.now(timezone.utc).isoformat(),
                            )
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


@celery_app.task(bind=True, max_retries=0)
def trans_eu_process_failed_webhooks(self) -> dict:
    """Retry processing failed webhook events from the dead letter queue.

    Runs every 15 minutes (crontab minute="*/15").
    Processes events where next_retry_at <= NOW().
    """
    db = DatabaseManager(Config.DB_PATH)
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

                import asyncio
                from services.trans_eu.webhook_ingestion import WebhookIngestionService
                service = WebhookIngestionService(db)

                async def _process():
                    return await service.process_webhook(
                        company_id=cid, event_id=event_id,
                        event_name=event_name,
                        occurred_at=payload.get("occurred_at", ""),
                        payload=payload,
                    )

                result = asyncio.run(_process())

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


@celery_app.task(bind=True, max_retries=0)
def trans_eu_health_check(self, company_id: int = None) -> dict:
    """Ping Trans.eu for each company with an active connection.

    Runs every 5 minutes (crontab minute="*/5").
    Updates last_health_check_status for each connection.
    """
    db = DatabaseManager(Config.DB_PATH)
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
                import asyncio
                loop = asyncio.new_event_loop()
                try:
                    health = loop.run_until_complete(
                        conn_mgr.test_connection(cid, "trans_eu")
                    )
                finally:
                    loop.close()

                if health:
                    checked += 1
            except Exception as e:
                logger.warning("Health check failed for company %d: %s", cid, e)

        return {"checked": checked, "total": len(rows)}

    except Exception as e:
        logger.exception("trans_eu_health_check failed: %s", e)
        return {"error": str(e)}


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
