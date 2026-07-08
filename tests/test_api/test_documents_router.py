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

        with pytest.raises(RuntimeError, match="DB error"):
            client.get(f"{BASE}/")

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
