from typing import Any, Dict, List, Optional

from pydantic import BaseModel

class OcrRequest(BaseModel):
    document_id: int
    engine: str = "auto"


class OcrResult(BaseModel):
    document_id: int
    ocr_text: str
    engine_used: str
    extracted_fields: Dict[str, Any]
    confidence: float = 0.0
    processing_time_ms: int = 0


class OcrFieldExtractionRequest(BaseModel):
    document_id: int
    fields_to_extract: Optional[List[str]] = None


class OcrFieldExtractionResponse(BaseModel):
    document_id: int
    fields: Dict[str, Any]
    errors: List[str] = []
