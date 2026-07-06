import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/generate")
async def generate_receipt(
    data: Dict[str, Any],
    db: DatabaseManager = Depends(get_db),
):
    receipt_data = data.get("receipt_data", {})
    if not receipt_data:
        receipt_data = data

    from services.invoicing.receipt_generator import ReceiptGenerator
    gen = ReceiptGenerator()
    path = gen.generate(receipt_data)
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Receipt generation failed")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")
