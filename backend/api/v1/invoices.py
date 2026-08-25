from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.invoice import InvoiceGenerateRequest, InvoiceSendEmailRequest
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _resolve_invoice_number(data: InvoiceGenerateRequest, svc) -> str:
    """Resolve the invoice number to use for the PDF and the DB record.

    A client-supplied ``invoice_number`` is kept as-is (backward compatible).
    When it is missing, empty, or the legacy non-sequence placeholder
    ``INV-{year}-{trip_id:04d}`` (the number ``generate_and_record`` writes
    to the DB), the next number is assigned server-side via the same
    ``invoice_number_sequences`` path the typed ``InvoiceService.create``
    uses (``get_next_number(get_format_key())``).
    """
    provided = (data.invoice_number or "").strip()
    placeholder = f"INV-{datetime.now().year}-{data.trip_id:04d}"
    if not provided or provided == placeholder:
        return svc._invoice_repo.get_next_number(svc.get_format_key())
    return provided


@router.post("/generate")
def generate_invoice(
    data: InvoiceGenerateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.invoicing.service import InvoiceService
    company_id = current_user.get("company_id", 0)
    svc = InvoiceService(db)

    trip_data = data.model_dump()
    inv_number = _resolve_invoice_number(data, svc)
    trip_data["invoice_number"] = inv_number
    # generate_and_record reads the trip id from the "id" key when it
    # persists the DB record — mirror that so the record targets this trip.
    trip_data["id"] = data.trip_id

    path = svc.generate_and_record(trip_data, mode=data.mode, company_id=company_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Invoice generation failed")

    headers = {"X-Invoice-Number": str(inv_number)}
    # generate_and_record persists the invoice row with the non-sequence
    # placeholder INV-{year}-{trip_id:04d}; rewrite it to the resolved number
    # so the DB record matches the PDF.  The row is unique per trip
    # (trip_id is UNIQUE), so get_by_number on the deterministic placeholder
    # identifies exactly the row created by this request.
    if data.mode == "client":
        try:
            placeholder = f"INV-{datetime.now().year}-{data.trip_id:04d}"
            record = svc._invoice_repo.get_by_number(placeholder)
            if record:
                svc._invoice_repo.update(record["id"], {"invoice_number": inv_number})
                headers["X-Invoice-Id"] = str(record["id"])
        except (ValueError, RuntimeError, OSError) as exc:
            logger.warning(
                "Could not rewrite placeholder invoice number for trip %s: %s",
                data.trip_id, exc,
            )
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf",
                        headers=headers)


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
            return {"status": "sent", "recipient": data.recipient_email}
        return {"status": "failed", "detail": "Email sending failed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
