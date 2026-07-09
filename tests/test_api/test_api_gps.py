"""Tests for GPS telemetry endpoints."""
import os

os.environ["OPERION_DB_PATH"] = ":memory:"


import pytest
from fastapi.testclient import TestClient

from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from backend.main import create_app


@pytest.fixture(autouse=True)
def _reset_redis_url(monkeypatch):
    """Other test modules may pollute OPERION_REDIS_URL — reset to a valid default."""
    monkeypatch.setenv("OPERION_REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def client():
    app = create_app()
    mock_user = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_dispatcher] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    return TestClient(app)


class TestGpsIngest:
    def test_ingest_single_ping(self, client):
        data = {
            "truck_id": 1,
            "latitude": 44.4268,
            "longitude": 26.1025,
            "speed_kmh": 85.0,
            "heading": 180,
            "timestamp": "2026-07-04T12:00:00Z",
        }
        response = client.post("/api/v1/fleet/gps/ingest", json=data)
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"

    def test_ingest_batch(self, client):
        pings = [
            {
                "truck_id": 1,
                "latitude": 44.4,
                "longitude": 26.1,
                "speed_kmh": 80.0,
                "heading": 90,
                "timestamp": "2026-07-04T12:01:00Z",
            },
            {
                "truck_id": 2,
                "latitude": 44.5,
                "longitude": 26.2,
                "speed_kmh": 60.0,
                "heading": 270,
                "timestamp": "2026-07-04T12:02:00Z",
            },
        ]
        response = client.post("/api/v1/fleet/gps/batch", json=pings)
        assert response.status_code == 202
        assert response.json()["count"] == 2

    def test_live_position_not_found(self, client):
        response = client.get("/api/v1/fleet/gps/live/99999")
        assert response.status_code == 404

    def test_gps_history_empty(self, client):
        response = client.get("/api/v1/fleet/gps/history/1")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
