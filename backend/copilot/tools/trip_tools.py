"""Co-Pilot tools for the Trip domain — profitability calculations.

Level-0 tools wrapping TripCalculator for AI-driven trip analysis.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from repositories.trip_repository import TripRepository
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


# ────────────────────────────────────────────────────────────────────────────
# trip.list / trip.get (§9.1 Level-0 read tools)
# ────────────────────────────────────────────────────────────────────────────


class TripListParams(BaseModel):
    """Input parameters for ``trip.list`` (§9.1 Level-0)."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(50, ge=1, le=200, description="Max trips to return")
    offset: int = Field(0, ge=0, description="Pagination offset")


class TripGetParams(BaseModel):
    """Input parameters for ``trip.get`` (§9.1 Level-0)."""

    model_config = ConfigDict(extra="forbid")

    trip_id: int = Field(..., gt=0, description="Trip ID to fetch")


def _scoped_trip_repo_call(db, scope_company_id, method_name: str, *args, **kwargs):
    """Run a TripRepository method scoped to *scope_company_id* via the tenant context."""
    from database.tenant_context import get_company_id, set_company_context

    prev = get_company_id()
    set_company_context(scope_company_id)
    try:
        return getattr(TripRepository(db), method_name)(*args, **kwargs)
    finally:
        set_company_context(prev)


@register_tool
class TripListTool(BaseTool):
    """List recent trips for the company."""

    name = "trip.list"
    tool_version = "1.0.0"
    description = (
        "List the most recent trips for the company — status, dates, "
        "client, truck and profitability fields."
    )
    required_permission = "trips:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    deprecated = False
    parameters_schema = TripListParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: TripListParams = params  # type: ignore[assignment]
        db = ctx.services.get("db")
        if db is None:
            return ToolResult(
                status="unavailable",
                message_key="copilot.error.no_db",
                message_params={"tool": self.name},
            )
        try:
            company_id = ctx.services.get("company_id", 0)
            rows = _scoped_trip_repo_call(db, company_id, "get_all", limit=p.limit, offset=p.offset)
            rows = rows or []
            return ToolResult(
                status="success",
                data={"trips": rows, "total": len(rows)},
                message_key="copilot.trip.list.success",
                message_params={"total": len(rows)},
            )
        except Exception as exc:
            logger.exception("trip.list failed")
            return ToolResult(
                status="failed",
                message_key="copilot.trip.list.error",
                message_params={"error": str(exc)},
            )


@register_tool
class TripGetTool(BaseTool):
    """Fetch one trip by id."""

    name = "trip.get"
    tool_version = "1.0.0"
    description = (
        "Fetch a single trip by its id — status, dates, client, truck and "
        "profitability fields."
    )
    required_permission = "trips:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    deprecated = False
    parameters_schema = TripGetParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: TripGetParams = params  # type: ignore[assignment]
        db = ctx.services.get("db")
        if db is None:
            return ToolResult(
                status="unavailable",
                message_key="copilot.error.no_db",
                message_params={"tool": self.name},
            )
        try:
            company_id = ctx.services.get("company_id", 0)
            row = _scoped_trip_repo_call(db, company_id, "get_by_id", p.trip_id, company_id=company_id)
            if not row:
                return ToolResult(
                    status="failed",
                    message_key="copilot.trip.not_found",
                    message_params={"trip_id": p.trip_id},
                )
            return ToolResult(
                status="success",
                data={"trip": row},
                message_key="copilot.trip.get.success",
                message_params={"trip_id": p.trip_id},
            )
        except Exception as exc:
            logger.exception("trip.get failed")
            return ToolResult(
                status="failed",
                message_key="copilot.trip.get.error",
                message_params={"error": str(exc)},
            )


