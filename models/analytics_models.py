from __future__ import annotations

from pydantic import BaseModel
from typing import Optional
from datetime import date
from .common import ServiceResult


class AnalyticsRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    client_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    group_by: str = "month"  # day, week, month, quarter, year


class RevenueReport(BaseModel):
    total_revenue: float
    total_cost: float
    total_profit: float
    margin_pct: float
    trip_count: int
    invoice_count: int
    average_trip_revenue: float
    currency: str = "EUR"


class OverdueReport(BaseModel):
    total_overdue: float
    overdue_count: int
    average_days_late: float
    items: list[dict] = []  # {invoice_number, client_name, amount, days_late, alert_level}


class KpiDashboard(BaseModel):
    revenue: RevenueReport
    overdue: OverdueReport
    active_trips: int
    active_vehicles: int
    total_distance_km: float
    total_fuel_liters: float
    period: tuple[date, date]
    generated_at: date


AnalyticsReportResult = ServiceResult[KpiDashboard]
