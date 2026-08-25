"""Payment profile repository — all payment profile DB access consolidated here."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class PaymentProfileRepository(BaseRepository):
    TABLE = "payment_profiles"
    COLUMNS = [
        "id", "profile_name", "recipient_type", "bank_name", "bank_account",
        "bank_code", "bank_bic", "iban", "payment_reference", "contact_name",
        "contact_email", "contact_phone", "notes", "is_active", "created_at",
        "updated_at", "company_id",
    ]

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_by_id(self, profile_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (profile_id,) + self._company_params(),
        )

    def get_all(self, include_inactive: bool = False, limit: int = 500) -> List[Dict[str, Any]]:
        if include_inactive:
            where = "1=1"
        else:
            where = "is_active = 1"
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE {where} {self._company_filter()} ORDER BY profile_name ASC LIMIT ?",
            self._company_params() + (limit,),
        )

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE profile_name LIKE ? {self._company_filter()} ORDER BY profile_name ASC LIMIT ?",
            (f"%{query}%",) + self._company_params() + (limit,),
        )

    def get_active_by_type(self, recipient_type: str, limit: int = 500) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 AND recipient_type = ? {self._company_filter()} ORDER BY profile_name ASC LIMIT ?",
            (recipient_type,) + self._company_params() + (limit,),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        now = datetime.utcnow().isoformat()
        data = dict(data)
        data = self._set_company_from_context(data)
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        if "id" in data:
            del data["id"]
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def update(self, profile_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        data = dict(data)
        data["updated_at"] = datetime.utcnow().isoformat()
        if "id" in data:
            del data["id"]
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (profile_id,) + self._company_params(), commit=True,
		)

    def delete(self, profile_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (profile_id,) + self._company_params(), commit=True,
		)
