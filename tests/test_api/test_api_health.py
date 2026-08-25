from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from tests.test_api.helpers import create_test_app

@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_has_status(self, client):
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_has_version(self, client):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "version" in data

    def test_health_has_database(self, client):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "database" in data

    def test_swagger_docs_available(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_available(self, client):
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert spec["info"]["title"] == "Operion ERP API"
        assert "paths" in spec
