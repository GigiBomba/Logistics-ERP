"""Tests for the OAuth2 client management API endpoints.

GET    /oauth2/clients              — list all clients (optionally by partner)
POST   /oauth2/clients              — register a new client
DELETE /oauth2/clients/{client_id}  — revoke a client
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/oauth2"


class TestOAuth2ListClients:
    """GET /api/v1/oauth2/clients"""

    def test_list_success(self, client):
        """List all clients returns 200 with clients list."""
        with patch("backend.api.v1.oauth2.OAuth2Service") as mock_svc_class:
            mock_svc = MagicMock()
            mock_svc.list_clients.return_value = [
                {"client_id": "abc", "secret_hash": "xxx", "name": "test"},
                {"client_id": "def", "secret_hash": "yyy", "name": "test2"},
            ]
            mock_svc_class.return_value = mock_svc

            resp = client.get(f"{BASE}/clients")

        assert resp.status_code == 200
        data = resp.json()
        assert "clients" in data
        assert len(data["clients"]) == 2
        mock_svc.list_clients.assert_called_once_with(None)

    def test_list_with_partner_filter(self, client):
        """List clients with partner filter returns filtered results."""
        with patch("backend.api.v1.oauth2.OAuth2Service") as mock_svc_class:
            mock_svc = MagicMock()
            mock_svc.list_clients.return_value = [
                {"client_id": "abc", "secret_hash": "xxx", "name": "test", "partner": "partner_a"},
            ]
            mock_svc_class.return_value = mock_svc

            resp = client.get(f"{BASE}/clients", params={"partner": "partner_a"})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["clients"]) == 1
        assert data["clients"][0]["client_id"] == "abc"
        mock_svc.list_clients.assert_called_once_with("partner_a")

    def test_list_excludes_secret_hash(self, client):
        """secret_hash must not appear in the response."""
        with patch("backend.api.v1.oauth2.OAuth2Service") as mock_svc_class:
            mock_svc = MagicMock()
            mock_svc.list_clients.return_value = [
                {"client_id": "abc", "secret_hash": "should_not_leak", "name": "test"},
            ]
            mock_svc_class.return_value = mock_svc

            resp = client.get(f"{BASE}/clients")

        assert resp.status_code == 200
        data = resp.json()
        assert "secret_hash" not in data["clients"][0]

    def test_list_empty(self, client):
        """Empty list of clients returns 200 with empty clients array."""
        with patch("backend.api.v1.oauth2.OAuth2Service") as mock_svc_class:
            mock_svc = MagicMock()
            mock_svc.list_clients.return_value = []
            mock_svc_class.return_value = mock_svc

            resp = client.get(f"{BASE}/clients")

        assert resp.status_code == 200
        data = resp.json()
        assert data["clients"] == []


class TestOAuth2RegisterClient:
    """POST /api/v1/oauth2/clients"""

    def test_register_success(self, client):
        """Register a new client returns 201 with client_id and client_secret."""
        with patch("backend.api.v1.oauth2.OAuth2Service") as mock_svc_class:
            mock_svc = MagicMock()
            mock_svc.register_client.return_value = ("client_123", "secret_456")
            mock_svc_class.return_value = mock_svc

            resp = client.post(
                f"{BASE}/clients",
                json={"name": "My Client", "partner": "partner_a", "scopes": ["read"]},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == "client_123"
        assert data["client_secret"] == "secret_456"
        assert "warning" in data
        mock_svc.register_client.assert_called_once_with(
            name="My Client",
            partner="partner_a",
            scopes=["read"],
        )

    def test_register_missing_name_returns_400(self, client):
        """Missing name field returns 400."""
        resp = client.post(
            f"{BASE}/clients",
            json={"partner": "partner_a", "scopes": []},
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "name" in data["detail"].lower()

    def test_register_missing_partner_returns_400(self, client):
        """Missing partner field returns 400."""
        resp = client.post(
            f"{BASE}/clients",
            json={"name": "My Client", "scopes": []},
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "partner" in data["detail"].lower()

    def test_register_blank_name_returns_400(self, client):
        """Blank name after strip returns 400."""
        resp = client.post(
            f"{BASE}/clients",
            json={"name": "   ", "partner": "partner_a"},
        )

        assert resp.status_code == 400

    def test_register_blank_partner_returns_400(self, client):
        """Blank partner after strip returns 400."""
        resp = client.post(
            f"{BASE}/clients",
            json={"name": "My Client", "partner": "   "},
        )

        assert resp.status_code == 400


class TestOAuth2RevokeClient:
    """DELETE /api/v1/oauth2/clients/{client_id}"""

    def test_revoke_success(self, client):
        """Revoke an existing client returns 200 with status."""
        with patch("backend.api.v1.oauth2.OAuth2Service") as mock_svc_class:
            mock_svc = MagicMock()
            mock_svc_class.return_value = mock_svc

            resp = client.delete(f"{BASE}/clients/client_123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "revoked"
        assert data["client_id"] == "client_123"
        mock_svc.revoke_client.assert_called_once_with("client_123")

    def test_revoke_error_propagation(self, client):
        """Service exception surfaces as 500."""
        with patch("backend.api.v1.oauth2.OAuth2Service") as mock_svc_class:
            mock_svc = MagicMock()
            mock_svc.revoke_client.side_effect = Exception("DB error")
            mock_svc_class.return_value = mock_svc

            # The route does not catch exceptions; TestClient has
            # raise_server_exceptions=False so it returns a 500 response.
            resp = client.delete(f"{BASE}/clients/client_123")
            assert resp.status_code == 500
