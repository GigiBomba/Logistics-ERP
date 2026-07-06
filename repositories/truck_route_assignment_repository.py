"""Truck-route assignment repository."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class TruckRouteAssignmentRepository(BaseRepository):
    TABLE = "truck_route_assignments"

    def assign(
        self,
        truck_id: str,
        route_id: int,
        status: str = "assigned",
        assigned_at: str = "",
        started_at: Optional[str] = None,
        notes: str = "",
    ) -> int:
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} (truck_id, route_id, status, assigned_at, started_at, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(truck_id), int(route_id), status, assigned_at, started_at, notes),
        )

    def complete(self, route_id: int, completed_at: str) -> bool:
        return self._execute_with_count(
            f"UPDATE {self.TABLE} SET status = 'completed', completed_at = ? "
            "WHERE route_id = ? AND status IN ('assigned', 'active')",
            (completed_at, route_id),
        ) > 0

    def get_by_truck(
        self, truck_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = f"""SELECT a.*, h.total_distance_km, h.duration_min, h.profile,
                            h.stops_json, h.fuel_estimates_json,
                            h.toll_estimates_json, h.profit_estimates_json
                     FROM {self.TABLE} a
                     JOIN route_history_v2 h ON h.id = a.route_id
                     WHERE a.truck_id = ?"""
        params: List[Any] = [str(truck_id)]
        if status:
            query += " AND a.status = ?"
            params.append(status)
        query += " ORDER BY COALESCE(a.started_at, a.assigned_at) DESC"
        return self._fetchall(query, tuple(params))
