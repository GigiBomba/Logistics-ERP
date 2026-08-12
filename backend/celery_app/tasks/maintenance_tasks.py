"""Scheduled maintenance tasks including data retention cleanup."""
import logging
from datetime import datetime, timedelta

from backend.celery_app.celery import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def cleanup_expired_data():
    """Clean up data past retention period."""
    from database.db_manager import DatabaseManager
    from backend.config import BackendSettings

    config = BackendSettings()
    db = DatabaseManager(config.db_path)

    now = datetime.now()

    # GPS telemetry: 90 days retention
    cutoff = (now - timedelta(days=90)).isoformat()
    count = db.conn.execute(
        "DELETE FROM gps_telemetry WHERE recorded_at < ?", (cutoff,)
    ).rowcount
    db.conn.commit()

    if count > 0:
        logger.info("Data retention: deleted %d GPS records older than 90 days", count)

    return {"gps_records_deleted": count}
