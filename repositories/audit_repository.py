"""Audit repository — all operation_events (audit log) DB access."""
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from repositories import BaseRepository

class AuditRepository(BaseRepository):
    TABLE = "operation_events"
    MAX_EVENTS = 5000
    COLUMNS = [
        "id", "event_type", "entity_type", "entity_id",
        "data_json", "user_id", "company_id", "created_at",
    ]

    def log_event(
        self,
        event_type: str,
        entity_type: str = "",
        entity_id: str = "",
        data: Optional[dict] = None,
        user_id: int = 0,
        company_id: int = 0,
    ) -> None:
        """Log a structured business event to the audit trail.

        Args:
            event_type:  Dot-separated event type, e.g. ``"trip.created"``.
            entity_type: Type of the primary entity, e.g. ``"trip"``.
            entity_id:   String ID of the primary entity.
            data:        Arbitrary key-value payload (will be JSON-serialised).
            user_id:     ID of the user who performed the action.
            company_id:  Company scope override (0 = use context).
        """
        try:
            now = datetime.now().isoformat()
            ev_id = uuid.uuid4().hex[:12]
            payload = json.dumps(data or {}, default=str)
            row_data = {
                "id": ev_id,
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "data_json": payload,
                "user_id": user_id,
                "created_at": now,
            }
            # Resolve company_id: explicit override > context > 0
            if company_id:
                row_data["company_id"] = company_id
            else:
                row_data = self._set_company_from_context(row_data)

            self._validate_columns(row_data)
            cols = ", ".join(row_data.keys())
            vals = ", ".join("?" for _ in row_data)
            self.begin_transaction()
            try:
                self._execute(
                    f"INSERT INTO operation_events ({cols}) VALUES ({vals})",
                    tuple(row_data.values()),
                    commit=False,
                )
                self._execute(
                    "DELETE FROM operation_events WHERE id NOT IN ("
                    "SELECT id FROM operation_events ORDER BY created_at DESC LIMIT ?"
                    f") {self._company_filter()}",
                    (self.MAX_EVENTS,) + self._company_params(),
                    commit=False,
                )
                self.commit_transaction()
            except Exception:
                self.rollback_transaction()
                raise
        except Exception as e:
            import logging
            try:
                self.rollback_transaction()
            except Exception:
                pass
            logging.getLogger("audit_repo").warning("Audit log write failed: %s", e)

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
