"""Scheduled maintenance tasks including data retention cleanup."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from backend.celery_app.celery import celery_app
from database.tenant_context import set_company_context
from repositories.company_repository import CompanyRepository
from repositories.gps_telemetry_repository import GpsTelemetryRepository

logger = logging.getLogger(__name__)


@celery_app.task
def cleanup_expired_data():
    """Clean up data past retention period.

    GPS telemetry is cleaned per active company so a single scheduled run
    never wipes another tenant's history.  ``company_id`` is passed
    explicitly to ``delete_older_than`` (via ``_company_filter_for``), so the
    delete is scoped regardless of the ambient tenant context.
    """
    from backend.config import BackendSettings
    from backend.db import DatabaseManager

    config = BackendSettings()
    db = DatabaseManager(config.db_path)

    try:
        now = datetime.now()

        # GPS telemetry: 90 days retention
        cutoff = (now - timedelta(days=90)).isoformat()
        repo = GpsTelemetryRepository(db)
        total = 0
        for company_id in CompanyRepository(db).get_active_ids():
            if not company_id:
                # Skip the admin/global scope row (id 0): passing 0 to
                # `_company_filter_for` is falsy, so it falls back to the
                # unscoped context filter and would delete ALL companies'
                # rows. Admin-scope GPS is intentionally exempt from
                # retention cleanup.
                continue
            set_company_context(company_id)
            count = repo.delete_older_than(cutoff, company_id=company_id)
            total += count

        if total > 0:
            logger.info("Data retention: deleted %d GPS records older than 90 days", total)

        return {"gps_records_deleted": total}
    finally:
        db.close()
