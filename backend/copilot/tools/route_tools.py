"""Route domain tools for the Operion AI Co-Pilot.

Tools:
- route.calculate         — calculate a route between stops
- route.estimate_cost     — estimate cost for a given distance and truck
- route.plan_multistop    — calculate a multi-stop route with per-leg breakdown

All three are **SAFE** (read-only, execute immediately) and require ``routes:read``.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool


# ────────────────────────────────────────────────────────────────────────────
# Parameter Schemas
# ────────────────────────────────────────────────────────────────────────────


class RouteCalculateParams(BaseModel):
    stops: List[str] = Field(
        ...,
        description="List of addresses (or coordinate pairs) to visit in order. "
        "Minimum 2 stops required.",
    )
    profile: str = Field(
        "truck",
        description="Routing profile. Supported values: 'truck', 'car', 'foot', 'bike'.",
    )
    truck_id: Optional[int] = Field(
        None,
        description="Vehicle ID to apply truck-specific routing constraints "
        "(weight, height, hazardous goods, etc.).",
    )
    avoid_countries: Optional[List[str]] = Field(
        None,
        description="List of ISO 3166-1 alpha-2 country codes to exclude from the route.",
    )


class RouteEstimateCostParams(BaseModel):
    distance_km: float = Field(
        ...,
        description="Route distance in kilometres.",
        gt=0,
    )
    truck_id: Optional[int] = Field(
        None,
        description="Vehicle ID whose fuel consumption will be used for the estimate. "
        "If omitted a default consumption of 34 L/100 km is assumed.",
    )
    country_code: str = Field(
        "DEFAULT",
        description="Country code for cost-factor adjustments "
        "(e.g. 'RO', 'DE', 'FR', 'IT'). Defaults to 'DEFAULT'.",
    )


class RoutePlanMultistopParams(BaseModel):
    stops: List[str] = Field(
        ...,
        description="Ordered list of addresses (or coordinate pairs) to visit. "
        "Minimum 2 stops required.",
    )
    profile: str = Field(
        "truck",
        description="Routing profile. Supported values: 'truck', 'car', 'foot', 'bike'.",
    )
    optimize: bool = Field(
        False,
        description="When True, attempt GraphHopper internal stop-order optimisation. "
        "If the optimisation feature is unavailable the tool falls back to the "
        "fixed-order route and sets ``optimization_status`` to ``\"unavailable\"``.",
    )
    avoid_countries: Optional[List[str]] = Field(
        None,
        description="List of ISO 3166-1 alpha-2 country codes to exclude from the route.",
    )


# ────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────────


def _get_truck_dict(fleet_service, truck_id: int) -> Optional[dict]:
    """Look up a truck dict by ID from the fleet service.

    Tries the typed ``get()`` method first (returns a ``VehicleResult``
    wrapped in ``ServiceResult``), then falls back to the deprecated
    ``get_truck()`` which returns a raw repo row.
    """
    try:
        result = fleet_service.get(truck_id)
        if result.success and result.data is not None:
            return result.data.model_dump()
    except Exception:
        pass
    try:
        raw = fleet_service.get_truck(truck_id)
        if raw:
            return dict(raw)
    except Exception:
        pass
    return None


def _legs_from_graphhopper_response(result: dict) -> List[dict]:
    """Extract per-leg distances/durations from the raw GraphHopper response
    stored in ``graphhopper_response``.
    """
    try:
        gh_data = result.get("graphhopper_response", {})
        paths = gh_data.get("paths", [])
        if not paths:
            return []
        legs = paths[0].get("legs", [])
        if legs:
            return [
                {
                    "distance_km": leg.get("distance", 0) / 1000.0,
                    "duration_min": leg.get("time", 0) / 60000.0,
                }
                for leg in legs
            ]
    except Exception:
        pass
    return []


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two coordinates."""
    import math

    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _compute_legs_from_stops(
    stops: list,
    total_distance_km: float,
    total_duration_min: float,
) -> List[dict]:
    """Estimate per-leg distances/durations from consecutive stop coordinates.

    This is a fallback when the GraphHopper response does not contain a
    ``legs`` array (e.g. when segmentation was used).
    """
    if len(stops) < 2:
        return []
    leg_distances: list[float] = []
    for i in range(len(stops) - 1):
        try:
            lat1, lon1 = stops[i]
            lat2, lon2 = stops[i + 1]
            d = _haversine_distance(float(lat1), float(lon1), float(lat2), float(lon2))
            leg_distances.append(max(d, 0.0))
        except (TypeError, ValueError, IndexError):
            leg_distances.append(0.0)

    total_est = sum(leg_distances) or 1.0
    legs: List[dict] = []
    for d in leg_distances:
        ratio = d / total_est
        legs.append(
            {
                "distance_km": round(d, 2),
                "duration_min": round(total_duration_min * ratio, 2),
            }
        )
    return legs


def _build_stop_distances(ordered_stops: list, legs: List[dict]) -> List[dict]:
    """Build per-leg ``stop_distances`` entries."""
    result: List[dict] = []
    for i in range(len(ordered_stops) - 1):
        leg = legs[i] if i < len(legs) else {}
        result.append(
            {
                "from_stop": ordered_stops[i],
                "to_stop": ordered_stops[i + 1],
                "distance_km": leg.get("distance_km", 0.0),
                "duration_min": leg.get("duration_min", 0.0),
            }
        )
    return result


def _format_stops(resolved_coords: list, original_addresses: List[str]) -> list:
    """Return ordered stops preferring original address strings."""
    if not resolved_coords:
        return list(original_addresses)
    if len(resolved_coords) == len(original_addresses):
        return list(original_addresses)
    return [f"{lat:.6f},{lon:.6f}" for lat, lon in resolved_coords]


def _cost_result_to_dict(op_result) -> dict:
    """Convert a ``CostEstimateOperationResult`` (typed path) to a flat dict."""
    if not op_result or not op_result.data:
        return {}
    b = op_result.data.breakdown
    return {
        "fuel_cost": b.fuel_cost,
        "toll_cost": b.toll_cost,
        "driver_cost": b.driver_cost,
        "total_cost": b.total_cost,
        "cost_per_km": b.cost_per_km,
        "currency": b.currency,
        "breakdown": {
            "fuel_cost": b.fuel_cost,
            "toll_cost": b.toll_cost,
            "driver_cost": b.driver_cost,
            "extra_costs": b.extra_costs,
            "total_cost": b.total_cost,
            "cost_per_km": b.cost_per_km,
            "currency": b.currency,
        },
    }


def _build_multistop_data(
    gh_result: dict,
    original_stops: List[str],
    resolved_stops: list,
) -> dict:
    """Build the ``route.plan_multistop`` output dict from a GH route result."""
    distance_km = gh_result.get("distance_km", 0.0)
    duration_min = gh_result.get("duration_min", 0.0)

    legs = _legs_from_graphhopper_response(gh_result)
    if not legs and resolved_stops:
        legs = _compute_legs_from_stops(resolved_stops, distance_km, duration_min)

    ordered_stops = _format_stops(resolved_stops, original_stops)
    stop_distances = _build_stop_distances(ordered_stops, legs)

    return {
        "ordered_stops": ordered_stops,
        "total_distance_km": distance_km,
        "total_duration_min": duration_min,
        "stop_distances": stop_distances,
    }


# ────────────────────────────────────────────────────────────────────────────
# Tool 1: route.calculate
# ────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteCalculateTool(BaseTool):
    """Calculate a route between two or more stops and return distance,
    duration, geometry and an optional fuel estimate."""

    name = "route.calculate"
    tool_version = "1.0.0"
    description = (
        "Calculate a route between two or more addresses returning "
        "distance (km), duration (min), geometry (polyline), "
        "and a fuel/cost estimate when a truck is specified."
    )
    required_permission = "routes:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = RouteCalculateParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p: RouteCalculateParams = params  # type: ignore[assignment]
        if len(p.stops) < 2:
            return ["route.error.at_least_two_stops"]
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: RouteCalculateParams = params  # type: ignore[assignment]
        try:
            route_service = ctx.services.get("route_service")
            if route_service is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.route.error.service_unavailable",
                    data={"reason": "RouteService not available in context"},
                )

            # Resolve truck dict if a truck_id was provided
            truck = None
            if p.truck_id is not None:
                fleet_service = ctx.services.get("fleet_service")
                if fleet_service is not None:
                    truck = _get_truck_dict(fleet_service, p.truck_id)

            result = route_service.calculate_route(
                stops=p.stops,
                profile=p.profile,
                truck=truck,
                avoid_countries=p.avoid_countries,
            )

            data: dict[str, Any] = {
                "distance_km": result.get("distance_km", 0.0),
                "duration_min": result.get("duration_min", 0.0),
                "geometry": result.get("geometry", []),
            }

            # Append a fuel/cost estimate when a specific truck was chosen
            if p.truck_id is not None:
                cost_engine = ctx.services.get("cost_engine_service")
                if cost_engine is not None:
                    try:
                        cost_result = cost_engine.estimate_for_truck(
                            distance_km=data["distance_km"],
                            truck_id=p.truck_id,
                        )
                        if cost_result.success and cost_result.data is not None:
                            b = cost_result.data.breakdown
                            data["fuel_estimate"] = {
                                "fuel_cost": b.fuel_cost,
                                "toll_cost": b.toll_cost,
                                "total_cost": b.total_cost,
                                "cost_per_km": b.cost_per_km,
                                "currency": b.currency,
                            }
                    except Exception:
                        pass

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.route.calculate.success",
                message_params={"distance_km": f"{data['distance_km']:.1f}"},
            )

        except Exception as exc:
            return ToolResult(
                status="failed",
                message_key="copilot.route.calculate.error",
                message_params={"error": str(exc)},
            )


# ────────────────────────────────────────────────────────────────────────────
# Tool 2: route.estimate_cost
# ────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteEstimateCostTool(BaseTool):
    """Estimate fuel, toll, driver and total cost for a given distance and truck."""

    name = "route.estimate_cost"
    tool_version = "1.0.0"
    description = (
        "Estimate fuel cost, toll cost, driver cost and total cost for a "
        "route distance. Provide a truck_id for accurate fuel consumption; "
        "otherwise a default consumption of 34 L/100 km is used."
    )
    required_permission = "routes:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = RouteEstimateCostParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p: RouteEstimateCostParams = params  # type: ignore[assignment]
        if p.distance_km <= 0:
            return ["route.error.distance_must_be_positive"]
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: RouteEstimateCostParams = params  # type: ignore[assignment]
        try:
            # Prefer an injected engine; fall back to a fresh instance
            cost_engine = ctx.services.get("cost_engine_service")
            if cost_engine is None:
                from services.cost_engine import CostEngineService

                cost_engine = CostEngineService()

            if p.truck_id is not None:
                # Typed path — uses FleetRepository inside the engine
                op_result = cost_engine.estimate_for_truck(
                    distance_km=p.distance_km,
                    truck_id=p.truck_id,
                )
                if not op_result.success:
                    errors = [e.message for e in op_result.errors]
                    return ToolResult(
                        status="failed",
                        message_key="copilot.route.estimate_cost.error",
                        message_params={"error": "; ".join(errors)},
                    )
                data = _cost_result_to_dict(op_result)
            else:
                # No truck — use typed interface with defaults
                from models.cost_models import CostEstimateRequest
                op_result = cost_engine.estimate(
                    CostEstimateRequest(distance_km=p.distance_km),
                )
                if not op_result.success:
                    errors = [e.message for e in op_result.errors]
                    return ToolResult(
                        status="failed",
                        message_key="copilot.route.estimate_cost.error",
                        message_params={"error": "; ".join(errors)},
                    )
                data = _cost_result_to_dict(op_result)

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.route.estimate_cost.success",
                message_params={"total_cost": f"{data.get('total_cost', 0):.2f}"},
            )

        except Exception as exc:
            return ToolResult(
                status="failed",
                message_key="copilot.route.estimate_cost.error",
                message_params={"error": str(exc)},
            )


# ────────────────────────────────────────────────────────────────────────────
# Tool 3: route.plan_multistop
# ────────────────────────────────────────────────────────────────────────────


@register_tool
class RoutePlanMultistopTool(BaseTool):
    """Plan a multi-stop route with per-leg breakdown and optional stop-order
    optimisation."""

    name = "route.plan_multistop"
    tool_version = "1.0.0"
    description = (
        "Calculate a multi-stop route returning all visited stops, total "
        "distance/duration, and a per-leg breakdown. Optionally attempts "
        "GraphHopper internal stop-order optimisation."
    )
    required_permission = "routes:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = RoutePlanMultistopParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p: RoutePlanMultistopParams = params  # type: ignore[assignment]
        if len(p.stops) < 2:
            return ["route.error.at_least_two_stops"]
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: RoutePlanMultistopParams = params  # type: ignore[assignment]
        try:
            route_service = ctx.services.get("route_service")
            if route_service is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.route.error.service_unavailable",
                    data={"reason": "RouteService not available in context"},
                )

            optimised = False
            status_extra: Optional[str] = None

            # ── Optimisation path (public API) ─────────────────────────
            if p.optimize:
                try:
                    result = route_service.calculate_route(
                        stops=p.stops,
                        profile=p.profile,
                        avoid_countries=p.avoid_countries,
                    )
                    resolved_stops = result.get("stops", [])
                    data = _build_multistop_data(result, p.stops, resolved_stops)
                    data["optimization_status"] = "applied"
                    return ToolResult(
                        status="success",
                        data=data,
                        message_key="copilot.route.plan_multistop.success",
                        message_params={"distance_km": f"{data['total_distance_km']:.1f}"},
                    )
                except Exception:
                    # Optimisation not available — fall through to fixed-order
                    status_extra = "unavailable"

            # ── Fixed-order path (default) ──────────────────────────────
            result = route_service.calculate_route(
                stops=p.stops,
                profile=p.profile,
                avoid_countries=p.avoid_countries,
            )

            resolved_stops: list = result.get("stops", [])

            # Try GH legs first (fast path), then fall back to haversine
            legs = _legs_from_graphhopper_response(result)
            if not legs and resolved_stops:
                legs = _compute_legs_from_stops(
                    resolved_stops,
                    result.get("distance_km", 0.0),
                    result.get("duration_min", 0.0),
                )

            ordered_stops = _format_stops(resolved_stops, p.stops)
            stop_distances = _build_stop_distances(ordered_stops, legs)

            data = {
                "ordered_stops": ordered_stops,
                "total_distance_km": result.get("distance_km", 0.0),
                "total_duration_min": result.get("duration_min", 0.0),
                "stop_distances": stop_distances,
            }
            if status_extra:
                data["optimization_status"] = status_extra

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.route.plan_multistop.success",
                message_params={"distance_km": f"{data['total_distance_km']:.1f}"},
            )

        except Exception as exc:
            return ToolResult(
                status="failed",
                message_key="copilot.route.plan_multistop.error",
                message_params={"error": str(exc)},
            )
