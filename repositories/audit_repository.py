"""Audit repository — all operation_events (audit log) DB access."""
import json
import uuid
from datetime import datetime
from typing import Any

from repositories import BaseRepository

class AuditRepository(BaseRepository):
    TABLE = "operation_events"
    MAX_EVENTS = 5000
    COLUMNS = [
        "id", "event_type", "data_json", "created_at", "company_id",
    ]

    def log_event(self, event_type: str, description: str) -> None:
        try:
            now = datetime.now().isoformat()
            ev_id = uuid.uuid4().hex[:12]
            payload = json.dumps({"event": event_type, "description": description})
            data = {
                "id": ev_id,
                "event_type": event_type,
                "data_json": payload,
                "created_at": now,
            }
            self._validate_columns(data, extra_allowed={"company_id"})
            data = self._set_company_from_context(data)
            cols = ", ".join(data.keys())
            vals = ", ".join("?" for _ in data)
            self._execute(
                f"INSERT INTO operation_events ({cols}) VALUES ({vals})",
                tuple(data.values()),
                commit=False,
            )
            self._execute(
                "DELETE FROM operation_events WHERE id NOT IN ("
                "SELECT id FROM operation_events ORDER BY created_at DESC LIMIT ?"
                f") {self._company_filter()}",
                (self.MAX_EVENTS,) + self._company_params(),
            )
        except Exception as e:
            import logging
            logging.getLogger("audit_repo").debug("Audit log write failed: %s", e)

    def log_event_with_details(self, event_id: str, event_type: str, data_json: str, created_at: str) -> None:
        try:
            data = {
                "id": event_id,
                "event_type": event_type,
                "data_json": data_json,
                "created_at": created_at,
            }
            self._validate_columns(data, extra_allowed={"company_id"})
            data = self._set_company_from_context(data)
            cols = ", ".join(data.keys())
            vals = ", ".join("?" for _ in data)
            self._execute(
                f"INSERT INTO operation_events ({cols}) VALUES ({vals})",
                tuple(data.values()),
                commit=True,
            )
        except Exception as e:
            import logging
            logging.getLogger("audit_repo").debug("Audit log write failed: %s", e)

    def get_events(self, event_type_prefix: str = "", limit: int = 50) -> list[dict[str, Any]]:
        if event_type_prefix:
            rows = self._fetchall(
                f"SELECT * FROM {self.TABLE} WHERE event_type LIKE ? {self._company_filter()} ORDER BY created_at DESC LIMIT ?",
                (f"{event_type_prefix}%",) + self._company_params() + (limit,),
            )
        else:
            rows = self._fetchall(
                f"SELECT * FROM {self.TABLE} WHERE 1=1 {self._company_filter()} ORDER BY created_at DESC LIMIT ?",
                self._company_params() + (limit,),
            )
        return rows

    def get_event_count(self, event_type_prefix: str = "") -> int:
        if event_type_prefix:
            row = self._fetchone(
                f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE event_type LIKE ? {self._company_filter()}",
                (f"{event_type_prefix}%",) + self._company_params(),
            )
        else:
            row = self._fetchone(
                f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE 1=1 {self._company_filter()}",
                self._company_params(),
            )
        return row["cnt"] if row else 0
