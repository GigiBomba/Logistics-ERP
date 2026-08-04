"""Co-Pilot tools for the Dispatch domain — assign, bulk-assign, and cancel trips.

Level 2 (BUSINESS) and Level 3 (DESTRUCTIVE) tools wrapping DispatchService.

Handle: ``dispatch.create``, ``dispatch.bulk_assign``, ``dispatch.cancel``.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Parameter models
# ═════════════════════════════════════════════════════════════════════════════


class DispatchCreateParams(BaseModel):
    """Parameters for ``dispatch.create`` (wraps ``assign_both``)."""

    trip_id: int = Field(..., gt=0, description="Trip ID to assign resources to")
    truck_id: Optional[int] = Field(
        None, gt=0, description="Truck ID to assign (optional if driver_id provided)"
    )
    driver_id: Optional[int] = Field(
        None, gt=0, description="Driver ID to assign (optional if truck_id provided)"
    )

    @field_validator("truck_id", "driver_id", mode="before")
    @classmethod
    def _coerce_none(cls, v: Any) -> Any:
        """Coerce empty strings to None for optional int fields."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("trip_id", mode="after")
    @classmethod
    def _check_at_least_one(cls, v: int, info: Any) -> int:
        truck = info.data.get("truck_id")
        driver = info.data.get("driver_id")
        if truck is None and driver is None:
            raise ValueError("At least one of truck_id or driver_id must be provided")
        return v


class BulkAssignParams(BaseModel):
    """Parameters for ``dispatch.bulk_assign``."""

    trip_ids: List[int] = Field(
        ..., min_length=1, description="List of trip IDs to assign resources to"
    )
    assign_type: str = Field(
        ...,
        description="Type of resource to assign — one of: 'truck', 'driver'",
        pattern=r"^(truck|driver)$",
    )
    assign_id: int = Field(..., gt=0, description="ID of the truck or driver to assign")


class DispatchCancelParams(BaseModel):
    """Parameters for ``dispatch.cancel`` (Level 3 — DESTRUCTIVE)."""

    trip_id: int = Field(..., gt=0, description="Trip ID to cancel")
    reason: str = Field(default="", description="Optional reason for cancellation")


# ═════════════════════════════════════════════════════════════════════════════
# Internal helpers — shared across dispatch tools
# ═════════════════════════════════════════════════════════════════════════════


def _build_dispatch_service(db: Any):  # type: ignore[no-untyped-def]
    """Construct a fully-wired DispatchService from a DB manager.

    Attempts to pull pre-built services from the database layer.  Falls back
    to constructing each dependency directly from the DB handle.
    """
    from backend.repositories.driver_repository import DriverRepository
    from backend.repositories.fleet_repository import FleetRepository
    from backend.services.conflict_service import TripConflictService
    from backend.services.trip_service import TripService
    from services.dispatch_service.dispatch_service import DispatchService

    trip_service = TripService(db)
    fleet_repo = FleetRepository(db)
    driver_repo = DriverRepository(db)
    conflict_service = TripConflictService(db)
    # Optional: DTA service, tacho repo, event bus, alert manager, ops engine
    # These are set to None; they are not critical for basic assignment/cancel.
    return DispatchService(
        trip_service=trip_service,
        fleet_repo=fleet_repo,
        driver_repo=driver_repo,
        conflict_service=conflict_service,
        dta_service=None,
        tacho_repo=None,
        event_bus=None,
        alert_manager=None,
        ops_engine=None,
    )


def _resolve_dispatch_service(ctx: ToolExecutionContext):
    """Return a DispatchService, first checking ``ctx.services``, else building from db."""
    svc = ctx.services.get("dispatch_service")
    if svc is not None:
        return svc

    db = ctx.services.get("db")
    if db is None:
        return None
    return _build_dispatch_service(db)


# ═════════════════════════════════════════════════════════════════════════════
# Tool 1: dispatch.create — Level 2 (BUSINESS)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class DispatchCreateTool(BaseTool):
    """Assign a truck and/or driver to a trip.

    Wraps ``DispatchService.assign_both()``.  At least one of *truck_id* or
    *driver_id* is required.  If both are supplied both are assigned
    atomically (driver failure rolls back truck assignment).
    """

    name = "dispatch.create"
    tool_version = "1.0.0"
    description = (
        "Assign a truck and/or driver to a trip. "
        "Provide at least one of truck_id or driver_id. "
        "Returns trip_id, truck_id, driver_id, and status."
    )
    required_permission = "dispatch:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = True          # Undo reverses assign_both via UndoStack trip status workflow
    deprecated = False
    parameters_schema = DispatchCreateParams

    # ── Validation ──────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.trip_id <= 0:
            errors.append("trip_id must be a positive integer")
        if p.truck_id is not None and p.truck_id <= 0:
            errors.append("truck_id must be a positive integer")
        if p.driver_id is not None and p.driver_id <= 0:
            errors.append("driver_id must be a positive integer")
        if p.truck_id is None and p.driver_id is None:
            errors.append("At least one of truck_id or driver_id must be provided")
        return errors

    # ── Execution ───────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            svc = _resolve_dispatch_service(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            result = svc.assign_both(
                trip_id=p.trip_id,
                truck_id=p.truck_id,
                driver_id=p.driver_id,
            )

            if not result.success:
                return ToolResult(
                    status="failed",
                    message_key="copilot.dispatch.create.failed",
                    message_params={
                        "trip_id": str(p.trip_id),
                        "error": getattr(result, 'message', str(getattr(result, 'errors', 'Unknown error'))),
                    },
                )

            return ToolResult(
                status="success",
                data={
                    "trip_id": result.trip_id,
                    "truck_id": p.truck_id,
                    "driver_id": p.driver_id,
                    "status": "assigned",
                    "details": result.details,
                },
                message_key="copilot.dispatch.create.success",
                message_params={
                    "trip_id": str(result.trip_id),
                    "truck_plate": result.details.get("truck_plate", "—"),
                    "driver_name": result.details.get("driver_name", "—"),
                },
                undo_token=str(result.undo_token) if result.undo_token else None,
            )

        except Exception as exc:
            logger.exception("dispatch.create failed for trip #%d", p.trip_id)
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )

    # ── Undo ─────────────────────────────────────────────────────────────

    async def undo(self, undo_token: str, ctx: ToolExecutionContext) -> ToolResult:
        """Reverse a dispatch.create by restoring the trip's previous state.

        The undo_token encodes the operation type, trip_id, and a snapshot
        of the trip fields *before* the assignment.  We restore those fields
        via TripService.update().
        """
        import json

        try:
            token = json.loads(undo_token)
            trip_id: int = token.get("trip_id", 0)
            previous_state: dict = token.get("previous_state", {})

            # Validate previous_state contains expected fields
            if not isinstance(previous_state, dict) or "status" not in previous_state:
                return ToolResult(
                    status="failed",
                    message_key="copilot.undo.invalid_token",
                    message_params={},
                )

            # Resolve TripService — prefer injected, fall back to manual construction
            trip_service = ctx.services.get("trip_service")
            if trip_service is None:
                db = ctx.services.get("db")
                if db is not None:
                    from backend.services.trip_service import TripService

                    trip_service = TripService(db)
                else:
                    return ToolResult(
                        status="unavailable",
                        message_key="copilot.error.no_db",
                    )

            from models.trip_models import TripUpdate
            # Map DB column names to TripUpdate field names
            _db_to_model = {"truck_number": "truck_plate", "net_profit": "profit"}
            mapped = {}
            for k, v in previous_state.items():
                model_key = _db_to_model.get(k, k)
                if model_key in TripUpdate.model_fields:
                    mapped[model_key] = v
            update_result = trip_service.update(trip_id, TripUpdate(**mapped))
            if update_result is None or not getattr(update_result, 'success', False):
                err = str(getattr(update_result, 'errors', 'Update failed')) if update_result else 'Update returned None'
                return ToolResult(status="failed", message_key="copilot.dispatch.undo_failed", message_params={"error": err})
            logger.info(
                "Undo dispatch.create for trip #%d: restored %s",
                trip_id,
                previous_state,
            )
            return ToolResult(
                status="success",
                message_key="copilot.undo.success",
                message_params={
                    "description": token.get(
                        "undo_description",
                        f"Restored trip #{trip_id}",
                    ),
                },
            )
        except json.JSONDecodeError:
            return ToolResult(
                status="failed",
                message_key="copilot.undo.invalid_token",
            )
        except Exception as exc:
            logger.exception("dispatch.create undo failed for token %s", undo_token)
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> DispatchCreateParams:
        assert isinstance(params, DispatchCreateParams)
        return params


# ═════════════════════════════════════════════════════════════════════════════
# Tool 2: dispatch.bulk_assign — Level 2 (BUSINESS)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class DispatchBulkAssignTool(BaseTool):
    """Bulk-assign a truck or driver to multiple trips.

    Wraps ``DispatchService.bulk_assign_truck()`` or
    ``DispatchService.bulk_assign_driver()`` depending on ``assign_type``.
    """

    name = "dispatch.bulk_assign"
    tool_version = "1.0.0"
    description = (
        "Assign a truck or driver to multiple trips in bulk. "
        "Specify assign_type='truck' or assign_type='driver' and the "
        "corresponding assign_id. Returns success_count, failed_count, "
        "and a list of failures."
    )
    required_permission = "dispatch:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = BulkAssignParams

    # ── Validation ──────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if not p.trip_ids:
            errors.append("trip_ids must be a non-empty list")
        if p.assign_type not in ("truck", "driver"):
            errors.append("assign_type must be 'truck' or 'driver'")
        if p.assign_id <= 0:
            errors.append("assign_id must be a positive integer")
        return errors

    # ── Execution ───────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            svc = _resolve_dispatch_service(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            if p.assign_type == "truck":
                bulk_result = svc.bulk_assign_truck(
                    trip_ids=p.trip_ids,
                    truck_id=p.assign_id,
                )
            else:
                bulk_result = svc.bulk_assign_driver(
                    trip_ids=p.trip_ids,
                    driver_id=p.assign_id,
                )

            failures: List[dict[str, Any]] = []
            for r in bulk_result.results:
                if not r.success:
                    failures.append({
                        "trip_id": r.trip_id,
                        "error": r.message,
                    })

            return ToolResult(
                status="success",
                data={
                    "success_count": bulk_result.succeeded,
                    "failed_count": bulk_result.failed,
                    "total": bulk_result.total,
                    "failures": failures,
                },
                message_key="copilot.dispatch.bulk_assign.success",
                message_params={
                    "success_count": str(bulk_result.succeeded),
                    "failed_count": str(bulk_result.failed),
                    "total": str(bulk_result.total),
                },
            )

        except Exception as exc:
            logger.exception("dispatch.bulk_assign failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> BulkAssignParams:
        assert isinstance(params, BulkAssignParams)
        return params


# ═════════════════════════════════════════════════════════════════════════════
# Tool 3: dispatch.cancel — Level 3 (DESTRUCTIVE)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class DispatchCancelTool(BaseTool):
    """Cancel a trip.

    Wraps ``DispatchService.cancel_trip()``.  This is a **destructive**
    action (Level 3) that requires explicit typed confirmation from the
    user before execution.
    """

    name = "dispatch.cancel"
    tool_version = "1.0.0"
    description = (
        "Cancel a trip. This action is destructive and irreversible. "
        "Requires typed confirmation before execution. "
        "Provide a reason for the cancellation."
    )
    required_permission = "dispatch:write"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    deprecated = False
    parameters_schema = DispatchCancelParams

    # ── Validation ──────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.trip_id <= 0:
            errors.append("trip_id must be a positive integer")
        return errors

    # ── Execution ───────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            svc = _resolve_dispatch_service(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            result = svc.cancel_trip(
                trip_id=p.trip_id,
                reason=p.reason,
            )

            if not result.success:
                return ToolResult(
                    status="failed",
                    message_key="copilot.dispatch.cancel.failed",
                    message_params={
                        "trip_id": str(p.trip_id),
                        "error": getattr(result, 'message', str(getattr(result, 'errors', 'Unknown error'))),
                    },
                )

            return ToolResult(
                status="success",
                data={
                    "trip_id": result.trip_id,
                    "status": "cancelled",
                    "operation": result.operation,
                },
                message_key="copilot.dispatch.cancel.success",
                message_params={
                    "trip_id": str(result.trip_id),
                    "reason": p.reason or "not specified",
                },
                undo_token=str(result.undo_token) if result.undo_token else None,
            )

        except Exception as exc:
            logger.exception("dispatch.cancel failed for trip #%d", p.trip_id)
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> DispatchCancelParams:
        assert isinstance(params, DispatchCancelParams)
        return params
