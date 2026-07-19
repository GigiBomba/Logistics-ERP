"""Test that the FastAPI app boots without Redis (graceful degradation)."""
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


class TestApiWithoutRedis:
    def test_health_still_works(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_documents_still_work(self, client):
        response = client.get("/api/v1/documents/")
        assert response.status_code == 200

    def test_document_read_not_found(self, client):
        response = client.get("/api/v1/documents/99999/read")
        assert response.status_code == 404
