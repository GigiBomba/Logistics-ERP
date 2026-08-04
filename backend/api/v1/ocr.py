import json
import os
import tempfile
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile

from backend.dependencies import get_document_service
from backend.dependencies_security import require_dispatcher
from backend.middleware.input_sanitizer import sanitize_filename
from backend.schemas.ocr import OcrRequest, OcrResult, OcrUploadResponse
from services.document_automation.sanitizer import sanitize_ocr_text_safe

router = APIRouter(prefix="/ocr", tags=["ocr"])

# OCR upload accepts camera captures (blueprint §6.4 Automation tab) plus
# PDFs so the desktop Document Center can reuse the same endpoint shape.
ALLOWED_OCR_MIME_TYPES = {
    "image/jpeg", "image/png", "image/tiff", "application/pdf",
}
MAX_OCR_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


def _sanitize_ocr_response(doc: dict[str, Any]) -> dict[str, Any]:
    """Sanitize OCR text in a document dict before returning via API.

    Provides defense-in-depth for any OCR text already stored in the
    database that wasn't sanitized at write time.
    """
    doc = dict(doc)
    raw_ocr = doc.get("ocr_text", "")
    if raw_ocr:
        doc["ocr_text"] = sanitize_ocr_text_safe(raw_ocr)
    raw_extracted = doc.get("extracted_data_json")
    if raw_extracted and isinstance(raw_extracted, str):
        try:
            parsed = json.loads(raw_extracted)
            if isinstance(parsed, dict) and "raw_text" in parsed:
                parsed["raw_text"] = sanitize_ocr_text_safe(parsed["raw_text"])
            doc["extracted_data_json"] = json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
    elif raw_extracted and isinstance(raw_extracted, dict):
        parsed = dict(raw_extracted)
        if "raw_text" in parsed:
            parsed["raw_text"] = sanitize_ocr_text_safe(parsed["raw_text"])
        doc["extracted_data_json"] = parsed
    return doc


def _derive_ocr_status(doc: dict[str, Any]) -> str:
    """Best-effort OCR status derived from what the DB actually stores.

    The ``documents`` table carries ``ocr_text`` / ``ocr_run_at`` /
    ``ocr_engine`` but **no** ``ocr_status`` / ``ocr_error`` columns, so the
    status is derived (roadmap 12 — no new columns invented):
      - no ``ocr_run_at``               → ``pending`` (queued / not started)
      - ``ocr_run_at`` + empty text     → ``empty``   (ran, extracted nothing;
        indistinguishable from a hard failure without an error column)
      - ``ocr_run_at`` + non-empty text → ``done``
    """
    if not doc.get("ocr_run_at"):
        return "pending"
    if doc.get("ocr_text"):
        return "done"
    return "empty"


@router.post("/process", response_model=OcrUploadResponse, status_code=201)
def process_ocr_upload(
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    """Upload an image for async OCR processing (blueprint §5.4).

    Contract (hard rules):
      - ``Idempotency-Key`` header is **required**; a retried upload after a
        dropped connection reuses the same key and the idempotency middleware
        deduplicates — exactly one document is created.
      - The response is ``OcrUploadResponse`` with ``status`` always
        ``queued``/``processing`` — extracted fields are **never** returned
        synchronously.  The result stays server-side until an explicit
        Local Download (``ocr_results`` category) request.
      - ``company_id`` comes from the JWT only; the created document row is
        company-scoped.
    """
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing required 'Idempotency-Key' header — generate a UUID "
                "once per upload action and reuse it across retries."
            ),
        )

    if not file.content_type or file.content_type not in ALLOWED_OCR_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Allowed types: {', '.join(sorted(ALLOWED_OCR_MIME_TYPES))}"
            ),
        )

    raw_filename = file.filename or "ocr_upload.png"
    safe_filename = sanitize_filename(raw_filename)

    # Write into a dedicated temp dir under the sanitized filename so the
    # stored document keeps a meaningful ``file_name`` (used by Local Download).
    temp_dir = tempfile.mkdtemp(prefix="ocr_process_")
    temp_path = os.path.join(temp_dir, safe_filename)
    try:
        content = file.file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        if len(content) > MAX_OCR_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_OCR_UPLOAD_SIZE // (1024 * 1024)} MB.",
            )
        with open(temp_path, "wb") as fh:
            fh.write(content)

        from models.document_models import DocumentUpload

        user_id = current_user.get("id", 0)
        # company_id flows through upload_document → UploadService.upload →
        # DocumentRepository.create so the row is CREATED company-scoped in
        # the single INSERT.  There is no post-insert UPDATE window where
        # the row exists unscoped (blueprint §1.8 / Gate-2 M2).
        result = service.upload_document(
            DocumentUpload(
                source_path=temp_path,
                category="ocr_results",
                entity_type="ocr",
                description="Uploaded via mobile OCR automation (async)",
                tags=["ocr", "mobile_automation"],
            ),
            user_id=user_id,
            company_id=current_user.get("company_id"),
        )
        if not result.success or not result.data:
            raise HTTPException(status_code=500, detail="OCR upload failed")

        document_id = result.data.id

        # The upload pipeline has already enqueued the document for the
        # background OCR worker queue — the response must never block on it.
        return OcrUploadResponse(
            document_id=str(document_id),
            status="queued",
            idempotency_key=idempotency_key,
        )
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/run", response_model=OcrResult)
def run_ocr(
    request: OcrRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    company_id = current_user.get("company_id", 0)
    try:
        doc = service.get_by_id(request.document_id, company_id=company_id)
    except Exception:
        raise HTTPException(status_code=500, detail="OCR service error")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = _sanitize_ocr_response(doc)
    return OcrResult(
        document_id=request.document_id,
        ocr_text=doc.get("ocr_text", ""),
        engine_used=doc.get("ocr_engine", "none"),
        extracted_fields=doc.get("extracted_data_json", {}),
        status=_derive_ocr_status(doc),
    )


@router.get("/status/{doc_id}", response_model=OcrResult)
def get_ocr_status(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    company_id = current_user.get("company_id", 0)
    try:
        doc = service.get_by_id(doc_id, company_id=company_id)
    except Exception:
        raise HTTPException(status_code=500, detail="OCR service error")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = _sanitize_ocr_response(doc)
    return OcrResult(
        document_id=doc_id,
        ocr_text=doc.get("ocr_text", ""),
        engine_used=doc.get("ocr_engine", "none"),
        extracted_fields=doc.get("extracted_data_json", {}),
        status=_derive_ocr_status(doc),
    )


@router.post("/batch", response_model=List[OcrResult])
def run_ocr_batch(
    doc_ids: List[int],
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    company_id = current_user.get("company_id", 0)
    results: List[OcrResult] = []
    for doc_id in doc_ids:
        doc = service.get_by_id(doc_id, company_id=company_id)
        if doc:
            doc = _sanitize_ocr_response(doc)
            results.append(
                OcrResult(
                    document_id=doc_id,
                    ocr_text=doc.get("ocr_text", ""),
                    engine_used=doc.get("ocr_engine", "none"),
                    extracted_fields=doc.get("extracted_data_json", {}),
                    status=_derive_ocr_status(doc),
                )
            )
    return results
