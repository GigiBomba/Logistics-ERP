"""Tests for Trans.eu HTTP client — OAuth token exchange, HTTP methods, error handling.

Covers: token exchange, refresh, CRUD methods, auth URL builder, error classes.
"""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.trans_eu.client import (
    TransEuClient, TransEuAPIError, TransEuAuthError, TransEuRateLimitError,
    TRANS_EU_API_BASE, TRANS_EU_TOKEN_ENDPOINT,
)
from services.freight_exchange.circuit_breaker import CircuitBreakerOpenError


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


class TestTransEuClientInit:
    def test_client_requires_api_key(self):
        c = TransEuClient(api_key="key123")
        assert c._api_key == "key123"

    def test_build_auth_url(self):
        c = TransEuClient(api_key="key123")
        url = c.build_auth_url("client_1", "http://localhost:19999/callback", "abc123")
        assert "client_id=client_1" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost" in url or "redirect_uri=http://localhost" in url
        assert "response_type=code" in url
        assert "state=abc123" in url

    def test_constants_defined(self):
        from services.trans_eu.client import TRANS_EU_API_BASE, TRANS_EU_TOKEN_ENDPOINT
        assert "api.platform.trans.eu" in TRANS_EU_API_BASE
        assert "auth-api/accounts/token" in TRANS_EU_TOKEN_ENDPOINT


class TestTransEuClientTokenExchange:
    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_exchange_code_for_token(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "tok", "expires_in": 21599, "refresh_token": "ref"}
        mock_resp.status_code = 200
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.exchange_code_for_token("auth_code", "http://localhost/redirect", "cid", "csecret"))

        assert result["access_token"] == "tok"
        assert result["expires_in"] == 21599

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_refresh_token(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "new_tok", "expires_in": 21599, "refresh_token": "new_ref"}
        mock_resp.status_code = 200
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.refresh_token("old_refresh", "cid", "csecret"))
        assert result["access_token"] == "new_tok"

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_exchange_raises_auth_error_on_401(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "unauthorized"
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        with pytest.raises(TransEuAuthError):
            _run(c.exchange_code_for_token("bad_code", "http://localhost/redirect", "cid", "csecret"))


class TestTransEuClientHttpMethods:
    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_get_request(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"items": []}
        mock_resp.status_code = 200
        mock_resp.content = b'{"items": []}'
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.get("access_tok", "/freights-api/v1/freights"))
        assert result == {"items": []}

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_get_with_params(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 1}]
        mock_resp.status_code = 200
        mock_resp.content = b'[{"id": 1}]'
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.get("tok", "/freights-api/v1/freights", params={"page": 1}))
        assert result[0]["id"] == 1

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_post_request(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "new"}
        mock_resp.status_code = 200
        mock_resp.content = b'{"id": "new"}'
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.post("tok", "/freights-api/v1/freights", json_data={"test": True}))
        assert result["id"] == "new"

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_put_request(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"updated": True}
        mock_resp.status_code = 200
        mock_resp.content = b'{"updated": true}'
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.put("tok", "/freights-api/v1/freights/1", json_data={"test": True}))
        assert result["updated"] is True

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_patch_request(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"patched": True}
        mock_resp.status_code = 200
        mock_resp.content = b'{"patched": true}'
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.patch("tok", "/freights-api/v1/freights/1", json_data={"field": "val"}))
        assert result["patched"] is True

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_delete_request(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        result = _run(c.delete("tok", "/freights-api/v1/freights/1"))
        assert result == {}

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_429_raises_rate_limit_error(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "rate limited"
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        with pytest.raises(TransEuRateLimitError):
            _run(c.get("tok", "/any-path"))

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_500_raises_api_error(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "server error"
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        with pytest.raises(TransEuAPIError, match="server error"):
            _run(c.get("tok", "/any-path"))

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_404_raises_api_error(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        c = TransEuClient(api_key="key123")
        with pytest.raises(TransEuAPIError, match="not found"):
            _run(c.get("tok", "/any-path"))


class TestTransEuClientHeaders:
    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_api_key_in_header(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.status_code = 200
        mock_resp.content = b"{}"
        mock_call = AsyncMock(return_value=mock_resp)
        mock_client.return_value.__aenter__.return_value.request = mock_call

        c = TransEuClient(api_key="my_app_key")
        _run(c.get("tok", "/path"))

        call_kwargs = mock_call.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Api-key") == "my_app_key"

    @patch("services.trans_eu.client.httpx.AsyncClient")
    def test_bearer_token_in_header(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.status_code = 200
        mock_resp.content = b"{}"
        mock_call = AsyncMock(return_value=mock_resp)
        mock_client.return_value.__aenter__.return_value.request = mock_call

        c = TransEuClient(api_key="x")
        _run(c.get("my_bearer_token", "/path"))

        call_kwargs = mock_call.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer my_bearer_token"
