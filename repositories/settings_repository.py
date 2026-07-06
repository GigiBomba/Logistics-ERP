"""Settings repository — all app settings DB access."""
from typing import Dict, List, Optional

from repositories import BaseRepository

class SettingsRepository(BaseRepository):
    TABLE = "settings"

    def get_settings_by_keys(self, keys: List[str]) -> Dict[str, str]:
        placeholders = ",".join("?" for _ in keys)
        rows = self._fetchall(
            f"SELECT key, value FROM {self.TABLE} WHERE key IN ({placeholders})",
            tuple(keys),
        )
        return {r["key"]: r["value"] for r in rows}

    def get_settings_by_key_pattern(self, pattern: str) -> Dict[str, str]:
        rows = self._fetchall(
            f"SELECT key, value FROM {self.TABLE} WHERE key LIKE ?",
            (pattern,),
        )
        return {r["key"]: r["value"] for r in rows}

    def get_setting_value(self, key: str) -> Optional[str]:
        row = self._fetchone(
            f"SELECT value FROM {self.TABLE} WHERE key = ?", (key,)
        )
        return row["value"] if row else None

    def upsert_setting(self, key: str, value: str) -> None:
        self._execute(
            f"INSERT OR REPLACE INTO {self.TABLE} (key, value) VALUES (?, ?)",
            (key, value),
        )

    def update_setting(self, key: str, value: str) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET value = ? WHERE key = ?",
            (value, key),
        )

    def get_table_names(self) -> List[str]:
        rows = self._fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r["name"] for r in rows]
