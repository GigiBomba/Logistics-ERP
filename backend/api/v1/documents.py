import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

from backend.dependencies import get_document_service, get_db
from backend.dependencies_security import require_dispatcher
from backend.errors import ErrorCode
from backend.schemas.common import PaginatedResponse
from backend.schemas.document import (
    DocumentLinkCreate,
    DocumentLinkResponse,
    DocumentLinkUpdate,
    DocumentReadResult,
    DocumentResponse,
    DocumentUpdate,
)
from backend.uploads import (
    DOCUMENT_SAFE_EXTENSIONS,
    sanitize_filename,
    strip_exif,
    validate_magic_bytes,
)
from database.db_manager import DatabaseManager

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
    result = service.advanced_search(
        query=query,
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


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    doc = service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.get("/{doc_id}/read", response_model=DocumentReadResult)
def read_document_info(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    doc = service.get_by_id(doc_id)
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

    import os
    import tempfile

    # ── Hardening (blueprint §18c.2) ──────────────────────────────────
    # 1) Filename sanitization: basename + whitelisted extension only.
    safe_name = sanitize_filename(file.filename, allow_extensions=DOCUMENT_SAFE_EXTENSIONS)
    if not safe_name:
        raise HTTPException(
            status_code=415,
            detail={
                "error_code": ErrorCode.UNSUPPORTED_MEDIA_TYPE.value,
                "detail": "Filename is invalid or has a disallowed extension.",
            },
        )
    ext = os.path.splitext(safe_name)[1].lower()

    # 2) Read + size cap.
    content = file.file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
        )

    # 3) Magic-byte sniffing — never trust MIME/extension alone.
    if not validate_magic_bytes(content, file.content_type):
        raise HTTPException(
            status_code=415,
            detail={
                "error_code": ErrorCode.UNSUPPORTED_MEDIA_TYPE.value,
                "detail": "File content does not match its declared type.",
            },
        )

    # 4) EXIF stripping for JPEG payloads (before persistence).
    if (file.content_type or "").lower() == "image/jpeg":
        content = strip_exif(content)

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)  # noqa: SIM115
    try:
        temp.write(content)
        temp.close()

        result = service.upload(
            source_path=temp.name,
            category=category,
            entity_type=entity_type,
            entity_id=entity_id,
            uploaded_by=uploaded_by,
        )
        if result:
            return DocumentResponse(**result)
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
    service.update(doc_id, **update.model_dump(exclude_none=True))
    doc = service.get_by_id(doc_id)
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
    service.update(doc_id, **update.model_dump(exclude_none=True))
    doc = service.get_by_id(doc_id)
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
    success = service.delete(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}


# ── Document links ─────────────────────────────────────────────────

@router.get("/{doc_id}/links", response_model=List[DocumentLinkResponse])
def list_document_links(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    """List all links attached to a document."""
    links = service.get_links(doc_id) if hasattr(service, "get_links") else []
    return [DocumentLinkResponse(**lk) for lk in links]


@router.post("/{doc_id}/links", response_model=DocumentLinkResponse)
def create_document_link(
    doc_id: int,
    link: DocumentLinkCreate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service=Depends(get_document_service),
):
    """Attach a document to an entity (e.g. proforma/trip/invoice)."""
    ok = service.link_document(
        doc_id, link.linked_entity_type, link.linked_entity_id,
        relation_type=link.relation_type,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to link document")
    for lk in service.get_links(doc_id):
        if (lk.get("linked_entity_type") == link.linked_entity_type
                and lk.get("linked_entity_id") == link.linked_entity_id):
            return DocumentLinkResponse(**lk)
    raise HTTPException(status_code=500, detail="Link created but could not be returned")


@router.put("/links/{link_id}", response_model=DocumentLinkResponse)
def update_document_link(
    link_id: int,
    update: DocumentLinkUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Update a link (e.g. backfill a placeholder entity_id=0 with the real id)."""
    from repositories.document_repository import DocumentRepository
    repo = DocumentRepository(db)
    link = repo.get_link_by_id(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    repo.update_link_entity_id_by_link_id(link_id, update.linked_entity_id)
    updated = repo.get_link_by_id(link_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Link update failed")
    return DocumentLinkResponse(**updated)


@router.delete("/links/{link_id}")
def delete_document_link(
    link_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Remove a document link."""
    from repositories.document_repository import DocumentRepository
    repo = DocumentRepository(db)
    link = repo.get_link_by_id(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    repo.remove_link(link_id)
    return {"status": "deleted", "link_id": link_id}
