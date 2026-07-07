from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_analytics_service
from backend.dependencies_security import require_dispatcher
from services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/financial", )
async def get_financial_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_financial(from_date=from_date, to_date=to_date)


@router.get("/financial/monthly", )
async def get_monthly_financial(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(24, ge=1, le=60),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_monthly_financial(months=months, from_date=from_date, to_date=to_date)


@router.get("/financial/cost-breakdown", )
async def get_cost_breakdown(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_cost_breakdown(months=months, from_date=from_date, to_date=to_date)


@router.get("/financial/trip-status", )
async def get_trip_status_distribution(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_trip_status_distribution(from_date=from_date, to_date=to_date)


@router.get("/financial/trip-volume", )
async def get_monthly_trip_volume(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_monthly_trip_volume(months=months, from_date=from_date, to_date=to_date)


@router.get("/financial/by-country", )
async def get_revenue_by_country(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_revenue_by_country(from_date=from_date, to_date=to_date)


@router.get("/financial/quarterly", )
async def get_revenue_quarterly(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    quarters: int = Query(8, ge=1, le=20),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_revenue_quarterly(quarters=quarters, from_date=from_date, to_date=to_date)


@router.get("/financial/invoice-aging", )
async def get_invoice_aging(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_invoice_aging()


@router.get("/revenue-by-client", )
async def get_revenue_by_client(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_revenue_by_client(from_date=from_date, to_date=to_date)


@router.get("/client", )
async def get_client_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_client_analytics(from_date=from_date, to_date=to_date)


@router.get("/client/growth", )
async def get_client_growth(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_client_growth(months=months, from_date=from_date, to_date=to_date)


@router.get("/client/retention", )
async def get_client_retention(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_client_retention()


@router.get("/client/concentration", )
async def get_revenue_concentration(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_revenue_concentration()


@router.get("/fleet", )
async def get_fleet_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_fleet(from_date=from_date, to_date=to_date)


@router.get("/fleet/utilization", )
async def get_truck_utilization(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_truck_utilization()


@router.get("/route/profitability", )
async def get_route_profitability(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_route_profitability(from_date=from_date, to_date=to_date)


@router.get("/route/by-country", )
async def get_profit_per_km_by_country(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_profit_per_km_by_country()


@router.get("/route/profit-vs-distance", )
async def get_profit_vs_distance(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    limit: int = Query(100, ge=1, le=1000),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_profit_vs_distance(limit=limit)


@router.get("/driver", )
async def get_driver_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_driver(from_date=from_date, to_date=to_date)


@router.get("/driver/comparison", )
async def get_driver_comparison(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_driver_comparison(from_date=from_date, to_date=to_date)


@router.get("/driver/profit-per-km", )
async def get_driver_profit_per_km(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_driver_profit_per_km()


@router.get("/driver/violations", )
async def get_driver_tacho_violations(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_driver_tacho_violations()


@router.get("/driver/monthly-activity", )
async def get_driver_monthly_activity(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_driver_monthly_activity(months=months, from_date=from_date, to_date=to_date)


@router.get("/document", )
async def get_document_analytics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_document()


@router.get("/document/upload-trend", )
async def get_document_upload_trend(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_document_upload_trend(months=months)


@router.get("/maintenance/alerts", )
async def get_maintenance_alerts(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_maintenance_alerts()


@router.post("/invalidate")
async def invalidate_cache(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    service.invalidate()
    return {"status": "cache invalidated"}


@router.get("/overview")
async def get_overview(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_data()
