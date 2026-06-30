import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from repositories.trip_repository import TripRepository
from utils.dates import parse_date

logger = logging.getLogger(__name__)

NON_ACTIVE_STATUSES = {"Delivered", "Completed", "Done", "Cancelled", "Paid"}


class TripConflictService:

    def __init__(self, db):
        self._trip_repo = TripRepository(db)

    def _parse_date(self, date_str) -> Optional[datetime]:
        return parse_date(date_str, "%d/%m/%Y")

    def _estimate_eta(self, trip: dict[str, Any], start_dt: datetime) -> datetime:
        eta_raw = trip.get("end_date", "")
        eta_dt = self._parse_date(eta_raw)
        if eta_dt:
            return eta_dt
        distance = float(trip.get("distance_km") or 0)
        if distance > 0:
            hours = distance / 60.0
            return start_dt + timedelta(hours=hours)
        return start_dt + timedelta(hours=4)

    def _get_departure(self, trip: dict[str, Any]) -> Optional[datetime]:
        dep = self._parse_date(trip.get("start_date", ""))
        if dep:
            return dep
        created = self._parse_date(trip.get("created_at", ""))
        if created:
            return created
        return None

    @staticmethod
    def _same_entity(truck_plate: str, other_truck: str, truck_id, other_truck_id, driver_id, other_driver) -> tuple:
        """Return (same_truck, same_driver) tuple comparing entity identifiers."""
        same_truck = bool(
            (truck_plate and other_truck and truck_plate == other_truck)
            or (truck_id is not None and other_truck_id is not None and truck_id == other_truck_id)
        )
        same_driver = bool(
            driver_id is not None and other_driver is not None and driver_id == other_driver
        )
        return same_truck, same_driver

    def check_conflicts(self, trip_data: dict[str, Any]) -> list[dict[str, Any]]:
        truck_plate = (trip_data.get("truck_number") or trip_data.get("truck_plate") or "").strip()
        truck_id = trip_data.get("truck_id")
        driver_id = trip_data.get("driver_id")
        self_trip_id = trip_data.get("id") or trip_data.get("trip_id_num")

        departure = self._get_departure(trip_data)
        if not departure:
            return []

        eta = self._estimate_eta(trip_data, departure)

        # Fetch only relevant trips: active trips matching truck OR driver
        candidate_ids = set()
        candidates: list[dict[str, Any]] = []

        if truck_plate or truck_id:
            truck_trips = self._trip_repo.get_active_for_truck(
                truck_plate=truck_plate, truck_id=truck_id,
            )
            for t in truck_trips:
                tid = t.get("id")
                if tid and tid != self_trip_id and tid not in candidate_ids:
                    candidate_ids.add(tid)
                    candidates.append(t)

        if driver_id:
            driver_trips = self._trip_repo.get_active_for_driver(driver_id)
            for t in driver_trips:
                tid = t.get("id")
                if tid and tid != self_trip_id and tid not in candidate_ids:
                    candidate_ids.add(tid)
                    candidates.append(t)

        conflicts = []
        for trip in candidates:
            trip_id_val = trip.get("id")

            other_truck = (trip.get("truck_number") or "").strip()
            other_truck_id = trip.get("truck_id")
            other_driver = trip.get("driver_id")

            same_truck, same_driver = self._same_entity(
                truck_plate, other_truck, truck_id, other_truck_id, driver_id, other_driver
            )
            if not same_truck and not same_driver:
                continue

            other_dep = self._get_departure(trip)
            if not other_dep:
                continue
            other_eta = self._estimate_eta(trip, other_dep)

            if departure < other_eta and eta > other_dep:
                conflicts.append({
                    "trip_id": trip_id_val,
                    "truck_plate": other_truck,
                    "driver_name": trip.get("driver_name", ""),
                    "driver_id": other_driver,
                    "status": trip.get("status", ""),
                    "overlap_description": f"{other_dep.strftime('%d/%m')} - {other_eta.strftime('%d/%m')}",
                    "same_truck": same_truck,
                    "same_driver": same_driver,
                })

        return conflicts

    def is_truck_available(self, truck_plate: str = "",
                           truck_id: Optional[int] = None,
                           from_date: Optional[str] = None,
                           to_date: Optional[str] = None) -> bool:
        if not truck_plate and not truck_id:
            return True
        conflicts = self.check_conflicts({
            "truck_plate": truck_plate,
            "truck_id": truck_id,
            "start_date": from_date or "",
            "end_date": to_date or "",
        })
        return len(conflicts) == 0

    def is_driver_available(self, driver_id: int,
                            from_date: Optional[str] = None,
                            to_date: Optional[str] = None) -> bool:
        if not driver_id:
            return True
        conflicts = self.check_conflicts({
            "driver_id": driver_id,
            "start_date": from_date or "",
            "end_date": to_date or "",
        })
        return len(conflicts) == 0

    def get_next_available_slot(self, truck_plate: str = "", truck_id: Optional[int] = None) -> Optional[str]:
        if not truck_plate and not truck_id:
            return None
        # Query only trips for this truck — fast, indexed
        trips = self._trip_repo.get_active_for_truck(
            truck_plate=truck_plate, truck_id=truck_id,
        )
        latest_eta = datetime.now()
        for trip in trips:
            dep = self._get_departure(trip)
            if not dep:
                continue
            eta = self._estimate_eta(trip, dep)
            if eta > latest_eta:
                latest_eta = eta
        return latest_eta.strftime("%d/%m/%Y %H:%M") if latest_eta > datetime.now() else None

    def get_next_available_slot_for_driver(self, driver_id: int) -> Optional[str]:
        if not driver_id:
            return None
        trips = self._trip_repo.get_active_for_driver(driver_id)
        latest_eta = datetime.now()
        for trip in trips:
            dep = self._get_departure(trip)
            if not dep:
                continue
            eta = self._estimate_eta(trip, dep)
            if eta > latest_eta:
                latest_eta = eta
        return latest_eta.strftime("%d/%m/%Y %H:%M") if latest_eta > datetime.now() else None

    def describe_conflict(self, conflict: dict[str, Any]) -> str:
        parts = []
        if conflict.get("same_truck"):
            parts.append(
                f"Truck {conflict['truck_plate']} is on trip TRP-{conflict['trip_id']}"
            )
        if conflict.get("same_driver"):
            parts.append(
                f"Driver {conflict['driver_name']} is on trip TRP-{conflict['trip_id']}"
            )
        parts.append(f"({conflict.get('overlap_description', '')})")
        return " ".join(parts)
