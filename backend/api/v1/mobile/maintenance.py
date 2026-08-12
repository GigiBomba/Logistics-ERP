"""Mobile maintenance endpoints (blueprint §6.5).

  - GET  /mobile/maintenance/schedule    — paginated schedule list (overdue_only filter)
  - POST /mobile/maintenance/schedule    — create schedule  [can_schedule_maintenance]
  - GET  /mobile/maintenance/cost-trend  — monthly + by-type cost aggregation

Every handler is company-scoped (404 for another company's truck).  ``overdue``
is computed through the REAL repository overdue thresholds
(``FleetRepository.schedule_is_overdue`` — the same source as the desktop
health-score count, so the mobile list can never disagree with desktop).

NOTE (§8.3 vs real code): blueprint §8.3 row 7 implies a dispatcher may
schedule maintenance, but the REAL ``PermissionService.can_schedule_maintenance``
matrix is admin + manager only — real code wins; dispatcher is 403 here
(mirrors the existing fleet maintenance-record gate).
"""
from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.mobile import (
    MaintenanceCostTrendOut,
    MaintenanceScheduleCreateRequest,
    MaintenanceScheduleOut,
)
from repositories.fleet_repository import FleetRepository
from services.permission_service import PermissionService

router = APIRouter(prefix="/maintenance", tags=["mobile_maintenance"])


def _check_permission(db: DatabaseManager, user_id: int, perm_check: str) -> None:
    """Gate-1: run the real PermissionService decision; 403 on denial."""
    if not user_id:
        return
    result = getattr(PermissionService(db), perm_check)(user_id)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Permission denied")


def _add_months(source_date, months: int):
    """Add calendar months (same helper semantics as the repo overdue logic)."""
    total_months = source_date.month - 1 + months
    year = source_date.year + total_months // 12
    month = total_months % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(source_date.day, max_day)
    return source_date.replace(year=year, month=month, day=day)


def _next_due(row: Dict[str, Any]) -> Optional[str]:
    """Next due ISO date: fixed_expiry_date, or last_done_date + interval_months."""
    fixed = row.get("fixed_expiry_date")
    if fixed:
        return str(fixed)[:10]
    months = row.get("interval_months")
    last_done = row.get("last_done_date")
    if months is not None and last_done:
        try:
            d = datetime.strptime(str(last_done)[:10], "%Y-%m-%d")
            return _add_months(d, int(months)).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    return None


def _schedule_out(row: Dict[str, Any]) -> dict:
    return {
        "id": row["id"],
        "truck_id": row["truck_id"],
        "truck_plate": row.get("plate_number") or "",
        "maintenance_type": row.get("maintenance_type") or "",
        "interval_km": row.get("interval_km"),
        "interval_months": row.get("interval_months"),
        "fixed_expiry_date": row.get("fixed_expiry_date"),
        "last_done_km": row.get("last_done_km"),
        "last_done_date": row.get("last_done_date"),
        "overdue": bool(row.get("overdue", False)),
        "next_due": _next_due(row),
    }


@router.get("/schedule", response_model=PaginatedResponse[MaintenanceScheduleOut])
def list_maintenance_schedule(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    overdue_only: bool = Query(False),
):
    """Paginated, company-scoped maintenance schedule list.

    ``overdue`` is computed via the REAL repo thresholds
    (``schedule_is_overdue``); ``overdue_only=true`` returns just the overdue
    schedules.  ``next_due`` is derived from fixed_expiry_date or
    last_done_date + interval_months.
    """
    company_id = current_user["company_id"]
    rows = FleetRepository(db).get_maintenance_schedules_with_overdue(company_id=company_id)
    if overdue_only:
        rows = [r for r in rows if r["overdue"]]
    total = len(rows)
    offset = (page - 1) * page_size
    items = [_schedule_out(r) for r in rows[offset : offset + page_size]]
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("/schedule", response_model=MaintenanceScheduleOut, status_code=201)
def create_maintenance_schedule(
    data: MaintenanceScheduleCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a company-scoped maintenance schedule.

    Gate: can_schedule_maintenance — admin + manager only (REAL matrix;
    dispatcher 403).
    """
    _check_permission(db, current_user.get("id") or 0, "can_schedule_maintenance")
    company_id = current_user["company_id"]
    repo = FleetRepository(db)

    truck = repo.get_by_id(data.truck_id, company_id=company_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    if data.fixed_expiry_date is None and data.interval_km is None and data.interval_months is None:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "missing_cadence",
                    "detail": "Provide at least one of interval_km, interval_months or fixed_expiry_date"},
        )

    schedule_id = repo.add_maintenance_schedule(
        truck_id=data.truck_id,
        maint_type=data.maintenance_type,
        interval_km=data.interval_km,
        interval_months=data.interval_months,
        fixed_expiry_date=data.fixed_expiry_date or "",
        created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        company_id=company_id,
    )
    row = db.execute(
        "SELECT s.*, t.plate_number FROM maintenance_schedules s "
        "LEFT JOIN trucks t ON t.id = s.truck_id "
        "WHERE s.id = ? AND s.company_id = ?",
        (schedule_id, company_id),
    ).fetchone()
    row = dict(row) if row else {
        "id": schedule_id, "truck_id": data.truck_id, "plate_number": truck.get("plate_number") or "",
        "maintenance_type": data.maintenance_type, "interval_km": data.interval_km,
        "interval_months": data.interval_months, "fixed_expiry_date": data.fixed_expiry_date,
        "last_done_km": None, "last_done_date": None,
    }
    row["overdue"] = False
    return _schedule_out(row)


@router.get("/cost-trend", response_model=MaintenanceCostTrendOut)
def maintenance_cost_trend(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    start_date: str = Query("", description="ISO date YYYY-MM-DD (default: 1 year ago)"),
    end_date: str = Query("", description="ISO date YYYY-MM-DD (default: today)"),
):
    """Maintenance cost trend: monthly totals + per-type totals (company-scoped)."""
    company_id = current_user["company_id"]

    def _coerce(value: str, fallback: str) -> str:
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid date '{value}' — expected YYYY-MM-DD",
                )
            return value
        return fallback

    today = datetime.utcnow().strftime("%Y-%m-%d")
    year_ago = (datetime.utcnow().replace(year=datetime.utcnow().year - 1)).strftime("%Y-%m-%d")
    start = _coerce(start_date, year_ago)
    end = _coerce(end_date, today)
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")

    monthly_rows = db.execute(
        "SELECT substr(date, 1, 7) AS month, COALESCE(SUM(cost), 0) AS total "
        "FROM maintenance_records "
        "WHERE company_id = ? AND date >= ? AND date <= ? AND cost IS NOT NULL "
        "GROUP BY month ORDER BY month",
        (company_id, start, end),
    ).fetchall()
    by_type_rows = db.execute(
        "SELECT maintenance_type AS type, COALESCE(SUM(cost), 0) AS total "
        "FROM maintenance_records "
        "WHERE company_id = ? AND date >= ? AND date <= ? AND cost IS NOT NULL "
        "GROUP BY maintenance_type ORDER BY total DESC, maintenance_type",
        (company_id, start, end),
    ).fetchall()

    return {
        "monthly": [{"label": r["month"], "total": float(r["total"])} for r in monthly_rows],
        "by_type": [{"label": r["type"], "total": float(r["total"])} for r in by_type_rows],
    }
