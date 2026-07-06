
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_list_documents_empty(client):
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_get_document_not_found(client):
    response = client.get("/api/v1/documents/99999")
    assert response.status_code == 404


def test_read_document_info_not_found(client):
    response = client.get("/api/v1/documents/99999/read")
    assert response.status_code == 404


def test_ocr_status_not_found(client):
    response = client.get("/api/v1/ocr/status/99999")
    assert response.status_code == 404
