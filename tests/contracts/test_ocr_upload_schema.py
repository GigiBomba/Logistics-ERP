"""Contract tests for the OCR automation upload (blueprint §5.4).

Validates ``OcrUploadResponse`` (``backend/schemas/ocr.py``) against the
mobile ``ocr_upload_response.dart`` contract:

- document_id (str, Dart String)
- status: Literal["queued", "processing"] — NEVER "completed"
- idempotency_key (str, echoed back)
"""
from __future__ import annotations


from backend.schemas.ocr import OcrUploadResponse

FULL_PAYLOAD = {
    "document_id": "17",
    "status": "queued",
    "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
}


class TestOcrUploadResponseContract:
    """Exact §5.4 response shape."""

    def test_full_payload_round_trips_with_exact_fields(self) -> None:
        resp = OcrUploadResponse.model_validate(FULL_PAYLOAD)
        data = resp.model_dump()
        assert set(data) == {"document_id", "status", "idempotency_key"}
        assert data == FULL_PAYLOAD

    def test_document_id_is_a_string(self) -> None:
        resp = OcrUploadResponse.model_validate(FULL_PAYLOAD)
        assert isinstance(resp.document_id, str)
        assert resp.document_id == "17"

    def test_status_accepts_processing(self) -> None:
        resp = OcrUploadResponse.model_validate(
            {**FULL_PAYLOAD, "status": "processing"}
        )
        assert resp.status == "processing"

    def test_status_never_allows_completed(self) -> None:
        """Blueprint's hard rule: the mobile client never sees 'completed'."""
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OcrUploadResponse.model_validate({**FULL_PAYLOAD, "status": "completed"})

    def test_idempotency_key_echoed(self) -> None:
        resp = OcrUploadResponse.model_validate(FULL_PAYLOAD)
        assert resp.idempotency_key == FULL_PAYLOAD["idempotency_key"]

    def test_unknown_fields_ignored_like_dart(self) -> None:
        """The Dart model reads only its known keys — extracted fields and
        engine details never surface in the serialized payload."""
        resp = OcrUploadResponse.model_validate(
            {**FULL_PAYLOAD, "ocr_text": "LEAK", "extracted_fields": {"x": 1}}
        )
        data = resp.model_dump()
        assert "ocr_text" not in data
        assert "extracted_fields" not in data
