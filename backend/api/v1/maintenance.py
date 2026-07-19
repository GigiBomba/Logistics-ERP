import warnings
from datetime import date, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.db import DatabaseManager
from backend.repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


class MaintenanceSummaryResponse(BaseModel):
    """Maintenance summary with truck-level breakdown and monthly costs."""

    model_config = ConfigDict(extra="ignore")

    trucks: List[dict] = []
    cost_monthly: List[dict] = []
    total_trucks: int = 0


class MaintenanceDataResponse(BaseModel):
    """Generic wrapper for maintenance data endpoints."""

    model_config = ConfigDict(extra="ignore")

    data: List[dict] = []


def _resolve_since(
    date_from: str,
    since: str,
    default_days: int = 365,
) -> str:
    """Resolve the since/date_from parameter, falling back to a default lookback."""
    if since:
        warnings.warn("'since' is deprecated, use 'date_from'", DeprecationWarning)
    start = date_from or since
    return start or (date.today() - timedelta(days=default_days)).isoformat()


@router.get("/summary", response_model=MaintenanceSummaryResponse)
def get_maintenance_summary(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return maintenance summary including truck breakdown and monthly costs."""
    company_id = current_user.get("company_id", 0)
    repo = FleetRepository(db)
    since_date = _resolve_since("", "")
    truck_summary = repo.get_maintenance_truck_summary(since_date, company_id=company_id)
    cost_monthly = repo.get_maintenance_cost_monthly(since_date, company_id=company_id)
    return MaintenanceSummaryResponse(
        trucks=truck_summary,
        cost_monthly=cost_monthly,
        total_trucks=len(truck_summary),
    )


@router.get("/cost-monthly", response_model=MaintenanceDataResponse)
def get_maintenance_cost_monthly(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: str = Query("", description="Start date (ISO format: YYYY-MM-DD)"),
    since: str = Query("", description="[DEPRECATED] Use date_from"),
    db: DatabaseManager = Depends(get_db),
):
    """Return monthly maintenance costs."""
    company_id = current_user.get("company_id", 0)
    repo = FleetRepository(db)
    since_date = _resolve_since(date_from, since)
    return MaintenanceDataResponse(data=repo.get_maintenance_cost_monthly(since_date, company_id=company_id))


@router.get("/cost-by-truck-monthly", response_model=MaintenanceDataResponse)
def get_maintenance_cost_by_truck_monthly(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: str = Query("", description="Start date (ISO format: YYYY-MM-DD)"),
    since: str = Query("", description="[DEPRECATED] Use date_from"),
    db: DatabaseManager = Depends(get_db),
):
    """Return monthly maintenance costs broken down by truck."""
    company_id = current_user.get("company_id", 0)
    repo = FleetRepository(db)
    since_date = _resolve_since(date_from, since)
    return MaintenanceDataResponse(data=repo.get_maintenance_cost_truck_monthly(since_date, company_id=company_id))


@router.get("/truck-summary", response_model=MaintenanceDataResponse)
def get_maintenance_truck_summary(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: str = Query("", description="Start date (ISO format: YYYY-MM-DD)"),
    since: str = Query("", description="[DEPRECATED] Use date_from"),
    db: DatabaseManager = Depends(get_db),
):
    """Return maintenance summary per truck."""
    company_id = current_user.get("company_id", 0)
    repo = FleetRepository(db)
    since_date = _resolve_since(date_from, since)
    return MaintenanceDataResponse(data=repo.get_maintenance_truck_summary(since_date, company_id=company_id))


@router.get("/top-categories", response_model=MaintenanceDataResponse)
def get_maintenance_top_categories(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: str = Query("", description="Start date (ISO format: YYYY-MM-DD)"),
    since: str = Query("", description="[DEPRECATED] Use date_from"),
    db: DatabaseManager = Depends(get_db),
):
    """Return most expensive maintenance categories."""
    company_id = current_user.get("company_id", 0)
    repo = FleetRepository(db)
    since_date = _resolve_since(date_from, since)
    return MaintenanceDataResponse(data=repo.get_maintenance_most_expensive_category(since_date, company_id=company_id))
