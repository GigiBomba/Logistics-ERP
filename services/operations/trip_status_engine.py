from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from models.trip_models import TripUpdate
from services.operations.alert_manager import AlertManager, AlertType, Severity
from services.operations.event_bus import (
    TRIP_CREATED,
    TRIP_STATUS_CHANGED,
    TRIP_UPDATED,
    VALID_TRANSITIONS,
    EventBus,
)
from services.operations.rules import Rules

logger = logging.getLogger("operations.trip_status_engine")


class TripStatusEngine:
    def __init__(self, db):
        from services.trip_service import TripService
        self._trip_service = TripService(db)
        self._alert_mgr = AlertManager(db)
        self._event_bus = EventBus()
        self._rules = Rules()
        self._subscribe()

    def _subscribe(self):
        self._event_bus.subscribe(TRIP_CREATED, self._on_trip_event)
        self._event_bus.subscribe(TRIP_UPDATED, self._on_trip_event)
        self._event_bus.subscribe(TRIP_STATUS_CHANGED, self._on_trip_status_change)
        logger.info("TripStatusEngine subscribed to events")

    def shutdown(self):
        try:
            self._event_bus.unsubscribe(TRIP_CREATED, self._on_trip_event)
            self._event_bus.unsubscribe(TRIP_UPDATED, self._on_trip_event)
            self._event_bus.unsubscribe(TRIP_STATUS_CHANGED, self._on_trip_status_change)
            logger.debug("TripStatusEngine unsubscribed events")
        except Exception:
            pass

    def _on_trip_event(self, ev: dict[str, Any]) -> None:
        trip_id = ev["data"].get("trip_id")
        if trip_id:
            self.evaluate_trip(trip_id)

    def _on_trip_status_change(self, ev: dict[str, Any]) -> None:
        trip_id = ev["data"].get("trip_id")
        new_status = ev["data"].get("new_status", "")
        # Only evaluate if the new status is one we monitor for delays
        if trip_id and new_status in ("Planned", "Loading"):
            self.evaluate_trip(trip_id)

    def evaluate_trip(self, trip_id: Any) -> int:
        count = 0
        try:
            trip_id_int = int(trip_id)
        except (TypeError, ValueError):
            return 0
        try:
            row = self._trip_service.get_by_id(trip_id_int)
            if row:
                delay_hours = self._rules.get("trip_delay_hours", 2)
                plate = row.get("truck_number") or "?"
                status = row.get("status") or ""
                created_raw = row.get("created_at")
                if created_raw and status in ("Planned", "Loading"):
                    created = None
                    raw_str = str(created_raw)
                    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
                        try:
                            created = datetime.strptime(raw_str[:19] if len(raw_str) > 10 else raw_str[:10], fmt)
                            break
                        except ValueError:
                            continue
                    if created is None:
                        return 0
                    hours_idle = (datetime.now() - created).total_seconds() / 3600
                    if hours_idle > delay_hours:
                        alert_truck_id = str(row.get("truck_id")) if row.get("truck_id") else plate
                        self._alert_mgr.create_alert(
                            AlertType.TRIP_DELAY, Severity.WARNING,
                            f"Trip {trip_id} delayed",
                            f"Trip has been in '{status}' for {int(hours_idle)} hours (truck {plate})",
                            truck_id=alert_truck_id,
                            trip_id=trip_id,
                        )
                        count += 1
        except Exception as e:
            logger.warning("evaluate_trip #%s failed: %s", trip_id, e, exc_info=True)
        return count

    def evaluate_all(self) -> int:
        count = 0
        try:
            trips = self._trip_service.get_by_statuses(["Planned", "Loading"])
            for t in trips:
                count += self.evaluate_trip(str(t["id"]))
        except Exception as e:
            logger.error("evaluate_all trips failed: %s", e)
        return count

    def get_valid_transitions(self, current_status: str) -> list:
        return VALID_TRANSITIONS.get(current_status, [])

    def transition(self, trip_id: int, new_status: str, trigger: str = "manual") -> bool:
        try:
            trip = self._trip_service.get_by_id(trip_id)
            if not trip:
                raise ValueError(f"Trip {trip_id} not found")

            old_status = trip.get("status", "")
            valid = self.get_valid_transitions(old_status)

            if new_status not in valid:
                raise ValueError(f"Cannot transition from {old_status} to {new_status}")

            self._trip_service.update(trip_id, TripUpdate(status=new_status))

            # Record trip status history
            try:
                self._trip_service._trip_repo.record_status_history(
                    trip_id, old_status, new_status, trigger
                )
            except Exception as hist_err:
                logger.warning("Failed to record status history for trip %d: %s", trip_id, hist_err)

            self._event_bus.publish(TRIP_STATUS_CHANGED, {
                "trip_id": trip_id,
                "old_status": old_status,
                "new_status": new_status,
            })

            logger.info("Trip %d status changed: %s -> %s", trip_id, old_status, new_status)
            return True
        except Exception as e:
            logger.error("transition failed for trip %d: %s", trip_id, e)
            raise
