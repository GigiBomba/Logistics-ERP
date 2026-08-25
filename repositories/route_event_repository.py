"""Route event repository — persists route lifecycle events."""
from __future__ import annotations

from typing import Optional

from repositories import BaseRepository

class RouteEventRepository(BaseRepository):
    TABLE = "route_events"
    COLUMNS = [
        "id", "route_id", "event_type", "payload_json", "created_at", "company_id",
    ]

    def create(
        self,
        route_id: Optional[int],
        event_type: str,
        payload_json: str,
        created_at: str,
    ) -> int:
        data = {"route_id": route_id, "event_type": event_type,
                "payload_json": payload_json, "created_at": created_at}
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({', '.join(data.keys())}) "
            f"VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()), commit=True,
		)

    def delete_orphans(self) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE route_id IS NOT NULL "
            f"AND route_id NOT IN (SELECT id FROM route_history_v2) "
            f"{self._company_filter()}",
            self._company_params(), commit=True,
		)
