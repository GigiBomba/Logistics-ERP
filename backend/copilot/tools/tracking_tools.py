"""Co-Pilot tools for the Tracking domain — live GPS positions and vehicle history.
Blueprint: §9.1 — Tracking, Level 0.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool


# ── Parameters ──────────────────────────────────────────────────────────────


class GetLivePositionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force_refresh: bool = Field(
        True,
        description="Bypass internal cache and poll the GPS adapter immediately.",
    )


class GetVehicleHistoryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_id: int = Field(..., description="ID of the vehicle to fetch history for.")
    date_from: Optional[str] = Field(None, description="Start date (YYYY-MM-DD).")
    date_to: Optional[str] = Field(None, description="End date (YYYY-MM-DD).")


# ── Tool 1: tracking.get_live_positions ─────────────────────────────────────


@register_tool
class GetLivePositionsTool(BaseTool):
    name = "tracking.get_live_positions"
    tool_version = "1.0.0"
    description = (
        "Fetch current live GPS positions for all tracked vehicles. "
        "Returns vehicle_id, lat, lon, timestamp, speed, heading, and status."
    )
    required_permission = "tracking:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = GetLivePositionsParams

    async def validate(self, params: GetLivePositionsParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: GetLivePositionsParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            from services.fleet_tracking_service import FleetTrackingService

            service = FleetTrackingService()  # singleton
            positions = service.get_positions(force_refresh=params.force_refresh)

            return ToolResult(
                status="success",
                data={
                    "positions": [
                        {
                            "vehicle_id": p.device_id,
                            "name": p.name,
                            "latitude": p.latitude,
                            "longitude": p.longitude,
                            "timestamp": p.timestamp.isoformat()
                            if hasattr(p.timestamp, "isoformat")
                            else str(p.timestamp),
                            "speed_kmh": p.speed_kmh,
                            "heading": p.heading,
                            "status": p.status,
                        }
                        for p in positions
                    ]
                },
                message_key="copilot.tracking.positions_fetched",
                message_params={"count": len(positions)},
            )
        except Exception as e:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )


# ── Tool 2: tracking.get_vehicle_history ────────────────────────────────────


@register_tool
class GetVehicleHistoryTool(BaseTool):
    name = "tracking.get_vehicle_history"
    tool_version = "1.0.0"
    description = (
        "Retrieve historical GPS tracking data for a specific vehicle. "
        "NOTE: This feature is currently unavailable in the system."
    )
    required_permission = "tracking:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = GetVehicleHistoryParams

    async def validate(self, params: GetVehicleHistoryParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: GetVehicleHistoryParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            from services.fleet_tracking_service import FleetTrackingService
            from repositories.fleet_repository import FleetRepository

            service = FleetTrackingService()  # singleton
            all_positions = service.get_positions(force_refresh=True)

            # Try to resolve vehicle plate from DB to match against position names
            db = ctx.services.get("db")
            truck_plate = ""
            if db is not None:
                try:
                    fleet_repo = FleetRepository(db)
                    truck = fleet_repo.get_by_id(params.vehicle_id)
                    if truck:
                        truck_plate = (truck.get("plate_number") or "").upper()
                except Exception:
                    pass

            # Filter positions matching the requested vehicle_id
            filtered = []
            for p in all_positions:
                if truck_plate and p.name.upper() == truck_plate:
                    filtered.append(p)
                elif str(p.device_id) == str(params.vehicle_id):
                    filtered.append(p)

            positions = [
                {
                    "device_id": p.device_id,
                    "name": p.name,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "timestamp": p.timestamp.isoformat()
                    if hasattr(p.timestamp, "isoformat")
                    else str(p.timestamp),
                    "speed_kmh": p.speed_kmh,
                    "heading": p.heading,
                    "status": p.status,
                }
                for p in filtered
            ]

            return ToolResult(
                status="success",
                data={
                    "vehicle_id": params.vehicle_id,
                    "positions": positions,
                },
                message_key="copilot.tracking.history_fetched",
                message_params={"vehicle_id": str(params.vehicle_id), "count": str(len(positions))},
            )
        except Exception as e:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )
