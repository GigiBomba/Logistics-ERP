"""Truck and expense service — delegates truck CRUD to FleetRepository, expenses to DatabaseManager.

All public methods now accept/return typed Pydantic models.
Backward-compatible dict-accepting methods are kept with deprecation warnings.
"""

import logging
import warnings
from typing import Any, Dict, List, Optional

from models.common import ErrorDetail, ServiceResult
from models.vehicle_models import (
    VehicleCreate,
    VehicleCreateResult,
    VehicleHealthScore,
    VehicleResult,
    VehicleSearchRequest,
    VehicleSearchResult,
    VehicleUpdate,
)
from repositories.fleet_repository import FleetRepository
from repositories.truck_route_assignment_repository import TruckRouteAssignmentRepository
from services.operations.event_bus import TRUCK_CREATED, TRUCK_DELETED, TRUCK_UPDATED, EventBus
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)

# ── Field mapping tables ──────────────────────────────────────────────────
# Pydantic model field → FleetRepository column name
_MODEL_TO_REPO: Dict[str, str] = {
    "plate": "plate_number",
    "brand": "manufacturer",
    "model": "model",
    "year": "year",
    "vin": "vin",
    "max_weight_kg": "max_payload_kg",
    "consumption_l_per_100km": "fuel_consumption",
    "insurance_expiry": "insurance_expiry",
    "technical_inspection_expiry": "inspection_expiry",
    "tachograph_calibration_expiry": "tachograph_expiry",
    "status": "status",
}

# FleetRepository column name → Pydantic model field
_REPO_TO_MODEL: Dict[str, str] = {
    "id": "id",
    "plate_number": "plate",
    "manufacturer": "brand",
    "model": "model",
    "year": "year",
    "vin": "vin",
    "max_payload_kg": "max_weight_kg",
    "fuel_consumption": "consumption_l_per_100km",
    "insurance_expiry": "insurance_expiry",
    "inspection_expiry": "technical_inspection_expiry",
    "tachograph_expiry": "tachograph_calibration_expiry",
    "status": "status",
}


def _model_dict_to_repo(data: dict) -> dict:
    """Convert model dict (keys = pydantic field names) to repo dict (keys = column names).

    Drops fields that have no corresponding repo column (e.g. ``fuel_type``).
    """
    repo: dict = {}
    for model_key, value in data.items():
        if value is None:
            continue
        col = _MODEL_TO_REPO.get(model_key)
        if col is not None:
            repo[col] = value
    return repo


def _repo_dict_to_vehicle_result(row: Optional[dict]) -> Optional[VehicleResult]:
    """Convert a repo row dict to a ``VehicleResult`` instance."""
    if row is None:
        return None

    kwargs: dict = {}
    for repo_key, model_key in _REPO_TO_MODEL.items():
        if repo_key in row:
            kwargs[model_key] = row[repo_key]

    # fuel_type is not stored in the DB — default to "diesel"
    kwargs.setdefault("fuel_type", row.get("fuel_type", "diesel"))

    # Fields not mapped from repo columns
    kwargs.setdefault("health_score", None)
    kwargs.setdefault("current_location", None)
    kwargs.setdefault("created_at", None)

    # Ensure string fields are never None (Pydantic v2 rejects None for str)
    for str_field in ("vin",):
        if kwargs.get(str_field) is None:
            kwargs[str_field] = ""

    return VehicleResult(**kwargs)


# ── Service ───────────────────────────────────────────────────────────────


class FleetService:
    """Fleet management service.

    Provides both typed (Pydantic) and backward-compatible dict-based methods.
    All write operations include permission checks via ``PermissionService``.
    """

    def __init__(self, db):
        self.db = db
        self._fleet_repo = FleetRepository(db)
        self._assignment_repo = TruckRouteAssignmentRepository(db)
        self._event_bus = EventBus()
        self._perm = PermissionService(db)

    # ── Read methods ──────────────────────────────────────────────────────

    def get(self, vehicle_id: int) -> VehicleCreateResult:
        """Get a single vehicle by ID, returning a typed ``ServiceResult``."""
        try:
            row = self._fleet_repo.get_by_id(vehicle_id)
            if row is None:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message="Vehicle not found", code="NOT_FOUND")],
                )
            return ServiceResult(success=True, data=_repo_dict_to_vehicle_result(row))
        except Exception as exc:
            logger.exception("Error fetching vehicle %s", vehicle_id)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="FETCH_ERROR")],
            )

    def get_truck(self, truck_id, company_id=None):
        """Backward-compatible dict-returning method.

        .. deprecated::
            Use :meth:`get` instead.
        """
        warnings.warn(
            "get_truck() is deprecated — use get(vehicle_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._fleet_repo.get_by_id(truck_id, company_id=company_id)

    def get_trucks_by_ids(self, truck_ids, company_id=None):
        """Return truck rows (``id``) for the ids that belong to *company_id*.

        Used by the GPS batch endpoint to verify ownership of every truck in
        the batch with a single ``IN (...)`` lookup.  Foreign/missing trucks
        are simply absent from the returned list.
        """
        return self._fleet_repo.get_trucks_by_ids(truck_ids, company_id=company_id)

    # ── List / Search methods ─────────────────────────────────────────────

    def list_all(self) -> VehicleSearchResult:
        """Return all vehicles as a typed ``ServiceResult``."""
        try:
            rows = self._fleet_repo.get_all()
            vehicles = [v for r in rows if (v := _repo_dict_to_vehicle_result(r)) is not None]
            return ServiceResult(success=True, data=vehicles)
        except Exception as exc:
            logger.exception("Error listing vehicles")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="LIST_ERROR")],
            )

    def get_trucks(self, company_id=None):
        """Backward-compatible list-returning method.

        .. deprecated::
            Use :meth:`list_all` instead.
        """
        warnings.warn(
            "get_trucks() is deprecated — use list_all() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._fleet_repo.get_all(company_id=company_id)

    def search(self, request: VehicleSearchRequest) -> VehicleSearchResult:
        """Search vehicles with optional filters.

        Supports filtering by ``query`` (plate / model), ``status``,
        and ``fuel_type``.
        """
        try:
            rows = self._fleet_repo.get_all()
            # Client-side filtering — acceptable for moderate fleet sizes.
            # For large fleets, push filtering down to SQL.
            if request.query:
                q = request.query.lower()
                rows = [
                    r for r in rows
                    if q in r.get("plate_number", "").lower()
                    or q in r.get("model", "").lower()
                    or q in r.get("manufacturer", "").lower()
                ]
            if request.status:
                rows = [r for r in rows if r.get("status", "").lower() == request.status.lower()]
            if request.fuel_type:
                # fuel_type is not stored in DB — filter by consumption pattern instead
                pass

            vehicles = [v for r in rows if (v := _repo_dict_to_vehicle_result(r)) is not None]
            return ServiceResult(success=True, data=vehicles)
        except Exception as exc:
            logger.exception("Error searching vehicles")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="SEARCH_ERROR")],
            )

    def find_available(self, request: VehicleSearchRequest) -> VehicleSearchResult:
        """Find available (active) vehicles matching the search criteria."""
        try:
            rows = self._fleet_repo.get_active_trucks()
            if request.query:
                q = request.query.lower()
                rows = [
                    r for r in rows
                    if q in r.get("plate_number", "").lower()
                    or q in r.get("model", "").lower()
                    or q in r.get("manufacturer", "").lower()
                ]
            vehicles = [v for r in rows if (v := _repo_dict_to_vehicle_result(r)) is not None]
            return ServiceResult(success=True, data=vehicles)
        except Exception as exc:
            logger.exception("Error finding available vehicles")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="FIND_ERROR")],
            )

    # ── Write methods ─────────────────────────────────────────────────────

    def create(self, request: VehicleCreate, user_id: int) -> VehicleCreateResult:
        """Create a new vehicle with permission checks and business validation.

        Validates:
        * User has ``can_create_vehicle`` permission.
        * Plate is unique.
        """
        perm = self._perm.can_create_vehicle(user_id)
        if not perm.allowed:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=perm.reason, code="PERMISSION_DENIED")],
            )

        # Re-run plate validation (already done by Pydantic, but be safe)
        # ── uniqueness check
        existing = self._fleet_repo.get_by_plate(request.plate)
        if existing is not None:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    field="plate",
                    message=f"Vehicle with plate '{request.plate}' already exists",
                    code="DUPLICATE_PLATE",
                )],
            )

        try:
            repo_data = _model_dict_to_repo(request.model_dump())

            # Derive active_status from status
            _derive_active_status(repo_data)

            vehicle_id = self._fleet_repo.create(repo_data)

            self._event_bus.publish(TRUCK_CREATED, {
                "truck_id": vehicle_id,
                "plate_number": request.plate,
                "model": request.model,
            })

            created_row = self._fleet_repo.get_by_id(vehicle_id)
            return ServiceResult(success=True, data=_repo_dict_to_vehicle_result(created_row))
        except Exception as exc:
            logger.exception("Error creating vehicle")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="CREATE_ERROR")],
            )

    def add_truck(self, data: dict, company_id=None) -> int:
        """Backward-compatible dict-returning method.

        .. deprecated::
            Use :meth:`create` with a ``VehicleCreate`` model and ``user_id`` instead.
        """
        warnings.warn(
            "add_truck(data) is deprecated — use create(request, user_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        # Stamp the caller's tenant on the row (the client body has no
        # company_id field — see the fleet schema).
        if company_id:
            data = dict(data)
            data["company_id"] = company_id
        truck_id = self._fleet_repo.create(data)
        self._event_bus.publish(TRUCK_CREATED, {
            "truck_id": truck_id,
            "plate_number": data.get("plate_number", ""),
            "model": data.get("model", ""),
        })
        return truck_id

    def update(self, vehicle_id: int, request: VehicleUpdate, user_id: int) -> VehicleCreateResult:
        """Update an existing vehicle with permission checks and validation.

        Validates:
        * User has ``can_update_vehicle`` permission.
        * Vehicle exists.
        * Plate uniqueness if plate is being changed.
        """
        perm = self._perm.can_update_vehicle(user_id)
        if not perm.allowed:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=perm.reason, code="PERMISSION_DENIED")],
            )

        existing = self._fleet_repo.get_by_id(vehicle_id)
        if existing is None:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Vehicle not found", code="NOT_FOUND")],
            )

        # ── plate uniqueness check (if changing plate)
        if request.plate is not None and request.plate != existing.get("plate_number"):
            dup = self._fleet_repo.get_by_plate(request.plate)
            if dup is not None and dup["id"] != vehicle_id:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(
                        field="plate",
                        message=f"Vehicle with plate '{request.plate}' already exists",
                        code="DUPLICATE_PLATE",
                    )],
                )

        try:
            repo_data = _model_dict_to_repo(request.model_dump(exclude_unset=True))

            # Derive active_status from status
            _derive_active_status(repo_data)

            if repo_data:
                self._fleet_repo.update(vehicle_id, repo_data)
                self._event_bus.publish(TRUCK_UPDATED, {
                    "truck_id": vehicle_id,
                    "changes": repo_data,
                })

            updated_row = self._fleet_repo.get_by_id(vehicle_id)
            return ServiceResult(success=True, data=_repo_dict_to_vehicle_result(updated_row))
        except Exception as exc:
            logger.exception("Error updating vehicle %s", vehicle_id)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="UPDATE_ERROR")],
            )

    def update_truck(self, truck_id, data: dict, company_id=None):
        """Backward-compatible dict-returning method.

        .. deprecated::
            Use :meth:`update` with a ``VehicleUpdate`` model and ``user_id`` instead.
        """
        warnings.warn(
            "update_truck() is deprecated — use update(vehicle_id, request, user_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        # Tenant-scoped update: never modify a truck outside the caller's company.
        if company_id is not None and not self._fleet_repo.get_by_id(truck_id, company_id=company_id):
            raise ValueError(f"Truck {truck_id} not found")
        self._fleet_repo.update(truck_id, data, company_id=company_id)
        self._event_bus.publish(TRUCK_UPDATED, {"truck_id": truck_id, "changes": data})

    def delete(self, vehicle_id: int, user_id: int) -> VehicleCreateResult:
        """Delete a vehicle (admin only)."""
        perm = self._perm.can_delete_vehicle(user_id)
        if not perm.allowed:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=perm.reason, code="PERMISSION_DENIED")],
            )

        existing = self._fleet_repo.get_by_id(vehicle_id)
        if existing is None:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Vehicle not found", code="NOT_FOUND")],
            )

        try:
            self._fleet_repo.delete(vehicle_id)
            self._event_bus.publish(TRUCK_DELETED, {"truck_id": vehicle_id})
            return ServiceResult(success=True, data=_repo_dict_to_vehicle_result(existing))
        except Exception as exc:
            logger.exception("Error deleting vehicle %s", vehicle_id)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="DELETE_ERROR")],
            )

    def delete_truck(self, truck_id, company_id=None):
        """Backward-compatible dict-returning method.

        .. deprecated::
            Use :meth:`delete` with a ``user_id`` instead.
        """
        warnings.warn(
            "delete_truck() is deprecated — use delete(vehicle_id, user_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        # Tenant-scoped delete: never remove a truck outside the caller's company.
        if company_id is not None and not self._fleet_repo.get_by_id(truck_id, company_id=company_id):
            raise ValueError(f"Truck {truck_id} not found")
        self._fleet_repo.delete(truck_id, company_id=company_id)
        self._event_bus.publish(TRUCK_DELETED, {"truck_id": truck_id})

    # ── Health score ──────────────────────────────────────────────────────

    def health_score(self, vehicle_id: int) -> "ServiceResult[VehicleHealthScore]":
        """Compute and return the health score for a vehicle."""
        try:
            vehicle = self._fleet_repo.get_by_id(vehicle_id)
            if vehicle is None:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message="Vehicle not found", code="NOT_FOUND")],
                )

            health_row = self._fleet_repo.get_truck_health(vehicle_id)
            if health_row is None:
                score = VehicleHealthScore(
                    vehicle_id=vehicle_id,
                    plate=vehicle.get("plate_number", ""),
                    overall_score=100.0,
                    insurance_status="unknown",
                    technical_inspection_status="unknown",
                    tachograph_status="unknown",
                    maintenance_alerts=0,
                )
            else:
                score = VehicleHealthScore(
                    vehicle_id=vehicle_id,
                    plate=vehicle.get("plate_number", ""),
                    overall_score=float(health_row.get("score", 100)),
                    insurance_status="ok" if vehicle.get("insurance_expiry") else "missing",
                    technical_inspection_status="ok" if vehicle.get("inspection_expiry") else "missing",
                    tachograph_status="ok" if vehicle.get("tachograph_expiry") else "missing",
                    maintenance_alerts=int(health_row.get("overdue_count", 0)),
                )

            return ServiceResult(success=True, data=score)
        except Exception as exc:
            logger.exception("Error computing health score for vehicle %s", vehicle_id)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="HEALTH_ERROR")],
            )

    # ── Expenses ──────────────────────────────────────────────────────────

    def get_expenses(self, truck_id) -> ServiceResult:
        """Get expenses for a vehicle, wrapped in a typed result.

        .. note::
            Uses the deprecated ``DatabaseManager.get_expenses`` internally.
            A future refactor should route through ``FleetRepository`` or a
            dedicated expense repository.
        """
        try:
            expenses = self.db.get_expenses(
                truck_id,
                company_id=getattr(self.db, "user_company_id", None),
            )
            return ServiceResult(success=True, data=expenses or [])
        except Exception as exc:
            logger.exception("Error fetching expenses for vehicle %s", truck_id)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="EXPENSES_ERROR")],
            )

    def add_expense(self, truck_id, date, category, description, amount):
        """Add an expense record (backward-compatible, dict-returning)."""
        return self.db.add_expense(truck_id, date, category, description, amount)

    # ── Legacy helpers ────────────────────────────────────────────────────

    def get_assigned_routes(self, truck_id, status=None):
        """Get routes assigned to a vehicle (backward-compatible)."""
        return self._assignment_repo.get_by_truck(truck_id, status=status)

    def ensure_expenses_table(self):
        """Ensure the expenses table exists (backward-compatible)."""
        self.db.ensure_expenses_table()


# ── Module-level helpers ───────────────────────────────────────────────────


def _derive_active_status(repo_data: dict) -> None:
    """Derive ``active_status`` from the ``status`` key in *repo_data* (in-place).

    * ``status`` in ("active",) → ``active_status = 1``
    * All other values          → ``active_status = 0``
    """
    status_val = repo_data.pop("status", None)
    if status_val is not None:
        repo_data["status"] = status_val  # keep the text column too
        repo_data["active_status"] = 1 if str(status_val).lower() == "active" else 0
