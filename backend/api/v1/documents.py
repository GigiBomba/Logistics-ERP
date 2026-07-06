import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from backend.dependencies import get_document_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.document import (
    DocumentLinkResponse,
    DocumentReadResult,
    DocumentResponse,
    DocumentUpdate,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
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
    result["items"] = [DocumentResponse(**doc) for doc in result["items"]]
    return PaginatedResponse(**result)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    service=Depends(get_document_service),
):
    doc = service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.get("/{doc_id}/read", response_model=DocumentReadResult)
async def read_document_info(
    doc_id: int,
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


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(""),
    entity_type: str = Form(""),
    entity_id: Optional[int] = Form(None),
    uploaded_by: str = Form("user"),
    service=Depends(get_document_service),
):
    import os
    import tempfile

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or ".bin")[1])  # noqa: SIM115
    try:
        content = await file.read()
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


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: int,
    update: DocumentUpdate,
    service=Depends(get_document_service),
):
    service.update(doc_id, **update.model_dump(exclude_none=True))
    doc = service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    service=Depends(get_document_service),
):
    success = service.delete(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted"}
