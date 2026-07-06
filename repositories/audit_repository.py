"""Audit repository — all operation_events (audit log) DB access."""
import json
import uuid
from datetime import datetime
from typing import Any

from repositories import BaseRepository

class AuditRepository(BaseRepository):
    TABLE = "operation_events"
    MAX_EVENTS = 5000

    def log_event(self, event_type: str, description: str) -> None:
        try:
            now = datetime.now().isoformat()
            ev_id = uuid.uuid4().hex[:12]
            payload = json.dumps({"event": event_type, "description": description})
            self._execute(
                "INSERT INTO operation_events (id, event_type, data_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (ev_id, event_type, payload, now),
                commit=False,
            )
            self._execute(
                "DELETE FROM operation_events WHERE id NOT IN ("
                "SELECT id FROM operation_events ORDER BY created_at DESC LIMIT ?"
                ")",
                (self.MAX_EVENTS,),
            )
        except Exception as e:
            import logging
            logging.getLogger("audit_repo").debug("Audit log write failed: %s", e)

    def log_event_with_details(self, event_id: str, event_type: str, data_json: str, created_at: str) -> None:
        try:
            self._execute(
                "INSERT INTO operation_events (id, event_type, data_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (event_id, event_type, data_json, created_at),
                commit=True,
            )
        except Exception as e:
            import logging
            logging.getLogger("audit_repo").debug("Audit log write failed: %s", e)

    def get_events(self, event_type_prefix: str = "", limit: int = 50) -> list[dict[str, Any]]:
        if event_type_prefix:
            rows = self._fetchall(
                f"SELECT * FROM {self.TABLE} WHERE event_type LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"{event_type_prefix}%", limit),
            )
        else:
            rows = self._fetchall(
                f"SELECT * FROM {self.TABLE} ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return rows

    def get_event_count(self, event_type_prefix: str = "") -> int:
        if event_type_prefix:
            row = self._fetchone(
                f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE event_type LIKE ?",
                (f"{event_type_prefix}%",),
            )
        else:
            row = self._fetchone(f"SELECT COUNT(*) AS cnt FROM {self.TABLE}")
        return row["cnt"] if row else 0
