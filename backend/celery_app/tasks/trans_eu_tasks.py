"""Trans.eu Celery tasks — background jobs for token management, freight sync,
webhook processing, health checks, and expired session cleanup.

All tasks are referenced by entries in ``backend/celery_app.schedule``.
"""
import logging
from datetime import datetime, timezone

from backend.celery_app.celery import celery_app
from backend.config import BackendSettings
from backend.dependencies import set_company_context
from config import Config
from database.db_manager import DatabaseManager

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

        rows = db.conn.execute(
            "SELECT id, company_id, user_id, refresh_token_encrypted, "
            "client_id, client_secret_encrypted, api_key_encrypted "
            "FROM trans_eu_user_tokens "
            "WHERE status = 'active' AND expires_at < ?",
            (cutoff.isoformat(),),
        ).fetchall()

        refreshed = 0
        failed = 0

        for row in rows:
            try:
                set_company_context(row[1])
                from services.trans_eu.client import TransEuClient

                api_key = row[6] if row[6] else ""
                client = TransEuClient(api_key=api_key)

                tokens = client.refresh_token(
                    refresh_token=row[3] or "",
                    client_id=row[4] or "",
                    client_secret=row[5] or "",
                )

                # Update tokens
                expires_in = tokens.get("expires_in", 21599)
                new_expires_at = datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + expires_in, tz=timezone.utc,
                )
                db.conn.execute(
                    "UPDATE trans_eu_user_tokens SET "
                    "access_token_encrypted = ?, refresh_token_encrypted = ?, "
                    "expires_at = ?, last_refreshed_at = ?, status = 'active' "
                    "WHERE id = ?",
                    (tokens["access_token"], tokens.get("refresh_token", row[3]),
                     new_expires_at.isoformat(), now.isoformat(), row[0]),
                )
                db.conn.commit()
                refreshed += 1
                logger.info("Refreshed token for user %d (company %d)", row[2], row[1])

            except Exception as e:
                logger.warning("Token refresh failed for user %d: %s", row[2], e)
                db.conn.execute(
                    "UPDATE trans_eu_user_tokens SET status = 'needs_reauth' WHERE id = ?",
                    (row[0],),
                )
                db.conn.commit()
                failed += 1

        return {"refreshed": refreshed, "failed": failed, "total": len(rows) if rows else 0}

    except Exception as e:
        logger.exception("trans_eu_refresh_tokens failed: %s", e)
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def trans_eu_sync_active_freights(self, company_id: int = None) -> dict:
    """Webhook fallback: poll Trans.eu for status changes on active freights.

    Runs every 10 minutes (crontab minute="*/10").
    Retries 3 times with 2-minute delay on failure.

    Args:
        company_id: If provided, scope to a single company.
                   Otherwise iterates all companies with active connections.
    """
    db = DatabaseManager(Config.DB_PATH)
    try:
        query = (
            "SELECT DISTINCT company_id FROM trans_eu_freight_offers "
            "WHERE status NOT IN ('closed', 'accepted')"
        )
        params = []
        if company_id is not None:
            query += " AND company_id = ?"
            params.append(company_id)
        rows = db.conn.execute(query, params).fetchall()

        synced = 0
        for row in rows:
            cid = row[0]
            set_company_context(cid)

            # Get active freights for this company
            freights = db.conn.execute(
                "SELECT trans_eu_freight_id FROM trans_eu_freight_offers "
                "WHERE company_id = ? AND status NOT IN ('closed', 'accepted') "
                "LIMIT 50",
                (cid,),
            ).fetchall()

            for freight_row in freights:
                try:
                    fid = freight_row[0]
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
                            db.conn.execute(
                                "UPDATE trans_eu_freight_offers SET status = ?, updated_at = ? "
                                "WHERE trans_eu_freight_id = ? AND company_id = ?",
                                (new_status, datetime.now(timezone.utc).isoformat(), fid, cid),
                            )
                            db.conn.commit()
                            synced += 1
                except Exception as e:
                    logger.warning("Failed to sync freight %d for company %d: %s", fid, cid, e)

        return {"synced": synced, "companies_checked": len(rows) if rows else 0}

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
                cid = row[1]
                set_company_context(cid)
                event_id = row[2]
                event_name = row[3]

                import json
                payload = json.loads(row[4]) if isinstance(row[4], str) else row[4]
                attempts = row[5]

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
                    db.conn.execute(
                        "UPDATE trans_eu_webhook_events_failed SET status = 'resolved' WHERE id = ?",
                        (row[0],),
                    )
                else:
                    raise RuntimeError(result.get("error", "unknown error"))

                db.conn.commit()
                processed += 1

            except Exception as e:
                attempts = row[5] + 1
                if attempts >= 10:
                    db.conn.execute(
                        "UPDATE trans_eu_webhook_events_failed SET status = 'failed_permanent' WHERE id = ?",
                        (row[0],),
                    )
                else:
                    # Calculate next retry: exponential backoff
                    delays = [60, 120, 240, 480, 960, 1800, 3600, 7200, 14400, 28800]
                    delay = delays[min(attempts, len(delays) - 1)]
                    next_retry = datetime.fromtimestamp(
                        datetime.now(timezone.utc).timestamp() + delay,
                        tz=timezone.utc,
                    )
                    db.conn.execute(
                        "UPDATE trans_eu_webhook_events_failed "
                        "SET attempt_count = ?, next_retry_at = ?, status = 'retrying' "
                        "WHERE id = ?",
                        (attempts, next_retry.isoformat(), row[0]),
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
                cid = row[0]
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

        return {"checked": checked, "total": len(rows) if rows else 0}

    except Exception as e:
        logger.exception("trans_eu_health_check failed: %s", e)
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=0)
def trans_eu_cleanup_expired_sessions(self) -> dict:
    """Archive expired/revoked Trans.eu user tokens and old webhook events.

    Runs daily at 03:00 UTC (crontab hour=3, minute=0).
    """
    db = DatabaseManager(Config.DB_PATH)
    try:
        # Clean up revoked tokens older than 30 days
        cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - (30 * 86400),
            tz=timezone.utc,
        )

        cursor = db.conn.execute(
            "DELETE FROM trans_eu_user_tokens "
            "WHERE status = 'revoked' AND last_refreshed_at < ?",
            (cutoff.isoformat(),),
        )
        tokens_deleted = cursor.rowcount if cursor.rowcount else 0

        # Archive old webhook events (> 90 days)
        event_cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - (90 * 86400),
            tz=timezone.utc,
        )
        cursor = db.conn.execute(
            "DELETE FROM trans_eu_webhook_events WHERE created_at < ?",
            (event_cutoff.isoformat(),),
        )
        events_deleted = cursor.rowcount if cursor.rowcount else 0

        db.conn.commit()
        return {"tokens_deleted": tokens_deleted, "events_deleted": events_deleted}

    except Exception as e:
        logger.exception("trans_eu_cleanup_expired_sessions failed: %s", e)
        return {"error": str(e)}
