"""Mobile subsystem repository — devices, messages, sync cursors.

These tables are scoped to ``user_id``, not ``company_id``, so the
``_company_filter`` pattern does not apply.
# read-only
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class MobileDeviceRepository(BaseRepository):
    TABLE = "mobile_devices"
    COLUMNS = [
        "id", "user_id", "device_token", "platform", "app_version",
        "last_seen_at", "created_at", "updated_at",
    ]

    def upsert(self, user_id: int, device_token: str, platform: str, app_version: str = "") -> None:
        now = datetime.utcnow().isoformat()
        self._execute(
            "INSERT OR REPLACE INTO mobile_devices "
            "(user_id, device_token, platform, app_version, last_seen_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, device_token, platform, app_version, now, now, now),
            commit=True,
        )

    def get_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE user_id = ? ORDER BY last_seen_at DESC",
            (user_id,),
        )

    def delete_by_user(self, user_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE user_id = ?", (user_id,),
            commit=True,
        )

    def update_last_seen(self, user_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET last_seen_at = ? WHERE user_id = ?",
            (datetime.utcnow().isoformat(), user_id),
            commit=True,
        )


class MobileMessageRepository(BaseRepository):
    TABLE = "mobile_messages"
    COLUMNS = [
        "id", "from_user_id", "to_user_id", "subject", "body",
        "is_read", "created_at",
    ]

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
            commit=True,
        )

    def get_for_user(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT m.*, u.display_name AS from_name "
            f"FROM {self.TABLE} m LEFT JOIN users u ON m.from_user_id = u.id "
            f"WHERE m.to_user_id = ? ORDER BY m.created_at DESC LIMIT ?",
            (user_id, limit),
        )

    def mark_read(self, message_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET is_read = 1 WHERE id = ?",
            (message_id,),
            commit=True,
        )
