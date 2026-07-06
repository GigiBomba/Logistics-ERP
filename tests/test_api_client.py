"""Tests for client.api_client — mock-driven HTTP client tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from client.api_client import ApiClient, DualModeDocumentService
from client.auth import Auth


@pytest.fixture
def mock_httpx_cls():
    """Patch httpx.Client and yield the class mock (for constructor args)."""
    with patch("client.api_client.httpx.Client") as mock_cls:
        mock_cls.return_value = MagicMock()
        yield mock_cls


@pytest.fixture
def client(mock_httpx_cls) -> ApiClient:
    return ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)


@pytest.fixture
def mock_instance(client, mock_httpx_cls):
    """The httpx.Client instance returned by the constructor."""
    return mock_httpx_cls.return_value


class TestApiClientInit:
    def test_default_headers_no_auth(self, mock_httpx_cls):
        ApiClient(base_url="http://test.local", verify_ssl=False)
        _, kwargs = mock_httpx_cls.call_args
        assert "headers" in kwargs
        assert "X-API-Key" not in kwargs["headers"]

    def test_default_headers_with_api_key(self, mock_httpx_cls):
        ApiClient(base_url="http://test.local", verify_ssl=False, api_key="sk-123")
        _, kwargs = mock_httpx_cls.call_args
        assert kwargs["headers"].get("X-API-Key") == "sk-123"

    def test_default_headers_with_auth_token(self, mock_httpx_cls):
        auth = Auth(token="abc", refresh_token="rtok")
        ApiClient(base_url="http://test.local", verify_ssl=False, auth=auth)
        _, kwargs = mock_httpx_cls.call_args
        headers = kwargs["headers"]
        assert "Authorization" in headers


class TestIsOnline:
    def test_online_when_health_returns_200(self, mock_instance):
        mock_instance.get.return_value = MagicMock(status_code=200)
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        assert client.is_online() is True

    def test_offline_when_health_not_200(self, mock_instance):
        mock_instance.get.return_value = MagicMock(status_code=503)
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        assert client.is_online() is False

    def test_offline_when_connection_error(self, mock_instance):
        mock_instance.get.side_effect = httpx.ConnectError("connection refused")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        assert client.is_online() is False

    def test_caches_result(self, mock_instance):
        mock_instance.get.return_value = MagicMock(status_code=200)
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        client.is_online()
        client.is_online()
        mock_instance.get.assert_called_once()


class TestCheckResponse:
    def test_non_401_returns_false(self, mock_instance):
        client = ApiClient(base_url="http://test.local", verify_ssl=False)
        resp = MagicMock(status_code=200)
        assert client._check_response(resp) is False

    def test_401_without_auth_returns_false(self, mock_instance):
        client = ApiClient(base_url="http://test.local", verify_ssl=False)
        resp = MagicMock(status_code=401)
        assert client._check_response(resp) is False

    def test_401_triggers_token_refresh(self, mock_instance):
        auth = Auth(token="expired", refresh_token="rtok123")
        client = ApiClient(base_url="http://test.local", verify_ssl=False, auth=auth)
        resp = MagicMock(status_code=401)
        with patch.object(client._auth, "refresh", return_value=True):
            result = client._check_response(resp)
        assert result is True

    def test_401_clear_auth_when_refresh_fails(self, mock_instance):
        auth = Auth(token="expired", refresh_token="rtok123")
        client = ApiClient(base_url="http://test.local", verify_ssl=False, auth=auth)
        resp = MagicMock(status_code=401)
        with patch.object(client._auth, "refresh", return_value=False):
            result = client._check_response(resp)
        assert result is False


class TestCrudMethods:
    """Verify CRUD methods construct correct HTTP requests."""

    def test_get_document(self, mock_instance):
        mock_instance.get.return_value = MagicMock(status_code=200, json=lambda: {"id": 1})
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_document(42)
        assert result == {"id": 1}

    def test_list_documents(self, mock_instance):
        mock_instance.get.return_value = MagicMock(
            status_code=200, json=lambda: [{"id": 1}]
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.list_documents(page=1, page_size=20)
        assert result == [{"id": 1}]

    def test_create_trip(self, mock_instance):
        mock_instance.post.return_value = MagicMock(status_code=201, json=lambda: {"id": 99})
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        payload = {"origin": "Berlin", "destination": "Paris"}
        result = client.create_trip(data=payload)
        assert result == {"id": 99}

    def test_update_trip(self, mock_instance):
        mock_instance.put.return_value = MagicMock(status_code=200, json=lambda: {"id": 1})
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        payload = {"status": "completed"}
        result = client.update_trip(trip_id=1, data=payload)
        assert result == {"id": 1}

    def test_delete_trip(self, mock_instance):
        mock_instance.delete.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.delete_trip(trip_id=5)
        assert result == {"success": True}


class TestDualModeDocumentService:
    """DualModeDocumentService tries API first, falls back to local."""

    @pytest.fixture
    def service(self, mock_instance):
        api = ApiClient(base_url="http://test.local", verify_ssl=False)
        svc = DualModeDocumentService(api_client=api, db=MagicMock())
        svc._local = MagicMock()
        return svc

    def test_get_by_id_delegates_to_api(self, service, mock_instance):
        mock_instance.get.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 5, "name": "doc.pdf"}
        )
        result = service.get_by_id(5)
        assert result == {"id": 5, "name": "doc.pdf"}

    def test_get_by_id_falls_back_to_local(self, service, mock_instance):
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        service._local.get_by_id.return_value = {"id": 5, "name": "cached.pdf"}
        result = service.get_by_id(5)
        assert result == {"id": 5, "name": "cached.pdf"}

    def test_list_documents_delegates_to_api(self, service, mock_instance):
        mock_instance.get.return_value = MagicMock(
            status_code=200, json=lambda: {"items": [{"id": 1}], "total": 1}
        )
        result = service.list_documents(page=1)
        assert result["total"] == 1

    def test_list_documents_falls_back_to_local(self, service, mock_instance):
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        service._local.advanced_search.return_value = {"items": [], "total": 0}
        result = service.list_documents(page=1)
        assert result["total"] == 0

    def test_health(self, service, mock_instance):
        mock_instance.get.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "healthy"}
        )
        result = service.health()
        assert result == {"status": "healthy"}
