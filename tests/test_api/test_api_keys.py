"""Integration tests for the API key management endpoints (/api/v1/api-keys/).

GET    /api/v1/api-keys/        — list API keys (optional ?partner= filter)
POST   /api/v1/api-keys/        — create a new API key
DELETE /api/v1/api-keys/{id}    — revoke an API key
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.test_api.conftest import StrippedMock

BASE = "/api/v1/api-keys"


class TestListApiKeys:
    """GET /api/v1/api-keys/"""

    def test_list_keys_returns_keys(self, client):
        """Returns 200 with keys and total count."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.list_keys.return_value = [
                {"id": 1, "name": "Test Key", "partner": "timocom"},
                {"id": 2, "name": "Prod Key", "partner": "timocom"},
            ]
            mock_cls.return_value = mock_repo

            resp = client.get(f"{BASE}/")
            assert resp.status_code == 200
            data = resp.json()
            assert "keys" in data
            assert data["total"] == 2
            assert data["keys"][0]["name"] == "Test Key"

    def test_list_keys_empty(self, client):
        """Returns empty keys list when none exist."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.list_keys.return_value = []
            mock_cls.return_value = mock_repo

            resp = client.get(f"{BASE}/")
            assert resp.status_code == 200
            data = resp.json()
            assert data["keys"] == []
            assert data["total"] == 0

    def test_list_keys_with_partner_filter(self, client):
        """Passes the partner query param to list_keys."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.list_keys.return_value = [
                {"id": 1, "name": "Timocom Key", "partner": "timocom"},
            ]
            mock_cls.return_value = mock_repo

            resp = client.get(f"{BASE}/?partner=timocom")
            assert resp.status_code == 200
            mock_repo.list_keys.assert_called_once_with("timocom")
            assert resp.json()["total"] == 1

    def test_list_keys_with_unknown_partner_returns_empty(self, client):
        """Unknown partner filter returns empty keys list."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.list_keys.return_value = []
            mock_cls.return_value = mock_repo

            resp = client.get(f"{BASE}/?partner=nonexistent")
            assert resp.status_code == 200
            assert resp.json()["keys"] == []

    def test_list_keys_requires_auth(self, app):
        """Without auth token, endpoint returns 401."""
        raw_client = TestClient(app)
        resp = raw_client.get(f"{BASE}/")
        assert resp.status_code == 401


class TestCreateApiKey:
    """POST /api/v1/api-keys/"""

    def test_create_key_success(self, client):
        """Returns 200 with key, id, and warning."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.create_key.return_value = (
                "ok_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f",
                42,
            )
            mock_cls.return_value = mock_repo

            resp = client.post(
                f"{BASE}/",
                json={"name": "My Key", "partner": "timocom"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["key"].startswith("ok_")
            assert data["id"] == 42
            assert "warning" in data
            assert "not be shown again" in data["warning"]

    def test_create_key_missing_name_returns_422(self, client):
        """Missing 'name' field returns 422."""
        resp = client.post(f"{BASE}/", json={"partner": "timocom"})
        assert resp.status_code == 422
        assert "name" in resp.json()["detail"].lower() or "'name'" in resp.json()["detail"]

    def test_create_key_missing_partner_returns_422(self, client):
        """Missing 'partner' field returns 422."""
        resp = client.post(f"{BASE}/", json={"name": "My Key"})
        assert resp.status_code == 422
        assert "partner" in resp.json()["detail"].lower() or "'partner'" in resp.json()["detail"]

    def test_create_key_missing_both_returns_422(self, client):
        """Missing both required fields returns 422."""
        resp = client.post(f"{BASE}/", json={})
        assert resp.status_code == 422

    def test_create_key_with_optional_fields(self, client):
        """All optional fields are forwarded to create_key."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.create_key.return_value = ("ok_test", 99)
            mock_cls.return_value = mock_repo

            resp = client.post(
                f"{BASE}/",
                json={
                    "name": "Scoped Key",
                    "partner": "graphhopper",
                    "scopes": ["read", "write"],
                    "created_by": 7,
                    "expires_at": "2027-12-31T23:59:59",
                },
            )
            assert resp.status_code == 200
            mock_repo.create_key.assert_called_once()
            kwargs = mock_repo.create_key.call_args[1]
            assert kwargs["name"] == "Scoped Key"
            assert kwargs["partner"] == "graphhopper"
            assert kwargs["scopes"] == ["read", "write"]
            assert kwargs["created_by"] == 7
            assert kwargs["expires_at"] == "2027-12-31T23:59:59"

    def test_create_key_requires_auth(self, app):
        """Without auth token, endpoint returns 401."""
        raw_client = TestClient(app)
        resp = raw_client.post(f"{BASE}/", json={"name": "X", "partner": "y"})
        assert resp.status_code == 401


class TestRevokeApiKey:
    """DELETE /api/v1/api-keys/{key_id}"""

    def test_revoke_key_success(self, client):
        """Returns 200 with status 'revoked'."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.revoke_key.return_value = True
            mock_cls.return_value = mock_repo

            resp = client.delete(f"{BASE}/42")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "revoked"
            assert data["id"] == 42

    def test_revoke_key_not_found_returns_404(self, client):
        """When key not found or already revoked, returns 404."""
        with patch("backend.repositories.api_key_repository.ApiKeyRepository") as mock_cls:
            mock_repo = StrippedMock()
            mock_repo.revoke_key.return_value = False
            mock_cls.return_value = mock_repo

            resp = client.delete(f"{BASE}/999")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"].lower()

    def test_revoke_key_requires_auth(self, app):
        """Without auth token, endpoint returns 401."""
        raw_client = TestClient(app)
        resp = raw_client.delete(f"{BASE}/1")
        assert resp.status_code == 401
