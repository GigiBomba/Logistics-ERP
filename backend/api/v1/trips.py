import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.dependencies import get_db, get_trip_service
from backend.schemas.trip import TripResponse
from config import Config
from database.db_manager import DatabaseManager
from services.trip_service import TripService

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("/", response_model=Dict[str, Any])
async def list_trips(
    search: str = Query("", description="Search query"),
    status: str = Query("", description="Status filter"),
    limit: int = Query(200, ge=1, le=1000),
    service: TripService = Depends(get_trip_service),
):
    items = service.get_filtered(search=search, status=status, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
):
    trip = service.get_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripResponse(**trip)


@router.post("/", response_model=Dict[str, int])
async def create_trip(
    data: Dict[str, Any],
    service: TripService = Depends(get_trip_service),
):
    trip_id = service.add(data)
    return {"id": trip_id}


@router.put("/{trip_id}")
async def update_trip(
    trip_id: int,
    data: Dict[str, Any],
    service: TripService = Depends(get_trip_service),
):
    service.update(trip_id, data)
    return {"status": "updated"}


@router.delete("/{trip_id}")
async def delete_trip(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
):
    service.delete(trip_id)
    return {"status": "deleted"}


@router.post("/conflicts/check")
async def check_trip_conflicts(
    data: Dict[str, Any],
    db: DatabaseManager = Depends(get_db),
):
    from services.conflict_service import TripConflictService
    svc = TripConflictService(db)
    conflicts = svc.check_conflicts(data)
    return {"conflicts": conflicts}


@router.get("/{trip_id}/export/pdf", response_class=FileResponse)
async def export_trip_pdf(
    trip_id: int,
    db: DatabaseManager = Depends(get_db),
):
    from services.export_service import ExportService
    svc = ExportService()
    trip = TripService(db).get_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    os.makedirs(Config.REPORTS_DIR, exist_ok=True)
    path = svc.generate_pdf([trip], filename=os.path.join(Config.REPORTS_DIR, f"trip_{trip_id}.pdf"))
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="PDF generation failed")
    return FileResponse(path, filename=f"trip_{trip_id}.pdf", media_type="application/pdf")


@router.get("/{trip_id}/export/xlsx", response_class=FileResponse)
async def export_trip_excel(
    trip_id: int,
    db: DatabaseManager = Depends(get_db),
):
    from services.export_service import ExportService
    svc = ExportService()
    trip = TripService(db).get_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    os.makedirs(Config.REPORTS_DIR, exist_ok=True)
    path = svc.generate_excel([trip], filename=os.path.join(Config.REPORTS_DIR, f"trip_{trip_id}.xlsx"))
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail="Excel generation failed")
    return FileResponse(path, filename=f"trip_{trip_id}.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
