"""Celery task for the mobile tachograph import pipeline (export_jobs table).

``import_tacho_job`` runs the REAL ``TachoService`` import pipeline (binary
probe → parser → ``_process_driver_card``, which persists activity rows) and
stores the compliance result JSON in the ``export_jobs`` row.  The honest
parser-missing error is surfaced verbatim (``No tachograph parser found ...``).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from backend.celery_app.celery import celery_app
from backend.db import DatabaseManager
from backend.desktop_config import Config
from repositories.export_job_repository import ExportJobRepository
from services.tacho_service import TachoService

logger = logging.getLogger(__name__)

EU_MAX_WEEKLY_DRIVING_MINUTES = 3360


def _build_compliance(rows) -> Dict[str, Any]:
    """Build the TachoComplianceResult-shaped dict from persisted activity rows.

    Mirrors the dispatcher/driver tacho timeline aggregation (the same
    buckets + EU 56h/2wk weekly cap) so the mobile poll endpoint can parse
    it with ``TachoComplianceResult(**json.loads(result_path))``.
    """
    days = []
    weekly_driving_minutes = 0
    violations = []
    for r in rows:
        r = dict(r)
        day = (r.get("activity_date") or "")[:10]
        driving = int(r.get("driving_minutes") or 0)
        weekly_driving_minutes += driving
        days.append({
            "date": day,
            "driving_minutes": driving,
            "working_minutes": int(r.get("work_minutes") or 0),
            "rest_minutes": int(r.get("rest_minutes") or 0),
            "availability_minutes": int(r.get("avail_minutes") or 0),
        })
        raw_v = r.get("violations")
        if raw_v:
            try:
                parsed = json.loads(raw_v) if isinstance(raw_v, str) else raw_v
                if isinstance(parsed, list):
                    violations.extend(str(v) for v in parsed)
            except (ValueError, TypeError):
                pass
    days.sort(key=lambda d: d["date"])
    # EU weekly cap (Regulation 561/2006): a per-week driving total over 56h is
    # a violation in its own right, surfaced verbatim like the daily ones.
    if weekly_driving_minutes > EU_MAX_WEEKLY_DRIVING_MINUTES:
        violations.append(
            f"Weekly driving {weekly_driving_minutes // 60}h"
            f"{weekly_driving_minutes % 60}m exceeds 56h limit"
        )
    return {
        "days": days,
        "weekly_driving_minutes": weekly_driving_minutes,
        "weekly_limit_minutes": EU_MAX_WEEKLY_DRIVING_MINUTES,
        "violations": violations,
    }


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def import_tacho_job(
    self,
    job_id: int,
    company_id: int,
    db_path: Optional[str] = None,
    engine: str = "sqlite",
) -> Dict[str, Any]:
    """Run a tacho file import and store the compliance result on the job.

    The REAL ``TachoService`` pipeline runs (``import_ddd_file`` — the typed
    ``import_file`` wrapper delegates to the same parser flow but requires an
    admin role context the Celery worker does not carry).  On success the
    compliance JSON is written to the job's ``result_path`` column; on failure
    the honest error message (e.g. parser binary missing) is recorded.
    """
    db = DatabaseManager(db_path or Config.DB_PATH, engine=engine or "sqlite")
    try:
        repo = ExportJobRepository(db)
        job = repo.get_raw(job_id)
        if not job:
            logger.error("import_tacho_job: job %d not found", job_id)
            return {"error": "tacho import job not found"}

        params = json.loads(job.get("params_json") or "{}")
        file_path = params.get("file_path", "")
        if not file_path or not os.path.isfile(file_path):
            repo.mark_error(job_id, "Tacho file not found", company_id)
            return {"error": "tacho file not found"}

        svc = TachoService(db)
        raw = svc.import_ddd_file(file_path, company_id=company_id)
        if not raw.get("success"):
            err = raw.get("error") or "Tacho import failed"
            logger.warning("import_tacho_job %d failed: %s", job_id, err)
            repo.mark_error(job_id, str(err), company_id)
            return {"error": str(err)}

        import_id = raw.get("import_id")
        rows = svc.tacho_driver_activity_repository.get_by_import(import_id) if import_id else []
        compliance = _build_compliance(rows)
        repo.mark_success(job_id, json.dumps(compliance), company_id)
        logger.info(
            "import_tacho_job %d done: import_id=%s days=%d weekly=%d",
            job_id, import_id, len(compliance["days"]), compliance["weekly_driving_minutes"],
        )
        return {"status": "success", "import_id": import_id}
    except Exception as exc:
        logger.exception("import_tacho_job %d failed", job_id)
        try:
            ExportJobRepository(db).mark_error(job_id, str(exc), company_id)
        except Exception:
            logger.exception("import_tacho_job %d: failed to mark error", job_id)
        return {"error": str(exc)}
    finally:
        db.close()
