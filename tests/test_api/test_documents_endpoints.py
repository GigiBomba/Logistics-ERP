"""Integration tests for the documents API endpoints (``/api/v1/documents``).

Uses ``client_with_mocks`` for mocked service layer.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/documents"

FAKE_DOC = {
    "id": 1,
    "title": "Invoice 2024-001",
    "category": "invoices",
    "entity_type": "trip",
    "entity_id": 42,
    "mime_type": "application/pdf",
    "file_name": "INV-2024-001.pdf",
    "file_size": 102400,
    "uploaded_by": "user",
    "uploaded_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z",
    "tags": "[]",
    "expiry_date": "",
    "ocr_text": "",
    "ocr_engine": None,
    "extracted_data_json": {},
    "doc_number": "INV-001",
    "is_archived": False,
}


class TestDocumentsListEndpoint:
    """GET /api/v1/documents/"""

    def test_list_documents_returns_200_with_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_result = {"items": [FAKE_DOC], "total": 1, "total_pages": 1}
        mocks["document_service"].advanced_search.return_value = fake_result

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_documents_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_result = {"items": [], "total": 0, "total_pages": 0}
        mocks["document_service"].advanced_search.return_value = fake_result

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_documents_passes_filters(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_result = {"items": [], "total": 0, "total_pages": 0}
        mocks["document_service"].advanced_search.return_value = fake_result

        resp = client.get(
            f"{BASE}/?query=test&category=invoices&entity_type=trip"
            "&date_from=2024-01-01&date_to=2024-12-31"
            "&mime_type=application/pdf&order=title ASC"
            "&page=1&page_size=10"
        )
        assert resp.status_code == 200
        mocks["document_service"].advanced_search.assert_called_once_with(
            query="test", category="invoices", entity_type="trip",
            date_from="2024-01-01", date_to="2024-12-31",
            mime_type="application/pdf", order="title ASC",
            page=1, page_size=10,
        )


class TestDocumentsGetEndpoint:
    """GET /api/v1/documents/{doc_id}"""

    def test_get_document_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = FAKE_DOC

        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["title"] == "Invoice 2024-001"

    def test_get_document_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE}/999")
        assert resp.status_code == 404


class TestDocumentsReadEndpoint:
    """GET /api/v1/documents/{doc_id}/read"""

    def test_read_document_returns_details(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = FAKE_DOC
        mocks["document_service"].get_links.return_value = []
        mocks["document_service"].get_versions.return_value = []

        resp = client.get(f"{BASE}/1/read")
        assert resp.status_code == 200
        body = resp.json()
        assert body["document"]["id"] == 1
        assert body["linked_entities"] == []
        assert body["versions"] == []

    def test_read_document_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE}/999/read")
        assert resp.status_code == 404


class TestDocumentsUploadEndpoint:
    """POST /api/v1/documents/upload"""

    def test_upload_document_success(self, client_with_mocks):
        client, mocks = client_with_mocks
        from unittest.mock import MagicMock
        mocks["document_service"].upload_document.return_value = MagicMock(
            success=True,
            data=MagicMock(model_dump=lambda: {**FAKE_DOC, "id": 10}),
        )

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 sample", "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 10

    def test_upload_document_wrong_mime_type(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.html", b"<html></html>", "text/html")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"].lower()

    def test_upload_document_too_large(self, client_with_mocks):
        client, mocks = client_with_mocks
        oversized = b"x" * (60 * 1024 * 1024)  # 60 MB > 50 MB limit
        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("big.pdf", oversized, "application/pdf")},
        )
        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"].lower()

    def test_upload_document_no_file_returns_422(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/upload")
        assert resp.status_code == 422

    def test_upload_document_with_metadata(self, client_with_mocks):
        client, mocks = client_with_mocks
        from unittest.mock import MagicMock
        mocks["document_service"].upload_document.return_value = MagicMock(
            success=True,
            data=MagicMock(model_dump=lambda: {**FAKE_DOC, "id": 20}),
        )

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("inv.pdf", b"%PDF-1.4", "application/pdf")},
            data={"category": "invoices", "entity_type": "trip",
                  "entity_id": "42", "uploaded_by": "alice"},
        )
        assert resp.status_code == 200
        mocks["document_service"].upload_document.assert_called_once()

    def test_upload_document_service_failure(self, client_with_mocks):
        client, mocks = client_with_mocks
        from unittest.mock import MagicMock
        mocks["document_service"].upload_document.return_value = MagicMock(
            success=False,
            data=None,
        )

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 500


class TestDocumentsUpdateEndpoint:
    """PUT /api/v1/documents/{doc_id}"""

    def test_update_document_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = FAKE_DOC

        resp = client.put(f"{BASE}/1", json={"title": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Invoice 2024-001"
        mocks["document_service"].update.assert_called_once()

    def test_update_document_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = None

        resp = client.put(f"{BASE}/999", json={"title": "Nope"})
        assert resp.status_code == 404


class TestDocumentsDeleteEndpoint:
    """DELETE /api/v1/documents/{doc_id}"""

    def test_delete_document_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].delete.return_value = True

        resp = client.delete(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        mocks["document_service"].delete.assert_called_once_with(1)

    def test_delete_document_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].delete.return_value = False

        resp = client.delete(f"{BASE}/999")
        assert resp.status_code == 404


class TestDocumentsAuth:
    """Authentication gates."""

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].advanced_search.side_effect = RuntimeError("err")
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 500
