"""Tests for the documents API router (``/api/v1/documents``)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/documents"


class TestDocumentsRouter:
    """CRUD + query + error handling for document endpoints."""

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

    # ── list ───────────────────────────────────────────────────────────────

    def test_list_documents_returns_200_with_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_result = {
            "items": [self.FAKE_DOC],
            "total": 1,
            "total_pages": 1,
        }
        mocks["document_service"].advanced_search.return_value = fake_result

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["total_pages"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Invoice 2024-001"

    def test_list_documents_passes_query_params(self, client_with_mocks):
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
            query="test",
            category="invoices",
            entity_type="trip",
            date_from="2024-01-01",
            date_to="2024-12-31",
            mime_type="application/pdf",
            order="title ASC",
            page=1,
            page_size=10,
        )

    # ── get by id ──────────────────────────────────────────────────────────

    def test_get_document_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = self.FAKE_DOC

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
        assert resp.json()["detail"] == "Document not found"

    # ── read (detail) ──────────────────────────────────────────────────────

    def test_get_document_read_returns_200_with_links_and_versions(
        self, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = self.FAKE_DOC
        mocks["document_service"].get_links.return_value = []
        mocks["document_service"].get_versions.return_value = []

        resp = client.get(f"{BASE}/1/read")
        assert resp.status_code == 200
        body = resp.json()
        assert body["document"]["id"] == 1
        assert body["linked_entities"] == []
        assert body["versions"] == []

    # ── update ─────────────────────────────────────────────────────────────

    def test_update_document_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = self.FAKE_DOC

        resp = client.put(f"{BASE}/1", json={"title": "Updated title"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Invoice 2024-001"
        mocks["document_service"].update.assert_called_once()

    # ── delete ─────────────────────────────────────────────────────────────

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
        assert resp.json()["detail"] == "Document not found"

    # ── error handling ─────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].advanced_search.side_effect = RuntimeError("DB error")

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 500

    # ── upload ─────────────────────────────────────────────────────────────

    def test_upload_document_success(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_result = {**self.FAKE_DOC, "id": 10}
        mocks["document_service"].upload.return_value = fake_result

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 sample content", "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 10
        assert body["title"] == "Invoice 2024-001"
        mocks["document_service"].upload.assert_called_once()

    def test_upload_document_wrong_mime_type(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.html", b"<html></html>", "text/html")},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"].lower()
        mocks["document_service"].upload.assert_not_called()

    def test_upload_document_too_large(self, client_with_mocks):
        client, mocks = client_with_mocks
        oversized = b"x" * (60 * 1024 * 1024)  # 60 MB

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("big.pdf", oversized, "application/pdf")},
        )
        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"].lower()
        mocks["document_service"].upload.assert_not_called()

    def test_upload_document_service_failure(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].upload.return_value = None

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")},
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Upload failed"

    def test_upload_document_no_file(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/upload")
        assert resp.status_code == 422

    def test_upload_document_with_metadata(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_result = {**self.FAKE_DOC, "id": 20, "category": "invoices"}
        mocks["document_service"].upload.return_value = fake_result

        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("inv.pdf", b"%PDF-1.4 invoice", "application/pdf")},
            data={
                "category": "invoices",
                "entity_type": "trip",
                "entity_id": "42",
                "uploaded_by": "alice",
            },
        )
        assert resp.status_code == 200
        mocks["document_service"].upload.assert_called_once()
        call_kwargs = mocks["document_service"].upload.call_args[1]
        assert call_kwargs["category"] == "invoices"
        assert call_kwargs["entity_type"] == "trip"
        assert call_kwargs["entity_id"] == 42
        assert call_kwargs["uploaded_by"] == "alice"

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
