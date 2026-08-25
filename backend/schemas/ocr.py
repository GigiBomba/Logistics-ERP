from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

class OcrRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    engine: str = "auto"


class OcrResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    ocr_text: str
    engine_used: str
    extracted_fields: Dict[str, Any]

    @field_validator("extracted_fields", mode="before")
    @classmethod
    def parse_extracted_fields(cls, value: Any) -> Any:
        """Accept JSON strings from the DB (``extracted_data_json`` is stored
        as text) and normalize them to a dict — mirrors
        ``DocumentResponse.extracted_data_json``."""
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return value if isinstance(value, dict) else {}

    confidence: float = 0.0
    processing_time_ms: int = 0
    # Roadmap 12: lets clients distinguish "not started" (pending),
    # "ran but extracted nothing" (empty), and "ran with text" (done).
    # Defaults keep old consumers working when the fields are not supplied.
    status: str = "pending"
    error: Optional[str] = None


class OcrUploadResponse(BaseModel):
    """Response from ``POST /api/v1/ocr/process`` (blueprint §5.4).

    Hard rule: status is **never** ``completed`` synchronously — the mobile
    client only ever sees ``queued``/``processing``, and extracted fields are
    never returned here.  The ``idempotency_key`` is echoed back so the
    client can confirm deduplication worked.
    """

    document_id: str
    status: Literal["queued", "processing"]
    idempotency_key: str


class OcrFieldExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    fields_to_extract: Optional[List[str]] = None


class OcrFieldExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    fields: Dict[str, Any]
    errors: List[str] = []
