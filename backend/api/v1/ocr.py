from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.dependencies import get_document_service
from backend.dependencies_security import require_dispatcher
from backend.schemas.ocr import OcrRequest, OcrResult

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/run", response_model=OcrResult)
async def run_ocr(
    request: OcrRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    try:
        doc = service.get_by_id(request.document_id)
    except Exception:
        raise HTTPException(status_code=500, detail="OCR service error")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return OcrResult(
        document_id=request.document_id,
        ocr_text=doc.get("ocr_text", ""),
        engine_used=doc.get("ocr_engine", "none"),
        extracted_fields=doc.get("extracted_data_json", {}),
    )


@router.get("/status/{doc_id}", response_model=OcrResult)
async def get_ocr_status(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    try:
        doc = service.get_by_id(doc_id)
    except Exception:
        raise HTTPException(status_code=500, detail="OCR service error")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return OcrResult(
        document_id=doc_id,
        ocr_text=doc.get("ocr_text", ""),
        engine_used=doc.get("ocr_engine", "none"),
        extracted_fields=doc.get("extracted_data_json", {}),
    )


@router.post("/batch", response_model=List[OcrResult])
async def run_ocr_batch(
    doc_ids: List[int],
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    results: List[Dict[str, Any]] = []
    for doc_id in doc_ids:
        doc = service.get_by_id(doc_id)
        if doc:
            results.append(
                OcrResult(
                    document_id=doc_id,
                    ocr_text=doc.get("ocr_text", ""),
                    engine_used=doc.get("ocr_engine", "none"),
                    extracted_fields=doc.get("extracted_data_json", {}),
                )
            )
    return results
