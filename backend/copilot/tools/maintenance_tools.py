"""Co-Pilot tools for the Fleet Maintenance domain — schedule and manage maintenance.

Level 2 (BUSINESS) tool wrapping FleetMaintenanceService.

Handles: ``maintenance.schedule``.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Valid maintenance types ──────────────────────────────────────────────────

VALID_MAINT_TYPES = frozenset({
    "oil_change",
    "brake_check",
    "tire_rotation",
    "inspection",
    "other",
})


# ═════════════════════════════════════════════════════════════════════════════
# Parameter models
# ═════════════════════════════════════════════════════════════════════════════


class MaintenanceScheduleParams(BaseModel):
    """Parameters for ``maintenance.schedule``.

    All interval / last-done fields are optional — the service applies
    sensible defaults when omitted.
    """

    truck_id: int = Field(..., gt=0, description="Truck ID to schedule maintenance for")
    maint_type: str = Field(
        ...,
        description="Type of maintenance — one of: oil_change, brake_check, tire_rotation, inspection, other",
    )
    interval_km: Optional[float] = Field(
        None, ge=0, description="Service interval in kilometres"
    )
    interval_months: Optional[int] = Field(
        None, ge=1, description="Service interval in months"
    )
    fixed_expiry_date: Optional[str] = Field(
        None,
        description="Fixed expiry date (YYYY-MM-DD) — overrides interval-based expiry",
    )
    last_done_km: Optional[float] = Field(
        None, ge=0, description="Odometer reading at last service"
    )
    last_done_date: Optional[str] = Field(
        None, description="Date of last service (YYYY-MM-DD)"
    )

    @field_validator("maint_type")
    @classmethod
    def _validate_maint_type(cls, v: str) -> str:
        lowered = v.strip().lower()
        if lowered not in VALID_MAINT_TYPES:
            raise ValueError(
                f"Invalid maint_type '{v}'. Must be one of: "
                f"{', '.join(sorted(VALID_MAINT_TYPES))}"
            )
        return lowered

    @field_validator("fixed_expiry_date", "last_done_date")
    @classmethod
    def _coerce_empty_string(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            return None
        return v


# ═════════════════════════════════════════════════════════════════════════════
# Tool: maintenance.schedule — Level 2 (BUSINESS)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class MaintenanceScheduleTool(BaseTool):
    """Create a maintenance schedule for a truck.

    Wraps ``FleetMaintenanceService.add_schedule()`` to register a recurring
    or fixed-expiry maintenance plan.  Returns the new ``schedule_id``.
    """

    name = "maintenance.schedule"
    tool_version = "1.0.0"
    description = (
        "Create a maintenance schedule for a truck. "
        "Specify the maintenance type (oil_change, brake_check, tire_rotation, "
        "inspection, other) along with optional interval parameters. "
        "Returns the new schedule_id."
    )
    required_permission = "maintenance:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = MaintenanceScheduleParams

    # ── Validation ──────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []

        if p.truck_id <= 0:
            errors.append("truck_id must be a positive integer")

        if p.maint_type not in VALID_MAINT_TYPES:
            errors.append(
                f"maint_type must be one of: {', '.join(sorted(VALID_MAINT_TYPES))}"
            )

        if p.interval_km is not None and p.interval_km < 0:
            errors.append("interval_km must be non-negative")

        if p.interval_months is not None and p.interval_months < 1:
            errors.append("interval_months must be at least 1")

        if p.last_done_km is not None and p.last_done_km < 0:
            errors.append("last_done_km must be non-negative")

        return errors

    # ── Execution ───────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            # ── Resolve FleetMaintenanceService ─────────────────────────
            svc = ctx.services.get("fleet_maintenance_service")
            if svc is None:
                db: Any = ctx.services.get("db")  # type: ignore[no-untyped-def]
                if db is None:
                    return ToolResult(
                        status="unavailable",
                        message_key="copilot.error.no_db",
                        message_params={"tool": self.name},
                    )
                from backend.services.fleet_maintenance_service import (
                    FleetMaintenanceService,
                )
                svc = FleetMaintenanceService(db)

            # ── Call service ────────────────────────────────────────────
            schedule_id_raw = svc.add_schedule(
                truck_id=p.truck_id,
                maint_type=p.maint_type,
                interval_km=p.interval_km,
                interval_months=p.interval_months,
                fixed_expiry_date=p.fixed_expiry_date or "",
                last_done_km=p.last_done_km,
                last_done_date=p.last_done_date or "",
            )
            schedule_id: int = int(schedule_id_raw) if schedule_id_raw is not None else 0

            return ToolResult(
                status="success",
                data={"schedule_id": schedule_id},
                message_key="copilot.maintenance.schedule.success",
                message_params={
                    "schedule_id": str(schedule_id),
                    "truck_id": str(p.truck_id),
                    "maint_type": p.maint_type,
                },
            )

        except Exception as exc:
            logger.exception(
                "maintenance.schedule failed for truck #%d", p.truck_id
            )
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> MaintenanceScheduleParams:
        assert isinstance(params, MaintenanceScheduleParams)
        return params
