"""Driver/Truck service — business logic for driver management and truck assignment."""
import logging
import warnings
from datetime import timedelta
from typing import Any, Optional

from repositories.driver_repository import DriverRepository
from repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository
from repositories.fleet_repository import FleetRepository
from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
from services.operations.event_bus import TRUCK_UPDATED, EventBus

from models.common import ErrorDetail, ServiceResult
from models.driver_models import (
    DriverCreate,
    DriverCreateResult,
    DriverHoursCheck,
    DriverHoursCheckResult,
    DriverHoursResult,
    DriverResult,
    DriverUpdate,
)
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class DriverTruckService:

    def __init__(self, db):
        self._db = db
        self._repo = DriverTruckAssignmentRepository(db)
        self._fleet_repo = FleetRepository(db)
        self._driver_repo = DriverRepository(db)
        self._tacho_activity_repo = TachoDriverActivityRepository(db)
        self._event_bus = EventBus()

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _dict_to_driver_result(d: Optional[dict], truck_data: Optional[dict] = None) -> Optional[DriverResult]:
        """Convert a raw repo dict to a typed DriverResult (or None).

        Optionally accepts truck_data to populate current_truck_id/current_truck_plate.
        """
        if d is None:
            return None
        result = DriverResult(**d)
        if truck_data:
            result.current_truck_id = truck_data.get("id")
            result.current_truck_plate = truck_data.get("plate_number", "")
        return result

    def _enrich_with_truck(self, driver_dict: Optional[dict]) -> Optional[DriverResult]:
        """Fetch truck assignment and return an enriched DriverResult."""
        if driver_dict is None:
            return None
        driver_id = driver_dict["id"]
        assignment = self._repo.get_by_driver(driver_id)
        truck_data = None
        if assignment:
            truck_data = self._fleet_repo.get_by_id(assignment["truck_id"])
        return self._dict_to_driver_result(driver_dict, truck_data)

    def _check_permission(self, perm_check: str, user_id: int) -> None:
        """Resolve a PermissionService method by name and raise on denial."""
        perm = PermissionService(self._db)
        method = getattr(perm, perm_check, None)
        if method is None:
            raise ValueError(f"Unknown permission check: {perm_check}")
        result = method(user_id)
        if not result.allowed:
            raise PermissionError(result.reason)

    # ── New typed CRUD methods ──────────────────────────────────────────────

    def create_driver(self, request: DriverCreate, user_id: int) -> DriverCreateResult:
        """Create a new driver.

        Args:
            request: Typed DriverCreate model with driver fields.
            user_id: ID of the user performing the action.

        Returns:
            DriverCreateResult (ServiceResult[DriverResult]).
        """
        self._check_permission("can_create_driver", user_id)

        data = request.model_dump()
        driver_id = self._driver_repo.create(data)
        driver_dict = self._driver_repo.get_by_id(driver_id)
        return DriverCreateResult(
            success=True,
            data=self._enrich_with_truck(driver_dict),
        )

    def update_driver(self, driver_id: int, request: DriverUpdate, user_id: int) -> DriverCreateResult:
        """Update an existing driver.

        Args:
            driver_id: ID of the driver to update.
            request: Typed DriverUpdate model with fields to change.
            user_id: ID of the user performing the action.

        Returns:
            DriverCreateResult (ServiceResult[DriverResult]).
        """
        self._check_permission("can_update_driver", user_id)

        existing = self._driver_repo.get_by_id(driver_id)
        if existing is None:
            return DriverCreateResult(
                success=False,
                errors=[ErrorDetail(message="Driver not found", code="NOT_FOUND")],
            )

        data = request.model_dump(exclude_unset=True, exclude_none=True)
        if not data:
            return DriverCreateResult(
                success=False,
                errors=[ErrorDetail(message="No fields to update", code="EMPTY_UPDATE")],
            )
        self._driver_repo.update(driver_id, data)
        driver_dict = self._driver_repo.get_by_id(driver_id)
        return DriverCreateResult(
            success=True,
            data=self._enrich_with_truck(driver_dict),
        )

    def get_driver(self, driver_id: int) -> DriverCreateResult:
        """Get a single driver by ID, returning a typed result.

        Args:
            driver_id: ID of the driver to retrieve.

        Returns:
            DriverCreateResult with the driver data or NOT_FOUND error.
        """
        driver_dict = self._driver_repo.get_by_id(driver_id)
        if driver_dict is None:
            return DriverCreateResult(
                success=False,
                errors=[ErrorDetail(message="Driver not found", code="NOT_FOUND")],
            )
        return DriverCreateResult(
            success=True,
            data=self._enrich_with_truck(driver_dict),
        )

    def list_drivers(self) -> ServiceResult[list[DriverResult]]:
        """List all drivers as a typed result.

        Returns:
            ServiceResult containing a list of DriverResult objects.
        """
        driver_dicts = self._driver_repo.get_all()
        drivers = []
        for d in driver_dicts:
            enriched = self._enrich_with_truck(d)
            if enriched is not None:
                drivers.append(enriched)
        return ServiceResult[list[DriverResult]](
            success=True,
            data=drivers,
        )

    def delete_driver(self, driver_id: int, user_id: int) -> DriverCreateResult:
        """Delete a driver. Admin only.

        Also unassigns the driver from any truck before deletion.

        Args:
            driver_id: ID of the driver to delete.
            user_id: ID of the user performing the action (admin required).

        Returns:
            DriverCreateResult with the deleted driver data.
        """
        self._check_permission("can_delete_driver", user_id)

        driver_dict = self._driver_repo.get_by_id(driver_id)
        if driver_dict is None:
            return DriverCreateResult(
                success=False,
                errors=[ErrorDetail(message="Driver not found", code="NOT_FOUND")],
            )

        # Unassign from truck before deletion (internal helper, no warning)
        self._do_unassign_driver(driver_id)

        self._driver_repo.delete(driver_id)
        return DriverCreateResult(
            success=True,
            data=self._enrich_with_truck(driver_dict),
        )

    # ── Hours check ─────────────────────────────────────────────────────────

    def check_hours(self, request: DriverHoursCheck) -> DriverHoursCheckResult:
        """Check if a driver has available hours for a given date.

        Computes hours from tachograph activity records and the driver's
        ``max_hours_per_day`` and ``hours_worked`` fields.

        Args:
            request: Typed DriverHoursCheck with driver_id, check_date, planned_hours.

        Returns:
            DriverHoursCheckResult containing DriverHoursResult.
        """
        driver_dict = self._driver_repo.get_by_id(request.driver_id)
        if driver_dict is None:
            return DriverHoursCheckResult(
                success=False,
                errors=[ErrorDetail(message="Driver not found", code="NOT_FOUND")],
            )

        driver_name = driver_dict.get("name", "")
        max_hours_per_day = float(driver_dict.get("max_hours_per_day", 9.0))

        # Try to fetch tacho activity for the check_date and current week
        hours_worked_today = 0.0
        hours_worked_week = 0.0
        try:
            from_date = request.check_date - timedelta(days=6)  # last 7 days
            records = self._tacho_activity_repo.get_by_driver(
                request.driver_id, from_date
            )

            check_date_str = request.check_date.isoformat()
            for r in records:
                driving_min = float(r.get("driving_minutes", 0) or 0)
                activity_date = r.get("activity_date", "")
                if activity_date == check_date_str:
                    hours_worked_today += driving_min / 60.0
                hours_worked_week += driving_min / 60.0
        except (ValueError, TypeError, AttributeError):
            logger.warning(
                "Could not fetch tacho activity for driver %s, "
                "falling back to driver.hours_worked",
                request.driver_id,
            )
            hours_worked_today = float(driver_dict.get("hours_worked", 0))
            hours_worked_week = hours_worked_today

        available_hours_today = round(max_hours_per_day - hours_worked_today, 2)
        planned_exceeds = request.planned_hours > available_hours_today
        is_compliant = not planned_exceeds
        warnings_list: list[str] = []

        if planned_exceeds:
            warnings_list.append(
                f"Planned hours ({request.planned_hours}h) exceed "
                f"available hours ({available_hours_today}h)"
            )
        if available_hours_today <= 0:
            warnings_list.append("No available hours remaining today")

        return DriverHoursCheckResult(
            success=True,
            data=DriverHoursResult(
                driver_id=request.driver_id,
                driver_name=driver_name,
                hours_worked_today=round(hours_worked_today, 2),
                hours_worked_week=round(hours_worked_week, 2),
                max_hours_per_day=max_hours_per_day,
                available_hours_today=available_hours_today,
                is_compliant=is_compliant,
                warnings=warnings_list,
            ),
        )

    # ── Truck assignment (typed) ────────────────────────────────────────────

    def assign_truck(self, driver_id: int, truck_id: int, user_id: int) -> DriverCreateResult:
        """Assign a truck to a driver.

        Wraps the existing assignment logic with a permission check and typed
        return value.

        Args:
            driver_id: ID of the driver.
            truck_id: ID of the truck.
            user_id: ID of the user performing the action.

        Returns:
            DriverCreateResult with the updated driver (including truck info).
        """
        self._check_permission("can_update_driver", user_id)

        driver_dict = self._driver_repo.get_by_id(driver_id)
        if driver_dict is None:
            return DriverCreateResult(
                success=False,
                errors=[ErrorDetail(message="Driver not found", code="NOT_FOUND")],
            )
        truck_dict = self._fleet_repo.get_by_id(truck_id)
        if truck_dict is None:
            return DriverCreateResult(
                success=False,
                errors=[ErrorDetail(message="Truck not found", code="NOT_FOUND")],
            )

        self._do_assign_driver_to_truck(driver_id, truck_id)

        # Fetch the updated driver with truck info
        driver_dict = self._driver_repo.get_by_id(driver_id)
        return DriverCreateResult(
            success=True,
            data=self._enrich_with_truck(driver_dict),
        )

    def unassign_driver_from_truck(self, driver_id: int, user_id: int) -> DriverCreateResult:
        """Remove truck assignment from a driver.

        Args:
            driver_id: ID of the driver.
            user_id: ID of the user performing the action.

        Returns:
            DriverCreateResult with the updated driver (truck fields cleared).
        """
        self._check_permission("can_update_driver", user_id)

        driver_dict = self._driver_repo.get_by_id(driver_id)
        if driver_dict is None:
            return DriverCreateResult(
                success=False,
                errors=[ErrorDetail(message="Driver not found", code="NOT_FOUND")],
            )

        self._do_unassign_driver(driver_id)

        # Re-fetch the driver (now without a truck)
        driver_dict = self._driver_repo.get_by_id(driver_id)
        return DriverCreateResult(
            success=True,
            data=self._enrich_with_truck(driver_dict),
        )

    # ── Internal helpers (no warnings — used by both new and legacy methods) ─

    def _do_assign_driver_to_truck(self, driver_id: int, truck_id: int) -> dict[str, Any]:
        """Core assignment logic — no deprecation warning."""
        self._repo.begin_transaction()

        try:
            existing_driver = self._repo.get_by_driver(driver_id)
            existing_truck = self._repo.get_by_truck(truck_id)

            action = "assigned"
            swapped_driver = None

            if existing_driver and existing_driver["truck_id"] != truck_id:
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
            self._repo.commit_transaction()

            self._event_bus.publish(TRUCK_UPDATED, {
                "truck_id": truck_id,
                "driver_id": driver_id,
                "action": action,
            })

            return {"action": action, "swapped_driver": swapped_driver}
        except (ValueError, RuntimeError, KeyError, TypeError):
            self._repo.rollback_transaction()
            raise

    def _do_unassign_driver(self, driver_id: int) -> Optional[int]:
        """Core unassign-driver logic — no deprecation warning."""
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

    def _do_unassign_truck(self, truck_id: int) -> Optional[int]:
        """Core unassign-truck logic — no deprecation warning."""
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

    # ── Existing methods (kept with backward compatibility) ─────────────────

    def assign_driver_to_truck(self, driver_id: int, truck_id: int, company_id=None) -> dict[str, Any]:
        """Legacy: assign a driver to a truck (raw dict return).

        Prefer :meth:`assign_truck` for typed results with permission checks.
        """
        warnings.warn(
            "assign_driver_to_truck() is deprecated — "
            "use assign_truck(driver_id, truck_id, user_id) for typed results",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._do_assign_driver_to_truck(driver_id, truck_id)

    def unassign_driver(self, driver_id: int, company_id=None) -> Optional[int]:
        """Legacy: unassign a driver from their truck (returns truck_id or None).

        Prefer :meth:`unassign_driver_from_truck` for typed results with
        permission checks.
        """
        warnings.warn(
            "unassign_driver() is deprecated — "
            "use unassign_driver_from_truck(driver_id, user_id) for typed results",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._do_unassign_driver(driver_id)

    def unassign_truck(self, truck_id: int) -> Optional[int]:
        """Legacy: unassign whatever driver is assigned to a truck (returns driver_id or None).

        Prefer :meth:`unassign_driver_from_truck` for typed results with
        permission checks.
        """
        warnings.warn(
            "unassign_truck(truck_id) is deprecated — "
            "use unassign_driver_from_truck(driver_id, user_id) for typed results "
            "with permission checks",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._do_unassign_truck(truck_id)

    def get_truck_for_driver(self, driver_id: int) -> Optional[dict[str, Any]]:
        """Legacy: returns a raw truck dict.

        Prefer :meth:`get_driver` which returns the driver with truck info
        populated in DriverResult.current_truck_plate / current_truck_id.
        """
        assignment = self._repo.get_by_driver(driver_id)
        if not assignment:
            return None
        return self._fleet_repo.get_by_id(assignment["truck_id"])

    def get_driver_for_truck(self, truck_id: int) -> Optional[dict[str, Any]]:
        """Legacy: returns a raw driver dict.

        Prefer :meth:`get_driver` for typed results.
        """
        assignment = self._repo.get_by_truck(truck_id)
        if not assignment:
            return None
        return self._driver_repo.get_by_id(assignment["driver_id"])

    def get_truck_plate_for_driver(self, driver_id: int, company_id=None) -> str:
        """Get the plate number of the truck assigned to a driver."""
        return self._repo.get_truck_plate_for_driver(driver_id)

    def get_plates_by_driver_ids(self, driver_ids: list[int]) -> dict[int, str]:
        """Batch version — one query for many drivers.

        Returns ``{driver_id: plate_number}``, replacing the per-driver
        ``get_truck_plate_for_driver`` loop (N+1) in the driver manager.
        """
        return self._repo.get_plates_by_driver_ids(driver_ids)

    def get_driver_name_for_truck(self, truck_id: int) -> str:
        """Get the name of the driver assigned to a truck."""
        return self._repo.get_driver_name_for_truck(truck_id)

    def get_driver_names_for_trucks(self, truck_ids: list[int]) -> dict[int, str]:
        """Batch version — one query for many trucks. Returns {truck_id: driver_name}."""
        return self._repo.get_driver_names_for_trucks(truck_ids)

    def on_driver_deleted(self, driver_id: int) -> None:
        """Handle driver deletion — unassign from truck."""
        self._do_unassign_driver(driver_id)

    def on_truck_deleted(self, truck_id: int) -> None:
        """Handle truck deletion — unassign from driver."""
        self._do_unassign_truck(truck_id)
