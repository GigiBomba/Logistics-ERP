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


class TestLoadDocuments:
    """Load tests for /api/v1/documents/ endpoints."""

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
        svc.advanced_search.return_value = {"items": [], "total": 0, "total_pages": 1}
        svc.get_by_id.return_value = {
            "id": 1, "file_name": "test.pdf", "file_size": 1024, "doc_number": "DOC-001",
            "category": "invoice", "entity_type": "trip", "entity_id": 1,
            "mime_type": "application/pdf", "uploaded_by": "user",
            "uploaded_at": "2026-07-09T00:00:00", "updated_at": "2026-07-09T00:00:00",
            "tags": "[]", "expiry_date": "", "is_archived": False,
            "ocr_text": "", "ocr_engine": "", "extracted_data_json": "{}",
            "is_signed": False, "cmr_number": "",
        }
        svc.upload_document.return_value = MagicMock(success=True, data=MagicMock(model_dump=lambda: {
            "id": 1, "file_name": "test.pdf", "file_size": 1024, "doc_number": "DOC-001",
            "category": "invoice", "entity_type": "trip", "entity_id": 1,
            "mime_type": "application/pdf", "uploaded_by": "user",
            "uploaded_at": "2026-07-09T00:00:00", "updated_at": "2026-07-09T00:00:00",
            "tags": [], "expiry_date": "", "is_archived": False,
            "ocr_text": "", "ocr_engine": "", "extracted_data_json": {},
            "is_signed": False, "cmr_number": "",
        }))
        svc.update.return_value = None
        svc.delete.return_value = True
        app.dependency_overrides[get_document_service] = lambda: svc

        yield TestClient(app)

        app.dependency_overrides.clear()

    # ── test 1: document search concurrency ───────────────────────────────

    def test_document_search_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/documents/")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"document_search success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 2: document upload concurrency ───────────────────────────────

    def test_document_upload_concurrency(self, client):
        def make_request():
            return client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")},
                data={"category": "invoice", "entity_type": "trip"},
            )

        for n in [1, 5, 10]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"document_upload success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 3: document get by id concurrency ────────────────────────────

    def test_document_get_by_id_concurrency(self, client):
        def make_request():
            return client.get("/api/v1/documents/1")

        for n in [1, 10, 50, 100]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"document_get_by_id success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 4: document update concurrency ───────────────────────────────

    def test_document_update_concurrency(self, client):
        payload = {"category": "contract", "tags": ["important"]}

        def make_request():
            return client.put("/api/v1/documents/1", json=payload)

        for n in [1, 10, 50]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"document_update success_rate={success_rate:.3f} < 0.99 at n={n}"

    # ── test 5: document delete concurrency ───────────────────────────────

    def test_document_delete_concurrency(self, client):
        def make_request():
            return client.delete("/api/v1/documents/1")

        for n in [1, 10]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.99, f"document_delete success_rate={success_rate:.3f} < 0.99 at n={n}"
