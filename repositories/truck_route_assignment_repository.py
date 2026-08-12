"""Truck-route assignment repository."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class TruckRouteAssignmentRepository(BaseRepository):
    TABLE = "truck_route_assignments"
    COLUMNS = [
        "id", "truck_id", "route_id", "status", "assigned_at", "started_at",
        "completed_at", "archived_at", "notes", "company_id",
    ]

    def assign(
        self,
        truck_id: str,
        route_id: int,
        status: str = "assigned",
        assigned_at: str = "",
        started_at: Optional[str] = None,
        notes: str = "",
    ) -> int:
        data = {"truck_id": str(truck_id), "route_id": int(route_id),
                "status": status, "assigned_at": assigned_at,
                "started_at": started_at, "notes": notes}
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({', '.join(data.keys())}) "
            f"VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()), commit=True,
		)

    def complete(self, route_id: int, completed_at: str) -> bool:
        return self._execute_with_count(
            f"UPDATE {self.TABLE} SET status = 'completed', completed_at = ? "
            f"WHERE route_id = ? AND status IN ('assigned', 'active') "
            f"{self._company_filter()}",
            (completed_at, route_id) + self._company_params(), commit=True,
		) > 0

    def get_by_truck(
        self, truck_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = f"""SELECT a.*, h.total_distance_km, h.duration_min, h.profile,
                            h.stops_json, h.fuel_estimates_json,
                            h.toll_estimates_json, h.profit_estimates_json
                     FROM {self.TABLE} a
                     JOIN route_history_v2 h ON h.id = a.route_id
                     WHERE a.truck_id = ? {self._company_filter('a')}"""
        params: List[Any] = [str(truck_id)] + list(self._company_params())
        if status:
            query += " AND a.status = ?"
            params.append(status)
        query += " ORDER BY COALESCE(a.started_at, a.assigned_at) DESC"
        return self._fetchall(query, tuple(params))
