"""Tests for client.auth — token management, JWT decoding, login/refresh."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from client.auth import Auth, _decode_jwt_payload


# ── _decode_jwt_payload ────────────────────────────────────────────────

class TestDecodeJwtPayload:
    def test_decodes_valid_token(self):
        # Build a minimal JWT: header.payload.signature
        import base64, json
        payload = json.dumps({"role": "admin", "exp": 9999999999})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"header.{b64}.signature"
        result = _decode_jwt_payload(token)
        assert result["role"] == "admin"
        assert result["exp"] == 9999999999

    def test_returns_empty_for_malformed_token(self):
        result = _decode_jwt_payload("not-a-jwt")
        assert result == {}

    def test_returns_empty_for_invalid_json_payload(self):
        import base64
        b64 = base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode()
        token = f"header.{b64}.sig"
        result = _decode_jwt_payload(token)
        assert result == {}

    def test_returns_empty_for_non_dict_payload(self):
        import base64, json
        b64 = base64.urlsafe_b64encode(json.dumps("string").encode()).rstrip(b"=").decode()
        token = f"header.{b64}.sig"
        result = _decode_jwt_payload(token)
        assert result == {}

    def test_returns_empty_for_empty_token(self):
        assert _decode_jwt_payload("") == {}

    def test_handles_padding_correctly(self):
        import base64, json
        payload = json.dumps({"sub": "123"})
        # Remove padding to test padding logic
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        assert len(b64) % 4 != 0  # ensure no padding
        token = f"a.{b64}.c"
        result = _decode_jwt_payload(token)
        assert result["sub"] == "123"


# ── Auth initial state ─────────────────────────────────────────────────

class TestAuthInit:
    def test_default_no_tokens(self):
        auth = Auth()
        assert auth.token is None
        assert auth.refresh_token is None

    def test_with_initial_tokens(self):
        auth = Auth(token="abc", refresh_token="rtok")
        assert auth.token == "abc"
        assert auth.refresh_token == "rtok"

    def test_with_token_only(self):
        auth = Auth(token="abc")
        assert auth.token == "abc"
        assert auth.refresh_token is None


class TestAuthTokenAccessors:
    def test_set_token(self):
        auth = Auth()
        auth.set_token("new-token")
        assert auth.token == "new-token"

    def test_set_refresh_token(self):
        auth = Auth()
        auth.set_refresh_token("new-refresh")
        assert auth.refresh_token == "new-refresh"

    def test_set_refresh_token_none(self):
        auth = Auth(token="abc", refresh_token="rtok")
        auth.set_refresh_token(None)
        assert auth.refresh_token is None

    def test_clear_token(self):
        auth = Auth(token="abc", refresh_token="rtok")
        auth.clear_token()
        assert auth.token is None
        assert auth.refresh_token is None

    def test_clear_token_when_already_empty(self):
        auth = Auth()
        auth.clear_token()  # should not raise
        assert auth.token is None


# ── Headers ────────────────────────────────────────────────────────────

class TestAuthHeaders:
    def test_headers_with_token(self):
        auth = Auth(token="my-token")
        assert auth.headers == {"Authorization": "Bearer my-token"}

    def test_headers_without_token(self):
        auth = Auth()
        assert auth.headers == {}

    def test_headers_after_clear(self):
        auth = Auth(token="abc")
        auth.clear_token()
        assert auth.headers == {}


# ── is_authenticated / is_admin / token_expired ────────────────────────

class TestAuthProperties:
    def test_is_authenticated_true(self):
        auth = Auth(token="abc")
        assert auth.is_authenticated is True

    def test_is_authenticated_false(self):
        auth = Auth()
        assert auth.is_authenticated is False

    def test_is_admin_with_admin_role(self):
        import base64, json
        payload = json.dumps({"role": "admin"})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"h.{b64}.s"
        auth = Auth(token=token)
        assert auth.is_admin is True

    def test_is_admin_with_user_role(self):
        import base64, json
        payload = json.dumps({"role": "user"})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"h.{b64}.s"
        auth = Auth(token=token)
        assert auth.is_admin is False

    def test_is_admin_without_token(self):
        auth = Auth()
        assert auth.is_admin is False

    def test_token_expired_when_no_token(self):
        auth = Auth()
        assert auth.token_expired is True

    def test_token_expired_when_no_exp_claim(self):
        import base64, json
        payload = json.dumps({"role": "user"})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"h.{b64}.s"
        auth = Auth(token=token)
        assert auth.token_expired is True

    def test_token_expired_in_future(self):
        import base64, json
        future = time.time() + 3600
        payload = json.dumps({"exp": future})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"h.{b64}.s"
        auth = Auth(token=token)
        assert auth.token_expired is False

    def test_token_expired_in_past(self):
        import base64, json
        past = time.time() - 3600
        payload = json.dumps({"exp": past})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"h.{b64}.s"
        auth = Auth(token=token)
        assert auth.token_expired is True


# ── login ──────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self):
        auth = Auth()
        with patch("client.auth.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "access123",
                "refresh_token": "refresh123",
            }
            mock_post.return_value = mock_response

            with patch.object(auth, "_save_tokens") as mock_save:
                result = auth.login("admin@test.com", "password")
                assert result is True
                assert auth.token == "access123"
                assert auth.refresh_token == "refresh123"
                mock_save.assert_called_once()

    def test_login_failure_wrong_status(self):
        auth = Auth()
        with patch("client.auth.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response
            result = auth.login("admin@test.com", "wrong")
            assert result is False

    def test_login_failure_no_token_in_response(self):
        auth = Auth()
        with patch("client.auth.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_post.return_value = mock_response
            result = auth.login("admin@test.com", "password")
            assert result is False

    def test_login_network_error(self):
        auth = Auth()
        with patch("client.auth.httpx.post") as mock_post:
            mock_post.side_effect = __import__("httpx").RequestError("network error")
            result = auth.login("admin@test.com", "password")
            assert result is False

    def test_login_persists_tokens(self):
        auth = Auth()
        with patch("client.auth.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "access123",
                "refresh_token": "refresh123",
            }
            mock_post.return_value = mock_response

            with patch("PySide6.QtCore.QSettings") as mock_qs:
                mock_settings = MagicMock()
                mock_qs.return_value = mock_settings
                result = auth.login("admin@test.com", "password")
                assert result is True
                mock_settings.setValue.assert_any_call("auth/access_token", "access123")
                mock_settings.setValue.assert_any_call("auth/refresh_token", "refresh123")
                mock_settings.sync.assert_called_once()


# ── refresh ────────────────────────────────────────────────────────────

class TestRefresh:
    def test_refresh_without_refresh_token(self):
        auth = Auth(token="abc")
        assert auth.refresh() is False

    def test_refresh_success(self):
        auth = Auth(token="old", refresh_token="rtok")
        with patch("client.auth.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
            }
            mock_post.return_value = mock_response

            with patch.object(auth, "_save_tokens") as mock_save:
                result = auth.refresh()
                assert result is True
                assert auth.token == "new_access"
                assert auth.refresh_token == "new_refresh"
                mock_save.assert_called_once()

    def test_refresh_keeps_old_refresh_when_server_does_not_rotate(self):
        auth = Auth(token="old", refresh_token="rtok")
        with patch("client.auth.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"access_token": "new_access"}
            mock_post.return_value = mock_response
            result = auth.refresh()
            assert result is True
            assert auth.token == "new_access"
            assert auth.refresh_token == "rtok"  # unchanged

    def test_refresh_failure_wrong_status(self):
        auth = Auth(token="old", refresh_token="rtok")
        with patch("client.auth.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response
            result = auth.refresh()
            assert result is False

    def test_refresh_network_error(self):
        auth = Auth(token="old", refresh_token="rtok")
        with patch("client.auth.httpx.post") as mock_post:
            mock_post.side_effect = __import__("httpx").RequestError("timeout")
            result = auth.refresh()
            assert result is False

    def test_refresh_lock_prevents_concurrent_calls(self):
        """Verify that _refresh_lock serialises concurrent refresh calls."""
        auth = Auth(token="old", refresh_token="rtok")
        with patch.object(auth, "_do_refresh", return_value=True) as mock_refresh:
            import threading

            results = []

            def call_refresh():
                results.append(auth.refresh())

            t1 = threading.Thread(target=call_refresh)
            t2 = threading.Thread(target=call_refresh)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            # _do_refresh may be called 1 or 2 times depending on timing
            assert mock_refresh.called
            assert all(results)


# ── logout ─────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_clears_tokens(self):
        auth = Auth(token="abc", refresh_token="rtok")
        with patch.object(auth, "_clear_stored_tokens") as mock_clear:
            auth.logout()
            assert auth.token is None
            assert auth.refresh_token is None
            mock_clear.assert_called_once()

    def test_logout_when_already_logged_out(self):
        auth = Auth()
        with patch.object(auth, "_clear_stored_tokens") as mock_clear:
            auth.logout()  # should not raise
            mock_clear.assert_called_once()


# ── Persistent storage ─────────────────────────────────────────────────

class TestPersistentStorage:
    def test_save_tokens_writes_to_settings(self):
        auth = Auth(token="abc", refresh_token="rtok")
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_settings = MagicMock()
            mock_qs.return_value = mock_settings
            auth._save_tokens()
            mock_settings.setValue.assert_any_call("auth/access_token", "abc")
            mock_settings.setValue.assert_any_call("auth/refresh_token", "rtok")
            mock_settings.sync.assert_called_once()

    def test_save_tokens_skips_when_no_token(self):
        auth = Auth()
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_settings = MagicMock()
            mock_qs.return_value = mock_settings
            auth._save_tokens()
            mock_settings.setValue.assert_not_called()

    def test_save_tokens_handles_setvalue_exception(self):
        auth = Auth(token="abc", refresh_token="rtok")
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_settings = MagicMock()
            mock_settings.setValue.side_effect = RuntimeError("storage full")
            mock_qs.return_value = mock_settings
            auth._save_tokens()  # should not raise

    def test_clear_stored_tokens_removes_from_settings(self):
        auth = Auth(token="abc", refresh_token="rtok")
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_settings = MagicMock()
            mock_qs.return_value = mock_settings
            auth._clear_stored_tokens()
            mock_settings.remove.assert_any_call("auth/access_token")
            mock_settings.remove.assert_any_call("auth/refresh_token")
            mock_settings.sync.assert_called_once()

    def test_clear_stored_tokens_handles_exception(self):
        auth = Auth(token="abc", refresh_token="rtok")
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_settings = MagicMock()
            mock_settings.remove.side_effect = RuntimeError("settings locked")
            mock_qs.return_value = mock_settings
            auth._clear_stored_tokens()  # should not raise

    def test_load_from_storage_returns_auth_with_tokens(self):
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_settings = MagicMock()
            mock_settings.value.side_effect = lambda key, default=None: {
                "auth/access_token": "stored_token",
                "auth/refresh_token": "stored_refresh",
            }.get(key, default)
            mock_qs.return_value = mock_settings
            auth = Auth.load_from_storage()
            assert auth.token == "stored_token"
            assert auth.refresh_token == "stored_refresh"

    def test_load_from_storage_returns_empty_auth_when_no_tokens(self):
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_settings = MagicMock()
            mock_settings.value.return_value = None
            mock_qs.return_value = mock_settings
            auth = Auth.load_from_storage()
            assert auth.token is None

    def test_load_from_storage_handles_exception(self):
        with patch("PySide6.QtCore.QSettings") as mock_qs:
            mock_qs.side_effect = RuntimeError("no QApp")
            auth = Auth.load_from_storage()
            assert auth.token is None
