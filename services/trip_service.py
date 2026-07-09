from typing import Any, Optional

from repositories.route_repository import RouteRepository
from repositories.trip_repository import TripRepository
from services.operations.event_bus import TRIP_CREATED, TRIP_DELETED, TRIP_UPDATED, EventBus

class TripService:
    def __init__(self, db):
        self.db = db
        self._event_bus = EventBus()
        self._trip_repo = TripRepository(db)
        self._route_repo = RouteRepository(db)

    def get_filtered(self, search: str = "", status: str = "", limit: int = 200) -> list[dict[str, Any]]:
        return self._trip_repo.get_filtered(search=search, truck="", status=status, limit=limit)

    def get_by_id(self, trip_id: int) -> Optional[dict[str, Any]]:
        return self._trip_repo.get_by_id(trip_id)

    def get_by_statuses(self, statuses: list[str]) -> list[dict[str, Any]]:
        return self._trip_repo.get_by_statuses(statuses)

    def get_all(self, limit: int = 500) -> list[dict[str, Any]]:
        return self._trip_repo.get_all(limit=limit)

    def add(self, data: dict[str, Any]) -> int:
        new_id = self._trip_repo.create(data)
        self._event_bus.publish(TRIP_CREATED, {"trip_id": new_id, "data": data})
        return new_id

    def update(self, trip_id: int, data: dict[str, Any]) -> None:
        self._trip_repo.update(trip_id, data)
        self._event_bus.publish(TRIP_UPDATED, {"trip_id": trip_id, "changes": data})

    def update_cmr_fields(self, trip_id: int, cmr_number: str, cmr_seq: int) -> None:
        self._trip_repo.update_cmr_fields(trip_id, cmr_number, cmr_seq)

    def get_route_stops_json(self, route_id: int) -> Optional[str]:
        return self._route_repo.get_stops_json(route_id)

    def delete(self, trip_id: int) -> None:
        self._trip_repo.delete(trip_id)
        self._event_bus.publish(TRIP_DELETED, {"trip_id": trip_id})
