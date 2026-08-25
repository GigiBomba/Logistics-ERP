"""User service — business logic for user management."""
from __future__ import annotations

from typing import Any, Dict, List

# Phase F: the packaged desktop build ships no ``backend`` package — the
# Team view (local-first) hashes passwords here via the shared module.
from utils.security import hash_password
from repositories.user_repository import UserRepository


class UserService:
    """High-level user operations used by the Team view.

    Delegates persistence to :class:`UserRepository` and handles
    cross-cutting concerns such as password hashing.
    """

    def __init__(self, db):
        self._repo = UserRepository(db)

    def list_users(self) -> List[Dict[str, Any]]:
        """Return all users (list of dicts)."""
        return self._repo.list_users()

    def create_user(
        self,
        email: str,
        password: str,
        role: str,
        display_name: str,
    ) -> int:
        """Hash *password* and persist a new user.

        Returns the new row id.
        """
        pwhash = hash_password(password)
        return self._repo.create_user(email, pwhash, role, display_name)

    def deactivate_user(self, user_id: int) -> None:
        """Set *user_id* as inactive."""
        self._repo.deactivate_user(user_id)
