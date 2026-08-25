from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict
from datetime import date


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: Dict[str, Any]
    cached: bool = False


class FinancialSummary(BaseModel):
    total_revenue: float = 0.0
    total_cost: float = 0.0
    total_profit: float = 0.0
    margin_pct: float = 0.0
    trip_count: int = 0
    invoice_count: int = 0
    average_trip_revenue: float = 0.0
    currency: str = "EUR"
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    model_config = ConfigDict(extra="ignore")


class MonthlyDataPoint(BaseModel):
    month: str  # "2026-07"
    revenue: float = 0.0
    cost: float = 0.0
    profit: float = 0.0
    trip_count: int = 0
    model_config = ConfigDict(extra="ignore")


class MonthlyFinancialResponse(BaseModel):
    data: List[MonthlyDataPoint] = []
    total: FinancialSummary = FinancialSummary()
    model_config = ConfigDict(extra="ignore")


class CostBreakdown(BaseModel):
    fuel_cost: float = 0.0
    toll_cost: float = 0.0
    salary_cost: float = 0.0
    maintenance_cost: float = 0.0
    other_costs: float = 0.0
    total_cost: float = 0.0
    model_config = ConfigDict(extra="ignore")


class TripStatusBreakdown(BaseModel):
    status: str
    count: int = 0
    percentage: float = 0.0
    model_config = ConfigDict(extra="ignore")


class ClientRevenueItem(BaseModel):
    client_id: int
    client_name: str
    total_revenue: float = 0.0
    trip_count: int = 0
    percentage: float = 0.0
    model_config = ConfigDict(extra="ignore")


class ClientRevenueResponse(BaseModel):
    data: List[ClientRevenueItem] = []
    total_revenue: float = 0.0
    model_config = ConfigDict(extra="ignore")


class FleetUtilizationItem(BaseModel):
    vehicle_id: int
    plate: str
    trip_count: int = 0
    distance_km: float = 0.0
    revenue: float = 0.0
    utilization_pct: float = 0.0
    model_config = ConfigDict(extra="ignore")


class RouteProfitabilityItem(BaseModel):
    route_id: Optional[int] = None
    origin: str = ""
    destination: str = ""
    distance_km: float = 0.0
    revenue: float = 0.0
    cost: float = 0.0
    profit: float = 0.0
    margin_pct: float = 0.0
    model_config = ConfigDict(extra="ignore")


class DriverComparisonItem(BaseModel):
    driver_id: int
    driver_name: str
    trip_count: int = 0
    distance_km: float = 0.0
    revenue: float = 0.0
    profit: float = 0.0
    profit_per_km: float = 0.0
    model_config = ConfigDict(extra="ignore")


class AlertSummary(BaseModel):
    total: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    model_config = ConfigDict(extra="ignore")


class AnalyticsOverview(BaseModel):
    financial: FinancialSummary = FinancialSummary()
    active_trips: int = 0
    active_vehicles: int = 0
    overdue_invoices: int = 0
    overdue_amount: float = 0.0
    alerts: AlertSummary = AlertSummary()
    model_config = ConfigDict(extra="ignore")


class MaintenanceAlertItem(BaseModel):
    vehicle_id: int
    plate: str
    alert_type: str
    description: str
    due_date: Optional[str] = None
    severity: str = "info"
    model_config = ConfigDict(extra="ignore")
