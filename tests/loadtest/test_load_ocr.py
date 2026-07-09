from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from backend.dependencies import get_document_service
from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow


class TestLoadOcr:
    """Load tests for /api/v1/ocr/ endpoints."""

    MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(api_v1_router)
        return app

    @pytest.fixture
    def client(self, app):
        app.dependency_overrides[get_current_user] = lambda: self.MOCK_USER
        app.dependency_overrides[require_dispatcher] = lambda: self.MOCK_USER
        app.dependency_overrides[require_admin] = lambda: self.MOCK_USER

        svc = MagicMock()
        svc.get_by_id.return_value = {
            "id": 1,
            "file_name": "doc.pdf",
            "file_size": 2048,
            "doc_number": "DOC-001",
            "ocr_text": "extracted text",
            "ocr_engine": "tesseract",
            "extracted_data_json": {},
            "category": "invoice",
            "entity_type": "trip",
            "entity_id": 1,
            "mime_type": "application/pdf",
            "uploaded_by": "user",
            "uploaded_at": "2026-07-09T00:00:00",
            "updated_at": "2026-07-09T00:00:00",
            "tags": "[]",
            "expiry_date": "",
            "is_archived": False,
            "is_signed": False,
            "cmr_number": "",
        }
        app.dependency_overrides[get_document_service] = lambda: svc

        yield TestClient(app)

        app.dependency_overrides.clear()

    # ── test 1: OCR batch large payload concurrency ───────────────────────

    def test_ocr_batch_large_payload(self, client):
        doc_ids = list(range(1, 101))

        def make_request():
            return client.post("/api/v1/ocr/batch", json=doc_ids)

        for n in [1, 5, 10]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"ocr_batch success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 2: OCR status polling under load ─────────────────────────────

    def test_ocr_status_polling_under_load(self, client):
        def make_request():
            return client.get("/api/v1/ocr/status/1")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"ocr_status success_rate={success_rate:.3f} < 0.99 at n={n}"
