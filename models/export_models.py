from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from .common import ServiceResult


class ExportRequest(BaseModel):
    format: Literal["pdf", "excel", "csv"] = "pdf"
    entity_type: str  # trip, invoice, receipt, cmr, dispatch_board, analytics
    entity_id: Optional[int] = None
    entity_ids: list[int] = []
    template: str = "default"
    filename: str = ""
    include_logo: bool = True
    language: str = "ro"  # ro, en


class ExportResult(BaseModel):
    file_path: str
    format: str
    entity_type: str
    file_size: int
    generated_at: datetime


ExportOperationResult = ServiceResult[ExportResult]
