"""Company repository — multi-tenant company CRUD.

NOTE: This repository manages the tenant entity (companies table) itself.
Company-level filtering is not applied because the company IS the tenant
root.  Cross-tenant admin reads rely on this behaviour.
# read-only
"""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class CompanyRepository(BaseRepository):
    TABLE = "companies"
    COLUMNS = [
        "id", "company_name", "subscription_tier", "is_active",
        "created_at", "updated_at",
    ]

    def get_by_id(self, company_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (company_id,),
        )

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} ORDER BY company_name LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        commit=True)

    def update(self, company_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (company_id,),
        commit=True)

    def get_active_ids(self) -> List[int]:
        rows = self._fetchall(
            f"SELECT id FROM {self.TABLE} WHERE is_active = 1 ORDER BY id",
        )
        return [r["id"] for r in rows]
