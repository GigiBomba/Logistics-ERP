import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/generate")
async def generate_invoice(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.invoicing.service import InvoiceService
    svc = InvoiceService(db)
    path = svc.generate_and_record(data, mode=data.get("mode", "client"))
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Invoice generation failed")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")


@router.post("/{invoice_id}/send")
async def send_invoice_email(
    invoice_id: int,
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.invoicing.service import InvoiceService
    svc = InvoiceService(db)
    recipient = data.get("recipient", "")
    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient email is required")
    trip_data = data.get("trip_data", {})
    mode = data.get("mode", "client")
    try:
        ok = svc.send_invoice_email(
            trip_id=data.get("trip_id", invoice_id),
            recipient=recipient,
            trip_data=trip_data,
            mode=mode,
        )
        if ok:
            return {"status": "sent", "recipient": recipient}
        return {"status": "failed", "detail": "Email sending failed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
