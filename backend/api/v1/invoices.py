import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.invoice import InvoiceGenerateRequest, InvoiceSendEmailRequest
from backend.db import DatabaseManager

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/generate")
def generate_invoice(
    data: InvoiceGenerateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.invoicing.service import InvoiceService
    company_id = current_user.get("company_id", 0)
    svc = InvoiceService(db)
    path = svc.generate_and_record(data.model_dump(), mode=data.mode, company_id=company_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Invoice generation failed")
    from backend.posthog_client import get_posthog
    _ph = get_posthog()
    if _ph:
        _ph.capture("invoice_generated", distinct_id=current_user.get("email", ""), properties={
            "company_id": company_id,
            "mode": data.mode,
        })
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")


@router.post("/{invoice_id}/send")
def send_invoice_email(
    invoice_id: int,
    data: InvoiceSendEmailRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.invoicing.service import InvoiceService
    company_id = current_user.get("company_id", 0)
    svc = InvoiceService(db)
    if not data.recipient_email:
        raise HTTPException(status_code=400, detail="Recipient email is required")
    try:
        ok = svc.send_invoice_email(
            trip_id=data.trip_id or invoice_id,
            recipient=data.recipient_email,
            trip_data=data.trip_data or {},
            mode=data.mode,
            company_id=company_id,
        )
        if ok:
            from backend.posthog_client import get_posthog
            _ph = get_posthog()
            if _ph:
                _ph.capture("invoice_sent", distinct_id=current_user.get("email", ""), properties={
                    "company_id": company_id,
                    "invoice_id": invoice_id,
                    "mode": data.mode,
                })
            return {"status": "sent", "recipient": data.recipient_email}
        return {"status": "failed", "detail": "Email sending failed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
