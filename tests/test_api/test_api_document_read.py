"""Test the enhanced document read endpoint."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_document_service
from backend.main import create_app

SAMPLE_DOC = {
    "id": 1,
    "doc_number": "DOC-2026-0001",
    "title": "Test Document",
    "category": "trips",
    "entity_type": "trip",
    "entity_id": 42,
    "file_name": "test.pdf",
    "file_size": 1024,
    "mime_type": "application/pdf",
    "uploaded_by": "user",
    "uploaded_at": "2026-01-15T10:00:00",
    "updated_at": "2026-01-15T10:00:00",
    "is_archived": False,
    "ocr_run_at": "2026-01-15T11:00:00",
    "ocr_engine": "auto",
    "ocr_text": "Extracted OCR text content",
    "extracted_data_json": json.dumps({"client": "ACME Corp", "amount": "1500.00"}),
    "tags": json.dumps(["invoice", "urgent"]),
    "is_signed": False,
    "cmr_number": "",
    "description": "",
    "expiry_date": "2027-06-15",
}


class MockDocumentService:
    def get_by_id(self, doc_id: int):
        if doc_id == 1:
            return dict(SAMPLE_DOC)
        return None

    def get_links(self, doc_id: int):
        if doc_id == 1:
            return [
                {
                    "id": 1,
                    "document_id": 1,
                    "linked_entity_type": "trip",
                    "linked_entity_id": 42,
                    "relation_type": "attached",
                    "created_at": "2026-01-15T10:00:00",
                }
            ]
        return []

    def get_versions(self, doc_id: int):
        if doc_id == 1:
            return [
                {
                    "id": 1,
                    "document_id": 1,
                    "version_number": 1,
                    "file_path": "/tmp/v1.pdf",
                    "file_size": 512,
                    "file_hash": "abc123",
                    "comment": "Initial upload",
                    "uploaded_by": "user",
                    "created_at": "2026-01-15T10:00:00",
                }
            ]
        return []


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_document_service] = lambda: MockDocumentService()
    return TestClient(app)


def test_read_document_info(client):
    response = client.get("/api/v1/documents/1/read")
    assert response.status_code == 200
    data = response.json()

    assert data["document"]["id"] == 1
    assert data["document"]["title"] == "Test Document"
    assert data["ocr_text"] == "Extracted OCR text content"
    assert data["extracted_fields"] == {"client": "ACME Corp", "amount": "1500.00"}
    assert len(data["linked_entities"]) == 1
    assert data["linked_entities"][0]["linked_entity_type"] == "trip"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1
    assert "invoice" in data["tags"]
    assert "urgent" in data["tags"]
    assert data["expiry"] == "2027-06-15"
    assert data["is_expired"] is False


def test_read_document_not_found(client):
    response = client.get("/api/v1/documents/99999/read")
    assert response.status_code == 404
