from datetime import date as _date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db, get_driver_repo
from backend.schemas.driver import DriverCreate, DriverResponse, DriverUpdate
from database.db_manager import DatabaseManager
from repositories.driver_repository import DriverRepository

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("/", response_model=Dict[str, Any])
async def list_drivers(
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: DriverRepository = Depends(get_driver_repo),
):
    items = repo.get_all(limit=limit, offset=offset)
    return {"items": items, "total": len(items)}


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(
    driver_id: int,
    repo: DriverRepository = Depends(get_driver_repo),
):
    driver = repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return DriverResponse(**driver)


@router.post("/", response_model=Dict[str, int], status_code=201)
async def create_driver(
    data: DriverCreate,
    repo: DriverRepository = Depends(get_driver_repo),
):
    driver_id = repo.create(data.model_dump())
    return {"id": driver_id}


@router.put("/{driver_id}")
async def update_driver(
    driver_id: int,
    data: DriverUpdate,
    repo: DriverRepository = Depends(get_driver_repo),
):
    existing = repo.get_by_id(driver_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_fields:
        repo.update(driver_id, update_fields)
    return {"status": "updated"}


@router.delete("/{driver_id}")
async def delete_driver(
    driver_id: int,
    repo: DriverRepository = Depends(get_driver_repo),
):
    existing = repo.get_by_id(driver_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Driver not found")
    repo.delete(driver_id)
    return {"status": "deleted"}


@router.post("/{driver_id}/assign-truck")
async def assign_driver_to_truck(
    driver_id: int,
    truck_id: int,
    db: DatabaseManager = Depends(get_db),
):
    from services.driver_truck_service import DriverTruckService
    svc = DriverTruckService(db)
    result = svc.assign_driver_to_truck(driver_id, truck_id)
    return {"status": "assigned", "data": result}


@router.post("/{driver_id}/unassign")
async def unassign_driver(
    driver_id: int,
    db: DatabaseManager = Depends(get_db),
):
    from services.driver_truck_service import DriverTruckService
    svc = DriverTruckService(db)
    result = svc.unassign_driver(driver_id)
    return {"status": "unassigned", "truck_id": result}


@router.get("/{driver_id}/truck-plate")
async def get_driver_truck_plate(
    driver_id: int,
    db: DatabaseManager = Depends(get_db),
):
    from services.driver_truck_service import DriverTruckService
    svc = DriverTruckService(db)
    plate = svc.get_truck_plate_for_driver(driver_id)
    return {"plate": plate}


@router.get("/{driver_id}/tacho-activity")
async def get_driver_tacho_activity(
    driver_id: int,
    from_date: str = Query(""),
    limit: int = Query(100, ge=1, le=500),
    db: DatabaseManager = Depends(get_db),
):
    from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
    repo = TachoDriverActivityRepository(db)
    from_date_parsed = _date.fromisoformat(from_date) if from_date else _date.min
    rows = repo.get_by_driver(driver_id, from_date=from_date_parsed)
    return {"items": rows[:limit], "total": len(rows)}
