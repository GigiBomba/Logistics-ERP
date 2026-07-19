"""Level 2 Co-Pilot CRUD tools for the Trip domain — requires user confirmation.

Wraps ``TripService.create()`` and ``TripService.update()`` with typed
Pydantic models for safe AI-driven trip mutations.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Parameters ──────────────────────────────────────────────────────────────


class TripCreateParams(BaseModel):
    """Input parameters for ``trip.create``."""

    model_config = {"extra": "forbid"}

    client_id: int = Field(..., gt=0, description="Client ID for the trip")
    loading_city: str = Field(..., description="Loading/pickup city")
    delivery_city: str = Field(..., description="Delivery city")
    loading_country: Optional[str] = Field(None, description="Loading country")
    delivery_country: Optional[str] = Field(None, description="Delivery country")
    route_id: Optional[int] = Field(None, description="Route ID to assign")
    truck_id: Optional[int] = Field(None, description="Truck ID to assign")


class TripUpdateParams(BaseModel):
    """Input parameters for ``trip.update``."""

    model_config = {"extra": "forbid"}

    trip_id: int = Field(..., gt=0, description="Trip ID to update")
    client_id: Optional[int] = Field(None, gt=0, description="Client ID")
    truck_id: Optional[int] = Field(None, description="Truck ID to assign")
    driver_id: Optional[int] = Field(None, description="Driver ID to assign")
    reference: Optional[str] = Field(None, description="Trip reference number")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    price_eur: Optional[float] = Field(None, ge=0, description="Trip price in EUR")
    currency: Optional[str] = Field(None, description="Currency code (e.g. EUR)")
    distance_km: Optional[float] = Field(None, gt=0, description="Distance in km")
    notes: Optional[str] = Field(None, description="Trip notes")
    status: Optional[str] = Field(None, description="Trip status (e.g. Planned, In Progress, Completed)")
    loading_city: Optional[str] = Field(None, description="Loading/pickup city")
    delivery_city: Optional[str] = Field(None, description="Delivery city")
    loading_country: Optional[str] = Field(None, description="Loading country")
    delivery_country: Optional[str] = Field(None, description="Delivery country")


# ── trip.create (Level 2) ──────────────────────────────────────────────────


@register_tool
class TripCreateTool(BaseTool):
    """Create a new trip.

    Wraps ``TripService.create(request, user_id)`` with a typed
    ``TripCreate`` model.  Requires ``trips:write`` permission and
    user confirmation.
    """

    name = "trip.create"
    tool_version = "1.0.0"
    description = (
        "Create a new trip for a client with loading/delivery details"
    )
    required_permission = "trips:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = TripCreateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> TripCreateParams:
        assert isinstance(params, TripCreateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.client_id <= 0:
            errors.append("client_id must be a positive integer")
        if not p.loading_city.strip():
            errors.append("loading_city is required")
        if not p.delivery_city.strip():
            errors.append("delivery_city is required")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.common import ServiceResult
            from models.trip_models import TripCreate, TripResult
            from backend.services.trip_service import TripService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            request = TripCreate(
                client_id=p.client_id,
                route_id=p.route_id,
                truck_id=p.truck_id,
                start_date=date.today(),
                # Store loading/delivery info in notes since TripCreate does
                # not have dedicated fields for them
                notes=(
                    f"Loading: {p.loading_city}"
                    f"{', ' + p.loading_country if p.loading_country else ''}"
                    f" | Delivery: {p.delivery_city}"
                    f"{', ' + p.delivery_country if p.delivery_country else ''}"
                ),
            )

            svc = TripService(db)
            result: ServiceResult[TripResult] = svc.create(  # type: ignore[assignment]
                request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            trip = result.data
            if trip is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": "Trip created but no data returned"},
                )
            return ToolResult(
                status="success",
                data={
                    "trip_id": trip.id,
                },
                message_key="copilot.trip.create.success",
                message_params={"trip_id": trip.id},
            )

        except Exception as exc:
            logger.exception("trip.create failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ── trip.update (Level 2) ──────────────────────────────────────────────────


@register_tool
class TripUpdateTool(BaseTool):
    """Update an existing trip.

    Wraps ``TripService.update(trip_id, request, user_id)`` with a typed
    ``TripUpdate`` model.  Only fields that are explicitly provided will be
    changed.
    """

    name = "trip.update"
    tool_version = "1.0.0"
    description = (
        "Update an existing trip's details including client, route, truck, "
        "driver, pricing, and status"
    )
    required_permission = "trips:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = TripUpdateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> TripUpdateParams:
        assert isinstance(params, TripUpdateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.trip_id <= 0:
            errors.append("trip_id must be a positive integer")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.common import ServiceResult
            from models.trip_models import TripResult, TripUpdate
            from backend.services.trip_service import TripService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            # Build TripUpdate with only the fields that were explicitly set
            request = TripUpdate(
                client_id=p.client_id,
                truck_id=p.truck_id,
                driver_id=p.driver_id,
                reference=p.reference,
                start_date=date.fromisoformat(p.start_date) if p.start_date is not None else None,
                end_date=date.fromisoformat(p.end_date) if p.end_date is not None else None,
                price_eur=p.price_eur,
                currency=p.currency,
                distance_km=p.distance_km,
                notes=p.notes,
                status=p.status,
            )

            # Append loading/delivery info to notes if provided
            location_parts: list[str] = []
            if p.loading_city is not None:
                location_parts.append(f"Loading: {p.loading_city}")
                if p.loading_country:
                    location_parts[-1] += f", {p.loading_country}"
            if p.delivery_city is not None:
                location_parts.append(f"Delivery: {p.delivery_city}")
                if p.delivery_country:
                    location_parts[-1] += f", {p.delivery_country}"
            if location_parts:
                loc_note = " | ".join(location_parts)
                if request.notes:
                    request.notes = f"{request.notes}\n{loc_note}"
                else:
                    request.notes = loc_note

            svc = TripService(db)
            result: ServiceResult[TripResult] = svc.update(  # type: ignore[assignment]
                p.trip_id, request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            trip = result.data
            return ToolResult(
                status="success",
                data={
                    "trip_id": trip.id if trip else p.trip_id,
                },
                message_key="copilot.trip.update.success",
                message_params={"trip_id": p.trip_id},
            )

        except ValueError as exc:
            # Covers date parsing errors
            return ToolResult(
                status="failed",
                message_key="copilot.error.invalid_parameter",
                message_params={"error": str(exc)},
            )
        except Exception as exc:
            logger.exception("trip.update failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )
