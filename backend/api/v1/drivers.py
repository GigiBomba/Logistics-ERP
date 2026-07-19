import warnings
from datetime import date as _date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.dependencies import get_db, get_driver_repo
from backend.schemas.common import PaginatedResponse
from backend.schemas.driver import DriverCreate, DriverResponse, DriverUpdate
from backend.db import DatabaseManager
from backend.repositories.driver_repository import DriverRepository

from backend.dependencies_security import require_dispatcher

router = APIRouter(prefix="/drivers", tags=["drivers"])


class DriverListResponse(PaginatedResponse[DriverResponse]):
    """Paginated list of drivers."""


@router.get("/", response_model=DriverListResponse)
def list_drivers(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    repo: DriverRepository = Depends(get_driver_repo),
):
    """Return paginated list of drivers."""
    company_id = current_user.get("company_id", 0)
    items = repo.get_all(company_id=company_id, limit=page_size, offset=(page - 1) * page_size)
    return PaginatedResponse.from_items(
        items=[DriverResponse(**d) for d in items],
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.get("/{driver_id}", response_model=DriverResponse)
def get_driver(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
):
    company_id = current_user.get("company_id", 0)
    driver = repo.get_by_id(driver_id, company_id=company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return DriverResponse(**driver)


@router.post("/", response_model=Dict[str, int], status_code=201)
def create_driver(
    data: DriverCreate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
):
    company_id = current_user.get("company_id", 0)
    driver_id = repo.create(data.model_dump(), company_id=company_id)
    from backend.posthog_client import get_posthog
    _ph = get_posthog()
    if _ph:
        _ph.capture("driver_created", distinct_id=current_user.get("email", ""), properties={
            "company_id": company_id,
            "driver_id": driver_id,
        })
    return {"id": driver_id}


@router.patch("/{driver_id}")
def update_driver_partial(
    driver_id: int,
    data: DriverUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
):
    """Partially update a driver (PATCH)."""
    company_id = current_user.get("company_id", 0)
    existing = repo.get_by_id(driver_id, company_id=company_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_fields:
        repo.update(driver_id, update_fields, company_id=company_id)
    return {"status": "updated"}


@router.put("/{driver_id}", deprecated=True)
def update_driver(
    driver_id: int,
    data: DriverUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /{driver_id} instead."""
    company_id = current_user.get("company_id", 0)
    existing = repo.get_by_id(driver_id, company_id=company_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_fields:
        repo.update(driver_id, update_fields, company_id=company_id)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "updated"}


@router.delete("/{driver_id}")
def delete_driver(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
):
    company_id = current_user.get("company_id", 0)
    existing = repo.get_by_id(driver_id, company_id=company_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    repo.delete(driver_id, company_id=company_id)
    return {"status": "deleted"}


@router.post("/{driver_id}/assign-truck")
def assign_driver_to_truck(
    driver_id: int,
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.services.driver_truck_service import DriverTruckService
    company_id = current_user.get("company_id", 0)
    svc = DriverTruckService(db)
    result = svc.assign_driver_to_truck(driver_id, truck_id, company_id=company_id)
    return {"status": "assigned", "data": result}


@router.post("/{driver_id}/unassign")
def unassign_driver(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.services.driver_truck_service import DriverTruckService
    company_id = current_user.get("company_id", 0)
    svc = DriverTruckService(db)
    result = svc.unassign_driver(driver_id, company_id=company_id)
    return {"status": "unassigned", "truck_id": result}


@router.get("/{driver_id}/truck-plate")
def get_driver_truck_plate(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.services.driver_truck_service import DriverTruckService
    company_id = current_user.get("company_id", 0)
    svc = DriverTruckService(db)
    plate = svc.get_truck_plate_for_driver(driver_id, company_id=company_id)
    return {"plate": plate}


@router.get("/by-truck/{truck_id}", response_model=DriverResponse)
def get_driver_by_truck(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Get the driver assigned to a specific truck."""
    company_id = current_user.get("company_id", 0)
    from backend.repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository
    assignment_repo = DriverTruckAssignmentRepository(db)
    assignment = assignment_repo.get_by_truck(truck_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="No driver assigned to this truck")
    driver_repo = DriverRepository(db)
    driver = driver_repo.get_by_id(assignment["driver_id"], company_id=company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return DriverResponse(**driver)


@router.get("/{driver_id}/tacho-activity", response_model=PaginatedResponse[dict])
def get_driver_tacho_activity(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    date_from: str = Query("", description="Start date (ISO format: YYYY-MM-DD)"),
    from_date: str = Query("", description="[DEPRECATED] Use date_from"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
    db: DatabaseManager = Depends(get_db),
):
    company_id = current_user.get("company_id", 0)
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    start = date_from or from_date
    from backend.repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
    repo = TachoDriverActivityRepository(db)
    from_date_parsed = _date.fromisoformat(start) if start else _date.min
    rows = repo.get_by_driver(driver_id, company_id=company_id, date_from=from_date_parsed)
    items = rows[:page_size]
    return PaginatedResponse.from_items(items=items, total=len(rows), page=page, page_size=page_size)
