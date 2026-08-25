"""OAuth2 client repository — client credentials grant management.

OAuth2 clients are cross-tenant authentication mechanisms.
They are not scoped to a single company, so ``_company_filter``
is intentionally omitted.
# read-only
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from repositories import BaseRepository


class OAuth2ClientRepository(BaseRepository):
    TABLE = "oauth2_clients"
    COLUMNS = [
        "id", "client_id", "client_name", "partner", "scopes",
        "secret_hash", "is_active", "created_by", "created_at",
        "last_used_at", "company_id",
    ]

    def get_by_client_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE client_id = ?", (client_id,),
        )

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
        )

    def update_last_used(self, client_id: str) -> None:
        from datetime import datetime
        self._execute(
            f"UPDATE {self.TABLE} SET last_used_at = ? WHERE client_id = ?",
            (datetime.utcnow().isoformat(), client_id), commit=True,
        )

    def update(self, client_id: str, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE client_id = ?",
            tuple(data.values()) + (client_id,), commit=True,
        )

    def delete(self, client_id: str) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE client_id = ?",
            (client_id,), commit=True,
        )
