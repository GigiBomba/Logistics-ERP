from pydantic import BaseModel, Field, field_validator
from typing import Optional
from .common import ServiceResult


class CostEstimateRequest(BaseModel):
    distance_km: float
    truck_id: Optional[int] = None
    fuel_type: str = "diesel"
    consumption_l_per_100km: Optional[float] = None
    fuel_price_per_liter: Optional[float] = None
    toll_cost_eur: float = 0.0
    driver_daily_rate: float = 0.0
    days: float = 1.0
    extra_costs: dict[str, float] = {}
    currency: str = "EUR"

    @field_validator("distance_km")
    @classmethod
    def distance_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Distance must be positive")
        return v


class CostBreakdown(BaseModel):
    fuel_cost: float
    toll_cost: float
    driver_cost: float
    extra_costs: dict[str, float] = {}
    total_cost: float
    cost_per_km: float
    currency: str


class CostEstimateResult(BaseModel):
    distance_km: float
    days: float
    breakdown: CostBreakdown
    truck_info: str = ""


CostEstimateOperationResult = ServiceResult[CostEstimateResult]
