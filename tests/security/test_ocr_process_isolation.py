"""OCR automation upload (``POST /api/v1/ocr/process``) — isolation tests.

Blueprint §5.4 + §1.7 + §1.8 (Gate 1 adjudication — D2 IMPLEMENT):
- ``Idempotency-Key`` header is REQUIRED; missing → 4xx with a clear message;
- the response is ``OcrUploadResponse{document_id, status: queued|processing,
  idempotency_key}`` — extracted fields are NEVER returned synchronously;
- the uploaded image persists as a company-scoped document row (documents
  table, ``category='ocr_results'``) so Local Download can later pull it;
- the same ``Idempotency-Key`` twice → exactly one document (dedupe via the
  repo's idempotency middleware);
- company Y cannot read company X's OCR document/result.

Uses the shared module-scoped fixtures from ``tests/security/conftest.py``
(client, auth_a, auth_b).
"""
from __future__ import annotations

import sqlite3
import uuid

import pytest

from backend.security import create_access_token

_OCR_PROCESS_URL = "/api/v1/ocr/process"

# A tiny but valid-looking PNG header (the upload path does not decode pixels).
_PNG_HEADER = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _unique_png() -> bytes:
    """Return a unique PNG payload per call.

    The upload service dedupes by file content hash, so every upload in the
    test suite must carry distinct bytes to create distinct documents.
    """
    return _PNG_HEADER + str(uuid.uuid4()).encode("utf-8")


def _doc_company_id(db_path: str, doc_id: str) -> int | None:
    """Return the company_id of a document row directly from the test DB."""
    conn = sqlite3.connect(db_path, timeout=3)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT company_id FROM documents WHERE id = ?", (int(doc_id),)
        ).fetchone()
        return row["company_id"] if row else None
    finally:
        conn.close()


def _doc_count(db_path: str, doc_id: str) -> int:
    """Count document rows with *doc_id* directly from the test DB."""
    conn = sqlite3.connect(db_path, timeout=3)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM documents WHERE id = ?", (int(doc_id),)
        ).fetchone()[0]
    finally:
        conn.close()


def _upload(client, headers: dict, key: str, content: bytes | None = None) -> "object":
    return client.post(
        _OCR_PROCESS_URL,
        files={"file": ("scan.png", content or _unique_png(), "image/png")},
        headers={**headers, "Idempotency-Key": key},
    )


class TestOcrProcessUpload:
    """Upload contract — shape, status literal, no sync extracted fields."""

    def test_upload_returns_contract_shape(
        self, client, auth_a: dict,
    ) -> None:
        key = str(uuid.uuid4())
        resp = _upload(client, auth_a, key)
        assert resp.status_code == 201, f"OCR upload failed: {resp.text}"

        body = resp.json()
        # Exact blueprint §5.4 shape — nothing more, nothing less.
        assert set(body.keys()) == {"document_id", "status", "idempotency_key"}
        assert isinstance(body["document_id"], str) and body["document_id"]
        assert body["status"] in ("queued", "processing"), (
            f"status must be queued/processing, got {body['status']}"
        )
        assert body["idempotency_key"] == key
        # Hard rule: extracted fields never appear synchronously.
        assert "ocr_text" not in body
        assert "extracted_fields" not in body
        assert "engine_used" not in body

    def test_upload_persists_document_scoped_to_company(
        self, client, auth_a: dict, test_db_path: str,
    ) -> None:
        key = str(uuid.uuid4())
        resp = _upload(client, auth_a, key)
        assert resp.status_code == 201, f"OCR upload failed: {resp.text}"
        doc_id = resp.json()["document_id"]

        assert _doc_company_id(test_db_path, doc_id) == 1, (
            f"Document {doc_id} must be scoped to company 1"
        )

    def test_missing_idempotency_key_rejected(
        self, client, auth_a: dict,
    ) -> None:
        resp = client.post(
            _OCR_PROCESS_URL,
            files={"file": ("scan.png", _unique_png(), "image/png")},
            headers=auth_a,
        )
        assert resp.status_code == 400, (
            f"Missing Idempotency-Key should be 400, got {resp.status_code}: {resp.text}"
        )
        assert "Idempotency" in resp.json().get("detail", "")

    def test_unauthorized_rejected(self, client) -> None:
        resp = client.post(
            _OCR_PROCESS_URL,
            files={"file": ("scan.png", _unique_png(), "image/png")},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    def test_disallowed_file_type_rejected(self, client, auth_a: dict) -> None:
        resp = client.post(
            _OCR_PROCESS_URL,
            files={"file": ("evil.exe", b"MZ\x90\x00", "application/x-msdownload")},
            headers={**auth_a, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp.status_code == 400


class TestOcrProcessIdempotency:
    """Same Idempotency-Key twice → exactly one document (dedupe)."""

    def test_same_key_twice_creates_exactly_one_document(
        self, client, test_db_path: str,
    ) -> None:
        key = str(uuid.uuid4())
        # The idempotency middleware tenant-scopes keys from the JWT's
        # ``company_id`` claim (R1).  Login-issued tokens carry only
        # ``sub``/``role`` (see ``_issue_tokens`` in backend/api/v1/auth.py),
        # so the middleware would skip caching and re-run the endpoint on the
        # second POST.  Send a company-scoped token so dedupe is actually
        # exercised — same pattern as tests/readiness/test_middleware.py.
        company_headers = {
            "Authorization": "Bearer " + create_access_token(
                {"sub": "dispatcher-a@test.com", "role": "dispatcher", "company_id": 1}
            )
        }
        first = _upload(client, company_headers, key)
        assert first.status_code == 201, f"First upload failed: {first.text}"
        first_doc = first.json()["document_id"]

        second = _upload(client, company_headers, key)
        # The idempotency middleware replays the cached response — the
        # endpoint never runs a second time.  (Under TestClient the replayed
        # body is empty — documented limitation at
        # tests/readiness/test_middleware.py — so dedupe is asserted via the
        # replay header + a direct row count below, not the body.)
        assert second.status_code == 201, f"Second upload failed: {second.text}"
        assert second.headers.get("Idempotency-Replayed") == "true"

        # Exactly one document row created for this key's document_id.
        count = _doc_count(test_db_path, first_doc)
        assert count == 1, f"Expected exactly one document row, found {count}"

    def test_distinct_keys_create_distinct_documents(
        self, client, auth_a: dict,
    ) -> None:
        first = _upload(client, auth_a, str(uuid.uuid4()))
        second = _upload(client, auth_a, str(uuid.uuid4()))
        assert first.status_code == 201 and second.status_code == 201
        assert first.json()["document_id"] != second.json()["document_id"]


class TestOcrProcessCompanyIsolation:
    """Company Y cannot read company X's OCR document/result."""

    def test_company_b_cannot_read_company_a_ocr_document(
        self, client, auth_a: dict, auth_b: dict,
    ) -> None:
        key = str(uuid.uuid4())
        resp = _upload(client, auth_a, key)
        assert resp.status_code == 201, f"OCR upload failed: {resp.text}"
        doc_id = resp.json()["document_id"]

        # Company B reading A's document via the documents API → 404.
        r = client.get(f"/api/v1/documents/{doc_id}", headers=auth_b)
        assert r.status_code == 404, (
            f"Company B should not read Company A's OCR document, got {r.status_code}"
        )

        # Company B reading A's OCR status/result → 404.
        r = client.get(f"/api/v1/ocr/status/{doc_id}", headers=auth_b)
        assert r.status_code == 404, (
            f"Company B should not read Company A's OCR result, got {r.status_code}"
        )

    def test_company_a_can_read_own_ocr_document(
        self, client, auth_a: dict,
    ) -> None:
        key = str(uuid.uuid4())
        resp = _upload(client, auth_a, key)
        assert resp.status_code == 201, f"OCR upload failed: {resp.text}"
        doc_id = resp.json()["document_id"]

        r = client.get(f"/api/v1/documents/{doc_id}", headers=auth_a)
        assert r.status_code == 200, f"Owner should read own document: {r.text}"
        body = r.json()
        assert body.get("category") == "ocr_results"
