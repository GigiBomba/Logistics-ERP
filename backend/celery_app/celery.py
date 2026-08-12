from celery import Celery

from backend.config import BackendSettings

settings = BackendSettings()

celery_app = Celery(
    "operion",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Bucharest",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

celery_app.conf.beat_schedule = {
    "flush-gps-every-30s": {
        "task": "backend.celery_app.tasks.ocr_tasks.flush_gps_batch_to_postgres",
        "schedule": 30.0,
    },
}

# Merge declarative schedule entries
try:
    from backend.celery_app.schedule import CELERY_BEAT_SCHEDULE
    celery_app.conf.beat_schedule.update(CELERY_BEAT_SCHEDULE)
except ImportError:
    pass
