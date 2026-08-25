from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from backend.db import DatabaseManager
from backend.dependencies import get_db, get_document_service
from backend.dependencies_security import require_dispatcher
from backend.middleware.input_sanitizer import sanitize_filename, sanitize_free_text
from backend.schemas.common import PaginatedResponse
from backend.schemas.document import (
    DocumentLinkResponse,
    DocumentReadResult,
    DocumentResponse,
    DocumentUpdate,
)
from database.time_utils import utc_now_iso

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=PaginatedResponse[DocumentResponse])
def list_documents(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    query: str = Query("", description="Search query"),
    category: str = Query("", description="Document category filter"),
    entity_type: str = Query("", description="Entity type filter"),
    date_from: str = Query("", description="Start date (YYYY-MM-DD)"),
    date_to: str = Query("", description="End date (YYYY-MM-DD)"),
    mime_type: str = Query("", description="MIME type filter"),
    order: str = Query("uploaded_at DESC", description="Sort order"),
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
    service=Depends(get_document_service),
):
    company_id = current_user.get("company_id", 0)
    result = service.advanced_search(
        query=query,
        company_id=company_id,
        category=category,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
        mime_type=mime_type,
        order=order,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[DocumentResponse(**doc) for doc in result["items"]],
        total=result["total"],
        total_pages=result["total_pages"],
    )


@router.get("/categories")
def document_categories(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Distinct non-empty document categories with counts (company-scoped).

    Registered BEFORE ``/{doc_id}`` so a GET on ``/documents/categories`` is
    never captured as a document id lookup.  Archived and empty categories are
    excluded.
    """
    company_id = current_user["company_id"]
    rows = db.execute(
        "SELECT category, COUNT(*) AS count FROM documents "
        "WHERE company_id = ? AND category != '' AND is_archived = 0 "
        "GROUP BY category ORDER BY category",
        (company_id,),
    ).fetchall()
    return [{"category": r["category"], "count": r["count"]} for r in rows]


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    company_id = current_user.get("company_id", 0)
    doc = service.get_by_id(doc_id, company_id=company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.get("/{doc_id}/read", response_model=DocumentReadResult)
def read_document_info(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    company_id = current_user.get("company_id", 0)
    doc = service.get_by_id(doc_id, company_id=company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    links = service.get_links(doc_id) if hasattr(service, "get_links") else []
    versions = service.get_versions(doc_id) if hasattr(service, "get_versions") else []

    tags_str = doc.get("tags", "[]")
    try:
        tag_list = json.loads(tags_str) if isinstance(tags_str, str) else tags_str
    except (json.JSONDecodeError, TypeError):
        tag_list = []

    expiry = doc.get("expiry_date", "")

    import datetime
    is_expired = bool(expiry and expiry < datetime.date.today().isoformat())

    return DocumentReadResult(
        document=DocumentResponse(**doc),
        ocr_text=doc.get("ocr_text", ""),
        extracted_fields=(
            json.loads(doc["extracted_data_json"])
            if isinstance(doc.get("extracted_data_json"), str)
            else doc.get("extracted_data_json", {})
        ),
        linked_entities=[DocumentLinkResponse(**lk) for lk in links] if links else [],
        versions=versions if versions else [],
        tags=tag_list if isinstance(tag_list, list) else [],
        expiry=expiry,
        is_expired=is_expired,
    )


ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf", "image/jpeg", "image/png", "image/tiff",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain", "text/csv",
}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


def _validate_upload(file: UploadFile) -> None:
    if file.content_type and file.content_type not in ALLOWED_DOCUMENT_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' is not allowed. "
                   f"Allowed types: {', '.join(sorted(ALLOWED_DOCUMENT_MIME_TYPES))}",
        )
    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
        )


@router.post("/upload", response_model=DocumentResponse)
def upload_document(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    file: UploadFile = File(...),
    category: str = Form(""),
    entity_type: str = Form(""),
    entity_id: Optional[int] = Form(None),
    uploaded_by: str = Form("user"),
    service=Depends(get_document_service),
):
    _validate_upload(file)

    # Sanitize user-supplied filename before any use — prevents path
    # traversal, injection via filename metadata, and control characters.
    raw_filename = file.filename or "upload.bin"
    safe_filename = sanitize_filename(raw_filename)
    # Also sanitize form-supplied metadata fields.
    safe_category = sanitize_free_text(category, max_length=100)
    safe_entity_type = sanitize_free_text(entity_type, max_length=50)

    import os
    import tempfile

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(safe_filename)[1])  # noqa: SIM115
    try:
        content = file.file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
            )
        temp.write(content)
        temp.close()

        from models.document_models import DocumentUpload
        user_id = current_user.get("id", 0)
        result = service.upload_document(
            DocumentUpload(
                source_path=temp.name,
                title=sanitize_free_text(os.path.splitext(safe_filename)[0], max_length=255),
                category=safe_category,
                entity_type=safe_entity_type,
                entity_id=entity_id,
            ),
            user_id=user_id,
        )
        if result.success:
            # Prefer the upload result payload when it already carries the
            # full response shape (services/mocks returning a complete row).
            dumped = getattr(result.data, "model_dump", None)
            if callable(dumped):
                payload = dumped()
                if isinstance(payload, dict) and "file_name" in payload and "doc_number" in payload:
                    return DocumentResponse(**payload)
            # Fall back to the persisted row (same path as GET
            # /documents/{doc_id}); the intermediate DocumentResult model
            # lacks doc_number/file_name/uploaded_by/uploaded_at and stores
            # updated_at as datetime, so serializing it 422s the response.
            doc_id = getattr(result.data, "id", None)
            doc = service.get_by_id(
                doc_id, company_id=current_user.get("company_id", 0),
            )
            if doc:
                return DocumentResponse(**doc)
            raise HTTPException(status_code=500, detail="Upload failed")
        raise HTTPException(status_code=500, detail="Upload failed")
    finally:
        os.unlink(temp.name)


@router.post("/{doc_id}/file")
def upload_document_file(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    file: UploadFile = File(...),
    skip_ocr: str = Form("false"),
    db: DatabaseManager = Depends(get_db),
    service=Depends(get_document_service),
):
    """Upload a document's binary file to an existing document row (Phase C).

    The desktop sync lane pushes local files here with ``skip_ocr=true`` so
    OCR is not re-triggered every sync cycle (the desktop's OCR text is
    already carried by the row sync).  Same-hash re-uploads are deduplicated —
    the file is not stored twice (the sync retry case returns the existing row).
    """
    company_id = current_user.get("company_id", 0)
    doc = service.get_by_id(doc_id, company_id=company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content = file.file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
        )
    file_hash = hashlib.sha256(content).hexdigest()

    # Dedup: identical content is already stored on this server row — but only
    # when the stored file actually exists (a deleted file + row hash must not
    # report deduped:true forever).
    stored = doc.get("file_path") or ""
    if (
        doc.get("file_hash") == file_hash
        and stored
        and os.path.isfile(stored)
    ):
        return {"status": "ok", "deduped": True, "id": doc_id, "file_hash": file_hash}

    from services.document.upload_service import DOCUMENTS_ROOT, UploadService

    raw_name = sanitize_filename(file.filename or "document.bin")
    safe_name = raw_name or "document.bin"
    target_dir = UploadService._ensure_category_dir(doc.get("category") or "other")
    # R2 (security): defense-in-depth containment — the sanitized target dir
    # must stay under DOCUMENTS_ROOT.
    root_real = os.path.realpath(DOCUMENTS_ROOT)
    if not os.path.realpath(target_dir).startswith(root_real + os.sep):
        raise HTTPException(status_code=400, detail="Invalid document category")
    target_path = UploadService._unique_path(target_dir, safe_name)
    with open(target_path, "wb") as out:
        out.write(content)

    now = utc_now_iso()
    db.execute(
        "UPDATE documents SET file_path = ?, file_hash = ?, file_size = ?, "
        "updated_at = ? WHERE id = ? AND company_id = ?",
        (target_path, file_hash, len(content), now, doc_id, company_id),
    )
    db.commit()

    # OCR-once: only enqueue OCR when the caller asks (manual upload); the
    # sync push passes skip_ocr=true and relies on the desktop's OCR text.
    if skip_ocr.lower() != "true":
        mime_type = doc.get("mime_type", "")
        if mime_type == "application/pdf" or mime_type.startswith("image/"):
            service.ocr.enqueue_ocr(doc_id, target_path, mime_type)

    return {"status": "ok", "deduped": False, "id": doc_id, "file_hash": file_hash}


@router.get("/{doc_id}/file")
def download_document_file(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    """Serve a document's binary file (company-scoped) — Phase C.

    Registered AFTER ``/{doc_id}`` so the metadata GET keeps precedence for
    id-only lookups.
    """
    company_id = current_user.get("company_id", 0)
    doc = service.get_by_id(doc_id, company_id=company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = doc.get("file_path") or ""
    if not path:
        raise HTTPException(status_code=404, detail="Document file not found")
    # R1 (security): file_path is attacker-influenced via the sync payload —
    # only serve files inside DOCUMENTS_ROOT.  Use 404 (not 403) so the
    # containment check does not leak whether a path exists.
    from services.document.upload_service import DOCUMENTS_ROOT

    real = os.path.realpath(path)
    root_real = os.path.realpath(DOCUMENTS_ROOT)
    if real != root_real and not real.startswith(root_real + os.sep):
        raise HTTPException(status_code=404, detail="Document file not found")
    if not os.path.isfile(real):
        raise HTTPException(status_code=404, detail="Document file not found")
    # Content-Disposition: attachment + a whitelisted media type (a
    # client-controlled mime_type must never be served inline as stored XSS).
    media_type = doc.get("mime_type") or "application/octet-stream"
    if media_type not in ALLOWED_DOCUMENT_MIME_TYPES:
        media_type = "application/octet-stream"
    return FileResponse(
        real,
        media_type=media_type,
        filename=doc.get("file_name") or os.path.basename(real),
        content_disposition_type="attachment",
    )


@router.patch("/{doc_id}", response_model=DocumentResponse)
def update_document_partial(
    doc_id: int,
    update: DocumentUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    """Partially update a document (PATCH)."""
    company_id = current_user.get("company_id", 0)
    service.update(doc_id, company_id=company_id, **update.model_dump(exclude_none=True))
    doc = service.get_by_id(doc_id, company_id=company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.put("/{doc_id}", response_model=DocumentResponse, deprecated=True)
def update_document(
    doc_id: int,
    update: DocumentUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /{doc_id} instead."""
    company_id = current_user.get("company_id", 0)
    service.update(doc_id, company_id=company_id, **update.model_dump(exclude_none=True))
    doc = service.get_by_id(doc_id, company_id=company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return DocumentResponse(**doc)


@router.delete("/{doc_id}")
def delete_document(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    company_id = current_user.get("company_id", 0)
    success = service.delete(doc_id, company_id=company_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}
