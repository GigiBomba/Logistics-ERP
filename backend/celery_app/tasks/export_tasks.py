"""Celery tasks for the mobile async export pipeline (export_jobs table).

``export_trips_job`` runs the REAL mobile trips export
(``services.mobile_export_service.build_trips_export`` → csv / xlsx / pdf,
with honest per-format error statuses) and transitions the ``export_jobs``
row to success/error.  The job params record the requesting user (Gate-29 A4)
so the typed export path can be driven with a real user id.

``_extract_db_path`` is shared with the tacho import task: it returns the DB
path/DSN a Celery worker needs to reconstruct a ``DatabaseManager`` (SQLite
pool path, PostgreSQL DSN, or the desktop ``Config.DB_PATH`` fallback).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from backend.celery_app.celery import celery_app
from backend.db import DatabaseManager
from backend.desktop_config import Config
from repositories.export_job_repository import ExportJobRepository
from services.mobile_export_service import build_trips_export

logger = logging.getLogger(__name__)


def _extract_db_path(db) -> str:
    """Return the DB path/DSN a Celery worker can reconstruct the DB from.

    Prefers the live ``DatabaseManager``'s pool path (SQLite ``ConnectionPool``
    stores ``_db_path``; the Postgres pool stores the DSN as ``_dsn``), falling
    back to the desktop ``Config.DB_PATH``.
    """
    sqlite_pool = getattr(db, "_pool", None)
    path = getattr(sqlite_pool, "_db_path", None)
    if path:
        return path
    pg_pool = getattr(db, "_pg_pool", None)
    dsn = getattr(pg_pool, "_dsn", None)
    if dsn:
        return dsn
    return Config.DB_PATH


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def export_trips_job(
    self,
    job_id: int,
    company_id: int,
    db_path: Optional[str] = None,
    engine: str = "sqlite",
) -> Dict[str, Any]:
    """Run a mobile trips history export and update the ``export_jobs`` row.

    ``task_always_eager=True`` (test environments) runs the job synchronously
    before the enqueuing request returns, so the row is typically already
    ``success``/``error`` by the time the client polls.
    """
    db = DatabaseManager(db_path or Config.DB_PATH, engine=engine or "sqlite")
    try:
        repo = ExportJobRepository(db)
        job = repo.get_raw(job_id)
        if not job:
            logger.error("export_trips_job: job %d not found", job_id)
            return {"error": "export job not found"}

        params = json.loads(job.get("params_json") or "{}")
        fmt = params.get("format", "csv")
        filters = params.get("filters") or {}
        user_id = params.get("user_id", 0)

        result_path = build_trips_export(db, company_id, fmt, filters)
        repo.mark_success(job_id, result_path, company_id)
        logger.info(
            "export_trips_job %d done: format=%s user_id=%d -> %s",
            job_id, fmt, user_id, result_path,
        )
        return {"status": "success", "result_path": result_path}
    except Exception as exc:
        logger.exception("export_trips_job %d failed", job_id)
        try:
            ExportJobRepository(db).mark_error(job_id, str(exc), company_id)
        except Exception:
            logger.exception("export_trips_job %d: failed to mark error", job_id)
        return {"error": str(exc)}
    finally:
        db.close()
