from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from repositories.trip_repository import TripRepository

logger = logging.getLogger(__name__)

NON_ACTIVE_STATUSES = {"Delivered", "Completed", "Done", "Cancelled", "Paid"}


class TripConflictService:

    def __init__(self, db):
        self._trip_repo = TripRepository(db)

    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse a trip date/datetime in ISO-8601 or DD/MM/YYYY form.

        Production ``start_date`` / ``end_date`` values are ISO-8601
        (``YYYY-MM-DD``, sometimes with a time component) while older
        records and some dialogs still pass ``DD/MM/YYYY``.  ISO formats are
        tried first (full string, so time components are kept); the legacy
        ``DD/MM/YYYY`` branch keeps the original slice-[:10] behaviour so
        trailing time text is tolerated.  Unparseable input returns ``None``.
        """
        if not date_str:
            return None
        raw = str(date_str).strip()
        if not raw:
            return None
        iso_with_t = raw[:-1] if raw.endswith("Z") else raw
        for candidate, fmt in (
            (iso_with_t, "%Y-%m-%dT%H:%M:%S"),
            (raw, "%Y-%m-%d %H:%M:%S"),
            (raw, "%Y-%m-%d %H:%M"),
            (raw, "%Y-%m-%d"),
            (raw[:10], "%d/%m/%Y"),
        ):
            try:
                return datetime.strptime(candidate, fmt)
            except (ValueError, TypeError):
                continue
        return None

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

    def _candidate_conflicts(
        self, trip_data: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Compute conflicts for ``trip_data`` against an in-memory candidate list.

        Shares the exact entity-matching and overlap logic with
        :meth:`check_conflicts`.  ``candidates`` are trip dicts (the rows the
        repo queries return).  The trip itself is skipped by id so callers may
        pass the full active set.
        """
        truck_plate = (trip_data.get("truck_number") or trip_data.get("truck_plate") or "").strip()
        truck_id = trip_data.get("truck_id")
        driver_id = trip_data.get("driver_id")
        self_trip_id = trip_data.get("id") or trip_data.get("trip_id_num")

        departure = self._get_departure(trip_data)
        if not departure:
            return []
        eta = self._estimate_eta(trip_data, departure)

        conflicts = []
        for trip in candidates:
            trip_id_val = trip.get("id")
            if not trip_id_val or trip_id_val == self_trip_id:
                continue

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

    def check_conflicts(self, trip_data: dict[str, Any], company_id=None) -> list[dict[str, Any]]:
        truck_plate = (trip_data.get("truck_number") or trip_data.get("truck_plate") or "").strip()
        truck_id = trip_data.get("truck_id")
        driver_id = trip_data.get("driver_id")
        self_trip_id = trip_data.get("id") or trip_data.get("trip_id_num")

        departure = self._get_departure(trip_data)
        if not departure:
            return []

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

        return self._candidate_conflicts(trip_data, candidates)

    def check_conflicts_batch(
        self, trips: list[dict[str, Any]], company_id=None
    ) -> dict[int, list[dict[str, Any]]]:
        """Check conflicts for many trips with a single reference-data fetch.

        Fetches the whole non-terminal trip universe ONCE (one query) instead
        of per-trip ``get_active_for_truck`` / ``get_active_for_driver`` calls
        (up to two queries per trip), then runs the same overlap logic against
        that in-memory candidate set.

        Returns ``{trip_id: [conflict, ...]}`` — the same per-trip result
        shape :meth:`check_conflicts` produces, keyed by trip id.  Trips with
        no conflicts are omitted.  Per-trip :meth:`check_conflicts` is
        unchanged and still used by the dispatch forms/dialogs.
        """
        if not trips:
            return {}

        # Single reference-data fetch: every non-terminal trip that could be a
        # candidate for any trip in the batch (the same exclusion set the
        # per-trip ``get_active_for_truck`` / ``get_active_for_driver``
        # queries use).
        candidates = self._trip_repo.get_active_excluding_statuses(
            list(NON_ACTIVE_STATUSES), limit=2000,
        )

        result: dict[int, list[dict[str, Any]]] = {}
        for trip in trips:
            tid = trip.get("id") or trip.get("trip_id_num")
            if tid is None:
                continue
            conflicts = self._candidate_conflicts(trip, candidates)
            if conflicts:
                result[tid] = conflicts
        return result

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

    def check_conflicts_for_trip(
        self,
        truck_plate: str = "",
        driver_id: Optional[int] = None,
        start_date: str = "",
        end_date: str = "",
        distance_km: float = 0,
    ) -> list[str]:
        """Convenience method that checks conflicts and returns human-readable descriptions.

        Delegates to :meth:`check_conflicts` and :meth:`describe_conflict` internally.
        The caller (view) only needs to display the returned messages.
        """
        conflicts = self.check_conflicts({
            "truck_plate": truck_plate,
            "driver_id": driver_id,
            "start_date": start_date,
            "end_date": end_date,
            "distance_km": distance_km,
        })
        return [self.describe_conflict(c) for c in conflicts]

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

    def get_next_available_slots_for_trucks(
        self, truck_plates: list[str]
    ) -> dict[str, str | None]:
        """Return {plate_number: next_available_time_or_None} for batch of trucks.

        Returns None for plates with no conflicts.
        """
        if not truck_plates:
            return {}
        placeholders = ", ".join("?" for _ in truck_plates)
        non_active = ", ".join(f"'{s}'" for s in sorted(NON_ACTIVE_STATUSES))
        rows = self._trip_repo._fetchall(
            f"""SELECT t.plate_number, MIN(trip.end_date) as next_available
                FROM trucks t
                LEFT JOIN trips trip ON t.id = trip.truck_id
                  AND trip.status NOT IN ({non_active})
                WHERE t.plate_number IN ({placeholders})
                GROUP BY t.plate_number""",
            tuple(truck_plates)
        )
        return {r["plate_number"]: r.get("next_available") for r in rows}

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
