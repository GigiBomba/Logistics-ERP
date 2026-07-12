from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from .common import ServiceResult


class DocumentUpload(BaseModel):
    source_path: str
    title: str = Field(default="", validate_default=True)
    category: str = ""  # invoice, cmr, receipt, contract, other
    entity_type: str = ""  # trip, client, vehicle, driver
    entity_id: Optional[int] = None
    description: str = ""
    tags: list[str] = []

    @field_validator("title", mode="before")
    @classmethod
    def title_defaults_to_filename(cls, v: str, info) -> str:
        if not v and "source_path" in info.data:
            import os
            return os.path.splitext(os.path.basename(info.data["source_path"]))[0]
        return v


class DocumentResult(BaseModel):
    id: int
    title: str
    category: str
    entity_type: str
    entity_id: Optional[int] = None
    filename: str
    file_size: int
    mime_type: str
    tags: list[str] = []
    description: str = ""
    ocr_processed: bool = False
    thumbnail_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


DocumentUploadResult = ServiceResult[DocumentResult]
DocumentListResult = ServiceResult[list[DocumentResult]]
