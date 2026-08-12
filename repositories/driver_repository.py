"""Driver repository — all driver DB access consolidated here."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class DriverRepository(BaseRepository):
    TABLE = "drivers"
    COLUMNS = [
        "id", "name", "phone", "email", "license_number", "license_category",
        "license_expiry", "medical_expiry", "hire_date", "monthly_salary",
        "notes", "is_active", "created_at", "updated_at",
        "passport_number", "passport_expiry", "adr_certificate",
        "adr_certificate_expiry", "driver_card_number",
    ]

    # ── Base CRUD ─────────────────────────────────────────────────────

    def get_by_id_with_adr(self, driver_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT name, adr_certificate_expiry FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (driver_id,) + self._company_params(),
        )

    def get_by_id(self, driver_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (driver_id,) + self._company_params(),
        )

    def get_all(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()} ORDER BY name ASC LIMIT ? OFFSET ?",
            self._company_params() + (limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        now = datetime.now().isoformat()
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
            tuple(data.values()),
        )

    def update(self, driver_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        data = dict(data)
        data["updated_at"] = datetime.now().isoformat()
        if "id" in data:
            del data["id"]
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (driver_id,) + self._company_params(),
        )

    def delete(self, driver_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (driver_id,) + self._company_params(),
        )

    # ── Domain-specific queries ───────────────────────────────────────

    def get_active_drivers(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 {self._company_filter()} ORDER BY name ASC",
            self._company_params(),
        )

    def get_expiring_licenses(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        return self._fetchall(
            f"""SELECT * FROM {self.TABLE}
                WHERE is_active = 1
                  AND license_expiry IS NOT NULL
                  AND license_expiry != ''
                  AND license_expiry >= ?
                  AND license_expiry <= ?
                  {self._company_filter()}
                ORDER BY license_expiry ASC""",
            (today, cutoff) + self._company_params(),
        )

    def get_expiring_medical(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        return self._fetchall(
            f"""SELECT * FROM {self.TABLE}
                WHERE is_active = 1
                  AND medical_expiry IS NOT NULL
                  AND medical_expiry != ''
                  AND medical_expiry >= ?
                  AND medical_expiry <= ?
                  {self._company_filter()}
                ORDER BY medical_expiry ASC""",
            (today, cutoff) + self._company_params(),
        )

    def get_expired_licenses(self) -> List[Dict[str, Any]]:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._fetchall(
            f"""SELECT * FROM {self.TABLE}
                WHERE is_active = 1
                  AND license_expiry IS NOT NULL
                  AND license_expiry != ''
                  AND license_expiry < ?
                  {self._company_filter()}
                ORDER BY license_expiry ASC""",
            (today,) + self._company_params(),
        )

    def get_expired_medical(self) -> List[Dict[str, Any]]:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._fetchall(
            f"""SELECT * FROM {self.TABLE}
                WHERE is_active = 1
                  AND medical_expiry IS NOT NULL
                  AND medical_expiry != ''
                  AND medical_expiry < ?
                  {self._company_filter()}
                ORDER BY medical_expiry ASC""",
            (today,) + self._company_params(),
        )

    def search_by_name(self, query: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE name LIKE ? {self._company_filter()} ORDER BY name ASC",
            (f"%{query}%",) + self._company_params(),
        )

    def get_by_card_number(self, card_number: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE driver_card_number = ? {self._company_filter()}",
            (card_number,) + self._company_params(),
        )

    def get_by_name_fuzzy(self, name: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE name LIKE ? {self._company_filter()} LIMIT 1",
            (f"%{name}%",) + self._company_params(),
        )

    def update_license_expiry(self, driver_id: int, expiry: str) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET license_expiry = ? WHERE id = ? {self._company_filter()}",
            (expiry, driver_id) + self._company_params(),
        )

    def count_active(self) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE is_active = 1 {self._company_filter()}",
            self._company_params(),
        )
        return row["cnt"] if row else 0
