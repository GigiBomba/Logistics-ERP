"""Tests for services.user_service — business-logic delegation and password hashing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.user_service import UserService


class TestUserService:
    """Unit tests for UserService (no database, all collaborators mocked)."""

    # ------------------------------------------------------------------
    # Per-test setup — construct service with mocked repository
    # ------------------------------------------------------------------

    def setup_method(self):
        """Create a fresh UserService instance with a mocked _repo and hash_password."""
        self.mock_repo = MagicMock()
        self.service = UserService.__new__(UserService)
        self.service._repo = self.mock_repo

    # ------------------------------------------------------------------
    # list_users
    # ------------------------------------------------------------------

    def test_list_users_empty(self):
        """list_users returns an empty list when the repo returns one."""
        self.mock_repo.list_users.return_value = []
        result = self.service.list_users()
        assert result == []
        self.mock_repo.list_users.assert_called_once_with()

    def test_list_users_non_empty(self):
        """list_users returns the repo's non-empty list unchanged."""
        expected = [
            {"id": 1, "email": "a@b.com", "role": "driver"},
            {"id": 2, "email": "b@c.com", "role": "admin"},
        ]
        self.mock_repo.list_users.return_value = expected
        result = self.service.list_users()
        assert result == expected
        self.mock_repo.list_users.assert_called_once_with()

    def test_list_users_delegates_to_repo(self):
        """list_users calls repo.list_users exactly once."""
        self.service.list_users()
        self.mock_repo.list_users.assert_called_once_with()

    # ------------------------------------------------------------------
    # create_user
    # ------------------------------------------------------------------

    @patch("services.user_service.hash_password", return_value="hashed_abc")
    def test_create_user_hashes_password_and_delegates(self, mock_hash):
        """create_user hashes the password and passes the hash to repo.create_user."""
        returned_id = self.service.create_user(
            "test@test.com", "s3cret", "admin", "Test User"
        )
        mock_hash.assert_called_once_with("s3cret")
        self.mock_repo.create_user.assert_called_once_with(
            "test@test.com", "hashed_abc", "admin", "Test User"
        )

    @patch("services.user_service.hash_password", return_value="hashed_xyz")
    def test_create_user_returns_new_id(self, mock_hash):
        """create_user returns the integer id returned by the repository."""
        self.mock_repo.create_user.return_value = 42
        user_id = self.service.create_user(
            "alice@example.com", "p@$$w0rd", "driver", "Alice"
        )
        assert user_id == 42

    @patch("services.user_service.hash_password", return_value="hashed_empty")
    def test_create_user_with_empty_email(self, mock_hash):
        """create_user works with an empty email (validation is the repo's concern)."""
        self.mock_repo.create_user.return_value = 1
        user_id = self.service.create_user("", "secret", "viewer", "")
        assert user_id == 1
        self.mock_repo.create_user.assert_called_once_with(
            "", "hashed_empty", "viewer", ""
        )

    @patch("services.user_service.hash_password", return_value="hashed_special")
    def test_create_user_with_special_characters(self, mock_hash):
        """create_user passes special characters through without mangling."""
        email = "user+tag@domain.com"
        display = "John O'Doe — tester"
        user_id = self.service.create_user(email, "p@ss!$ecure", "admin", display)
        self.mock_repo.create_user.assert_called_once_with(
            email, "hashed_special", "admin", display
        )
        assert user_id == self.mock_repo.create_user.return_value

    # ------------------------------------------------------------------
    # deactivate_user
    # ------------------------------------------------------------------

    def test_deactivate_user_calls_repo_with_id(self):
        """deactivate_user delegates to repo.deactivate_user with the given id."""
        self.service.deactivate_user(7)
        self.mock_repo.deactivate_user.assert_called_once_with(7)

    def test_deactivate_user_multiple_calls(self):
        """deactivate_user can be called multiple times with different ids."""
        self.service.deactivate_user(1)
        self.service.deactivate_user(2)
        self.service.deactivate_user(3)
        assert self.mock_repo.deactivate_user.call_count == 3
        self.mock_repo.deactivate_user.assert_any_call(1)
        self.mock_repo.deactivate_user.assert_any_call(2)
        self.mock_repo.deactivate_user.assert_any_call(3)

    def test_deactivate_user_with_zero(self):
        """deactivate_user passes id=0 through (edge case)."""
        self.service.deactivate_user(0)
        self.mock_repo.deactivate_user.assert_called_once_with(0)

    def test_deactivate_user_with_negative(self):
        """deactivate_user passes a negative id through (edge case)."""
        self.service.deactivate_user(-1)
        self.mock_repo.deactivate_user.assert_called_once_with(-1)

    # ------------------------------------------------------------------
    # Error propagation
    # ------------------------------------------------------------------

    def test_list_users_raises(self):
        """If repo.list_users raises, the service lets it propagate."""
        self.mock_repo.list_users.side_effect = RuntimeError("DB down")
        with pytest.raises(RuntimeError, match="DB down"):
            self.service.list_users()

    def test_create_user_raises_on_repo_error(self):
        """If repo.create_user raises, the service lets it propagate."""
        self.mock_repo.create_user.side_effect = ValueError("constraint violation")
        with patch("services.user_service.hash_password", return_value="h"):
            with pytest.raises(ValueError, match="constraint violation"):
                self.service.create_user("a@b.com", "p", "admin", "A")

    def test_deactivate_user_raises(self):
        """If repo.deactivate_user raises, the service lets it propagate."""
        self.mock_repo.deactivate_user.side_effect = ConnectionError("timeout")
        with pytest.raises(ConnectionError, match="timeout"):
            self.service.deactivate_user(99)
