"""Trip status workflow — status transitions, validation, and odometer updates.

Extracted from OperationsEngine to reduce responsibilities.
Handles force_trip_status, get_valid_transitions, and truck odometer updates.
"""

import logging
from typing import Any

from services.operations.event_bus import (
    TRIP_STATUS_CHANGED,
    TRUCK_ODOMETER_UPDATED,
    VALID_TRANSITIONS,
)
from services.operations.undo_stack import UndoCommand

logger = logging.getLogger("operations.trip_status_workflow")


class TripStatusWorkflow:
    """Manages trip status transitions and side effects (odometer, undo, events)."""

    def __init__(self, db, trip_service, event_bus, maintenance_engine, undo_stack):
        self._db = db
        self._trip_service = trip_service
        self._event_bus = event_bus
        self._maintenance_engine = maintenance_engine
        self._undo_stack = undo_stack

    def get_valid_transitions(self, current_status: str) -> list[str]:
        """Return list of valid next statuses based on current status."""
        return VALID_TRANSITIONS.get(current_status, [])

    def force_trip_status(self, trip_id: int, new_status: str, skip_undo: bool = False) -> bool:
        """Force a trip to a specific status, updating odometer if completed."""
        if not self._trip_service:
            logger.error("force_trip_status: TripService not available")
            return False
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if not trip:
                logger.error("force_trip_status: trip %d not found", trip_id)
                return False

            old_status = trip.get("status", "")
            if old_status == new_status:
                return True

            normalized_old = {
                "InTransit": "In Transit",
                "Active": "In Transit",
                "InProgress": "In Transit",
            }.get(old_status, old_status)

            normalized_new = {
                "InTransit": "In Transit",
                "Active": "In Transit",
                "InProgress": "In Transit",
            }.get(new_status, new_status)

            valid_targets = VALID_TRANSITIONS.get(normalized_old, [])
            if normalized_new not in valid_targets:
                logger.warning(
                    "force_trip_status: invalid transition %s -> %s for trip %d",
                    old_status, new_status, trip_id,
                )
                return False

            self._trip_service.update(trip_id, {"status": normalized_new})

            if normalized_new in ("Delivered", "Completed"):
                self._update_truck_odometer_on_completion(trip)

            self._event_bus.publish(TRIP_STATUS_CHANGED, {
                "trip_id": trip_id,
                "old_status": old_status,
                "new_status": new_status,
            })

            logger.info("Trip %d status changed: %s -> %s", trip_id, old_status, new_status)

            if not skip_undo:
                prev_odo = None
                if new_status in ("Delivered", "Completed"):
                    truck_id = trip.get("truck_id")
                    if truck_id:
                        from repositories.fleet_repository import FleetRepository
                        fleet_repo = FleetRepository(self._db)
                        truck = fleet_repo.get_by_id(int(truck_id))
                        if truck:
                            prev_odo = truck.get("mileage")
                self._undo_stack.push(UndoCommand(
                    trip_id=trip_id,
                    old_status=old_status,
                    new_status=new_status,
                    previous_odometer=prev_odo,
                    truck_id=trip.get("truck_id"),
                ))

            return True
        except Exception as e:
            logger.error("force_trip_status failed for trip %d: %s", trip_id, e)
            return False

    def _update_truck_odometer_on_completion(self, trip: dict[str, Any]) -> None:
        """Update truck odometer when trip is completed, preferring truck_id FK."""
        try:
            distance_km = trip.get("distance_km")
            truck_id = trip.get("truck_id")
            truck_number = trip.get("truck_number")

            if not distance_km or distance_km <= 0:
                logger.debug("Trip %s has no distance, skipping odometer update", trip.get("id"))
                return

            from repositories.fleet_repository import FleetRepository
            fleet_repo = FleetRepository(self._db)
            truck = None

            if truck_id:
                truck = fleet_repo.get_by_id(int(truck_id))

            if not truck and truck_number:
                truck = fleet_repo.get_by_plate(truck_number)

            if not truck:
                logger.warning("Truck not found (id=%s, plate=%s), cannot update odometer",
                               truck_id, truck_number)
                return

            current_odometer = truck.get("mileage", 0) or 0
            new_odometer = current_odometer + distance_km

            fleet_repo.update(truck["id"], {"mileage": new_odometer})

            logger.info("Updated truck %s odometer: %.1f -> %.1f km (+%.1f km)",
                       truck.get("plate_number", truck["id"]), current_odometer, new_odometer, distance_km)

            if self._maintenance_engine:
                self._maintenance_engine.evaluate_truck(truck["id"])

            self._event_bus.publish(TRUCK_ODOMETER_UPDATED, {
                "truck_id": truck["id"],
                "truck_number": truck.get("plate_number", ""),
                "previous_km": current_odometer,
                "added_km": distance_km,
                "new_total_km": new_odometer,
            })
        except Exception as e:
            logger.error("Failed to update truck odometer: %s", e)
