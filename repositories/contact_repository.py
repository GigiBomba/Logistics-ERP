"""Contact repository — CRUD for client_contacts table."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class ContactRepository(BaseRepository):
    TABLE = "client_contacts"
    COLUMNS = [
        "id", "client_id", "contact_type", "full_name", "title", "phone", "email",
        "is_primary", "notes", "created_at", "company_id",
    ]

    def get_by_id(self, contact_id: int, company_id=None) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter_for(company_id)}",
            (contact_id,) + self._company_params_for(company_id),
        )

    def get_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE client_id = ? {self._company_filter()} ORDER BY is_primary DESC, created_at ASC",
            (client_id,) + self._company_params(),
        )

    def get_primary_for_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Return the contact marked is_primary=1 for the given client."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} "
            "WHERE client_id = ? AND is_primary = 1 "
            f"{self._company_filter()} "
            "ORDER BY id ASC LIMIT 1",
            (client_id,) + self._company_params(),
        )

    def create(self, data: Dict[str, Any], company_id=None) -> int:
        self._validate_columns(data)
        from datetime import datetime
        data = dict(data)
        if company_id:
            data["company_id"] = company_id
        data = self._set_company_from_context(data)
        data.setdefault("created_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})", tuple(data.values())
        , commit=True)

    def update(self, contact_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (contact_id,) + self._company_params(), commit=True,
		)

    def delete(self, contact_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (contact_id,) + self._company_params(), commit=True,
		)

    def set_primary(self, client_id: int, contact_id: int) -> None:
        self.begin_transaction()
        self._execute(
            f"UPDATE {self.TABLE} SET is_primary = 0 WHERE client_id = ? {self._company_filter()}",
            (client_id,) + self._company_params(),
            commit=False,
        )
        self._execute(
            f"UPDATE {self.TABLE} SET is_primary = 1 WHERE id = ? {self._company_filter()}",
            (contact_id,) + self._company_params(),
            commit=False,
        )
        self.commit_transaction()
