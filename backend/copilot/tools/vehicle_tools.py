"""Vehicle search & health-score tools — Fleet domain, Level 0.
Blueprint: §9.1 — Fleet (Vehicles), Level 0.
"""

from __future__ import annotations
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool


# ── Parameters ──────────────────────────────────────────────────────────────


class VehicleSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = ""
    status: str = ""
    fuel_type: str = ""


class VehicleHealthScoreParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_id: int


# ── vehicle.search (Level 0) ────────────────────────────────────────────────


@register_tool
class VehicleSearchTool(BaseTool):
    name = "vehicle.search"
    tool_version = "1.0.0"
    description = "Search for available vehicles in the fleet by plate, model, status, or fuel type"
    required_permission = "fleet:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = VehicleSearchParams

    async def validate(self, params: VehicleSearchParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: VehicleSearchParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            from backend.services.fleet_service import FleetService
            from models.vehicle_models import VehicleSearchRequest

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )
            fleet_svc = FleetService(db)

            request = VehicleSearchRequest(
                query=params.query,
                status=params.status or None,
                fuel_type=params.fuel_type or None,
            )
            result = fleet_svc.find_available(request)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            vehicles = [v.model_dump() for v in (result.data or [])]
            return ToolResult(
                status="success",
                data={"vehicles": vehicles},
                message_key="copilot.step.vehicle_search_done",
            )
        except Exception as e:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )


# ── vehicle.health_score (Level 0) ──────────────────────────────────────────


@register_tool
class VehicleHealthScoreTool(BaseTool):
    name = "vehicle.health_score"
    tool_version = "1.0.0"
    description = "Get the health score for a vehicle including insurance, inspection, and tachograph status"
    required_permission = "fleet:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = VehicleHealthScoreParams

    async def validate(self, params: VehicleHealthScoreParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: VehicleHealthScoreParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            from backend.services.fleet_service import FleetService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )
            fleet_svc = FleetService(db)

            result = fleet_svc.health_score(params.vehicle_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            score_data = result.data.model_dump() if result.data else {}
            return ToolResult(
                status="success",
                data={"health_score": score_data},
                message_key="copilot.step.vehicle_health_score_done",
            )
        except Exception as e:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )
