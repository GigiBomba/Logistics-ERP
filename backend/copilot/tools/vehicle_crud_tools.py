"""Level 2 Co-Pilot CRUD tools for the Vehicle (Fleet) domain — requires user confirmation.

Wraps ``FleetService.create()`` and ``FleetService.update()`` with typed
Pydantic models for safe AI-driven vehicle mutations.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Parameters ──────────────────────────────────────────────────────────────


class VehicleCreateParams(BaseModel):
    """Input parameters for ``vehicle.create``."""

    model_config = {"extra": "forbid"}

    plate: str = Field(..., min_length=1, description="Vehicle license plate number")
    brand: str = Field(..., description="Vehicle brand / manufacturer")
    year: Optional[int] = Field(None, description="Manufacturing year")
    fuel_type: Optional[str] = Field(None, description="Fuel type (e.g. diesel, petrol, electric)")


class VehicleUpdateParams(BaseModel):
    """Input parameters for ``vehicle.update``."""

    model_config = {"extra": "forbid"}

    vehicle_id: int = Field(..., gt=0, description="Vehicle ID to update")
    plate: Optional[str] = Field(None, min_length=1, description="Vehicle license plate number")
    brand: Optional[str] = Field(None, description="Vehicle brand / manufacturer")
    year: Optional[int] = Field(None, description="Manufacturing year")
    fuel_type: Optional[str] = Field(None, description="Fuel type (e.g. diesel, petrol, electric)")


# ── vehicle.create (Level 2) ───────────────────────────────────────────────


@register_tool
class VehicleCreateTool(BaseTool):
    """Create a new vehicle in the fleet.

    Wraps ``FleetService.create(request, user_id)`` with a typed
    ``VehicleCreate`` model.  Requires ``fleet:write`` permission and
    user confirmation.
    """

    name = "vehicle.create"
    tool_version = "1.0.0"
    description = (
        "Create a new vehicle in the fleet with plate, brand, year, and fuel type"
    )
    required_permission = "fleet:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = VehicleCreateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> VehicleCreateParams:
        assert isinstance(params, VehicleCreateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if not p.plate.strip():
            errors.append("Plate number is required")
        if not p.brand.strip():
            errors.append("Brand is required")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.vehicle_models import VehicleCreate, VehicleResult
            from models.common import ServiceResult
            from backend.services.fleet_service import FleetService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            request = VehicleCreate(
                plate=p.plate,
                brand=p.brand,
                year=p.year,
                fuel_type=p.fuel_type or "diesel",
            )

            svc = FleetService(db)
            result: ServiceResult[VehicleResult] = svc.create(  # type: ignore[assignment]
                request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            vehicle = result.data
            if vehicle is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": "Vehicle created but no data returned"},
                )
            return ToolResult(
                status="success",
                data={
                    "vehicle_id": vehicle.id,
                },
                message_key="copilot.vehicle.create.success",
                message_params={"plate": vehicle.plate},
            )

        except Exception as exc:
            logger.exception("vehicle.create failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ── vehicle.update (Level 2) ───────────────────────────────────────────────


@register_tool
class VehicleUpdateTool(BaseTool):
    """Update an existing vehicle.

    Wraps ``FleetService.update(vehicle_id, request, user_id)`` with a typed
    ``VehicleUpdate`` model.  Only fields that are explicitly provided will
    be changed.
    """

    name = "vehicle.update"
    tool_version = "1.0.0"
    description = (
        "Update an existing vehicle's plate, brand, year, or fuel type"
    )
    required_permission = "fleet:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = VehicleUpdateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> VehicleUpdateParams:
        assert isinstance(params, VehicleUpdateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.vehicle_id <= 0:
            errors.append("vehicle_id must be a positive integer")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.vehicle_models import VehicleResult, VehicleUpdate
            from models.common import ServiceResult
            from backend.services.fleet_service import FleetService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            request = VehicleUpdate(
                plate=p.plate,
                brand=p.brand,
                year=p.year,
                fuel_type=p.fuel_type,
            )

            svc = FleetService(db)
            result: ServiceResult[VehicleResult] = svc.update(  # type: ignore[assignment]
                p.vehicle_id, request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            vehicle = result.data
            return ToolResult(
                status="success",
                data={
                    "vehicle_id": vehicle.id if vehicle else p.vehicle_id,
                },
                message_key="copilot.vehicle.update.success",
                message_params={"vehicle_id": p.vehicle_id},
            )

        except Exception as exc:
            logger.exception("vehicle.update failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )
