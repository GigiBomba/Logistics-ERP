"""Mobile analytics endpoints (blueprint §6.4).

  - GET /mobile/analytics/revenue?group_by=&start_date=&end_date
        -> {trend, per_client, per_route}     [can_view_analytics]
  - GET /mobile/analytics/fleet-utilization?start_date=&end_date=
        -> {status_split, trucks}             [can_view_analytics]
  - GET /mobile/analytics/driver-performance?start_date=&end_date=
        -> {rows}                             [can_view_analytics]
  - GET /mobile/analytics/invoice-aging
        -> {current, bucket_31_60, bucket_61_90, overdue, total_outstanding}
                                              [can_view_analytics]
  - GET /mobile/analytics/export?report=&start_date=&end_date=
        -> {download_url, expires_at} (SYNC CSV) [can_view_analytics]

Gate: EVERY endpoint here (including export) runs the REAL
``PermissionService.can_view_analytics`` imperatively — dispatcher gets 403
(§8.3: "View analytics" is manager/admin; the desktop analytics router uses
require_dispatcher, which DIVERGES — the mobile contract gates with
can_view_analytics; real code wins).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.schemas.mobile import (
    AnalyticsExportResponse,
    AnalyticsRevenueResponse,
    DriverPerformanceResponse,
    FleetUtilizationResponse,
    InvoiceAgingResponse,
)
from repositories.export_job_repository import ExportJobRepository
from services.mobile_analytics_aggregator import MobileAnalyticsAggregator
from services.permission_service import PermissionService

router = APIRouter(prefix="/analytics", tags=["mobile_analytics"])

_VALID_REPORTS = {"revenue", "fleet", "drivers", "invoice_aging"}


def _check_permission(db: DatabaseManager, user_id: int, perm_check: str) -> None:
    """Gate-1: run the real PermissionService decision; 403 on denial.

    ``user_id`` 0 (env-configured admin) skips the check — the desktop
    convention for the system/internal admin (no users-table row).
    """
    if not user_id:
        return
    result = getattr(PermissionService(db), perm_check)(user_id)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Permission denied")


def _dates(start_date: str, end_date: str) -> tuple[Optional[str], Optional[str]]:
    """Validate optional ISO dates (YYYY-MM-DD); returns (from, to)."""
    for value, field in ((start_date, "start_date"), (end_date, "end_date")):
        if value:
            try:
                datetime.fromisoformat(value)
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid {field} — expected ISO date (YYYY-MM-DD).",
                )
    return (start_date or None, end_date or None)


def _export_token_and_url(job_id: int, company_id: int) -> tuple[str, str, str]:
    """Mint a 10-minute signed download token for an export file."""
    from backend.services.local_download_service import (
        KIND_EXPORT_FILE,
        create_download_token,
    )

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=600)
    token = create_download_token(
        record_id=job_id,
        company_id=company_id,
        kind=KIND_EXPORT_FILE,
        expires_at=expires_at,
    )
    return token, f"/api/v1/mobile/company/export/download/{token}", expires_at.isoformat()


@router.get("/revenue", response_model=AnalyticsRevenueResponse)
def analytics_revenue(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    group_by: str = Query("period", pattern="^(period|client|route)$"),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """Revenue trend / per-client / per-route chart inputs (gate: can_view_analytics)."""
    _check_permission(db, current_user.get("id") or 0, "can_view_analytics")
    from_date, to_date = _dates(start_date, end_date)
    data = MobileAnalyticsAggregator(db).revenue(
        current_user["company_id"], from_date, to_date, group_by,
    )
    return AnalyticsRevenueResponse(**data)


@router.get("/fleet-utilization", response_model=FleetUtilizationResponse)
def analytics_fleet_utilization(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """Fleet status split + per-truck utilization (gate: can_view_analytics)."""
    _check_permission(db, current_user.get("id") or 0, "can_view_analytics")
    from_date, to_date = _dates(start_date, end_date)
    data = MobileAnalyticsAggregator(db).fleet_utilization(
        current_user["company_id"], from_date, to_date,
    )
    return FleetUtilizationResponse(**data)


@router.get("/driver-performance", response_model=DriverPerformanceResponse)
def analytics_driver_performance(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """Per-driver performance rows (gate: can_view_analytics). No rating field."""
    _check_permission(db, current_user.get("id") or 0, "can_view_analytics")
    from_date, to_date = _dates(start_date, end_date)
    data = MobileAnalyticsAggregator(db).driver_performance(
        current_user["company_id"], from_date, to_date,
    )
    return DriverPerformanceResponse(**data)


@router.get("/invoice-aging", response_model=InvoiceAgingResponse)
def analytics_invoice_aging(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Invoice aging buckets (gate: can_view_analytics)."""
    _check_permission(db, current_user.get("id") or 0, "can_view_analytics")
    data = MobileAnalyticsAggregator(db).invoice_aging(current_user["company_id"])
    return InvoiceAgingResponse(**data)


@router.get("/export", response_model=AnalyticsExportResponse)
def analytics_export(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    report: str = Query(...),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """Synchronous analytics CSV export (gate: can_view_analytics).

    Generates a small CSV for the requested report, stores it under the
    export dir, records an ``export_jobs`` row and returns a 10-minute signed
    download URL (kind='export_file') served by the existing
    ``GET /mobile/company/export/download/{token}`` endpoint.
    """
    _check_permission(db, current_user.get("id") or 0, "can_view_analytics")

    if report not in _VALID_REPORTS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown report — expected one of {sorted(_VALID_REPORTS)}",
        )

    company_id = current_user["company_id"]
    from_date, to_date = _dates(start_date, end_date)
    aggregator = MobileAnalyticsAggregator(db)
    csv_text = aggregator.to_csv(report, company_id, from_date, to_date)

    from services.mobile_export_service import get_export_dir

    export_dir = get_export_dir()
    filename = (
        f"analytics_{report}_{company_id}_"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    )
    path = os.path.join(export_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(csv_text)

    job_id = ExportJobRepository(db).create(
        kind="analytics_export",
        params={"report": report},
        company_id=company_id,
        status="success",
        result_path=path,
    )
    token, url, expires_at = _export_token_and_url(job_id, company_id)
    return AnalyticsExportResponse(download_url=url, expires_at=expires_at)
