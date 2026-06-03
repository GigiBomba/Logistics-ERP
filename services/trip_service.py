from datetime import datetime
from typing import Any, Dict, List, Optional

from services.operations.event_bus import EventBus, TRIP_CREATED, TRIP_UPDATED, TRIP_DELETED
from repositories.trip_repository import TripRepository


class TripService:
    def __init__(self, db):
        self.db = db
        self._event_bus = EventBus()
        self._trip_repo = TripRepository(db)

    def get_filtered(self, search: str = "", status: str = "") -> List[Dict[str, Any]]:
        return self.db.get_filtered_trips(search, status=status)

    def get_by_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self.db.get_trip_by_id(trip_id)

    def get_by_statuses(self, statuses: List[str]) -> List[Dict[str, Any]]:
        return self._trip_repo.get_by_statuses(statuses)

    def get_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        return self._trip_repo.get_all(limit=limit)

    def add(self, data: Dict[str, Any]) -> int:
        new_id = self.db.add_trip(data)
        self._event_bus.publish(TRIP_CREATED, {"trip_id": new_id, "data": data})
        return new_id

    def update(self, trip_id: int, data: Dict[str, Any]) -> None:
        self.db.update_trip(trip_id, data)
        self._event_bus.publish(TRIP_UPDATED, {"trip_id": trip_id, "changes": data})

    def delete(self, trip_id: int) -> None:
        self.db.delete_trip(trip_id)
        self._event_bus.publish(TRIP_DELETED, {"trip_id": trip_id})

    def duplicate(self, trip_id: int, timestamp: Optional[str] = None) -> None:
        old = self.get_by_id(trip_id)
        if not old:
            return
        if "id" in old:
            del old["id"]
        old["created_at"] = timestamp or datetime.now().strftime("%d/%m/%Y %H:%M")
        old["status"] = "Planned"
        self.add(old)
