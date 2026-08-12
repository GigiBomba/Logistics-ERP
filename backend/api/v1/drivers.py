import warnings
from datetime import date as _date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.dependencies import get_db, get_driver_repo
from backend.schemas.common import PaginatedResponse
from backend.schemas.driver import DriverCreate, DriverResponse, DriverUpdate
from database.db_manager import DatabaseManager
from repositories.driver_repository import DriverRepository

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
    items = repo.get_all(limit=page_size, offset=(page - 1) * page_size)
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
    driver = repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return DriverResponse(**driver)


@router.post("/", response_model=Dict[str, int], status_code=201)
def create_driver(
    data: DriverCreate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
):
    driver_id = repo.create(data.model_dump())
    return {"id": driver_id}


@router.patch("/{driver_id}")
def update_driver_partial(
    driver_id: int,
    data: DriverUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
):
    """Partially update a driver (PATCH)."""
    existing = repo.get_by_id(driver_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_fields:
        repo.update(driver_id, update_fields)
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
    existing = repo.get_by_id(driver_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_fields:
        repo.update(driver_id, update_fields)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "updated"}


@router.delete("/{driver_id}")
def delete_driver(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    repo: DriverRepository = Depends(get_driver_repo),
):
    existing = repo.get_by_id(driver_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    repo.delete(driver_id)
    return {"status": "deleted"}


@router.post("/{driver_id}/assign-truck")
def assign_driver_to_truck(
    driver_id: int,
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.driver_truck_service import DriverTruckService
    svc = DriverTruckService(db)
    result = svc.assign_driver_to_truck(driver_id, truck_id)
    return {"status": "assigned", "data": result}


@router.post("/{driver_id}/unassign")
def unassign_driver(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.driver_truck_service import DriverTruckService
    svc = DriverTruckService(db)
    result = svc.unassign_driver(driver_id)
    return {"status": "unassigned", "truck_id": result}


@router.get("/{driver_id}/truck-plate")
def get_driver_truck_plate(
    driver_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.driver_truck_service import DriverTruckService
    svc = DriverTruckService(db)
    plate = svc.get_truck_plate_for_driver(driver_id)
    return {"plate": plate}


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
    if from_date:
        warnings.warn("'from_date' is deprecated, use 'date_from'", DeprecationWarning)
    start = date_from or from_date
    from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
    repo = TachoDriverActivityRepository(db)
    from_date_parsed = _date.fromisoformat(start) if start else _date.min
    rows = repo.get_by_driver(driver_id, date_from=from_date_parsed)
    items = rows[:page_size]
    return PaginatedResponse.from_items(items=items, total=len(rows), page=page, page_size=page_size)
