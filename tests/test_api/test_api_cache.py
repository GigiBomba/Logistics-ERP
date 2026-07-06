"""Test that the FastAPI app boots without Redis (graceful degradation)."""
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app

@pytest.fixture
def client():
    app = create_app()
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
