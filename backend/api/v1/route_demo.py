"""Public route demo endpoint — no auth required."""
from __future__ import annotations

import math
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/route-demo", tags=["route-demo"])

# ─── Cost constants ───
FUEL_PRICE = 1.65
CONSUMPTION_L_PER_100KM = 32
DRIVER_SALARY_PER_DAY = 100
TOLL_RATE_PER_KM = 0.22
EXTRA_COST_PER_KM = 0.03
EXTRA_COST_PER_DAY = 12
REVENUE_PER_KM = 1.5


def _calculate_costs(distance_km: float, duration_min: float) -> Dict[str, Any]:
    """Compute all cost metrics from route distance and duration."""
    hours = duration_min / 60.0
    days = max(1, math.ceil(hours / 9))

    fuel_cost = (distance_km / 100) * CONSUMPTION_L_PER_100KM * FUEL_PRICE
    toll_cost = distance_km * TOLL_RATE_PER_KM
    salary_cost = days * DRIVER_SALARY_PER_DAY
    extra_costs = distance_km * EXTRA_COST_PER_KM + days * EXTRA_COST_PER_DAY
    total_cost = fuel_cost + toll_cost + salary_cost + extra_costs
    profit = distance_km * REVENUE_PER_KM - total_cost

    return {
        "distance_km": round(distance_km, 1),
        "duration_hours": round(hours, 1),
        "fuelCost": round(fuel_cost),
        "tollCost": round(toll_cost),
        "salaryCost": salary_cost,
        "extraCosts": round(extra_costs),
        "totalCost": round(total_cost),
        "profit": round(profit),
    }


@router.post("/calculate")
def calculate_route_demo(data: Dict[str, Any]):
    origin = data.get("origin", "").strip()
    destination = data.get("destination", "").strip()

    if not origin or not destination:
        raise HTTPException(status_code=400, detail="origin and destination are required")

    # Geocode both cities
    from services.geocode_nominatim import geocode_place

    try:
        origin_coords = geocode_place(origin, timeout=15)
        if not origin_coords:
            raise HTTPException(status_code=400, detail=f"Could not geocode origin: {origin}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Geocoding failed for origin '{origin}': {exc}") from exc

    try:
        dest_coords = geocode_place(destination, timeout=15)
        if not dest_coords:
            raise HTTPException(status_code=400, detail=f"Could not geocode destination: {destination}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Geocoding failed for destination '{destination}': {exc}") from exc

    points = [origin_coords, dest_coords]

    # Route with both profiles
    from backend.services.route_service import GraphHopperClient

    gh_client = GraphHopperClient()

    try:
        standard_result = gh_client.route(points, profile="truck")
        standard_costs = _calculate_costs(
            standard_result["distance_km"],
            standard_result["duration_min"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Route calculation (standard) failed: {exc}") from exc

    try:
        optimized_result = gh_client.route(points, profile="truck_fast")
        optimized_costs = _calculate_costs(
            optimized_result["distance_km"],
            optimized_result["duration_min"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Route calculation (optimized) failed: {exc}") from exc

    return {
        "standard": standard_costs,
        "optimized": optimized_costs,
    }
