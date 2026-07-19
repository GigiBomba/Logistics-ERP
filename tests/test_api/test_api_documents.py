
import pytest
from fastapi.testclient import TestClient

from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from backend.main import create_app
from tests.test_api.helpers import create_test_app


@pytest.fixture
def client():
    app = create_test_app()
    mock_user = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_dispatcher] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
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
