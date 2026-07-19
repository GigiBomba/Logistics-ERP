"""Level 2 Co-Pilot CRUD tools for the Driver domain — requires user confirmation.

Wraps ``DriverTruckService.create_driver()`` and
``DriverTruckService.update_driver()`` with typed Pydantic models for safe
AI-driven driver mutations.
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


class DriverCreateParams(BaseModel):
    """Input parameters for ``driver.create``."""

    model_config = {"extra": "forbid"}

    name: str = Field(..., min_length=1, description="Driver name")
    license_number: str = Field(..., description="Driver's license number")
    phone: str = Field("", description="Phone number")
    email: str = Field("", description="Email address")
    max_hours_per_day: int = Field(9, ge=1, le=24, description="Maximum driving hours per day")


class DriverUpdateParams(BaseModel):
    """Input parameters for ``driver.update``."""

    model_config = {"extra": "forbid"}

    driver_id: int = Field(..., gt=0, description="Driver ID to update")
    name: Optional[str] = Field(None, min_length=1, description="Driver name")
    license_number: Optional[str] = Field(None, description="Driver's license number")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    max_hours_per_day: Optional[int] = Field(None, ge=1, le=24, description="Maximum driving hours per day")


# ── driver.create (Level 2) ────────────────────────────────────────────────


@register_tool
class DriverCreateTool(BaseTool):
    """Create a new driver.

    Wraps ``DriverTruckService.create_driver(request, user_id)`` with a typed
    ``DriverCreate`` model.  Requires ``drivers:write`` permission and
    user confirmation.
    """

    name = "driver.create"
    tool_version = "1.0.0"
    description = (
        "Create a new driver with license, contact, and working hours information"
    )
    required_permission = "drivers:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = DriverCreateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> DriverCreateParams:
        assert isinstance(params, DriverCreateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if not p.name.strip():
            errors.append("Driver name is required")
        if not p.license_number.strip():
            errors.append("License number is required")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.driver_models import DriverCreate, DriverResult
            from models.common import ServiceResult
            from backend.services.driver_truck_service import DriverTruckService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            request = DriverCreate(
                name=p.name,
                license_number=p.license_number,
                phone=p.phone,
                email=p.email,
                max_hours_per_day=float(p.max_hours_per_day),
            )

            svc = DriverTruckService(db)
            result: ServiceResult[DriverResult] = svc.create_driver(  # type: ignore[assignment]
                request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            driver = result.data
            if driver is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": "Driver created but no data returned"},
                )
            return ToolResult(
                status="success",
                data={
                    "driver_id": driver.id,
                },
                message_key="copilot.driver.create.success",
                message_params={"name": driver.name},
            )

        except Exception as exc:
            logger.exception("driver.create failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ── driver.update (Level 2) ────────────────────────────────────────────────


@register_tool
class DriverUpdateTool(BaseTool):
    """Update an existing driver.

    Wraps ``DriverTruckService.update_driver(driver_id, request, user_id)``
    with a typed ``DriverUpdate`` model.  Only fields that are explicitly
    provided will be changed.
    """

    name = "driver.update"
    tool_version = "1.0.0"
    description = (
        "Update an existing driver's name, license, contact, or working hours"
    )
    required_permission = "drivers:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = DriverUpdateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> DriverUpdateParams:
        assert isinstance(params, DriverUpdateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.driver_id <= 0:
            errors.append("driver_id must be a positive integer")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.driver_models import DriverResult, DriverUpdate
            from models.common import ServiceResult
            from backend.services.driver_truck_service import DriverTruckService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            request = DriverUpdate(
                name=p.name,
                license_number=p.license_number,
                phone=p.phone,
                email=p.email,
                max_hours_per_day=float(p.max_hours_per_day) if p.max_hours_per_day is not None else None,
            )

            svc = DriverTruckService(db)
            result: ServiceResult[DriverResult] = svc.update_driver(  # type: ignore[assignment]
                p.driver_id, request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            driver = result.data
            return ToolResult(
                status="success",
                data={
                    "driver_id": driver.id if driver else p.driver_id,
                },
                message_key="copilot.driver.update.success",
                message_params={"driver_id": p.driver_id},
            )

        except Exception as exc:
            logger.exception("driver.update failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )
