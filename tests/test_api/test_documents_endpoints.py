"""Integration tests for the documents API endpoints (``/api/v1/documents``).

Uses ``client_with_mocks`` for mocked service layer.
"""
from __future__ import annotations

from datetime import date, timedelta
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


class TestDocumentsExpiryEndpoints:
    """GET /api/v1/documents/expiring and GET /api/v1/documents/overdue."""

    @staticmethod
    def _doc(doc_id: int, expiry_date: str) -> dict:
        return {**FAKE_DOC, "id": doc_id, "expiry_date": expiry_date}

    def test_expiring_returns_upcoming_not_expired(self, client_with_mocks):
        client, mocks = client_with_mocks
        today = date.today()
        mocks["document_service"].get_expiring.return_value = [
            self._doc(1, (today + timedelta(days=5)).isoformat()),
            self._doc(2, (today + timedelta(days=1)).isoformat()),
            self._doc(3, (today - timedelta(days=3)).isoformat()),  # expired → excluded
        ]

        resp = client.get(f"{BASE}/expiring?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert {item["id"] for item in data["items"]} == {1, 2}

    def test_expiring_passes_days_to_service(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_expiring.return_value = []

        resp = client.get(f"{BASE}/expiring?days=14")
        assert resp.status_code == 200
        mocks["document_service"].get_expiring.assert_called_once_with(days_ahead=14)

    def test_expiring_defaults_days_to_30(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_expiring.return_value = []

        resp = client.get(f"{BASE}/expiring")
        assert resp.status_code == 200
        mocks["document_service"].get_expiring.assert_called_once_with(days_ahead=30)

    def test_overdue_returns_past_expiries(self, client_with_mocks):
        client, mocks = client_with_mocks
        today = date.today()
        mocks["document_service"].get_overdue.return_value = [
            self._doc(1, (today - timedelta(days=10)).isoformat()),
            self._doc(2, (today - timedelta(days=1)).isoformat()),
        ]

        resp = client.get(f"{BASE}/overdue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert {item["id"] for item in data["items"]} == {1, 2}

    def test_expiring_and_overdue_are_company_scoped(self, app):
        """Both endpoints must pass the JWT company_id to the service."""
        from backend.dependencies import get_document_service
        from backend.dependencies_security import require_dispatcher

        svc = MagicMock()
        svc.get_expiring.return_value = []
        svc.get_overdue.return_value = []
        app.dependency_overrides[get_document_service] = lambda: svc
        app.dependency_overrides[require_dispatcher] = lambda: {
            "id": 1, "email": "test@test.com", "role": "dispatcher",
            "company_id": 1,
        }
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(f"{BASE}/expiring?days=30")
        assert resp.status_code == 200
        svc.get_expiring.assert_called_once_with(days_ahead=30, company_id=1)

        resp = client.get(f"{BASE}/overdue")
        assert resp.status_code == 200
        svc.get_overdue.assert_called_once_with(company_id=1)
