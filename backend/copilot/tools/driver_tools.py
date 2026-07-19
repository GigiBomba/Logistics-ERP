"""Driver check-hours tool — Driver domain, Level 0.
Blueprint: §9.1 — Drivers, Level 0.
"""

from __future__ import annotations
from datetime import date
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool


# ── Parameters ──────────────────────────────────────────────────────────────


class DriverCheckHoursParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    driver_id: int
    date: str = ""


# ── driver.check_hours (Level 0) ────────────────────────────────────────────


@register_tool
class DriverCheckHoursTool(BaseTool):
    name = "driver.check_hours"
    tool_version = "1.0.0"
    description = "Check if a driver has available hours for a given date, verifying compliance with work-hour regulations"
    required_permission = "drivers:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = DriverCheckHoursParams

    async def validate(self, params: DriverCheckHoursParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: DriverCheckHoursParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            from backend.services.driver_truck_service import DriverTruckService
            from models.driver_models import DriverHoursCheck

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )
            svc = DriverTruckService(db)

            check_date = date.fromisoformat(params.date) if params.date else date.today()

            request = DriverHoursCheck(
                driver_id=params.driver_id,
                check_date=check_date,
            )
            result = svc.check_hours(request)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            hours_data = result.data.model_dump() if result.data else {}
            return ToolResult(
                status="success",
                data={"hours": hours_data},
                message_key="copilot.step.driver_hours_check_done",
            )
        except Exception as e:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )
