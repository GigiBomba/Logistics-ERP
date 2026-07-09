import os
import tempfile
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/tacho", tags=["tacho"])


ALLOWED_TACHO_MIME_TYPES = {
    "application/octet-stream", "application/x-ddd", "",
}
MAX_TACHO_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/import", status_code=201)
async def import_tacho_file(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    file: UploadFile = File(...),
    db: DatabaseManager = Depends(get_db),
):
    content = await file.read()
    if len(content) > MAX_TACHO_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_TACHO_UPLOAD_SIZE // (1024*1024)} MB.",
        )

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".ddd")  # noqa: SIM115
    try:
        temp.write(content)
        temp.close()
        from services.tacho_service import TachoService
        svc = TachoService(db)
        result = svc.import_ddd_file(temp.name)
        return {"status": "imported", "result": str(result)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if os.path.isfile(temp.name):
            os.unlink(temp.name)


@router.get("/import-history")
async def get_tacho_import_history(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    limit: int = Query(50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db),
):
    from repositories.tacho_import_repository import TachoImportRepository
    repo = TachoImportRepository(db)
    rows = repo.get_recent(limit=limit)
    return {"items": rows, "total": len(rows)}


@router.get("/status")
async def get_tacho_status(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.tacho_service import TachoService
    try:
        svc = TachoService(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok", "data": str(svc)}
