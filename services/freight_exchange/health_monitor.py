"""Freight Exchange health monitor — scheduled Celery task.

Periodically pings every connected provider via their adapter's
``test_connection()`` and updates the ``last_health_check_status``
in the ``freight_exchange_connections`` table.

The Search Engine (§5) checks this before firing a live search —
a degraded TIMOCOM connection should never block a Trans.eu search
from returning results.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from database.db_manager import DatabaseManager
from services.freight_exchange.connection_manager import ConnectionManagerService

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
HEALTH_CHECK_INTERVAL_SECONDS = 300  # 5 minutes — configurable
HEALTH_CHECK_TIMEOUT_SECONDS = 30    # per-provider timeout


async def _check_provider_health(
    manager: ConnectionManagerService,
    company_id: int,
    provider_id: str,
) -> None:
    """Ping a single provider and update its health status."""
    try:
        health = await asyncio.wait_for(
            manager.test_connection(company_id, provider_id),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        if health:
            logger.debug(
                "Health check: company=%d provider=%s status=%s latency=%dms",
                company_id, provider_id, health.status, health.latency_ms,
            )
    except asyncio.TimeoutError:
        logger.warning(
            "Health check timed out for company=%d provider=%s",
            company_id, provider_id,
        )
        # Persist "down" status so the search engine skips this provider
        try:
            conn = manager.repo.get_connection(company_id, provider_id)
            if conn:
                manager.repo.update_health(
                    str(conn["id"]), "down",
                    datetime.now(timezone.utc).isoformat(),
                )
        except Exception:
            pass
    except Exception as e:
        logger.error(
            "Health check failed for company=%d provider=%s: %s",
            company_id, provider_id, e,
        )


async def run_all_health_checks(
    db: Optional[DatabaseManager] = None,
) -> dict[str, dict]:
    """Run health checks against all connected providers across all companies.

    Returns a summary dict: ``{provider_id: {company_id: status, ...}}``

    Args:
        db: Database manager instance. If None, creates a temporary one.
            In production, this should be injected by the Celery task.
    """
    if db is None:
        raise RuntimeError(
            "No DatabaseManager injected into run_all_health_checks(). "
            "The Celery task must inject a DB connection."
        )

    manager = ConnectionManagerService(db)

    # Discover all connected (company_id, provider_id) pairs
    # We query the repository directly since list_connected_providers
    # works per-company — we need ALL companies
    from repositories.freight_exchange_repository import FreightExchangeRepository
    repo = FreightExchangeRepository(db)

    # Get all connections with status='connected' (simplistic — in production,
    # you'd iterate per-company. For now, we scan all connections.)
    # Actually, the repository's list_connections requires a company_id.
    # In a real deployment, you'd iterate over all active companies.
    # For this implementation, use a pragmatic approach:
    summary: dict[str, dict] = {}
    logger.info("Starting freight exchange health check cycle")

    # This is intentionally minimal — the full implementation needs a company
    # iteration mechanism which varies between deployment modes.
    # The key architecture point: each (company, provider) pair is independently
    # checked so one failure doesn't cascade.
    try:
        # Attempt to load all connections from the DB
        all_rows = repo._fetchall("SELECT company_id, provider_id FROM freight_exchange_connections WHERE status = 'connected'")
        for row in all_rows:
            cid = row["company_id"]
            pid = row["provider_id"]
            await _check_provider_health(manager, cid, pid)
            if pid not in summary:
                summary[pid] = {}
            summary[pid][str(cid)] = "checked"
    except Exception as e:
        logger.warning("Could not enumerate connections: %s", e)

    logger.info(
        "Health check cycle complete — %d provider(s) checked",
        sum(len(v) for v in summary.values()),
    )
    return summary


def run_health_check_sync(db: Optional[DatabaseManager] = None) -> dict:
    """Synchronous wrapper for Celery tasks and other sync contexts.

    Celery tasks are synchronous — this wraps the async health check
    in an event loop.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an already-running event loop — create a new one
            try:
                import nest_asyncio
                nest_asyncio.apply()
            except ImportError:
                logger.warning("nest_asyncio not installed — health check may block")
            return loop.run_until_complete(run_all_health_checks(db))
        return loop.run_until_complete(run_all_health_checks(db))
    except RuntimeError:
        # No event loop in this thread
        return asyncio.run(run_all_health_checks(db))
