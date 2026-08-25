"""Settings repository — all app settings DB access."""
from __future__ import annotations

from typing import Dict, List, Optional

from repositories import BaseRepository

class SettingsRepository(BaseRepository):
    TABLE = "settings"
    COLUMNS = ["key", "value", "company_id"]

    def get_settings_by_keys(self, keys: List[str]) -> Dict[str, str]:
        placeholders = ",".join("?" for _ in keys)
        rows = self._fetchall(
            f"SELECT key, value FROM {self.TABLE} WHERE key IN ({placeholders}) "
            f"{self._company_filter()}",
            tuple(keys) + self._company_params(),
        )
        return {r["key"]: r["value"] for r in rows}

    def get_settings_by_key_pattern(self, pattern: str) -> Dict[str, str]:
        rows = self._fetchall(
            f"SELECT key, value FROM {self.TABLE} WHERE key LIKE ? "
            f"{self._company_filter()}",
            (pattern,) + self._company_params(),
        )
        return {r["key"]: r["value"] for r in rows}

    def get_setting_value(self, key: str) -> Optional[str]:
        row = self._fetchone(
            f"SELECT value FROM {self.TABLE} WHERE key = ? {self._company_filter()}",
            (key,) + self._company_params(),
        )
        return row["value"] if row else None

    def upsert_setting(self, key: str, value: str) -> None:
        data = {"key": key, "value": value}
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        # INSERT OR REPLACE with composite PK (key, company_id) ensures
        # tenant isolation — one tenant's settings never overwrite another's.
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        self._execute(
            f"INSERT OR REPLACE INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
		)

    def update_setting(self, key: str, value: str) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET value = ? WHERE key = ? {self._company_filter()}",
            (value, key) + self._company_params(), commit=True,
		)

    def get_table_names(self) -> List[str]:
        if getattr(self.db, "_engine", "sqlite") == "postgresql":
            rows = self._fetchall(
                "SELECT table_name AS name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        else:
            rows = self._fetchall(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        return [r["name"] for r in rows]
