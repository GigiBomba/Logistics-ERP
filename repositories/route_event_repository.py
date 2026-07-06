"""Route event repository — persists route lifecycle events."""
from typing import Optional

from repositories import BaseRepository

class RouteEventRepository(BaseRepository):
    TABLE = "route_events"

    def create(
        self,
        route_id: Optional[int],
        event_type: str,
        payload_json: str,
        created_at: str,
    ) -> int:
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} (route_id, event_type, payload_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (route_id, event_type, payload_json, created_at),
        )

    def delete_orphans(self) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE route_id IS NOT NULL "
            "AND route_id NOT IN (SELECT id FROM route_history_v2)"
        )
