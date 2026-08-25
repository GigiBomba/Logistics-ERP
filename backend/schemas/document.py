from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

def _parse_json_str(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


class DocumentBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    category: str = ""
    entity_type: str = ""
    entity_id: Optional[int] = None
    tags: Optional[List[str]] = None
    description: str = ""
    expiry_date: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(extra="ignore")

    id: int
    doc_number: str
    file_name: str
    file_size: int
    mime_type: str
    uploaded_by: str
    uploaded_at: str
    updated_at: str
    is_archived: bool = False
    ocr_run_at: Optional[str] = None
    ocr_engine: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_data_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_signed: bool = False
    cmr_number: str = ""

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, value: Any) -> Any:
        parsed = _parse_json_str(value)
        if isinstance(parsed, list):
            return parsed
        return []

    @field_validator("extracted_data_json", mode="before")
    @classmethod
    def parse_extracted(cls, value: Any) -> Any:
        parsed = _parse_json_str(value)
        if isinstance(parsed, dict):
            return parsed
        return {}


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    expiry_date: Optional[str] = None


class DocumentLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linked_entity_type: str
    linked_entity_id: int
    relation_type: str = "attached"


class DocumentLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    document_id: int
    linked_entity_type: str
    linked_entity_id: int
    relation_type: str
    created_at: str


class DocumentReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: DocumentResponse
    ocr_text: str = ""
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    linked_entities: List[DocumentLinkResponse] = Field(default_factory=list)
    versions: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    expiry: str = ""
    is_expired: bool = False
