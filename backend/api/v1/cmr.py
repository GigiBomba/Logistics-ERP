import os
import tempfile
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/cmr", tags=["cmr"])


@router.post("/generate")
async def generate_cmr(
    data: Dict[str, Any],
    db: DatabaseManager = Depends(get_db),
):
    trip_data = data.get("trip_data", {})
    if not trip_data:
        raise HTTPException(status_code=400, detail="trip_data is required")

    from services.invoicing.cmr_generator import CMRGenerator
    gen = CMRGenerator(db)
    output_dir = tempfile.mkdtemp(prefix="cmr_")
    try:
        result = gen.generate_all_copies(trip_data, output_dir=output_dir)
        if isinstance(result, dict):
            first_valid = next((v for v in result.values() if v and os.path.isfile(v)), None)
            if first_valid:
                return FileResponse(first_valid, filename=os.path.basename(first_valid),
                                    media_type="application/pdf")
            raise HTTPException(status_code=500, detail="CMR generation produced no files")
        if isinstance(result, str) and os.path.isfile(result):
            return FileResponse(result, filename=os.path.basename(result),
                                media_type="application/pdf")
        raise HTTPException(status_code=500, detail="CMR generation failed")
    finally:
        try:
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            pass
