"""Trip service — business logic layer with typed Pydantic models.

All CRUD operations return ``ServiceResult`` wrapping the appropriate model.
Write operations include permission checks and business validation
(client/truck/driver existence).  Backward-compatible dict-based shims
are provided with deprecation warnings.
"""

import logging
import warnings
from typing import Any, Optional, Union

from models.trip_models import TripCreate, TripUpdate, TripResult, TripCreateResult, TripListResult
from models.common import ServiceResult, ErrorDetail
from repositories.audit_repository import AuditRepository
from repositories.route_repository import RouteRepository
from repositories.trip_repository import TripRepository
from services.audit_service import AuditService
from services.operations.event_bus import TRIP_CREATED, TRIP_DELETED, TRIP_UPDATED, EventBus
from services.permission_service import PermissionService, PermissionCheckResult

logger = logging.getLogger(__name__)

# ── Field name mappings ──────────────────────────────────────────────────────
# Pydantic model field → DB column name (for create/update)
_MODEL_TO_DB: dict[str, str] = {
    "price_eur": "total_price_eur",
    "route_id": "route_history_v2_id",
    "truck_plate": "truck_number",
}

# DB column name → Pydantic model field (for results)
_DB_TO_RESULT: dict[str, Optional[str]] = {
    "total_price_eur": "price_eur",
    "net_profit": "profit",
    "route_history_v2_id": "route_id",
    "truck_number": "truck_plate",
    "fuel_cost": None,      # consumed in cost calculation
    "toll_cost": None,      # consumed in cost calculation
    "salary_cost": None,    # consumed in cost calculation
    "extra_costs": None,    # consumed in cost calculation
}

# Model fields that have no DB column and should be omitted when sending to repo
_MODEL_ONLY_FIELDS = frozenset({"stops", "reference", "notes"})


def _model_to_db(data: dict) -> dict:
    """Convert Pydantic model dict to DB column dict (skipping model-only fields)."""
    result: dict[str, Any] = {}
    for k, v in data.items():
        if k in _MODEL_ONLY_FIELDS:
            continue
        db_key: str = _MODEL_TO_DB.get(k, k)  # type: ignore[assignment]
        result[db_key] = v
    return result


def _db_to_trip_result(row: dict) -> TripResult:
    """Convert a DB row dict to a ``TripResult``."""
    mapped: dict[str, Any] = {}
    for k, v in row.items():
        target = _DB_TO_RESULT.get(k)
        if target:
            mapped[target] = v
        elif k not in ("fuel_cost", "toll_cost", "salary_cost", "extra_costs"):
            mapped[k] = v

    # Derive cost where possible
    cost: Optional[float] = None
    cost_fields = ("fuel_cost", "toll_cost", "salary_cost", "extra_costs")
    if all(f in row for f in cost_fields):
        cost = (
            (row.get("fuel_cost", 0) or 0)
            + (row.get("toll_cost", 0) or 0)
            + (row.get("salary_cost", 0) or 0)
            + (row.get("extra_costs", 0) or 0)
        )
    if cost is not None:
        mapped["cost"] = cost

    # Derive margin percentage
    price = mapped.get("price_eur", 0) or 0
    profit = mapped.get("profit")
    if profit is not None and price > 0:
        mapped["margin_pct"] = round((profit / price) * 100, 2)

    # Ensure required fields that may not exist in every DB row
    mapped.setdefault("reference", "")
    mapped.setdefault("notes", "")

    return TripResult(**mapped)


class TripService:
    """Trip business logic with typed Pydantic models."""

    def __init__(self, db):
        self.db = db
        self._event_bus = EventBus()
        self._trip_repo = TripRepository(db)
        self._route_repo = RouteRepository(db)

    # ═════════════════════════════════════════════════════════════════════
    # New typed API
    # ═════════════════════════════════════════════════════════════════════

    def create(self, request: TripCreate, user_id: int = 0) -> TripCreateResult:
        """Create a new trip from a validated TripCreate model.

        Performs permission and business validation before persisting.
        Returns a ``ServiceResult`` wrapping the created ``TripResult``.
        """
        logger.info("Creating trip: client_id=%s", request.client_id)

        # ── Permission check ───────────────────────────────────────────
        if user_id:
            perm = PermissionService(self.db)
            check = perm.can_create_trip(user_id)
            if not check.allowed:
                logger.warning("Permission denied creating trip: user_id=%s", user_id)
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message=check.reason, code="permission_denied")],
                )

        try:
            # ── Business validation ────────────────────────────────────
            self._validate_external_refs(
                client_id=request.client_id,
                truck_id=request.truck_id,
                driver_id=request.driver_id,
            )

            # ── Persist ────────────────────────────────────────────────
            data = _model_to_db(request.model_dump(exclude_none=True))
            new_id = self._trip_repo.create(data)
            self._event_bus.publish(TRIP_CREATED, {"trip_id": new_id, "data": data})
            AuditService(self.db).log(
                event_type="trip.created",
                entity_type="trip",
                entity_id=str(new_id),
                data={
                    "client_id": request.client_id,
                    "price_eur": request.price_eur,
                    "truck_id": request.truck_id,
                    "driver_id": request.driver_id,
                },
                user_id=user_id,
            )
            logger.info("Trip created successfully: trip_id=%s", new_id)

            # ── Return result ──────────────────────────────────────────
            row = self._trip_repo.get_by_id(new_id)
            if row:
                result = _db_to_trip_result(row)
                return ServiceResult(success=True, data=result)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Trip created but not found after insert", code="not_found")],
            )

        except ValueError as e:
            logger.error("Validation error creating trip: %s", e)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="validation_error")],
            )
        except PermissionError as e:
            logger.error("Permission error creating trip: %s", e)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="permission_denied")],
            )
        except Exception as e:
            logger.error("Failed to create trip: %s", e, exc_info=True)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="internal_error")],
            )

    def update(self, trip_id: int, request: Union[TripUpdate, dict[str, Any]], user_id: int = 0) -> TripCreateResult:
        """Update an existing trip.

        Accepts either a ``TripUpdate`` model (preferred) or a raw dict
        (deprecated).  Performs permission checks and business validation
        on any referenced foreign keys included in the request.
        """
        # ── Normalise input ────────────────────────────────────────────
        is_dict_input = isinstance(request, dict)
        if is_dict_input:
            warnings.warn(
                "Passing a dict to TripService.update() is deprecated; use TripUpdate instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            # Keep the raw dict path for backward compatibility — it uses DB column names
            # directly and preserves the original exception-raising behaviour.
            logger.info("Updating trip (deprecated dict path): trip_id=%s, changes=%s",
                        trip_id, {k: v for k, v in request.items() if k != '_csrf_token'})
            try:
                self._trip_repo.update(trip_id, dict(request))
                self._event_bus.publish(TRIP_UPDATED, {"trip_id": trip_id, "changes": request})
                AuditService(self.db).log(
                    event_type="trip.updated",
                    entity_type="trip",
                    entity_id=str(trip_id),
                    data={"changed_fields": list(request.keys())},
                    user_id=user_id,
                )
                logger.info("Trip updated successfully: trip_id=%s", trip_id)
            except Exception as e:
                logger.error("Failed to update trip: trip_id=%s, data=%s — %s", trip_id, request, e, exc_info=True)
                raise
            row = self._trip_repo.get_by_id(trip_id)
            if row:
                return ServiceResult(success=True, data=_db_to_trip_result(row))
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Trip not found after update", code="not_found")],
            )

        if not isinstance(request, TripUpdate):
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="request must be TripUpdate or dict", code="type_error")],
            )

        trip_update = request
        logger.info("Updating trip: trip_id=%s", trip_id)

        # ── Permission check ───────────────────────────────────────────
        if user_id:
            perm = PermissionService(self.db)
            check = perm.can_update_trip(user_id)
            if not check.allowed:
                logger.warning("Permission denied updating trip: user_id=%s, trip_id=%s", user_id, trip_id)
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message=check.reason, code="permission_denied")],
                )

        try:
            # ── Business validation for provided refs ──────────────────
            if trip_update.client_id is not None:
                self._validate_external_refs(client_id=trip_update.client_id)
            if trip_update.truck_id is not None:
                self._validate_external_refs(truck_id=trip_update.truck_id)
            if trip_update.driver_id is not None:
                self._validate_external_refs(driver_id=trip_update.driver_id)

            # ── Persist ────────────────────────────────────────────────
            data = _model_to_db(trip_update.model_dump(exclude_none=True, exclude_unset=True))
            if not data:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message="No fields to update", code="empty_update")],
                )

            self._trip_repo.update(trip_id, data)
            self._event_bus.publish(TRIP_UPDATED, {"trip_id": trip_id, "changes": data})
            AuditService(self.db).log(
                event_type="trip.updated",
                entity_type="trip",
                entity_id=str(trip_id),
                data={"changed_fields": list(data.keys())},
                user_id=user_id,
            )
            logger.info("Trip updated successfully: trip_id=%s", trip_id)

            # ── Return result ──────────────────────────────────────────
            row = self._trip_repo.get_by_id(trip_id)
            if row:
                result = _db_to_trip_result(row)
                return ServiceResult(success=True, data=result)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Trip not found after update", code="not_found")],
            )

        except ValueError as e:
            logger.error("Validation error updating trip %s: %s", trip_id, e)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="validation_error")],
            )
        except PermissionError as e:
            logger.error("Permission error updating trip %s: %s", trip_id, e)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="permission_denied")],
            )
        except Exception as e:
            logger.error("Failed to update trip %s: %s", trip_id, e, exc_info=True)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="internal_error")],
            )

    def get(self, trip_id: int) -> TripCreateResult:
        """Fetch a single trip by ID, returning a ``ServiceResult``."""
        try:
            row = self._trip_repo.get_by_id(trip_id)
            if not row:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message=f"Trip {trip_id} not found", code="not_found")],
                )
            result = _db_to_trip_result(row)
            return ServiceResult(success=True, data=result)
        except Exception as e:
            logger.error("Failed to get trip %s: %s", trip_id, e, exc_info=True)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="internal_error")],
            )

    def list_all(self, limit: int = 500) -> TripListResult:
        """Return all trips as a typed list result."""
        try:
            rows = self._trip_repo.get_all(limit=limit)
            results = [_db_to_trip_result(r) for r in rows]
            return ServiceResult(success=True, data=results)
        except Exception as e:
            logger.error("Failed to list trips: %s", e, exc_info=True)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="internal_error")],
            )

    def delete(self, trip_id: int, user_id: int = 0) -> TripCreateResult:
        """Delete a trip by ID.

        Requires admin-level permission when ``user_id`` is provided.
        Returns a ``ServiceResult`` with the deleted trip data (before deletion)
        if successful.
        """
        logger.info("Deleting trip: trip_id=%s, user_id=%s", trip_id, user_id)

        # ── Permission check ───────────────────────────────────────────
        if user_id:
            perm = PermissionService(self.db)
            check = perm.can_delete_trip(user_id)
            if not check.allowed:
                logger.warning("Permission denied deleting trip: user_id=%s, trip_id=%s", user_id, trip_id)
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message=check.reason, code="permission_denied")],
                )

        try:
            # Fetch data before deleting so we can return it
            row = self._trip_repo.get_by_id(trip_id)
            if not row:
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message=f"Trip {trip_id} not found", code="not_found")],
                )

            self._trip_repo.delete(trip_id)
            self._event_bus.publish(TRIP_DELETED, {"trip_id": trip_id})
            AuditService(self.db).log(
                event_type="trip.deleted",
                entity_type="trip",
                entity_id=str(trip_id),
                data={"client_id": row.get("client_id")},
                user_id=user_id,
            )
            logger.info("Trip deleted successfully: trip_id=%s", trip_id)

            result = _db_to_trip_result(row)
            return ServiceResult(success=True, data=result)

        except PermissionError as e:
            logger.error("Permission error deleting trip %s: %s", trip_id, e)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="permission_denied")],
            )
        except Exception as e:
            logger.error("Failed to delete trip %s: %s", trip_id, e, exc_info=True)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(e), code="internal_error")],
            )

    # ═════════════════════════════════════════════════════════════════════
    # Business validation helpers
    # ═════════════════════════════════════════════════════════════════════

    def _validate_external_refs(
        self,
        client_id: Optional[int] = None,
        truck_id: Optional[int] = None,
        driver_id: Optional[int] = None,
    ) -> None:
        """Verify that referenced foreign keys exist.

        Raises ``ValueError`` if any referenced entity is not found.
        """
        if client_id is not None:
            from repositories.client_repository import ClientRepository
            client_repo = ClientRepository(self.db)
            client = client_repo.get_by_id(client_id)
            if not client:
                raise ValueError(f"Client with id {client_id} not found")
        if truck_id is not None:
            from repositories.fleet_repository import FleetRepository
            fleet_repo = FleetRepository(self.db)
            truck = fleet_repo.get_by_id(truck_id)
            if not truck:
                raise ValueError(f"Truck with id {truck_id} not found")
        if driver_id is not None:
            from repositories.driver_repository import DriverRepository
            driver_repo = DriverRepository(self.db)
            driver = driver_repo.get_by_id(driver_id)
            if not driver:
                raise ValueError(f"Driver with id {driver_id} not found")

    # ═════════════════════════════════════════════════════════════════════
    # Backward-compatible wrappers (deprecated)
    # ═════════════════════════════════════════════════════════════════════

    def add(self, data: dict[str, Any]) -> int:
        """Deprecated: use ``create()`` with a ``TripCreate`` model instead.

        This shim preserves the original behaviour (raw DB dict in, raw ID out)
        but emits a deprecation warning.
        """
        warnings.warn(
            "TripService.add() is deprecated; use create() with a TripCreate model.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.info("Adding trip (deprecated): %s", {k: v for k, v in data.items() if k != '_csrf_token'})
        try:
            new_id = self._trip_repo.create(data)
            self._event_bus.publish(TRIP_CREATED, {"trip_id": new_id, "data": data})
            logger.info("Trip created successfully (deprecated add): trip_id=%s", new_id)
            return new_id
        except Exception as e:
            logger.error("Failed to add trip: data=%s — %s", data, e, exc_info=True)
            raise

    # ═════════════════════════════════════════════════════════════════════
    # Legacy query passthrough (return raw dicts for existing callers)
    # ═════════════════════════════════════════════════════════════════════

    def get_filtered(self, search: str = "", status: str = "", limit: int = 200) -> list[dict[str, Any]]:
        return self._trip_repo.get_filtered(search=search, truck="", status=status, limit=limit)

    def get_by_id(self, trip_id: int) -> Optional[dict[str, Any]]:
        return self._trip_repo.get_by_id(trip_id)

    def get_by_statuses(self, statuses: list[str]) -> list[dict[str, Any]]:
        return self._trip_repo.get_by_statuses(statuses)

    def get_all(self, limit: int = 500) -> list[dict[str, Any]]:
        return self._trip_repo.get_all(limit=limit)

    def update_cmr_fields(self, trip_id: int, cmr_number: str, cmr_seq: int, user_id: int = 0) -> None:
        self._trip_repo.update_cmr_fields(trip_id, cmr_number, cmr_seq)
        AuditService(self.db).log(
            event_type="trip.cmr_updated",
            entity_type="trip",
            entity_id=str(trip_id),
            data={"cmr_number": cmr_number, "cmr_seq": cmr_seq},
            user_id=user_id,
        )

    def get_route_stops_json(self, route_id: int) -> Optional[str]:
        return self._route_repo.get_stops_json(route_id)

    def extract_route_pickup_delivery(self, trip_data: dict) -> tuple[str, str]:
        """Extract pickup and delivery addresses from a trip's route stops.

        Returns a ``(pickup_address, delivery_address)`` tuple.
        Returns ``("", "")`` when route data is unavailable or unparseable.
        """
        import json as _json
        route_id = trip_data.get("route_history_v2_id")
        if not route_id:
            return "", ""
        try:
            stops_json = self.get_route_stops_json(route_id)
            if not stops_json:
                return "", ""
            stops = _json.loads(stops_json)
            if isinstance(stops, list) and len(stops) >= 2:
                return (
                    stops[0].get("address", ""),
                    stops[-1].get("address", ""),
                )
        except Exception:
            logger.warning("Failed to extract route stops for route_id=%s", route_id, exc_info=True)
        return "", ""
