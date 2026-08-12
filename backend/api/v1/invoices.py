import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.invoice import InvoiceSendEmailRequest
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/generate")
def generate_invoice(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.invoicing.service import InvoiceService
    svc = InvoiceService(db)
    # Multi-tenant: the company_id is derived from the authenticated user —
    # never from the request body — so an invoice is always created inside
    # the caller's own tenant.
    company_id = current_user.get("company_id", 0) or 0
    # Accept either a nested ``trip_data`` payload (desktop client) or the
    # flat trip dict (legacy / load-test callers).  ``generate_and_record``
    # persists the invoice record and registers the PDF in the Document
    # Center server-side.
    trip_data = data.get("trip_data") or data
    mode = data.get("mode", "client")
    path = svc.generate_and_record(trip_data, mode=mode, company_id=company_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Invoice generation failed")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")


@router.post("/{invoice_id}/send")
def send_invoice_email(
    invoice_id: int,
    data: InvoiceSendEmailRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.invoicing.service import InvoiceService
    svc = InvoiceService(db)
    if not data.recipient:
        raise HTTPException(status_code=400, detail="Recipient email is required")
    try:
        ok = svc.send_invoice_email(
            trip_id=data.trip_id or invoice_id,
            recipient=data.recipient,
            trip_data=data.trip_data or {},
            mode=data.mode,
            company_id=current_user.get("company_id", 0) or 0,
        )
        if ok:
            return {"status": "sent", "recipient": data.recipient}
        return {"status": "failed", "detail": "Email sending failed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
