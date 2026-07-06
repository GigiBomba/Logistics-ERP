import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from backend.dependencies import get_db
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/tacho", tags=["tacho"])


@router.post("/import", status_code=201)
async def import_tacho_file(
    file: UploadFile = File(...),
    db: DatabaseManager = Depends(get_db),
):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".ddd")  # noqa: SIM115
    try:
        content = await file.read()
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
    limit: int = Query(50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db),
):
    from repositories.tacho_import_repository import TachoImportRepository
    repo = TachoImportRepository(db)
    rows = repo.get_recent(limit=limit)
    return {"items": rows, "total": len(rows)}


@router.get("/status")
async def get_tacho_status(
    db: DatabaseManager = Depends(get_db),
):
    from services.tacho_service import TachoService
    svc = TachoService(db)
    return {"status": "ok", "data": str(svc)}
