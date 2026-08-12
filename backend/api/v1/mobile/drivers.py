"""Mobile driver endpoints (blueprint §6.2).

  - GET    /mobile/drivers                     — paginated driver list (search / status / expiring)
  - POST   /mobile/drivers                     — create driver         [can_create_driver]
  - GET    /mobile/drivers/{driver_id}         — driver detail
  - PATCH  /mobile/drivers/{driver_id}         — update driver         [can_update_driver]
  - GET    /mobile/drivers/{driver_id}/tacho   — tachograph timeline (blueprint §6.2)

Every handler is company-scoped (404 for another company's driver).  The first
business-logic line of every mutation is the PermissionService gate (403 on
denial).

Driver ``status`` reuses the legacy derivation from ``/mobile/dispatcher/drivers``:
'off' default → 'available' when the driver has an active truck assignment →
'driving' when the driver also has an active (non-delivered/cancelled) trip.

Tachograph timeline is sourced from the real ``tacho_driver_activity`` table
(the same data the desktop ``GET /drivers/{driver_id}/tacho-activity`` returns):
each row's ``driving_minutes``/``work_minutes``/``rest_minutes``/``avail_minutes``
map 1:1 onto the four buckets.  ``weekly_driving_minutes`` is the sum of
``driving_minutes`` over the queried range (default: the last 7 days); the EU
weekly limit is fixed at 3360 minutes (56 h).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.mobile import (
    DriverCreateRequest,
    DriverOut,
    DriverUpdateRequest,
    TachoDayBucket,
    TachoTimelineOut,
)
from repositories.driver_repository import DriverRepository
from services.permission_service import PermissionService

router = APIRouter(prefix="/drivers", tags=["mobile_drivers"])


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


def _get_driver_or_404(
    repo: DriverRepository, driver_id: int, company_id: int
) -> Dict[str, Any]:
    driver = repo.get_by_id(driver_id, company_id=company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


def _driver_status_and_truck(
    db: DatabaseManager, driver: Dict[str, Any]
) -> tuple[str, Optional[int]]:
    """Derive the 3-state status + current truck, reusing the legacy logic.

    'driving' → has an active trip; 'available' → has an active truck
    assignment but no active trip; else 'off'.
    """
    driver_id = driver["id"]
    trip = db.execute(
        "SELECT 1 FROM trips WHERE driver_id = ? AND status NOT IN ('Delivered', 'Cancelled', 'Paid') "
        "AND company_id = ? LIMIT 1",
        (driver_id, driver.get("company_id") or 0),
    ).fetchone()
    if trip:
        return "driving", None
    # driver_truck_assignments has no company_id column; the driver has already
    # been company-verified, and driver_id is globally unique.
    assignment = db.execute(
        "SELECT truck_id FROM driver_truck_assignments WHERE driver_id = ? AND active = 1 LIMIT 1",
        (driver_id,),
    ).fetchone()
    if assignment:
        return "available", assignment["truck_id"]
    return "off", None


def _to_driver_out(db: DatabaseManager, driver: Dict[str, Any]) -> dict:
    status, truck_id = _driver_status_and_truck(db, driver)
    return {
        "id": driver["id"],
        "company_id": driver.get("company_id") or 0,
        "name": driver.get("name") or "",
        "phone": driver.get("phone") or "",
        "email": driver.get("email") or "",
        "status": status,
        "license_number": driver.get("license_number") or "",
        "license_category": driver.get("license_category") or "",
        "license_expiry": driver.get("license_expiry"),
        "medical_expiry": driver.get("medical_expiry"),
        "adr_certificate_expiry": driver.get("adr_certificate_expiry"),
        "current_truck_id": truck_id,
        "is_active": bool(driver.get("is_active", 1)),
        "created_at": driver.get("created_at"),
        "updated_at": driver.get("updated_at"),
    }


@router.get("", response_model=PaginatedResponse[DriverOut])
def list_drivers(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str = Query("", description="LIKE filter on name/phone/license_number"),
    status: str = Query("", description="Filter derived status: driving | available | off"),
    expiring_within_days: int = Query(
        30, ge=0, description="Only drivers with an expiry within N days (license/medical/ADR); 0 disables"
    ),
):
    """Paginated, company-scoped driver list.

    ``status`` filters the *derived* 3-state (computed in Python, so the
    filter is applied after derivation).  ``expiring_within_days`` matches
    drivers where ``license_expiry`` OR ``medical_expiry`` OR
    ``adr_certificate_expiry`` falls within today..today+N (default N = 30,
    matching DriverRepository's 30-day window when the param is omitted).
    """
    company_id = current_user["company_id"]
    conditions = ["company_id = ?"]
    params: list = [company_id]
    if search:
        like = f"%{search}%"
        conditions.append("(name LIKE ? OR phone LIKE ? OR license_number LIKE ?)")
        params.extend([like, like, like])
    if expiring_within_days and expiring_within_days > 0:
        today = date.today().strftime("%Y-%m-%d")
        cutoff = (date.today() + timedelta(days=expiring_within_days)).strftime("%Y-%m-%d")
        conditions.append(
            "( (license_expiry IS NOT NULL AND license_expiry != '' AND license_expiry >= ? AND license_expiry <= ?) "
            "OR (medical_expiry IS NOT NULL AND medical_expiry != '' AND medical_expiry >= ? AND medical_expiry <= ?) "
            "OR (adr_certificate_expiry IS NOT NULL AND adr_certificate_expiry != '' AND adr_certificate_expiry >= ? AND adr_certificate_expiry <= ?) )"
        )
        params.extend([today, cutoff, today, cutoff, today, cutoff])
    where = " AND ".join(conditions)

    rows = db.execute(
        f"SELECT * FROM drivers WHERE {where} ORDER BY name ASC", tuple(params)
    ).fetchall()
    all_drivers = [_to_driver_out(db, dict(r)) for r in rows]

    if status:
        all_drivers = [d for d in all_drivers if d["status"] == status]

    total = len(all_drivers)
    offset = (page - 1) * page_size
    items = all_drivers[offset : offset + page_size]
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("", response_model=DriverOut, status_code=201)
def create_driver(
    data: DriverCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a company-scoped driver (gate: can_create_driver)."""
    _check_permission(db, current_user.get("id") or 0, "can_create_driver")
    company_id = current_user["company_id"]
    repo = DriverRepository(db)
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    driver_id = repo.create(fields, company_id=company_id)
    return _to_driver_out(db, _get_driver_or_404(repo, driver_id, company_id))


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Company-scoped driver detail (404 for missing / other-company drivers)."""
    company_id = current_user["company_id"]
    return _to_driver_out(db, _get_driver_or_404(DriverRepository(db), driver_id, company_id))


@router.patch("/{driver_id}", response_model=DriverOut)
def update_driver(
    driver_id: int,
    data: DriverUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update a driver (gate: can_update_driver)."""
    _check_permission(db, current_user.get("id") or 0, "can_update_driver")
    company_id = current_user["company_id"]
    repo = DriverRepository(db)
    _get_driver_or_404(repo, driver_id, company_id)
    fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if fields:
        repo.update(driver_id, fields, company_id=company_id)
    return _to_driver_out(db, _get_driver_or_404(repo, driver_id, company_id))


def build_tacho_timeline(
    db: DatabaseManager,
    driver_id: int,
    start_date: str = "",
    end_date: str = "",
) -> TachoTimelineOut:
    """Build a driver's tachograph timeline over a date range.

    Shared by the dispatcher tacho endpoint (``GET /drivers/{driver_id}/tacho``)
    and the driver self-service endpoint (``GET /mobile/driver/tacho``) so both
    surfaces produce IDENTICAL buckets.  Buckets are filled from the REAL
    ``tacho_driver_activity`` table (the same source as desktop
    ``GET /drivers/{driver_id}/tacho-activity``); no synthetic data is invented.

    ``start_date`` / ``end_date`` default to 6 days ago / today (a 7-day
    rolling window).  The caller is responsible for verifying the driver
    belongs to the caller's company — this helper only reads activity rows by
    driver_id (the activity table has no company_id column).
    """
    end = end_date or date.today().isoformat()
    start = start_date or (date.today() - timedelta(days=6)).isoformat()
    try:
        start_parsed = date.fromisoformat(start)
        end_parsed = date.fromisoformat(end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid date format (expected YYYY-MM-DD)") from exc

    from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository

    # tacho_driver_activity has no company_id column; the caller has already
    # company-verified the driver (404 otherwise), so scoping by driver_id is
    # sufficient and safe.
    rows = TachoDriverActivityRepository(db).get_by_driver(
        driver_id, date_from=start_parsed, company_id=None
    )
    buckets: List[TachoDayBucket] = []
    weekly_driving_minutes = 0
    for r in rows:
        r = dict(r)
        day = (r.get("activity_date") or "")[:10]
        if day and day > end_parsed.isoformat():
            continue
        driving = int(r.get("driving_minutes") or 0)
        weekly_driving_minutes += driving
        buckets.append(
            TachoDayBucket(
                date=day,
                driving_minutes=driving,
                working_minutes=int(r.get("work_minutes") or 0),
                rest_minutes=int(r.get("rest_minutes") or 0),
                availability_minutes=int(r.get("avail_minutes") or 0),
            )
        )
    buckets.sort(key=lambda b: b.date)
    return TachoTimelineOut(
        days=buckets,
        weekly_driving_minutes=weekly_driving_minutes,
        weekly_limit_minutes=3360,
    )


@router.get("/{driver_id}/tacho", response_model=TachoTimelineOut)
def get_driver_tacho(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    start_date: str = Query("", description="ISO date YYYY-MM-DD (default: 6 days ago)"),
    end_date: str = Query("", description="ISO date YYYY-MM-DD (default: today)"),
):
    """Tachograph timeline for a driver over a date range (dispatcher gate).

    Company-verifies the driver (404 otherwise) then builds the timeline via
    the shared ``build_tacho_timeline`` helper (identical output to the
    driver self-service endpoint ``GET /mobile/driver/tacho``).
    """
    company_id = current_user["company_id"]
    _get_driver_or_404(DriverRepository(db), driver_id, company_id)

    return build_tacho_timeline(db, driver_id, start_date=start_date, end_date=end_date)
