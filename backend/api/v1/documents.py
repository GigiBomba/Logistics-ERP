import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

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
            return DocumentResponse(**result.data.model_dump())
        raise HTTPException(status_code=500, detail="Upload failed")
    finally:
        os.unlink(temp.name)


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
