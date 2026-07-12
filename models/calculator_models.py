from pydantic import BaseModel, Field, field_validator
from typing import Optional
from .common import ServiceResult


class CalculationRequest(BaseModel):
    km: float
    price_eur: float
    fuel_price: float
    days: float = 1.0
    consum_litri: float  # consumption in liters per 100km
    extra_in: Optional[float] = None  # extra income (None = use default formula)
    sal_in: float = 0.0  # salary included
    taxa_in: float = 0.0  # tax included
    fuel_cost_override: Optional[float] = None  # pre-calculated fuel cost from route planner

    @field_validator("km")
    @classmethod
    def km_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Distance (km) must be positive")
        return v

    @field_validator("price_eur")
    @classmethod
    def price_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Price cannot be negative")
        return v

    @field_validator("fuel_price")
    @classmethod
    def fuel_price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Fuel price must be positive")
        return v

    @field_validator("days")
    @classmethod
    def days_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Days must be positive")
        return v

    @field_validator("consum_litri")
    @classmethod
    def consumption_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Consumption must be positive")
        return v


class TripCalculationResult(BaseModel):
    km: float
    price_eur: float
    fuel_price: float
    days: float
    consum_litri: float
    extra_in: float = 0.0
    sal_in: float = 0.0
    taxa_in: float = 0.0
    total_income: float
    fuel_consumed_liters: float
    fuel_cost: float
    toll_cost: float = 0.0
    salary_cost: float = 0.0
    extra_costs: float = 0.0
    net_profit: float
    profit_per_km: float
    gross_per_km: float = 0.0
    margin_percent: float
    cost_per_km: float
    currency: str = "EUR"


CalculationOperationResult = ServiceResult[TripCalculationResult]
