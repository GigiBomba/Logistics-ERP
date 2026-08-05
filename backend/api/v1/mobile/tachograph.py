"""Mobile tachograph endpoints (blueprint §6.7, Phase 4A).

  - POST /mobile/tacho/import (multipart: driver_id + .ddd/.esm file) -> 202
        {job_id}  [can_upload_document — dispatcher allowed]
        Creates an ``export_jobs`` row (``kind='tacho_import'``), saves the
        uploaded bytes and dispatches the Celery ``import_tacho_job`` task.
  - GET  /mobile/tacho/import/{job_id}/status -> {status, result?, error?}
        [can_upload_document]
        Polls the job; on success returns the REAL TachoComplianceResult
        (days / weekly driving / weekly_limit 3360 / verbatim violations).
        On failure the honest error message is returned (e.g. the external
        parser binary ``tools/tachograph/tachograph.exe`` is not installed).

The parse itself runs through the REAL desktop ``TachoService.import_ddd_file``
pipeline (binary probe -> parser -> ``_process_driver_card``); this module only
wires the upload + job lifecycle.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.config import BackendSettings
from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.schemas.mobile import (
    TACHO_ALLOWED_EXTENSIONS,
    TachoComplianceResult,
    TachoImportJobResponse,
    TachoImportJobStatusResponse,
)
from repositories.export_job_repository import ExportJobRepository
from services.permission_service import PermissionService

router = APIRouter(prefix="/tacho", tags=["mobile_tacho"])


def _check_upload_permission(db: DatabaseManager, user_id: int) -> None:
    """Gate tacho endpoints with the real PermissionService (can_upload_document)."""
    if not user_id:
        return
    result = PermissionService(db).can_upload_document(user_id)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Permission denied")


def get_tacho_upload_dir() -> str:
    """Return the uploaded-tacho staging directory, creating it if necessary."""
    upload_dir = BackendSettings().tacho_upload_dir or "data/tacho_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


@router.post("/import", response_model=TachoImportJobResponse, status_code=202)
def import_tacho_file(
    driver_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Upload a tachograph file for async parsing (gate: can_upload_document).

    The file is validated (extension ``.ddd``/``.esm``, driver belongs to the
    company), staged to disk, and an ``export_jobs`` row (kind='tacho_import')
    is created before the Celery task is dispatched.  Returns 202 {job_id}.
    """
    _check_upload_permission(db, current_user.get("id") or 0)
    company_id = current_user["company_id"]

    driver = db.execute(
        "SELECT id FROM drivers WHERE id = ? AND company_id = ?",
        (driver_id, company_id),
    ).fetchone()
    if not driver:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "driver_not_found", "detail": "Driver not found in this company."},
        )

    filename = (file.filename or "upload.ddd").strip()
    ext = os.path.splitext(filename)[1].lower()
    if ext not in TACHO_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "invalid_file_type",
                "detail": f"File type must be one of {', '.join(TACHO_ALLOWED_EXTENSIONS)}.",
            },
        )

    data = file.file.read()
    if not data:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "empty_file", "detail": "The uploaded file is empty."},
        )

    saved_path = os.path.join(
        get_tacho_upload_dir(), f"tacho_{uuid.uuid4().hex}{ext}"
    )
    with open(saved_path, "wb") as fh:
        fh.write(data)

    job_id = ExportJobRepository(db).create(
        kind="tacho_import",
        params={
            "driver_id": driver_id,
            "file_path": saved_path,
            "file_name": filename,
        },
        company_id=company_id,
        status="processing",
    )

    from backend.celery_app.tasks.export_tasks import _extract_db_path
    from backend.celery_app.tasks.tacho_tasks import import_tacho_job

    import_tacho_job.apply_async(  # type: ignore[attr-defined]
        args=(job_id, company_id),
        kwargs={"db_path": _extract_db_path(db), "engine": getattr(db, "_engine", "sqlite")},
    )
    return TachoImportJobResponse(job_id=job_id)


@router.get("/import/{job_id}/status", response_model=TachoImportJobStatusResponse)
def tacho_import_status(
    job_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Poll a tacho import job (gate: can_upload_document).

    Returns ``{status, result?, error?}`` — ``result`` is the compliance
    payload on success; ``error`` carries the honest message on failure
    (e.g. parser binary not installed).
    """
    _check_upload_permission(db, current_user.get("id") or 0)
    company_id = current_user["company_id"]

    job = ExportJobRepository(db).get(job_id, company_id=company_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "job_not_found", "detail": "Import job not found."},
        )

    status = job.get("status") or "processing"
    result: Optional[TachoComplianceResult] = None
    if status == "success" and job.get("result_path"):
        try:
            result = TachoComplianceResult(**json.loads(job["result_path"]))
        except (ValueError, TypeError, json.JSONDecodeError):
            result = None
    return TachoImportJobStatusResponse(
        status=status, result=result, error=job.get("error"),
    )
