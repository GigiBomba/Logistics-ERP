"""Tests for client.auth_manager — singleton auth state management."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from client.auth import Auth
from client.auth_manager import (
    clear_auth,
    get_auth,
    hydrate_from_storage,
    is_admin,
    require_admin_async,
    set_auth,
)


@pytest.fixture(autouse=True)
def _reset_auth():
    clear_auth()
    yield


class TestGetSetClear:
    def test_get_returns_none_when_not_set(self):
        assert get_auth() is None

    def test_set_and_get(self):
        auth = Auth(token="abc")
        set_auth(auth)
        assert get_auth() is auth

    def test_set_overwrites(self):
        set_auth(Auth(token="first"))
        second = Auth(token="second")
        set_auth(second)
        assert get_auth() is second

    def test_clear_resets_to_none(self):
        set_auth(Auth(token="abc"))
        clear_auth()
        assert get_auth() is None

    def test_clear_calls_clear_token(self):
        mock_auth = MagicMock(spec=Auth)
        set_auth(mock_auth)
        clear_auth()
        mock_auth.clear_token.assert_called_once()


class TestIsAdmin:
    def test_false_when_no_auth(self):
        clear_auth()
        assert is_admin() is False

    def test_false_when_not_admin(self):
        mock_auth = MagicMock(spec=Auth)
        mock_auth.is_admin = False
        set_auth(mock_auth)
        assert is_admin() is False

    def test_true_when_admin(self):
        mock_auth = MagicMock(spec=Auth)
        mock_auth.is_admin = True
        set_auth(mock_auth)
        assert is_admin() is True


class TestHydrateFromStorage:
    def test_returns_false_when_no_stored_auth(self):
        with patch("client.auth_manager.Auth.load_from_storage") as mock_load:
            mock_auth = MagicMock(spec=Auth)
            mock_auth.is_authenticated = False
            mock_load.return_value = mock_auth

            result = hydrate_from_storage()
            assert result is False

    def test_restores_valid_session(self):
        with patch("client.auth_manager.Auth.load_from_storage") as mock_load:
            mock_auth = MagicMock(spec=Auth)
            mock_auth.is_authenticated = True
            mock_auth.token_expired = False
            mock_load.return_value = mock_auth

            result = hydrate_from_storage()
            assert result is True
            assert get_auth() is mock_auth

    def test_clears_expired_token(self):
        with patch("client.auth_manager.Auth.load_from_storage") as mock_load:
            mock_auth = MagicMock(spec=Auth)
            mock_auth.is_authenticated = True
            mock_auth.token_expired = True
            mock_load.return_value = mock_auth

            result = hydrate_from_storage()
            assert result is False
            assert get_auth() is None


class TestRequireAdminAsync:
    def test_returns_true_when_already_admin(self):
        mock_auth = MagicMock(spec=Auth)
        mock_auth.is_admin = True
        set_auth(mock_auth)

        result = require_admin_async()
        assert result is True

    def test_returns_false_when_login_cancelled(self):
        clear_auth()
        with patch(
            "ui.dialogs.login_dialog.QtLoginDialog", MagicMock()
        ) as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = 0  # QDialog.Rejected
            mock_dlg_cls.return_value = mock_dlg

            result = require_admin_async()
            assert result is False

    def test_returns_true_after_successful_login(self):
        clear_auth()
        with patch(
            "ui.dialogs.login_dialog.QtLoginDialog", MagicMock()
        ) as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = 1  # QDialog.Accepted
            mock_dlg_cls.return_value = mock_dlg

            # After successful login, auth should be set (simulated)
            set_auth(MagicMock(spec=Auth, is_admin=True))

            result = require_admin_async()
            assert result is True


class TestGetSetClearExtended:
    """Additional edge cases for get/set/clear."""

    def test_set_auth_replaces_existing(self):
        auth1 = Auth(token="first")
        auth2 = Auth(token="second")
        set_auth(auth1)
        set_auth(auth2)
        assert get_auth() is auth2
        assert get_auth() is not auth1

    def test_clear_when_already_none(self):
        clear_auth()  # already cleared by fixture
        clear_auth()  # should not raise
        assert get_auth() is None

    def test_get_auth_after_clear_returns_none(self):
        set_auth(Auth(token="abc"))
        clear_auth()
        assert get_auth() is None

    def test_multiple_clear_calls(self):
        set_auth(Auth(token="abc"))
        clear_auth()
        clear_auth()
        clear_auth()
        assert get_auth() is None

    def test_clear_calls_clear_token_on_real_auth(self):
        auth = Auth(token="abc", refresh_token="rtok")
        set_auth(auth)
        clear_auth()
        assert auth.token is None
        assert auth.refresh_token is None


class TestIsAdminExtended:
    def test_is_admin_with_real_auth_admin_role(self):
        import base64, json
        payload = json.dumps({"role": "admin"})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"h.{b64}.s"
        auth = Auth(token=token)
        set_auth(auth)
        assert is_admin() is True

    def test_is_admin_with_real_auth_user_role(self):
        import base64, json
        payload = json.dumps({"role": "user"})
        b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
        token = f"h.{b64}.s"
        auth = Auth(token=token)
        set_auth(auth)
        assert is_admin() is False

    def test_is_admin_returns_false_when_get_auth_returns_none(self):
        clear_auth()
        assert is_admin() is False


class TestHydrateFromStorageExtended:
    def test_clears_stored_tokens_when_expired(self):
        with patch("client.auth_manager.Auth.load_from_storage") as mock_load:
            mock_auth = MagicMock(spec=Auth)
            mock_auth.is_authenticated = True
            mock_auth.token_expired = True
            mock_load.return_value = mock_auth

            result = hydrate_from_storage()
            assert result is False
            assert get_auth() is None
            mock_auth._clear_stored_tokens.assert_called_once()

    def test_no_clear_when_not_authenticated(self):
        with patch("client.auth_manager.Auth.load_from_storage") as mock_load:
            mock_auth = MagicMock(spec=Auth)
            mock_auth.is_authenticated = False
            mock_load.return_value = mock_auth

            result = hydrate_from_storage()
            assert result is False
            mock_auth._clear_stored_tokens.assert_not_called()

    def test_hydrate_when_load_raises_exception(self):
        with patch("client.auth_manager.Auth.load_from_storage") as mock_load:
            mock_load.side_effect = RuntimeError("unexpected")
            with pytest.raises(RuntimeError):
                hydrate_from_storage()

    def test_hydrate_sets_singleton(self):
        with patch("client.auth_manager.Auth.load_from_storage") as mock_load:
            mock_auth = MagicMock(spec=Auth)
            mock_auth.is_authenticated = True
            mock_auth.token_expired = False
            mock_load.return_value = mock_auth

            result = hydrate_from_storage()
            assert result is True
            assert get_auth() is mock_auth


class TestRequireAdminAsyncExtended:
    def test_returns_false_when_import_fails(self):
        clear_auth()
        # Patch the module where QtLoginDialog is lazily imported from
        with patch("builtins.__import__") as mock_import:
            def side_effect(name, *args, **kwargs):
                if name == "ui.dialogs.login_dialog":
                    raise ImportError("No UI module")
                # Fall back to real import for everything else
                if name in ("ui.dialogs", "ui"):
                    raise ImportError("No UI module")
                return __import__(name, *args, **kwargs)
            mock_import.side_effect = side_effect
            result = require_admin_async()
            assert result is False

    def test_returns_false_when_dialog_raises_exception(self):
        clear_auth()
        with patch(
            "ui.dialogs.login_dialog.QtLoginDialog", MagicMock()
        ) as mock_dlg_cls:
            mock_dlg_cls.side_effect = RuntimeError("dialog creation failed")
            result = require_admin_async()
            assert result is False

    def test_returns_false_when_login_dialog_returns_false(self):
        clear_auth()
        with patch(
            "ui.dialogs.login_dialog.QtLoginDialog", MagicMock()
        ) as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = 1  # Accepted
            mock_dlg_cls.return_value = mock_dlg
            # But is_admin returns False after login
            result = require_admin_async()
            assert result is False

    def test_returns_false_when_parent_provided_but_no_admin(self):
        clear_auth()
        with patch(
            "ui.dialogs.login_dialog.QtLoginDialog", MagicMock()
        ) as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = 0
            mock_dlg_cls.return_value = mock_dlg
            result = require_admin_async(parent=MagicMock())
            assert result is False

    def test_returns_true_when_already_admin_no_dialog(self):
        mock_auth = MagicMock(spec=Auth)
        mock_auth.is_admin = True
        set_auth(mock_auth)
        with patch("ui.dialogs.login_dialog.QtLoginDialog") as mock_cls:
            result = require_admin_async()
            assert result is True
            mock_cls.assert_not_called()
