from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.receipt import ReceiptGenerateRequest
from backend.db import DatabaseManager

router = APIRouter(prefix="/receipts", tags=["receipts"])

# Default receipt number hard-coded in ReceiptGenerator.generate when the
# receipt_data payload has no receipt_number — a non-sequence placeholder.
_GENERATOR_DEFAULT_RECEIPT_NUMBER = "RCT-000000"


def _resolve_receipt_number(receipt_data: Dict[str, Any], db: DatabaseManager) -> str:
    """Resolve the receipt number for a /generate request.

    A client-supplied ``receipt_number`` is kept as-is (backward compatible).
    When it is missing, empty, or the generator's non-sequence default
    ``RCT-000000``, the next number is assigned server-side via the same
    ``invoice_number_sequences`` path the typed
    ``ReceiptService.generate_and_record`` uses
    (``get_next_number(format_key)``).
    """
    provided = (receipt_data.get("receipt_number") or "").strip()
    if not provided or provided == _GENERATOR_DEFAULT_RECEIPT_NUMBER:
        from services.invoicing.receipt_service import ReceiptService
        svc = ReceiptService(db)
        fmt_key = receipt_data.get("_format_key", svc.get_format_key())
        return svc.get_next_number(format_key=fmt_key)
    return provided


@router.post("/generate")
def generate_receipt(
    data: ReceiptGenerateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    receipt_data = data.receipt_data or data.model_dump(exclude={"receipt_data"}, exclude_none=True)
    if not receipt_data:
        receipt_data = data.model_dump(exclude_none=True)

    # Resolve the receipt number server-side so the PDF carries a sequence
    # number instead of the generator's RCT-000000 placeholder in remote mode.
    receipt_number = _resolve_receipt_number(receipt_data, db)
    receipt_data["receipt_number"] = receipt_number

    from services.invoicing.receipt_generator import ReceiptGenerator
    gen = ReceiptGenerator()
    try:
        path = gen.generate(receipt_data)
    except Exception:
        raise HTTPException(status_code=500, detail="Receipt generation failed")
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Receipt generation failed")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf",
                        headers={"X-Receipt-Number": str(receipt_number)})
