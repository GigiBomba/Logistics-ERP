from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/proformas", tags=["proformas"])


@router.post("/generate")
def generate_proforma(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Generate a proforma invoice PDF.

    Accepts either a nested ``proforma_data`` payload (desktop client) or a
    flat proforma dict.  ``ProformaService.generate_and_record`` persists the
    proforma record and registers the PDF in the Document Center server-side.
    """
    from services.invoicing.proforma_service import ProformaService
    proforma_data = data.get("proforma_data") or data
    svc = ProformaService(db)
    try:
        path = svc.generate_and_record(proforma_data)
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Proforma generation failed")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")
