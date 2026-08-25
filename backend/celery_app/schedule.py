"""Celery beat schedule configuration.

Import and merge this schedule into your main Celery app config,
or ensure the beat schedule includes these entries.

Usage::

    from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE
    celery_app.conf.beat_schedule.update(CELERY_BEAT_SCHEDULE)
"""
from __future__ import annotations

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-data": {
        "task": "backend.celery_app.tasks.maintenance_tasks.cleanup_expired_data",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
    },
    "maintenance-forecast-daily": {
        "task": "backend.celery_app.tasks.insight_tasks.maintenance_forecast_job",
        "schedule": crontab(hour=5, minute=0),  # 5 AM daily
    },
    "overdue-invoice-daily": {
        "task": "backend.celery_app.tasks.insight_tasks.overdue_invoice_job",
        "schedule": crontab(hour=5, minute=30),  # 5:30 AM daily
    },
    "fleet-availability-daily": {
        "task": "backend.celery_app.tasks.insight_tasks.fleet_availability_job",
        "schedule": crontab(hour=6, minute=0),  # 6 AM daily
    },
    "fuel-cost-trend-daily": {
        "task": "backend.celery_app.tasks.insight_tasks.fuel_cost_trend_job",
        "schedule": crontab(hour=6, minute=30),
    },
    "return-load-matcher-daily": {
        "task": "backend.celery_app.tasks.insight_tasks.return_load_matcher_job",
        "schedule": crontab(hour=7, minute=0),
    },
    "driver-hours-forecast-daily": {
        "task": "backend.celery_app.tasks.insight_tasks.driver_hours_forecast_job",
        "schedule": crontab(hour=7, minute=30),
    },
    "copilot-retention-daily": {
        "task": "backend.celery_app.tasks.retention_tasks.enforce_copilot_retention",
        "schedule": crontab(hour=4, minute=0),  # 4 AM daily
    },
    "trans-eu-refresh-tokens": {
        "task": "backend.celery_app.tasks.trans_eu_tasks.trans_eu_refresh_tokens",
        "schedule": crontab(minute="*/30"),
    },
    "trans-eu-sync-active-freights": {
        "task": "backend.celery_app.tasks.trans_eu_tasks.trans_eu_sync_active_freights",
        "schedule": crontab(minute="*/10"),
    },
    "trans-eu-process-failed-webhooks": {
        "task": "backend.celery_app.tasks.trans_eu_tasks.trans_eu_process_failed_webhooks",
        "schedule": crontab(minute="*/15"),
    },
    "trans-eu-health-check": {
        "task": "backend.celery_app.tasks.trans_eu_tasks.trans_eu_health_check",
        "schedule": crontab(minute="*/5"),
    },
    "trans-eu-cleanup-expired-sessions": {
        "task": "backend.celery_app.tasks.trans_eu_tasks.trans_eu_cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=0),
    },
}
