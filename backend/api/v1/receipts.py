import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.receipt import ReceiptGenerateRequest
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/generate")
def generate_receipt(
    data: ReceiptGenerateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    receipt_data = data.receipt_data or data.model_dump(exclude={"receipt_data"}, exclude_none=True)
    if not receipt_data:
        receipt_data = data.model_dump(exclude_none=True)

    from services.invoicing.receipt_generator import ReceiptGenerator
    gen = ReceiptGenerator()
    try:
        path = gen.generate(receipt_data)
    except Exception:
        raise HTTPException(status_code=500, detail="Receipt generation failed")
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Receipt generation failed")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")
