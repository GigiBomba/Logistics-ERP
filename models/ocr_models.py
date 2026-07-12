from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from .common import ServiceResult


class OcrProcessRequest(BaseModel):
    document_id: int
    language: str = "auto"
    extract_fields: bool = True
    match_to_trips: bool = True


class ExtractedFields(BaseModel):
    document_number: Optional[str] = None
    document_date: Optional[str] = None
    client_name: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    reference: Optional[str] = None
    raw_text: str = ""
    confidence: float = 0.0
    additional_fields: dict[str, str] = {}


class MatchedTrip(BaseModel):
    trip_id: int
    trip_reference: str
    confidence: float
    match_reason: str = ""


class OcrResult(BaseModel):
    document_id: int
    success: bool
    extracted_fields: ExtractedFields = ExtractedFields()
    matched_trips: list[MatchedTrip] = []
    processing_time_ms: float = 0.0
    error_message: str = ""
    processed_at: Optional[datetime] = None


OcrProcessResult = ServiceResult[OcrResult]
