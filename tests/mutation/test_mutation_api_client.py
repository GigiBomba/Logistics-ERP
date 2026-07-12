"""Mutation tests for API client — verifies behavior under corrupted responses.

Tests that removing guards or changing retry logic would cause tests to fail,
ensuring the ``ApiClient`` implementation is correct and resilient.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from client.api_client import ApiClient
from client.auth import Auth

pytestmark = pytest.mark.mutation


# ── Helpers ──────────────────────────────────────────────────────────────────────


def _make_json_response(status_code: int = 200, json_data: object = None) -> MagicMock:
    """Build a mock ``httpx.Response`` that returns *json_data* from ``.json()``."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def _make_raise_for_status(resp: MagicMock) -> None:
    """Install ``raise_for_status`` on *resp* so it raises when status >= 400."""
    if resp.status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{resp.status_code} Error",
            request=MagicMock(),
            response=resp,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Retry logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestMutationApiClientRetry:
    """Kill mutations on retry logic — verifies the right failures trigger retry.

    ``_request_with_retry`` catches ``httpx.HTTPError`` subclasses
    (``ConnectError``, ``TimeoutException``, ``RemoteProtocolError``,
    ``ReadError``) and retries up to 3 times with exponential backoff.
    4xx responses are **not** retried — they pass through as valid HTTP
    responses and the caller (e.g. ``_get``) calls ``raise_for_status()``.
    """

    @pytest.fixture
    def client(self):
        """Return an ``ApiClient`` whose ``_client`` is a plain ``MagicMock``.

        This lets us control ``_client.request`` return values / side effects
        without touching real network or the ``httpx.Client`` constructor.
        """
        with patch("client.api_client.httpx.Client") as mock_cls:
            mock_transport = MagicMock()
            mock_cls.return_value = mock_transport
            c = ApiClient(base_url="http://test", api_key="mutation-key")
            c._client = mock_transport  # ensure we hold the mock
            yield c

    # ── Should retry ──────────────────────────────────────────────────────────────

    def test_retry_on_connection_error(self, client):
        """``ConnectError`` should trigger retry → second attempt succeeds."""
        ok_resp = _make_json_response(200, {"status": "ok"})

        client._client.request.side_effect = [
            httpx.ConnectError("Connection refused"),
            ok_resp,
        ]

        result = client._get("/test")
        assert result == {"status": "ok"}
        assert client._client.request.call_count == 2, (
            "Expected 2 calls (1 failed + 1 retry)"
        )

    def test_retry_on_timeout(self, client):
        """``TimeoutException`` should trigger retry."""
        ok_resp = _make_json_response(200, {"status": "ok"})

        client._client.request.side_effect = [
            httpx.TimeoutException("Timed out after 5s"),
            ok_resp,
        ]

        result = client._get("/test")
        assert result == {"status": "ok"}
        assert client._client.request.call_count == 2

    def test_retry_on_remote_protocol_error(self, client):
        """``RemoteProtocolError`` should trigger retry."""
        ok_resp = _make_json_response(200, {"status": "ok"})

        client._client.request.side_effect = [
            httpx.RemoteProtocolError("Connection closed unexpectedly"),
            ok_resp,
        ]

        result = client._get("/test")
        assert result == {"status": "ok"}
        assert client._client.request.call_count == 2

    def test_retry_on_read_error(self, client):
        """``ReadError`` should trigger retry."""
        ok_resp = _make_json_response(200, {"status": "ok"})

        client._client.request.side_effect = [
            httpx.ReadError("Connection reset by peer"),
            ok_resp,
        ]

        result = client._get("/test")
        assert result == {"status": "ok"}
        assert client._client.request.call_count == 2

    def test_exhausts_retries_then_raises(self, client):
        """After 3 failed attempts, ``RuntimeError`` is raised."""
        client._client.request.side_effect = httpx.ConnectError("Always down")

        with pytest.raises(RuntimeError, match="API server unreachable"):
            client._get("/test")
        assert client._client.request.call_count == 3

    # ── Should NOT retry ──────────────────────────────────────────────────────────

    def test_no_retry_on_400(self, client):
        """400 Bad Request should NOT trigger retry.

        A 400 is a valid HTTP response.  ``_request_with_retry`` returns it
        immediately and ``_get`` raises ``HTTPStatusError`` from
        ``raise_for_status()``.
        """
        resp = _make_json_response(400, {"detail": "Bad Request"})
        _make_raise_for_status(resp)
        client._client.request.return_value = resp

        with pytest.raises(httpx.HTTPStatusError, match="400"):
            client._get("/test")
        assert client._client.request.call_count == 1, (
            "400 must not retry"
        )

    def test_no_retry_on_404(self, client):
        """404 should NOT trigger retry."""
        resp = _make_json_response(404, {"detail": "Not Found"})
        _make_raise_for_status(resp)
        client._client.request.return_value = resp

        with pytest.raises(httpx.HTTPStatusError, match="404"):
            client._get("/test")
        assert client._client.request.call_count == 1

    def test_no_retry_on_422(self, client):
        """422 validation error should NOT trigger retry."""
        resp = _make_json_response(422, {"detail": "Validation Error"})
        _make_raise_for_status(resp)
        client._client.request.return_value = resp

        with pytest.raises(httpx.HTTPStatusError, match="422"):
            client._get("/test")
        assert client._client.request.call_count == 1

    def test_no_retry_on_500(self, client):
        """500 server error should NOT trigger retry from the client side.

        ``_request_with_retry`` only retries on transport-level exceptions;
        a 500 is a valid HTTP response that passes straight through.
        """
        resp = _make_json_response(500, {"detail": "Server Error"})
        _make_raise_for_status(resp)
        client._client.request.return_value = resp

        with pytest.raises(httpx.HTTPStatusError, match="500"):
            client._get("/test")
        assert client._client.request.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Auth / token refresh
# ═══════════════════════════════════════════════════════════════════════════════


class TestMutationApiClientAuth:
    """Kill mutations on auth token handling.

    ``_check_response`` is called after every request inside
    ``_request_with_retry``.  If the response is 401 and an ``Auth`` instance
    with a ``refresh_token`` exists, a silent refresh is attempted.  On success
    the original request is retried; on failure the token is cleared.
    """

    @pytest.fixture
    def client(self):
        """Return an ``ApiClient`` with a mock transport and a real ``Auth``
        instance that has a refresh token."""
        with patch("client.api_client.httpx.Client") as mock_cls:
            mock_transport = MagicMock()
            mock_cls.return_value = mock_transport
            auth = Auth(token="access-old", refresh_token="refresh-token")
            c = ApiClient(
                base_url="http://test",
                api_key="mutation-key",
                auth=auth,
            )
            c._client = mock_transport
            yield c

    def test_token_refresh_on_401(self, client):
        """401 triggers token refresh and retries the original request.

        Kill: removing the 401 check in ``_check_response`` would cause the
        client to fail on expired tokens instead of silently refreshing.
        """
        fail_resp = _make_json_response(401, {"detail": "Token expired"})
        _make_raise_for_status(fail_resp)

        success_resp = _make_json_response(200, {"data": "protected"})

        client._client.request.side_effect = [fail_resp, success_resp]

        # Bypass real HTTP refresh call — simulate success
        client._auth.refresh = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = client._get("/secure-data")

        assert result == {"data": "protected"}
        assert client._client.request.call_count == 2, (
            "Expected original request + retry after refresh"
        )
        client._auth.refresh.assert_called_once()

    def test_token_refresh_updates_headers(self, client):
        """After a successful refresh the ``Authorization`` header is updated.

        Kill: removing the header update in ``_check_response`` would leave
        the client sending the stale (expired) token on subsequent requests.
        """
        fail_resp = _make_json_response(401, {"detail": "Token expired"})
        _make_raise_for_status(fail_resp)

        success_resp = _make_json_response(200, {"data": "ok"})

        client._client.request.side_effect = [fail_resp, success_resp]

        client._auth.refresh = MagicMock(return_value=True)  # type: ignore[method-assign]
        # After refresh the Auth.headers property returns the new token
        client._auth.headers = {"Authorization": "Bearer access-new"}  # type: ignore[method-assign]

        client._get("/secure-data")

        # The second request should carry the refreshed header
        _, kwargs = client._client.request.call_args_list[1]
        assert "headers" not in kwargs or kwargs.get("headers") is None, (
            "Headers are set on the client, not passed per-request"
        )
        # Instead verify the client's default headers were updated
        assert client._client.headers.get("Authorization") == "Bearer access-new"

    def test_stale_token_cleared_after_failed_refresh(self, client):
        """If refresh fails, the old token should be removed.

        Kill: removing the ``clear_token()`` call would leave a stale/expired
        token in memory, causing subsequent requests to fail at the server
        with no opportunity to re-authenticate.
        """
        resp = _make_json_response(401, {"detail": "Token expired"})
        _make_raise_for_status(resp)
        client._client.request.return_value = resp

        # Simulate refresh failure
        client._auth.refresh = MagicMock(return_value=False)  # type: ignore[method-assign]

        with patch("client.auth_manager.clear_auth") as mock_clear_auth:
            with pytest.raises(httpx.HTTPStatusError):
                client._get("/secure-data")

            client._auth.refresh.assert_called_once()
            # Token must be cleared
            assert client._auth.token is None, (
                "Token should be None after failed refresh"
            )
            assert client._auth.refresh_token is None, (
                "Refresh token should also be cleared"
            )
            mock_clear_auth.assert_called_once()

    def test_no_refresh_without_refresh_token(self, client):
        """If ``Auth`` has no ``refresh_token``, a 401 clears auth immediately.

        Kill: checking ``refresh_token`` before attempting refresh prevents
        a pointless HTTP call that would always fail.
        """
        client._auth.set_refresh_token(None)  # no refresh token
        client._auth.refresh = MagicMock(return_value=False)  # type: ignore[method-assign]

        resp = _make_json_response(401, {"detail": "Token expired"})
        _make_raise_for_status(resp)
        client._client.request.return_value = resp

        with patch("client.auth_manager.clear_auth") as mock_clear_auth:
            with pytest.raises(httpx.HTTPStatusError):
                client._get("/secure-data")

            # refresh() should never have been called (no refresh_token)
            client._auth.refresh.assert_not_called()
            mock_clear_auth.assert_called_once()
            assert client._auth.token is None

    def test_401_without_auth_does_nothing(self, client):
        """If no ``Auth`` is configured, a 401 passes through without crash.

        Kill: the ``self._auth is not None`` guard prevents ``AttributeError``
        when checking ``refresh_token`` on ``None``.
        """
        client._auth = None
        resp = _make_json_response(401, {"detail": "Unauthorized"})
        _make_raise_for_status(resp)
        client._client.request.return_value = resp

        with pytest.raises(httpx.HTTPStatusError, match="401"):
            client._get("/test")

        assert client._client.request.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# JSON parsing
# ═══════════════════════════════════════════════════════════════════════════════


class TestMutationApiClientJsonParsing:
    """Kill mutations on JSON parsing guards.

    ``_get`` / ``_post`` / ``_put`` / ``_delete`` all wrap ``resp.json()`` in
    a ``try/except Exception`` and return a fallback dict instead of crashing.
    Removing those guards would cause the client to crash on non-JSON responses.
    """

    @pytest.fixture
    def client(self):
        with patch("client.api_client.httpx.Client") as mock_cls:
            mock_transport = MagicMock()
            mock_cls.return_value = mock_transport
            c = ApiClient(base_url="http://test", api_key="mutation-key")
            c._client = mock_transport
            yield c

    def test_non_json_response_handled(self, client):
        """HTML response should not crash — returns fallback dict.

        Kill: removing the ``try/except`` around ``resp.json()`` would raise
        ``ValueError`` (or ``json.JSONDecodeError``) and crash the caller.
        """
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.side_effect = ValueError("Expecting value: line 1 column 1")
        client._client.request.return_value = resp

        result = client._get("/test")
        assert result == {"detail": "Invalid JSON response from server"}

    def test_empty_response_handled(self, client):
        """Empty body should not crash — returns fallback dict."""
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.side_effect = ValueError("No JSON object could be decoded")
        client._client.request.return_value = resp

        result = client._get("/test")
        assert result == {"detail": "Invalid JSON response from server"}

    def test_partial_json_still_parsed(self, client):
        """If the server returns valid JSON, it must be returned as-is.

        This test ensures the guard doesn't accidentally catch valid responses.
        """
        resp = _make_json_response(200, {"items": [1, 2, 3]})
        client._client.request.return_value = resp

        result = client._get("/test")
        assert result == {"items": [1, 2, 3]}

    def test_post_non_json_returns_fallback(self, client):
        """Non-JSON on POST also returns the fallback dict."""
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.side_effect = ValueError("Not JSON")
        client._client.request.return_value = resp

        result = client._post("/test", json_data={"key": "value"})
        assert result == {"detail": "Invalid JSON response from server"}

    def test_put_non_json_returns_fallback(self, client):
        """Non-JSON on PUT also returns the fallback dict."""
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.side_effect = ValueError("Not JSON")
        client._client.request.return_value = resp

        result = client._put("/test", json_data={"key": "value"})
        assert result == {"detail": "Invalid JSON response from server"}

    def test_delete_non_json_returns_fallback(self, client):
        """Non-JSON on DELETE also returns the fallback dict."""
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.side_effect = ValueError("Not JSON")
        client._client.request.return_value = resp

        result = client._delete("/test")
        assert result == {"detail": "Invalid JSON response from server"}
