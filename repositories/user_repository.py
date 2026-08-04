"""User repository — user DB access consolidated here."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class UserRepository(BaseRepository):
    TABLE = "users"
    COLUMNS = [
        "id", "email", "password_hash", "role", "display_name",
        "is_active", "created_at", "updated_at",
    ]

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a user by primary key."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (user_id,) + self._company_params(),
        )

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetch a user by email (global — no company scoping)."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE email = ?",
            (email,),
        )

    def list_users(self) -> List[Dict[str, Any]]:
        """Return users scoped to the current company, ordered by role then email."""
        return self._fetchall(
            f"SELECT id, email, role, display_name, is_active, created_at "
            f"FROM {self.TABLE} WHERE 1=1 {self._company_filter()} "
            f"ORDER BY role, email",
            self._company_params(),
        )

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: str,
        display_name: str,
        company_id: int | None = None,
    ) -> int:
        """Insert a new active user scoped to the current company and return the new row id."""
        data = {
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "display_name": display_name,
        }
        if company_id is not None:
            data["company_id"] = company_id
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)

        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        values = tuple(data.values())

        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}, is_active) "
            f"VALUES ({placeholders}, 1)",
            values, commit=True,
        )

    def deactivate_user(self, user_id: int) -> None:
        """Set *user_id* as inactive (scoped to the current company)."""
        self._execute(
            f"UPDATE {self.TABLE} SET is_active = 0 WHERE id = ? {self._company_filter()}",
            (user_id,) + self._company_params(), commit=True,
		)
