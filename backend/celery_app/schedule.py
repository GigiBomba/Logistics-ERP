"""Celery beat schedule configuration.

Import and merge this schedule into your main Celery app config,
or ensure the beat schedule includes these entries.

Usage::

    from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE
    celery_app.conf.beat_schedule.update(CELERY_BEAT_SCHEDULE)
"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-data": {
        "task": "backend.celery_app.tasks.maintenance_tasks.cleanup_expired_data",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
    },
}
