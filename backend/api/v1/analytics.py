from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_analytics_service
from backend.dependencies_security import require_dispatcher
from backend.schemas.analytics import (
    AlertSummary,
    AnalyticsOverview,
    ClientRevenueItem,
    ClientRevenueResponse,
    CostBreakdown,
    DriverComparisonItem,
    FinancialSummary,
    FleetUtilizationItem,
    MaintenanceAlertItem,
    MonthlyDataPoint,
    MonthlyFinancialResponse,
    RouteProfitabilityItem,
    TripStatusBreakdown,
)
from backend.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/financial", response_model=FinancialSummary)
def get_financial_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> FinancialSummary:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_financial(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return FinancialSummary()
    if isinstance(result, dict):
        return FinancialSummary(**result)
    if isinstance(result, list) and result:
        rev = sum(r.get("revenue", 0) for r in result if isinstance(r, dict))
        prof = sum(r.get("profit", 0) for r in result if isinstance(r, dict))
        trips = sum(r.get("trip_count", 0) for r in result if isinstance(r, dict))
        return FinancialSummary(
            total_revenue=rev,
            total_profit=prof,
            total_cost=rev - prof,
            margin_pct=(prof / rev * 100) if rev else 0.0,
            trip_count=trips,
        )
    return FinancialSummary()


@router.get("/financial/monthly", response_model=MonthlyFinancialResponse)
def get_monthly_financial(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(24, ge=1, le=60),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> MonthlyFinancialResponse:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_monthly_financial(company_id=company_id, months=months, from_date=start, to_date=end)
    if not result:
        return MonthlyFinancialResponse()
    data = [MonthlyDataPoint(**r) if isinstance(r, dict) else MonthlyDataPoint() for r in result]
    total_rev = sum(d.revenue for d in data)
    total_cost = sum(d.cost for d in data)
    total_profit = sum(d.profit for d in data)
    total_trips = sum(d.trip_count for d in data)
    total = FinancialSummary(
        total_revenue=total_rev,
        total_cost=total_cost,
        total_profit=total_profit,
        margin_pct=(total_profit / total_rev * 100) if total_rev else 0.0,
        trip_count=total_trips,
    )
    return MonthlyFinancialResponse(data=data, total=total)


@router.get("/financial/cost-breakdown", response_model=CostBreakdown)
def get_cost_breakdown(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> CostBreakdown:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_cost_breakdown(company_id=company_id, months=months, from_date=start, to_date=end)
    if not result:
        return CostBreakdown()
    if isinstance(result, dict):
        return CostBreakdown(**result)
    if isinstance(result, list) and result:
        fuel = sum(r.get("fuel_cost", 0) for r in result if isinstance(r, dict))
        toll = sum(r.get("toll_cost", 0) for r in result if isinstance(r, dict))
        salary = sum(r.get("salary_cost", 0) for r in result if isinstance(r, dict))
        other = sum(r.get("extra_costs", 0) for r in result if isinstance(r, dict))
        return CostBreakdown(
            fuel_cost=fuel,
            toll_cost=toll,
            salary_cost=salary,
            other_costs=other,
            total_cost=fuel + toll + salary + other,
        )
    return CostBreakdown()


@router.get("/financial/trip-status", response_model=List[TripStatusBreakdown])
def get_trip_status_distribution(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[TripStatusBreakdown]:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_trip_status_distribution(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return []
    items = [TripStatusBreakdown(**r) if isinstance(r, dict) else TripStatusBreakdown() for r in result]
    total = sum(i.count for i in items) or 1
    for item in items:
        item.percentage = round(item.count / total * 100, 1)
    return items


@router.get("/financial/trip-volume", response_model=MonthlyFinancialResponse)
def get_monthly_trip_volume(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> MonthlyFinancialResponse:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_monthly_trip_volume(company_id=company_id, months=months, from_date=start, to_date=end)
    if not result:
        return MonthlyFinancialResponse()
    data = []
    for r in result:
        if isinstance(r, dict):
            dp = MonthlyDataPoint(
                month=r.get("month", ""),
                trip_count=r.get("trip_count", 0),
            )
            data.append(dp)
    total_trips = sum(d.trip_count for d in data)
    total = FinancialSummary(trip_count=total_trips)
    return MonthlyFinancialResponse(data=data, total=total)


@router.get("/financial/by-country", response_model=List[dict])
def get_revenue_by_country(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_revenue_by_country(company_id=company_id, from_date=start, to_date=end)
    return list(result) if result else []


@router.get("/financial/quarterly", response_model=MonthlyFinancialResponse)
def get_revenue_quarterly(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    quarters: int = Query(8, ge=1, le=20),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> MonthlyFinancialResponse:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_revenue_quarterly(company_id=company_id, quarters=quarters, from_date=start, to_date=end)
    if not result:
        return MonthlyFinancialResponse()
    data = []
    for r in result:
        if isinstance(r, dict):
            dp = MonthlyDataPoint(
                month=r.get("quarter", r.get("month", "")),
                revenue=r.get("revenue", 0.0),
                profit=r.get("profit", 0.0),
                trip_count=r.get("trip_count", 0),
            )
            data.append(dp)
    total_rev = sum(d.revenue for d in data)
    total_profit = sum(d.profit for d in data)
    total_trips = sum(d.trip_count for d in data)
    total = FinancialSummary(
        total_revenue=total_rev,
        total_cost=total_rev - total_profit,
        total_profit=total_profit,
        margin_pct=(total_profit / total_rev * 100) if total_rev else 0.0,
        trip_count=total_trips,
    )
    return MonthlyFinancialResponse(data=data, total=total)


@router.get("/financial/invoice-aging", response_model=dict)
def get_invoice_aging(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    company_id = current_user.get("company_id", 0)
    result = service.get_invoice_aging(company_id=company_id)
    return dict(result) if result else {}


@router.get("/revenue-by-client", response_model=ClientRevenueResponse)
def get_revenue_by_client(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ClientRevenueResponse:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_revenue_by_client(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return ClientRevenueResponse()
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                ClientRevenueItem(
                    client_id=i + 1,
                    client_name=r.get("client", r.get("client_name", "")),
                    total_revenue=r.get("revenue", r.get("total_revenue", 0.0)),
                    trip_count=r.get("trip_count", 0),
                )
            )
    total_rev = sum(item.total_revenue for item in items)
    for item in items:
        item.percentage = round(item.total_revenue / total_rev * 100, 1) if total_rev else 0.0
    return ClientRevenueResponse(data=items, total_revenue=total_rev)


@router.get("/client", response_model=ClientRevenueResponse)
def get_client_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ClientRevenueResponse:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_client_analytics(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return ClientRevenueResponse()
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                ClientRevenueItem(
                    client_id=i + 1,
                    client_name=r.get("client", r.get("client_name", "")),
                    total_revenue=r.get("revenue", r.get("total_revenue", 0.0)),
                    trip_count=r.get("trip_count", 0),
                )
            )
    total_rev = sum(item.total_revenue for item in items)
    for item in items:
        item.percentage = round(item.total_revenue / total_rev * 100, 1) if total_rev else 0.0
    return ClientRevenueResponse(data=items, total_revenue=total_rev)


@router.get("/client/growth", response_model=List[dict])
def get_client_growth(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    company_id = current_user.get("company_id", 0)
    result = service.get_client_growth(company_id=company_id, months=months, from_date=start, to_date=end)
    return list(result) if result else []


@router.get("/client/retention", response_model=List[dict])
def get_client_retention(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    result = service.get_client_retention(company_id=company_id)
    return list(result) if result else []


@router.get("/client/concentration", response_model=List[dict])
def get_revenue_concentration(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    result = service.get_revenue_concentration(company_id=company_id)
    return list(result) if result else []


@router.get("/fleet", response_model=List[FleetUtilizationItem])
def get_fleet_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[FleetUtilizationItem]:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_fleet(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return []
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                FleetUtilizationItem(
                    vehicle_id=i + 1,
                    plate=r.get("truck", r.get("plate", "")),
                    trip_count=r.get("trip_count", 0),
                    distance_km=r.get("total_km", r.get("distance_km", 0.0)),
                    revenue=r.get("profit", r.get("revenue", 0.0)),
                )
            )
    return items


@router.get("/fleet/utilization", response_model=List[FleetUtilizationItem])
def get_truck_utilization(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[FleetUtilizationItem]:
    company_id = current_user.get("company_id", 0)
    result = service.get_truck_utilization(company_id=company_id)
    if not result:
        return []
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                FleetUtilizationItem(
                    vehicle_id=i + 1,
                    plate=r.get("truck", r.get("plate", "")),
                    trip_count=r.get("trip_count", 0),
                    distance_km=r.get("total_km", r.get("distance_km", 0.0)),
                )
            )
    return items


@router.get("/route/profitability", response_model=List[RouteProfitabilityItem])
def get_route_profitability(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[RouteProfitabilityItem]:
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    company_id = current_user.get("company_id", 0)
    result = service.get_route_profitability(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return []
    items = []
    for r in result:
        if isinstance(r, dict):
            label = r.get("route_label", "")
            parts = label.split(" → ", 1) if " → " in label else ["", ""]
            items.append(
                RouteProfitabilityItem(
                    origin=parts[0] if len(parts) > 0 else "",
                    destination=parts[1] if len(parts) > 1 else "",
                    distance_km=r.get("avg_km", 0.0),
                    profit=r.get("avg_profit", r.get("profit", 0.0)),
                )
            )
    return items


@router.get("/route/by-country", response_model=List[dict])
def get_profit_per_km_by_country(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    result = service.get_profit_per_km_by_country(company_id=company_id)
    return list(result) if result else []


@router.get("/route/profit-vs-distance", response_model=List[dict])
def get_profit_vs_distance(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    limit: int = Query(100, ge=1, le=1000),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    result = service.get_profit_vs_distance(company_id=company_id, limit=limit)
    return list(result) if result else []


@router.get("/driver", response_model=List[DriverComparisonItem])
def get_driver_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[DriverComparisonItem]:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_driver(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return []
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                DriverComparisonItem(
                    driver_id=i + 1,
                    driver_name=r.get("driver", r.get("driver_name", "")),
                    trip_count=r.get("trip_count", 0),
                    distance_km=r.get("total_km", r.get("distance_km", 0.0)),
                    profit=r.get("profit", 0.0),
                )
            )
    return items


@router.get("/driver/comparison", response_model=List[DriverComparisonItem])
def get_driver_comparison(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[DriverComparisonItem]:
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    company_id = current_user.get("company_id", 0)
    result = service.get_driver_comparison(company_id=company_id, from_date=start, to_date=end)
    if not result:
        return []
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                DriverComparisonItem(
                    driver_id=i + 1,
                    driver_name=r.get("driver", r.get("driver_name", "")),
                    trip_count=r.get("trip_count", 0),
                    distance_km=r.get("total_km", r.get("distance_km", 0.0)),
                    revenue=r.get("revenue", 0.0),
                    profit=r.get("profit", 0.0),
                    profit_per_km=r.get("profit_per_km", 0.0),
                )
            )
    return items


@router.get("/driver/profit-per-km", response_model=List[DriverComparisonItem])
def get_driver_profit_per_km(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[DriverComparisonItem]:
    company_id = current_user.get("company_id", 0)
    result = service.get_driver_profit_per_km(company_id=company_id)
    if not result:
        return []
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                DriverComparisonItem(
                    driver_id=i + 1,
                    driver_name=r.get("driver_name", ""),
                    trip_count=r.get("trip_count", 0),
                    distance_km=r.get("total_km", r.get("distance_km", 0.0)),
                    profit=r.get("total_profit", r.get("profit", 0.0)),
                    profit_per_km=r.get("profit_per_km", 0.0),
                )
            )
    return items


@router.get("/driver/violations", response_model=List[dict])
def get_driver_tacho_violations(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    result = service.get_driver_tacho_violations(company_id=company_id)
    return list(result) if result else []


@router.get("/driver/monthly-activity", response_model=List[dict])
def get_driver_monthly_activity(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    date_from: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_from"),
    date_to: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="[DEPRECATED] Use date_to"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    if to_date:
        warnings.warn("'to_date' is deprecated, use 'date_to'", DeprecationWarning)
    start = date_from or from_date
    end = date_to or to_date
    result = service.get_driver_monthly_activity(company_id=company_id, months=months, from_date=start, to_date=end)
    return list(result) if result else []


@router.get("/document", response_model=dict)
def get_document_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    company_id = current_user.get("company_id", 0)
    result = service.get_document(company_id=company_id)
    return dict(result) if result else {}


@router.get("/document/upload-trend", response_model=List[dict])
def get_document_upload_trend(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[dict]:
    company_id = current_user.get("company_id", 0)
    result = service.get_document_upload_trend(company_id=company_id, months=months)
    return list(result) if result else []


@router.get("/maintenance/alerts", response_model=List[MaintenanceAlertItem])
def get_maintenance_alerts(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[MaintenanceAlertItem]:
    company_id = current_user.get("company_id", 0)
    result = service.get_maintenance_alerts(company_id=company_id)
    if not result:
        return []
    items = []
    for i, r in enumerate(result):
        if isinstance(r, dict):
            items.append(
                MaintenanceAlertItem(
                    vehicle_id=i + 1,
                    plate=r.get("truck", r.get("plate", "")),
                    alert_type="maintenance",
                    description=r.get("description", ""),
                    due_date=r.get("next_due_date", r.get("due_date")),
                    severity="warning",
                )
            )
    return items


@router.post("/invalidate", response_model=dict)
def invalidate_cache(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    company_id = current_user.get("company_id", 0)
    service.invalidate(company_id=company_id)
    return {"status": "cache invalidated"}


@router.get("/overview", response_model=AnalyticsOverview)
def get_overview(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsOverview:
    company_id = current_user.get("company_id", 0)
    result = service.get_data(company_id=company_id)
    if not result:
        return AnalyticsOverview()
    if isinstance(result, dict):
        return AnalyticsOverview(**result)
    if isinstance(result, tuple) and len(result) >= 2:
        alerts, overdue_amount = result[0], result[1]
        if isinstance(alerts, list):
            critical = sum(1 for a in alerts if isinstance(a, dict) and a.get("type") == "RED")
            warning = sum(1 for a in alerts if isinstance(a, dict) and a.get("type") == "YELLOW")
            # overdue_amount may come through as a list (e.g. per_driver data) — coerce safely
            try:
                amount = float(overdue_amount) if not isinstance(overdue_amount, (list, tuple)) else 0.0
            except (TypeError, ValueError):
                amount = 0.0
            return AnalyticsOverview(
                overdue_amount=amount,
                alerts=AlertSummary(total=len(alerts), critical=critical, warning=warning),
            )
    return AnalyticsOverview()
