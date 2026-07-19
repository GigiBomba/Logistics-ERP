"""Co-Pilot tools for the Trip domain — profitability calculations.

Level-0 tools wrapping TripCalculator for AI-driven trip analysis.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from services.calculator import TripCalculator

logger = logging.getLogger(__name__)


class CalculateProfitabilityParams(BaseModel):
    """Input parameters for trip.calculate_profitability."""

    km: float = Field(..., gt=0, description="Distance in kilometres")
    price_eur: float = Field(..., ge=0, description="Trip price in EUR")
    fuel_price: float = Field(..., gt=0, description="Fuel price per litre")
    days: int = Field(..., gt=0, description="Number of days for the trip")
    consum_litri: float = Field(
        ..., gt=0, description="Fuel consumption in litres per 100 km"
    )
    truck_id: Optional[int] = Field(
        None,
        description=(
            "Truck ID for automatic fuel consumption lookup. "
            "When provided, ``consum_litri`` is ignored and the truck's "
            "stored consumption is used instead."
        ),
    )


@register_tool
class CalculateProfitabilityTool(BaseTool):
    """Calculate trip profitability.

    Wraps ``TripCalculator`` — the canonical service for trip cost
    and profit analysis.

    Uses ``TripCalculator.calculate_raw()`` with the caller-supplied
    consumption.  If a *truck_id* is supplied it is ignored (the estimate
    path was removed to comply with the Level‑0 read-only invariant).
    """

    name = "trip.calculate_profitability"
    tool_version = "1.0.0"
    description = (
        "Calculate trip profitability including net profit, fuel cost, "
        "toll cost, salary cost, extra costs, profit per km, and margin percentage"
    )
    required_permission = "trips:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    deprecated = False
    parameters_schema = CalculateProfitabilityParams

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        params = self._assert_params(params)
        errors: list[str] = []
        if params.km <= 0:
            errors.append("Distance (km) must be positive")
        if params.price_eur < 0:
            errors.append("Price cannot be negative")
        if params.fuel_price <= 0:
            errors.append("Fuel price must be positive")
        if params.days <= 0:
            errors.append("Days must be positive")
        if params.consum_litri <= 0:
            errors.append("Consumption must be positive")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            # ── Basic path (raw calculation) ────────────────────────────
            return await self._execute_basic(p)

        except Exception as exc:
            logger.exception("trip.calculate_profitability failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> CalculateProfitabilityParams:
        assert isinstance(params, CalculateProfitabilityParams)
        return params

    async def _execute_basic(
        self,
        params: CalculateProfitabilityParams,
    ) -> ToolResult:
        """Run a raw calculation without truck lookup."""
        raw = TripCalculator.calculate_raw(  # type: ignore[call-arg]
            km=params.km,
            price_eur=params.price_eur,
            fuel_price=params.fuel_price,
            days=float(params.days),
            consum_litri=params.consum_litri,
        )
        return ToolResult(
            status="success",
            data={
                "net_profit": raw.net_profit,
                "fuel_cost": raw.fuel_cost,
                "toll_cost": raw.toll_cost,
                "salary_cost": raw.salary_cost,
                "extra_costs": raw.extra_costs,
                "profit_per_km": raw.rate_per_km,
                "margin_percent": raw.margin_percent,
            },
            message_key="copilot.trip.calculate_profitability.success",
            message_params={},
        )


