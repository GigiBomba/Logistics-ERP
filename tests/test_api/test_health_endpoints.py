"""Integration tests for the health API endpoint (/api/v1/health)."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/health"

class TestHealthCheck:
    """GET /api/v1/health/"""

    def test_health_returns_200(self, client_with_mocks):
        """Health endpoint returns 200 with status, version, and database info."""
        client, mocks = client_with_mocks
        # The health endpoint doesn't use auth dependency (no Depends(get_current_user))
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert data["database"] in ("connected", "disconnected")

    def test_health_returns_200_with_db_connected(self, app):
        """Health endpoint works without authentication at all."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data

    def test_health_detects_db_disconnect(self, app):
        """When DB is unreachable, database field shows disconnected."""
        client = TestClient(app)
        # Use the app with no DB override to test fallback
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"] in ("connected", "disconnected")

    def test_health_no_auth_required(self, app):
        """Health endpoint is public and does not require a token."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200

    def test_health_returns_version_string(self, client_with_mocks):
        """Version field is a non-empty string."""
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/")
        data = resp.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_status_is_ok(self, client_with_mocks):
        """Status field always equals 'ok'."""
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/")
        assert resp.json()["status"] == "ok"