"""Dispatch service — business logic for dispatch board operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from datetime import datetime, timedelta
from typing import Optional

from services.dispatch_service.availability import AvailabilityChecker
from services.dispatch_service.errors import (
    DispatchError,
    DriverNotFoundError,
    InvalidStatusTransitionError,
    ResourceUnavailableError,
    TripArchivedError,
    TripNotFoundError,
    TruckNotFoundError,
)
from services.dispatch_service.models import (
    BulkDispatchResult,
    DispatchBoardFilters,
    DispatchDataResponse,
    DispatchResult,
    UndoToken,
)
from services.operations.alert_manager import Alert, AlertType, Severity
from services.operations.event_bus import (
    ALERT_CREATED,
    TRIP_ASSIGNED,
    TRIP_STATUS_CHANGED,
    VALID_TRANSITIONS,
)

logger = logging.getLogger(__name__)

# ── Canonical status → column mapping (replicated from board_state.py) ──
STATUS_TO_COLUMN: dict[str, str] = {
    "Planned": "Planned",
    "Scheduled": "Planned",
    "Pending": "Planned",
    "Loading": "Loading",
    "Preparing": "Loading",
    "Pickup": "Loading",
    "In Transit": "In Transit",
    "InTransit": "In Transit",
    "Active": "In Transit",
    "InProgress": "In Transit",
    "Delivered": "Delivered",
    "Completed": "Delivered",
    "Done": "Delivered",
    "Invoiced": "Delivered",
    "Paid": "Delivered",
    "Cancelled": "Cancelled",
}

COLUMN_KEYS = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]


class DispatchService:
    """Pure business logic for dispatch operations. No GUI dependencies."""

    def __init__(
        self,
        trip_service,
        fleet_repo,
        driver_repo,
        conflict_service,
        dta_service=None,
        tacho_repo=None,
        event_bus=None,
        alert_manager=None,
        ops_engine=None,
    ):
        self._trip_service = trip_service
        self._fleet_repo = fleet_repo
        self._driver_repo = driver_repo
        self._conflict_service = conflict_service
        self._dta_service = dta_service
        self._event_bus = event_bus
        self._alert_manager = alert_manager
        self._ops_engine = ops_engine

        self._availability = AvailabilityChecker(
            fleet_repo=fleet_repo,
            driver_repo=driver_repo,
            conflict_service=conflict_service,
            tacho_repo=tacho_repo,
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def assign_truck(self, trip_id: int, truck_id: int) -> DispatchResult:
        """Assign a truck to a trip with full validation."""
        # 1. Validate existence
        trip = self._validate_trip_exists(trip_id)
        truck = self._validate_truck_exists(truck_id)

        # 2. Build availability check data
        trip_data: dict[str, Any] = {"truck_id": truck_id}

        # 3. Run availability check
        avail = self._availability.check_truck(truck, trip_data)
        if not avail.available:
            raise ResourceUnavailableError(avail.status_text)

        # 4. Snapshot current state for undo
        previous = {
            "truck_number": trip.get("truck_number"),
            "truck_id": trip.get("truck_id"),
        }

        # 5. Get truck plate and update trip
        plate = truck.get("plate") or truck.get("truck_number") or str(truck_id)
        self._trip_service.update(
            trip_id,
            {"truck_number": plate, "truck_id": truck_id},
        )

        # 6. Emit event (best-effort fire-and-forget)
        try:
            if self._event_bus is not None:
                self._event_bus.publish(
                    TRIP_ASSIGNED,
                    {
                        "trip_id": trip_id,
                        "truck_id": truck_id,
                        "truck_plate": plate,
                    },
                )
        except Exception:
            logger.debug("Failed to publish TRIP_ASSIGNED event for trip #%d", trip_id)

        # 7. Build undo token and result
        undo_token = UndoToken(
            operation="assign_truck",
            trip_id=trip_id,
            previous_state=previous,
            undo_description=f"Unassign truck {plate} from trip #{trip_id}",
        )

        logger.info("Assigned truck %s (id=%d) to trip #%d", plate, truck_id, trip_id)
        return DispatchResult(
            success=True,
            trip_id=trip_id,
            operation="assign_truck",
            message=f"Assigned truck {plate} to trip #{trip_id}",
            undo_token=undo_token,
            details={"truck_plate": plate},
        )

    def assign_driver(self, trip_id: int, driver_id: int) -> DispatchResult:
        """Assign a driver to a trip with full validation."""
        # 1. Validate existence
        trip = self._validate_trip_exists(trip_id)
        driver = self._validate_driver_exists(driver_id)

        # 2. Build availability check data
        trip_data: dict[str, Any] = {"driver_id": driver_id}

        # 3. Run availability check
        avail = self._availability.check_driver(driver, trip_data)
        if not avail.available:
            raise ResourceUnavailableError(avail.status_text)

        # 4. Snapshot current state for undo
        previous = {
            "driver_id": trip.get("driver_id"),
            "driver_name": trip.get("driver_name"),
        }

        # 5. Get driver name and update trip
        driver_name = driver.get("name") or driver.get("driver_name") or ""
        self._trip_service.update(
            trip_id,
            {"driver_id": driver_id, "driver_name": driver_name},
        )

        # 6. Emit event (best-effort fire-and-forget)
        try:
            if self._event_bus is not None:
                self._event_bus.publish(
                    TRIP_ASSIGNED,
                    {
                        "trip_id": trip_id,
                        "driver_id": driver_id,
                        "driver_name": driver_name,
                    },
                )
        except Exception:
            logger.debug("Failed to publish TRIP_ASSIGNED event for trip #%d", trip_id)

        # 7. Build undo token and result
        undo_token = UndoToken(
            operation="assign_driver",
            trip_id=trip_id,
            previous_state=previous,
            undo_description=f"Unassign driver {driver_name} from trip #{trip_id}",
        )

        logger.info("Assigned driver %s (id=%d) to trip #%d", driver_name, driver_id, trip_id)
        return DispatchResult(
            success=True,
            trip_id=trip_id,
            operation="assign_driver",
            message=f"Assigned driver {driver_name} to trip #{trip_id}",
            undo_token=undo_token,
            details={"driver_name": driver_name, "driver_id": driver_id},
        )

    def assign_both(
        self,
        trip_id: int,
        truck_id: int | None,
        driver_id: int | None,
    ) -> DispatchResult:
        """Assign both truck and driver. Rolls back truck if driver assignment fails."""
        truck_undo: UndoToken | None = None
        truck_plate: str = ""

        # 1. Assign truck if requested
        if truck_id is not None:
            truck_result = self.assign_truck(trip_id, truck_id)
            truck_undo = truck_result.undo_token
            truck_plate = truck_result.details.get("truck_plate", "")

        # 2. Assign driver if requested
        driver_name: str = ""
        if driver_id is not None:
            try:
                driver_result = self.assign_driver(trip_id, driver_id)
                driver_name = driver_result.details.get("driver_name", "")
            except DispatchError:
                # Rollback truck assignment if driver fails
                if truck_undo is not None:
                    self._trip_service.update(
                        trip_id,
                        truck_undo.previous_state,
                    )
                    logger.info(
                        "Rolled back truck assignment on trip #%d after driver assignment failure",
                        trip_id,
                    )
                raise

        # 3. Best-effort DTA pairing
        if self._dta_service is not None and driver_id is not None and truck_id is not None:
            try:
                self._dta_service.assign_driver_to_truck(driver_id, truck_id)
                logger.debug(
                    "DTA pairing: driver %d <-> truck %d", driver_id, truck_id,
                )
            except Exception:
                logger.debug(
                    "DTA pairing failed for driver %d / truck %d (best-effort)",
                    driver_id,
                    truck_id,
                )

        # 4. Build composite result
        details: dict[str, Any] = {}
        if truck_plate:
            details["truck_plate"] = truck_plate
        if driver_name:
            details["driver_name"] = driver_name

        logger.info(
            "Assigned both truck=%s driver=%s to trip #%d",
            truck_plate or "(none)",
            driver_name or "(none)",
            trip_id,
        )
        return DispatchResult(
            success=True,
            trip_id=trip_id,
            operation="assign_both",
            message=f"Assigned truck {truck_plate or '—'} and driver {driver_name or '—'} to trip #{trip_id}",
            details=details,
        )

    def bulk_assign_truck(self, trip_ids: list[int], truck_id: int) -> BulkDispatchResult:
        """Bulk assign a truck to multiple trips."""
        # 1. Validate truck once upfront (fail fast)
        truck = self._validate_truck_exists(truck_id)
        plate = truck.get("plate") or truck.get("truck_number") or str(truck_id)

        results: list[DispatchResult] = []
        undo_tokens: list[UndoToken] = []
        succeeded = 0
        failed = 0

        for trip_id in trip_ids:
            try:
                result = self.assign_truck(trip_id, truck_id)
                succeeded += 1
                results.append(result)
                if result.undo_token is not None:
                    undo_tokens.append(result.undo_token)
            except DispatchError as e:
                failed += 1
                results.append(
                    DispatchResult(
                        success=False,
                        trip_id=trip_id,
                        operation="assign_truck",
                        message=str(e),
                    )
                )
                logger.error(
                    "Bulk assign truck %s (id=%d) failed for trip #%d: %s",
                    plate, truck_id, trip_id, e,
                )

        logger.info(
            "Bulk assign truck %s: %d succeeded, %d failed out of %d",
            plate, succeeded, failed, len(trip_ids),
        )
        return BulkDispatchResult(
            total=len(trip_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
            undo_tokens=undo_tokens,
        )

    def bulk_assign_driver(self, trip_ids: list[int], driver_id: int) -> BulkDispatchResult:
        """Bulk assign a driver to multiple trips."""
        # 1. Validate driver once upfront (fail fast)
        driver = self._validate_driver_exists(driver_id)
        driver_name = driver.get("name") or driver.get("driver_name") or ""

        results: list[DispatchResult] = []
        undo_tokens: list[UndoToken] = []
        succeeded = 0
        failed = 0

        for trip_id in trip_ids:
            try:
                result = self.assign_driver(trip_id, driver_id)
                succeeded += 1
                results.append(result)
                if result.undo_token is not None:
                    undo_tokens.append(result.undo_token)
            except DispatchError as e:
                failed += 1
                results.append(
                    DispatchResult(
                        success=False,
                        trip_id=trip_id,
                        operation="assign_driver",
                        message=str(e),
                    )
                )
                logger.error(
                    "Bulk assign driver %s (id=%d) failed for trip #%d: %s",
                    driver_name, driver_id, trip_id, e,
                )

        logger.info(
            "Bulk assign driver %s: %d succeeded, %d failed out of %d",
            driver_name, succeeded, failed, len(trip_ids),
        )
        return BulkDispatchResult(
            total=len(trip_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
            undo_tokens=undo_tokens,
        )

    def transition_status(self, trip_id: int, new_status: str) -> DispatchResult:
        """Transition a trip to a new status. Delegates to OperationsEngine for undo."""
        # 1. Validate trip exists
        trip = self._validate_trip_exists(trip_id)
        old_status = trip.get("status", "")

        # 2. Validate transition
        valid = VALID_TRANSITIONS.get(old_status, [])
        if new_status not in valid:
            raise InvalidStatusTransitionError(
                f"Cannot transition trip #{trip_id} from '{old_status}' to '{new_status}'"
                f" — valid options: {valid}"
            )

        # 3a. If ops_engine available, delegate to it (handles undo internally)
        if self._ops_engine is not None:
            try:
                self._ops_engine.force_trip_status(trip_id, new_status)
                logger.info(
                    "Trip #%d status transitioned (via ops_engine): %s -> %s",
                    trip_id, old_status, new_status,
                )
                return DispatchResult(
                    success=True,
                    trip_id=trip_id,
                    operation="transition_status",
                    message=f"Trip #{trip_id} status changed from '{old_status}' to '{new_status}'",
                    details={"old_status": old_status, "new_status": new_status},
                )
            except Exception as e:
                logger.error(
                    "OpsEngine transition failed for trip #%d: %s", trip_id, e,
                )
                raise DispatchError(
                    f"Failed to transition trip #{trip_id} via ops_engine: {e}"
                ) from e

        # 3b. No ops_engine — update manually and emit event
        self._trip_service.update(trip_id, {"status": new_status})

        # Emit event (best-effort fire-and-forget)
        try:
            if self._event_bus is not None:
                self._event_bus.publish(
                    TRIP_STATUS_CHANGED,
                    {
                        "trip_id": trip_id,
                        "old_status": old_status,
                        "new_status": new_status,
                    },
                )
        except Exception:
            logger.debug(
                "Failed to publish TRIP_STATUS_CHANGED event for trip #%d", trip_id,
            )

        logger.info(
            "Trip #%d status transitioned: %s -> %s", trip_id, old_status, new_status,
        )
        return DispatchResult(
            success=True,
            trip_id=trip_id,
            operation="transition_status",
            message=f"Trip #{trip_id} status changed from '{old_status}' to '{new_status}'",
            details={"old_status": old_status, "new_status": new_status},
        )

    def cancel_trip(self, trip_id: int, reason: str = "") -> DispatchResult:
        """Cancel a trip. Semantic alias for transition_status with 'Cancelled'."""
        result = self.transition_status(trip_id, "Cancelled")
        logger.info("Trip #%d cancelled (reason: %s)", trip_id, reason or "not specified")
        return result

    def complete_trip(self, trip_id: int) -> DispatchResult:
        """Complete a trip. Semantic alias for transition_status with 'Delivered'."""
        result = self.transition_status(trip_id, "Delivered")
        logger.info("Trip #%d completed (Delivered)", trip_id)
        return result

    def get_dispatch_board_data(
        self, filters: DispatchBoardFilters | None = None,
    ) -> DispatchDataResponse:
        """Load dispatch board data: trips grouped by column, alert counts, status counts."""
        # 1. Apply defaults
        if filters is None:
            filters = DispatchBoardFilters()

        # 2. Fetch all relevant trips — prefer targeted status query, fall back to get_all
        all_statuses = list(STATUS_TO_COLUMN.keys())
        all_trips: list[dict[str, Any]] = []
        try:
            # Attempt efficient status-filtered query via trip repo
            repo = self._trip_service._trip_repo
            all_trips = repo.get_by_statuses(all_statuses)
        except Exception:
            # Fall back to fetching all trips via TripService
            try:
                all_trips = self._trip_service.get_all(limit=filters.limit)
            except Exception:
                logger.error("Failed to fetch trips for dispatch board", exc_info=True)
                all_trips = []

        # 3. Prepare column buckets
        column_trips: dict[str, list[dict[str, Any]]] = {
            col: [] for col in COLUMN_KEYS
        }

        # 4. Compute cutoff for delivered/cancelled trips
        cutoff = (datetime.now() - timedelta(days=filters.delivered_window_days)).strftime("%Y-%m-%d")

        # 5. Resolve route repo once (best-effort)
        route_repo = getattr(self._trip_service, "_route_repo", None)

        # 6. Group and filter trips
        for trip in all_trips:
            raw_status = trip.get("status", "")
            column = STATUS_TO_COLUMN.get(raw_status)
            if not column:
                continue

            # Apply delivered/cancelled cutoff
            if column in ("Delivered", "Cancelled"):
                trip_date = trip.get("end_date", "") or trip.get("created_at", "")
                trip_date = str(trip_date)[:10] if trip_date else ""
                if trip_date and trip_date < cutoff:
                    continue

            # 7. Build card_data
            card_data = self._build_card_data(trip, route_repo)
            column_trips[column].append(card_data)

        # 8. Compute status counts
        status_counts = {k: len(v) for k, v in column_trips.items()}

        return DispatchDataResponse(
            column_trips=column_trips,
            alert_counts={},
            status_counts=status_counts,
        )

    # ── Private helpers ─────────────────────────────────────────────────────

    def _build_card_data(
        self,
        trip: dict[str, Any],
        route_repo: Any,
    ) -> dict[str, Any]:
        """Build a single card data dict from a trip row."""
        trip_id = trip.get("id", 0)
        status = trip.get("status", "Planned")
        truck_plate = trip.get("truck_number", "") or ""
        driver_name = trip.get("driver_name", "") or ""
        driver_id = trip.get("driver_id")
        truck_id = trip.get("truck_id")

        origin, destination = self._resolve_route(trip, route_repo)

        departure = trip.get("start_date", "") or ""
        eta = trip.get("end_date", "") or ""

        return {
            "trip_id": f"#{trip_id}",
            "trip_id_num": trip_id,
            "status": status,
            "truck_plate": truck_plate,
            "truck_id": truck_id,
            "driver_name": driver_name,
            "driver_id": driver_id,
            "origin": origin,
            "destination": destination,
            "departure_date": departure,
            "eta": eta,
            "alerts_count": 0,
        }

    def _resolve_route(
        self,
        trip: dict[str, Any],
        route_repo: Any,
    ) -> tuple[str, str]:
        """Resolve origin/destination from route_history_v2 if available."""
        route_id = trip.get("route_history_v2_id")
        if not route_id or route_repo is None:
            return "", ""

        try:
            route = route_repo.get_by_id(int(route_id))
            if not route:
                return "", ""

            summary = route.get("route_summary_json")
            if not summary:
                return "", ""

            summary_data = json.loads(summary) if isinstance(summary, str) else summary
            origin = summary_data.get("origin", "") or ""
            destination = summary_data.get("destination", "") or ""
            return origin, destination
        except Exception:
            logger.debug("Failed to resolve route for trip #%d", trip.get("id"))
            return "", ""

    def _validate_trip_exists(self, trip_id: int) -> dict[str, Any]:
        """Validate trip exists and is not archived."""
        trip = self._trip_service.get_by_id(trip_id)
        if not trip:
            raise TripNotFoundError(f"Trip #{trip_id} not found")
        return trip

    def _validate_truck_exists(self, truck_id: int) -> dict[str, Any]:
        """Validate truck exists and is active."""
        truck = self._fleet_repo.get_by_id(truck_id)
        if not truck:
            raise TruckNotFoundError(f"Truck #{truck_id} not found")
        return truck

    def _validate_driver_exists(self, driver_id: int) -> dict[str, Any]:
        """Validate driver exists and is active."""
        driver = self._driver_repo.get_by_id(driver_id)
        if not driver:
            raise DriverNotFoundError(f"Driver #{driver_id} not found")
        return driver

    # ═════════════════════════════════════════════════════════════════════
    # Delay evaluation (business logic extracted from dispatch_board UI)
    # ═════════════════════════════════════════════════════════════════════

    @staticmethod
    def evaluate_trip_delay(trip_data: dict, now: Optional[datetime] = None) -> tuple[bool, int]:
        """Determine whether a trip is delayed and by how many minutes.

        Pure business logic — no side effects.  Returns ``(is_delayed, minutes_overdue)``.

        * **In Transit**: delayed if ``now > eta``
        * **Loading**: delayed if ``now > departure + 2h``
        * **Planned**: delayed if ``departure < now - 24h``
        * Other statuses are never considered delayed.
        """
        if now is None:
            now = datetime.now()

        status = trip_data.get("status", "")
        eta = trip_data.get("eta", "")
        departure = trip_data.get("departure_date", "")

        # ── In Transit ──────────────────────────────────────────────
        if status in ("In Transit", "InTransit", "Active", "InProgress"):
            if not eta:
                return False, 0
            try:
                eta_dt = DispatchService._parse_trip_date(eta)
                if eta_dt is None:
                    return False, 0
                if now > eta_dt:
                    minutes = int((now - eta_dt).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass
            return False, 0

        # ── Loading ─────────────────────────────────────────────────
        if status in ("Loading", "Preparing", "Pickup"):
            if not departure:
                return False, 0
            try:
                dep_dt = DispatchService._parse_trip_date(departure)
                if dep_dt is None:
                    return False, 0
                threshold = dep_dt + timedelta(hours=2)
                if now > threshold:
                    minutes = int((now - threshold).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass
            return False, 0

        # ── Planned ─────────────────────────────────────────────────
        if status in ("Planned", "Scheduled", "Pending"):
            if not departure:
                return False, 0
            try:
                dep_dt = DispatchService._parse_trip_date(departure)
                if dep_dt is None:
                    return False, 0
                threshold = now - timedelta(hours=24)
                if dep_dt < threshold:
                    minutes = int((threshold - dep_dt).total_seconds() / 60)
                    return True, minutes
            except Exception:
                pass
            return False, 0

        return False, 0

    @staticmethod
    def _parse_trip_date(date_str: str):
        """Parse a trip date string, trying common formats."""
        from utils.dates import parse_date as _pd
        return _pd(date_str, "%d/%m/%Y")

    def create_delay_alert(self, trip_data: dict, minutes_overdue: int) -> Optional[Alert]:
        """Create a delay alert for a trip.

        Uses the injected ``alert_manager``.  Skips if an unresolved
        TRIP_DELAY alert already exists for the same trip.
        Returns the created ``Alert``, or ``None`` if skipped.
        """
        if self._alert_manager is None:
            logger.debug("create_delay_alert: no AlertManager available")
            return None

        trip_id = trip_data.get("trip_id_num")
        if not trip_id:
            return None

        # Check for existing unresolved delay alert
        existing = self._alert_manager.get_alerts(
            alert_type=AlertType.TRIP_DELAY,
            resolved=False,
            limit=1000,
        )
        for alert in existing:
            if alert.trip_id == str(trip_id):
                logger.debug("create_delay_alert: duplicate skipped for trip %d", trip_id)
                return None

        severity = Severity.CRITICAL if minutes_overdue > 120 else Severity.WARNING
        truck_plate = trip_data.get("truck_plate", "")
        driver_name = trip_data.get("driver_name", "")
        title = f"Trip #{trip_id} — Delay"
        message = (
            f"Trip #{trip_id} is {minutes_overdue} minutes overdue"
            f" (truck: {truck_plate or 'N/A'}, driver: {driver_name or 'N/A'})"
        )

        alert = self._alert_manager.create_alert(
            alert_type=AlertType.TRIP_DELAY,
            severity=severity,
            title=title,
            message=message,
            truck_id=truck_plate if truck_plate else None,
            trip_id=str(trip_id),
            metadata={
                "minutes_overdue": minutes_overdue,
                "status": trip_data.get("status", ""),
            },
        )
        logger.info("Created delay alert for trip %d (%d minutes overdue)", trip_id, minutes_overdue)
        return alert

    def resolve_delay_alert(self, trip_id: int) -> bool:
        """Resolve any active (unresolved) delay alerts for a trip.

        Returns ``True`` if an alert was resolved, ``False`` otherwise.
        """
        if self._alert_manager is None:
            logger.debug("resolve_delay_alert: no AlertManager available")
            return False

        existing = self._alert_manager.get_alerts(
            alert_type=AlertType.TRIP_DELAY,
            resolved=False,
            limit=1000,
        )
        for alert in existing:
            if alert.trip_id == str(trip_id):
                self._alert_manager.resolve_alert(alert.id)
                logger.info("Resolved delay alert for trip %d", trip_id)
                return True
        return False
