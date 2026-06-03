import logging
from typing import Any, Dict, Optional

from repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository
from services.operations.event_bus import EventBus, TRUCK_UPDATED

logger = logging.getLogger(__name__)


class DriverTruckService:

    def __init__(self, db):
        self._db = db
        self._repo = DriverTruckAssignmentRepository(db)
        self._fleet_repo = FleetRepository(db)
        self._driver_repo = DriverRepository(db)
        self._event_bus = EventBus()

    def assign_driver_to_truck(self, driver_id: int, truck_id: int) -> Dict[str, Any]:
        existing_driver = self._repo.get_by_driver(driver_id)
        existing_truck = self._repo.get_by_truck(truck_id)

        action = "assigned"
        swapped_driver = None

        if existing_driver and existing_driver["truck_id"] != truck_id:
            old_truck_id = existing_driver["truck_id"]
            self._repo.unassign_driver(driver_id)
            action = "reassigned"

        if existing_truck and existing_truck["driver_id"] != driver_id:
            other_driver_id = existing_truck["driver_id"]
            if existing_driver and existing_driver["truck_id"] == truck_id and existing_driver["driver_id"] == other_driver_id:
                pass
            else:
                self._repo.unassign_truck(truck_id)
                swapped_driver = other_driver_id
                action = "swapped"

        self._repo.assign(driver_id, truck_id)

        self._event_bus.publish(TRUCK_UPDATED, {
            "truck_id": truck_id,
            "driver_id": driver_id,
            "action": action,
        })

        return {"action": action, "swapped_driver": swapped_driver}

    def unassign_driver(self, driver_id: int) -> Optional[int]:
        existing = self._repo.get_by_driver(driver_id)
        if not existing:
            return None
        truck_id = existing["truck_id"]
        self._repo.unassign_driver(driver_id)

        self._event_bus.publish(TRUCK_UPDATED, {
            "truck_id": truck_id,
            "driver_id": None,
            "action": "unassigned",
        })
        return truck_id

    def unassign_truck(self, truck_id: int) -> Optional[int]:
        existing = self._repo.get_by_truck(truck_id)
        if not existing:
            return None
        driver_id = existing["driver_id"]
        self._repo.unassign_truck(truck_id)

        self._event_bus.publish(TRUCK_UPDATED, {
            "truck_id": truck_id,
            "driver_id": None,
            "action": "unassigned",
        })
        return driver_id

    def get_truck_for_driver(self, driver_id: int) -> Optional[Dict[str, Any]]:
        assignment = self._repo.get_by_driver(driver_id)
        if not assignment:
            return None
        return self._fleet_repo.get_by_id(assignment["truck_id"])

    def get_driver_for_truck(self, truck_id: int) -> Optional[Dict[str, Any]]:
        assignment = self._repo.get_by_truck(truck_id)
        if not assignment:
            return None
        return self._driver_repo.get_by_id(assignment["driver_id"])

    def get_truck_plate_for_driver(self, driver_id: int) -> str:
        return self._repo.get_truck_plate_for_driver(driver_id)

    def get_driver_name_for_truck(self, truck_id: int) -> str:
        return self._repo.get_driver_name_for_truck(truck_id)

    def on_driver_deleted(self, driver_id: int) -> None:
        self.unassign_driver(driver_id)

    def on_truck_deleted(self, truck_id: int) -> None:
        self.unassign_truck(truck_id)
