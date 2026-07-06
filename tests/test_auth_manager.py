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
