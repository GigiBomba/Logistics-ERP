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
    def test_default_headers_no_auth(self, mock_httpx_cls, monkeypatch):
        monkeypatch.delenv("OPERION_API_KEY", raising=False)
        monkeypatch.delenv("OPERION_ADMIN_EMAIL", raising=False)
        monkeypatch.delenv("OPERION_ADMIN_PASSWORD_HASH", raising=False)
        # Reset ClientConfig singleton so it re-reads clean env
        import client.config
        client.config._CONFIG = None
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
        mock_instance.request.return_value = MagicMock(status_code=200, json=lambda: {"id": 1})
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_document(42)
        assert result == {"id": 1}

    def test_list_documents(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: [{"id": 1}]
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.list_documents(page=1, page_size=20)
        assert result == [{"id": 1}]

    def test_create_trip(self, mock_instance):
        mock_instance.request.return_value = MagicMock(status_code=201, json=lambda: {"id": 99})
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        payload = {"origin": "Berlin", "destination": "Paris"}
        result = client.create_trip(data=payload)
        assert result == {"id": 99}

    def test_update_trip(self, mock_instance):
        mock_instance.request.return_value = MagicMock(status_code=200, json=lambda: {"id": 1})
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        payload = {"status": "completed"}
        result = client.update_trip(trip_id=1, data=payload)
        assert result == {"id": 1}

    def test_delete_trip(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
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
        mock_instance.get.return_value = MagicMock(status_code=200)
        mock_instance.request.return_value = MagicMock(
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
        mock_instance.get.return_value = MagicMock(status_code=200)
        mock_instance.request.return_value = MagicMock(
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
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "healthy"}
        )
        result = service.health()
        assert result == {"status": "healthy"}


class TestInitParams:
    """Verify constructor parameter handling for SSL, timeout, config."""

    def test_verify_ssl_passed_to_httpx(self, mock_httpx_cls):
        ApiClient(base_url="http://test.local", verify_ssl=True)
        _, kwargs = mock_httpx_cls.call_args
        assert kwargs["verify"] is True

    def test_verify_ssl_false_passed_to_httpx(self, mock_httpx_cls):
        ApiClient(base_url="http://test.local", verify_ssl=False)
        _, kwargs = mock_httpx_cls.call_args
        assert kwargs["verify"] is False

    def test_timeout_default_is_30(self, mock_httpx_cls):
        ApiClient(base_url="http://test.local", verify_ssl=False)
        _, kwargs = mock_httpx_cls.call_args
        assert kwargs["timeout"] == 30.0

    def test_follow_redirects_enabled(self, mock_httpx_cls):
        ApiClient(base_url="http://test.local", verify_ssl=False)
        _, kwargs = mock_httpx_cls.call_args
        assert kwargs["follow_redirects"] is True

    def test_api_key_and_auth_token_together(self, mock_httpx_cls):
        auth = Auth(token="abc123")
        ApiClient(base_url="http://test.local", verify_ssl=False,
                  api_key="key-456", auth=auth)
        _, kwargs = mock_httpx_cls.call_args
        headers = kwargs["headers"]
        assert headers.get("X-API-Key") == "key-456"
        assert headers.get("Authorization") == "Bearer abc123"


class TestCrudErrors:
    """Verify CRUD error handling (ConnectError, non-2xx)."""

    def test_get_raises_runtime_error_on_connect_error(self, mock_instance):
        mock_instance.request.side_effect = httpx.ConnectError("connection refused")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(RuntimeError, match="unreachable"):
            client.get_document(1)

    def test_post_raises_runtime_error_on_connect_error(self, mock_instance):
        mock_instance.request.side_effect = httpx.ConnectError("connection refused")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(RuntimeError, match="unreachable"):
            client.create_trip(data={})

    def test_put_raises_runtime_error_on_connect_error(self, mock_instance):
        mock_instance.request.side_effect = httpx.ConnectError("connection refused")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(RuntimeError, match="unreachable"):
            client._put("/test", json_data={})

    def test_delete_raises_runtime_error_on_connect_error(self, mock_instance):
        mock_instance.request.side_effect = httpx.ConnectError("connection refused")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(RuntimeError, match="unreachable"):
            client._delete("/test")

    def test_get_raises_on_http_error_status(self, mock_instance):
        resp = MagicMock(status_code=500)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=resp
        )
        mock_instance.request.return_value = resp
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(httpx.HTTPStatusError):
            client.get_document(1)

    def test_post_raises_on_http_error_status(self, mock_instance):
        resp = MagicMock(status_code=400)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=resp
        )
        mock_instance.request.return_value = resp
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(httpx.HTTPStatusError):
            client.create_trip(data={})

    def test_put_raises_on_http_error_status(self, mock_instance):
        resp = MagicMock(status_code=403)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=resp
        )
        mock_instance.request.return_value = resp
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(httpx.HTTPStatusError):
            client._put("/test", json_data={})

    def test_delete_raises_on_http_error_status(self, mock_instance):
        resp = MagicMock(status_code=404)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=resp
        )
        mock_instance.request.return_value = resp
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(httpx.HTTPStatusError):
            client._delete("/test")


class TestBinaryMethods:
    """Verify _download and _post_binary return raw bytes."""

    def test_download_returns_bytes(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, content=b"PDF content"
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client._download("/api/v1/trips/1/export/pdf")
        assert result == b"PDF content"

    def test_post_binary_returns_bytes(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, content=b"XLSX content"
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client._post_binary("/api/v1/invoices/generate", json_data={})
        assert result == b"XLSX content"

    def test_download_raises_runtime_error_on_connect_error(self, mock_instance):
        mock_instance.request.side_effect = httpx.ConnectError("connection refused")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        with pytest.raises(RuntimeError, match="unreachable"):
            client._download("/test")

    def test_export_trip_pdf_delegates_to_download(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, content=b"%PDF-1.4"
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.export_trip_pdf(42)
        assert result == b"%PDF-1.4"
        # Verify the correct URL was called
        call_url = mock_instance.request.call_args[0][1]
        assert "/api/v1/trips/42/export/pdf" in call_url

    def test_export_trip_xlsx_delegates_to_download(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, content=b"PK\x03\x04"
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.export_trip_xlsx(42)
        assert result == b"PK\x03\x04"
        call_url = mock_instance.request.call_args[0][1]
        assert "/api/v1/trips/42/export/xlsx" in call_url


class TestCleanParams:
    def test_strips_none_values(self):
        result = ApiClient._clean_params(a=None, b="hello", c=1)
        assert result == {"b": "hello", "c": 1}

    def test_strips_empty_strings(self):
        result = ApiClient._clean_params(a="", b="world", c="")
        assert result == {"b": "world"}

    def test_keeps_falsy_non_none_values(self):
        result = ApiClient._clean_params(limit=0, offset=0, enabled=False)
        assert result == {"limit": 0, "offset": 0, "enabled": False}

    def test_returns_empty_dict_for_all_none(self):
        result = ApiClient._clean_params(a=None, b=None)
        assert result == {}


class TestUpdateAuth:
    def test_update_auth_sets_headers(self, mock_instance, mock_httpx_cls):
        client = ApiClient(base_url="http://test.local", verify_ssl=False)
        auth = Auth(token="new_token")
        client.update_auth(auth)
        assert client._auth is auth
        # Verify client headers updated
        mock_instance.headers.update.assert_called_with(
            {"Authorization": "Bearer new_token"}
        )

    def test_update_auth_with_none(self, mock_instance, mock_httpx_cls):
        client = ApiClient(base_url="http://test.local", verify_ssl=False)
        client.update_auth(None)
        assert client._auth is None

    def test_update_auth_clears_old_headers(self, mock_instance, mock_httpx_cls):
        old_auth = Auth(token="old_token")
        client = ApiClient(base_url="http://test.local", verify_ssl=False, auth=old_auth)
        new_auth = Auth(token="new_token")
        client.update_auth(new_auth)
        assert client._auth is new_auth
        mock_instance.headers.update.assert_called_with(
            {"Authorization": "Bearer new_token"}
        )

    def test_update_auth_none_removes_stale_header(self, mock_instance, mock_httpx_cls):
        """Logout (update_auth(None)) must drop the stale Authorization
        header — otherwise the client keeps sending a dead token and 401s
        on every request forever."""
        old_auth = Auth(token="old_token")
        client = ApiClient(base_url="http://test.local", verify_ssl=False, auth=old_auth)
        client.update_auth(None)
        assert client._auth is None
        mock_instance.headers.pop.assert_called_with("Authorization", None)

    def test_update_auth_tokenless_removes_stale_header(self, mock_instance, mock_httpx_cls):
        old_auth = Auth(token="old_token")
        client = ApiClient(base_url="http://test.local", verify_ssl=False, auth=old_auth)
        client.update_auth(Auth())  # cleared token, no refresh token
        assert client._auth is not None
        mock_instance.headers.pop.assert_called_with("Authorization", None)


class TestClose:
    def test_close_calls_client_close(self, mock_instance, mock_httpx_cls):
        client = ApiClient(base_url="http://test.local", verify_ssl=False)
        client.close()
        mock_instance.close.assert_called_once()


class TestFleetEndpoints:
    def test_list_trucks(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"items": [{"id": 1, "plate": "AB-123"}]}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.list_trucks()
        assert result == {"items": [{"id": 1, "plate": "AB-123"}]}
        call_url = mock_instance.request.call_args[0][1]
        assert "/api/v1/fleet/trucks" in call_url

    def test_get_truck(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 7, "plate": "CD-456"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_truck(7)
        assert result["plate"] == "CD-456"
        call_url = mock_instance.request.call_args[0][1]
        assert "/api/v1/fleet/trucks/7" in call_url

    def test_create_truck(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=201, json=lambda: {"id": 10}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.create_truck({"plate": "EF-789"})
        assert result["id"] == 10

    def test_update_truck(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 10, "plate": "EF-789"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.update_truck(10, {"plate": "EF-789"})
        assert result["plate"] == "EF-789"

    def test_delete_truck(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.delete_truck(5)
        assert result == {"success": True}

    def test_get_live_position(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"truck_id": 1, "lat": 52.52, "lng": 13.40}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_live_position(1)
        assert result["lat"] == 52.52


class TestDriverEndpoints:
    def test_list_drivers(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"items": [{"id": 1, "name": "John"}]}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.list_drivers()
        assert len(result["items"]) == 1

    def test_get_driver(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 5, "name": "Jane"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_driver(5)
        assert result["name"] == "Jane"

    def test_create_driver(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=201, json=lambda: {"id": 20}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.create_driver({"name": "Bob"})
        assert result["id"] == 20

    def test_assign_driver_to_truck(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.assign_driver_to_truck(1, 5)
        assert result["success"] is True


class TestHealthCheck:
    def test_health_check_returns_status(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "healthy"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.health_check()
        assert result == {"status": "healthy"}


class TestDocumentListEndpoints:
    def test_get_document_links_returns_list(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: [{"doc_id": 1, "entity_type": "trip"}]
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_document_links(1)
        assert isinstance(result, list)
        assert result[0]["doc_id"] == 1

    def test_get_document_links_returns_empty_list_when_not_list(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_document_links(1)
        assert result == []

    def test_get_document_versions_returns_list(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: [{"id": 1, "version": 2}]
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_document_versions(1)
        assert isinstance(result, list)
        assert result[0]["version"] == 2

    def test_get_document_categories_returns_list(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: [{"name": "Invoice"}, {"name": "Contract"}]
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_document_categories()
        assert len(result) == 2


class TestRetryOn401:
    """Verify that 401 triggers retry in each HTTP method."""

    def test_get_retries_on_401(self, mock_instance):
        auth = Auth(token="expired", refresh_token="rtok")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False, auth=auth)
        # First call returns 401, second returns 200
        resp_401 = MagicMock(status_code=401)
        resp_200 = MagicMock(status_code=200, json=lambda: {"id": 42})
        mock_instance.request.side_effect = [resp_401, resp_200]
        with patch.object(client._auth, "refresh", return_value=True):
            result = client.get_document(42)
        assert result == {"id": 42}
        assert mock_instance.request.call_count == 2

    def test_post_retries_on_401(self, mock_instance):
        auth = Auth(token="expired", refresh_token="rtok")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False, auth=auth)
        resp_401 = MagicMock(status_code=401)
        resp_201 = MagicMock(status_code=201, json=lambda: {"id": 99})
        mock_instance.request.side_effect = [resp_401, resp_201]
        with patch.object(client._auth, "refresh", return_value=True):
            result = client.create_trip(data={"origin": "Berlin"})
        assert result["id"] == 99
        assert mock_instance.request.call_count == 2

    def test_put_retries_on_401(self, mock_instance):
        auth = Auth(token="expired", refresh_token="rtok")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False, auth=auth)
        resp_401 = MagicMock(status_code=401)
        resp_200 = MagicMock(status_code=200, json=lambda: {"id": 1})
        mock_instance.request.side_effect = [resp_401, resp_200]
        with patch.object(client._auth, "refresh", return_value=True):
            result = client.update_trip(1, data={"status": "done"})
        assert result["id"] == 1
        assert mock_instance.request.call_count == 2

    def test_delete_retries_on_401(self, mock_instance):
        auth = Auth(token="expired", refresh_token="rtok")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False, auth=auth)
        resp_401 = MagicMock(status_code=401)
        resp_200 = MagicMock(status_code=200, json=lambda: {"success": True})
        mock_instance.request.side_effect = [resp_401, resp_200]
        with patch.object(client._auth, "refresh", return_value=True):
            result = client.delete_trip(5)
        assert result["success"] is True
        assert mock_instance.request.call_count == 2

    def test_download_retries_on_401(self, mock_instance):
        auth = Auth(token="expired", refresh_token="rtok")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False, auth=auth)
        resp_401 = MagicMock(status_code=401)
        resp_200 = MagicMock(status_code=200, content=b"binary data")
        mock_instance.request.side_effect = [resp_401, resp_200]
        with patch.object(client._auth, "refresh", return_value=True):
            result = client.export_trip_pdf(1)
        assert result == b"binary data"
        assert mock_instance.request.call_count == 2

    def test_failed_refresh_removes_stale_header(self, mock_instance):
        """When the refresh fails, the dead Bearer header must be dropped —
        otherwise every subsequent request 401s forever."""
        auth = Auth(token="expired", refresh_token="rtok")
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False, auth=auth)
        req = httpx.Request("GET", "http://test.local/api/v1/documents/42")
        mock_instance.request.return_value = httpx.Response(401, request=req)
        with patch.object(client._auth, "refresh", return_value=False):
            with pytest.raises(httpx.HTTPStatusError):
                client.get_document(42)
        mock_instance.headers.pop.assert_called_with("Authorization", None)


class TestDualModeDocumentServiceExtended:
    """Extended tests for DualModeDocumentService covering all fallback paths."""

    @pytest.fixture
    def service(self, mock_instance):
        api = ApiClient(base_url="http://test.local", verify_ssl=False)
        svc = DualModeDocumentService(api_client=api, db=MagicMock())
        svc._local = MagicMock()
        return svc

    def test_read_document_info_delegates_to_api(self, service, mock_instance):
        api_response = {
            "document": {"id": 1},
            "ocr_text": "sample text",
            "extracted_fields": {},
        }
        mock_instance.get.return_value = MagicMock(status_code=200)
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: api_response
        )
        result = service.read_document_info(1)
        assert result["ocr_text"] == "sample text"

    def test_read_document_info_falls_back_to_local(self, service, mock_instance):
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        service._local.get_by_id.return_value = {
            "id": 1, "name": "doc.pdf", "ocr_text": "cached ocr",
            "extracted_data_json": {}, "tags": [], "expiry_date": "",
        }
        service._local.get_links.return_value = []
        service._local.get_versions.return_value = []
        result = service.read_document_info(1)
        assert result["ocr_text"] == "cached ocr"

    def test_read_document_info_returns_empty_when_no_db(self, mock_instance):
        api = ApiClient(base_url="http://test.local", verify_ssl=False)
        svc = DualModeDocumentService(api_client=api, db=None)
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        result = svc.read_document_info(1)
        assert result == {}

    def test_get_categories_delegates_to_api(self, service, mock_instance):
        mock_instance.get.return_value = MagicMock(status_code=200)
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: [{"name": "Invoice"}]
        )
        result = service.get_categories()
        assert result == [{"name": "Invoice"}]

    def test_get_categories_falls_back_to_local(self, service, mock_instance):
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        service._local.get_categories.return_value = [{"name": "Cached"}]
        result = service.get_categories()
        assert result == [{"name": "Cached"}]

    def test_get_categories_returns_empty_when_no_db(self, mock_instance):
        api = ApiClient(base_url="http://test.local", verify_ssl=False)
        svc = DualModeDocumentService(api_client=api, db=None)
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        result = svc.get_categories()
        assert result == []

    def test_get_links_delegates_to_api(self, service, mock_instance):
        mock_instance.get.return_value = MagicMock(status_code=200)
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: [{"doc_id": 1}]
        )
        result = service.get_links(1)
        assert result == [{"doc_id": 1}]

    def test_get_links_falls_back_to_local(self, service, mock_instance):
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        service._local.get_links.return_value = [{"doc_id": 1}]
        result = service.get_links(1)
        assert result == [{"doc_id": 1}]

    def test_get_links_returns_empty_when_no_db(self, mock_instance):
        api = ApiClient(base_url="http://test.local", verify_ssl=False)
        svc = DualModeDocumentService(api_client=api, db=None)
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        result = svc.get_links(1)
        assert result == []

    def test_get_versions_delegates_to_api(self, service, mock_instance):
        mock_instance.get.return_value = MagicMock(status_code=200)
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: [{"id": 1, "version": 2}]
        )
        result = service.get_versions(1)
        assert result == [{"id": 1, "version": 2}]

    def test_get_versions_falls_back_to_local(self, service, mock_instance):
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        service._local.get_versions.return_value = [{"id": 1, "version": 2}]
        result = service.get_versions(1)
        assert result == [{"id": 1, "version": 2}]

    def test_get_versions_returns_empty_when_no_db(self, mock_instance):
        api = ApiClient(base_url="http://test.local", verify_ssl=False)
        svc = DualModeDocumentService(api_client=api, db=None)
        mock_instance.get.side_effect = httpx.ConnectError("offline")
        result = svc.get_versions(1)
        assert result == []


class TestListTrips:
    def test_list_trips_passes_params(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"items": [{"id": 1}]}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        client.list_trips(search="Berlin", status="active", limit=50)
        call_kwargs = mock_instance.request.call_args[1]
        assert call_kwargs["params"]["search"] == "Berlin"
        assert call_kwargs["params"]["status"] == "active"
        assert call_kwargs["params"]["limit"] == 50

    def test_get_trip(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 1, "origin": "Berlin"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_trip(1)
        assert result["origin"] == "Berlin"

    def test_check_trip_conflicts(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"conflicts": []}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.check_trip_conflicts({"trip_id": 1})
        assert result["conflicts"] == []


class TestClientEndpoints:
    def test_list_clients(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"items": [{"id": 1, "name": "Acme"}]}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.list_clients()
        assert result["items"][0]["name"] == "Acme"

    def test_list_clients_sends_include_inactive_true(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"items": []}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        client.list_clients(include_inactive=True)
        call_kwargs = mock_instance.request.call_args[1]
        assert call_kwargs["params"]["include_inactive"] is True

    def test_list_clients_sends_include_inactive_false(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"items": []}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        client.list_clients()
        call_kwargs = mock_instance.request.call_args[1]
        assert call_kwargs["params"]["include_inactive"] is False

    def test_get_client(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"id": 3, "name": "Beta"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_client(3)
        assert result["name"] == "Beta"

    def test_create_client(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=201, json=lambda: {"id": 7}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.create_client("Gamma Corp")
        assert result["id"] == 7

    def test_get_client_dashboard(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"revenue": 50000, "trip_count": 12}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_client_dashboard(1)
        assert result["revenue"] == 50000

    def test_deactivate_client(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.deactivate_client(1)
        assert result["success"] is True

    def test_update_client_contact(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "updated"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.update_client_contact(
            5, {"full_name": "Jane Smith", "phone": "+40123"}
        )
        assert result["status"] == "updated"
        call_args, call_kwargs = mock_instance.request.call_args
        assert call_args[0] == "PATCH"
        assert "/api/v1/clients/contacts/5" in call_args[1]
        assert call_kwargs["json"] == {"full_name": "Jane Smith", "phone": "+40123"}

    def test_delete_client_contact(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "deleted"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.delete_client_contact(5)
        assert result["status"] == "deleted"
        call_args, _ = mock_instance.request.call_args
        assert call_args[0] == "DELETE"
        assert "/api/v1/clients/contacts/5" in call_args[1]

    def test_upload_document(self, mock_instance, tmp_path):
        mock_instance.request.return_value = MagicMock(
            status_code=201, json=lambda: {"id": 99}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF content")
        result = client.upload_document(str(test_file), category="invoice")
        assert result["id"] == 99


class TestSettingsAndAlertEndpoints:
    def test_get_company_config(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"company_name": "Operion"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_company_config()
        assert result["company_name"] == "Operion"

    def test_list_alerts(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"items": [{"id": "alert-1"}]}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.list_alerts()
        assert len(result["items"]) == 1

    def test_resolve_alert(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.resolve_alert("alert-1")
        assert result["success"] is True

    def test_get_admin_diagnostics(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "all good"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.get_admin_diagnostics()
        assert result["status"] == "all good"


class TestPostWithDataAndFiles:
    def test_add_document_tag_uses_data(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        client.add_document_tag(1, "important")
        call_kwargs = mock_instance.request.call_args[1]
        assert call_kwargs["data"] == {"tag": "important"}

    def test_run_ocr(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"job_id": "ocr-123"}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.run_ocr(1, engine="tesseract")
        assert result["job_id"] == "ocr-123"

    def test_generate_invoice_via_post_binary(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, content=b"PDF invoice"
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.generate_invoice({"trip_id": 1}, mode="client")
        assert result == b"PDF invoice"

    def test_send_invoice_email(self, mock_instance):
        mock_instance.request.return_value = MagicMock(
            status_code=200, json=lambda: {"sent": True}
        )
        client = ApiClient(base_url="http://test.local/api/v1", verify_ssl=False)
        result = client.send_invoice_email(1, "test@example.com")
        assert result["sent"] is True
