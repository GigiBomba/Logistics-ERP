import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse

from backend.dependencies import get_db, get_trip_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.trip import (
    TripConflictCheckRequest,
    TripCreateRequest,
    TripResponse,
    TripUpdateRequest,
)
from config import Config
from database.db_manager import DatabaseManager
from services.trip_service import TripService

from backend.dependencies_security import require_dispatcher

router = APIRouter(prefix="/trips", tags=["trips"])


class TripListResponse(PaginatedResponse[TripResponse]):
    """Paginated list of trips."""


@router.get("/", response_model=TripListResponse)
def list_trips(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    search: str = Query("", description="Search query"),
    status: str = Query("", description="Status filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    service: TripService = Depends(get_trip_service),
):
    """Return paginated list of trips."""
    items = service.get_filtered(search=search, status=status, limit=page_size)
    return PaginatedResponse.from_items(
        items=[TripResponse(**t) for t in items],
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
):
    trip = service.get_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripResponse(**trip)


@router.post("/", response_model=Dict[str, int])
def create_trip(
    data: TripCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
):
    trip_id = service.add(data.model_dump(exclude_unset=True))
    return {"id": trip_id}


@router.patch("/{trip_id}")
def update_trip_partial(
    trip_id: int,
    data: TripUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
):
    """Partially update a trip (PATCH)."""
    service.update(trip_id, data.model_dump(exclude_unset=True))
    return {"status": "updated"}


@router.put("/{trip_id}", deprecated=True)
def update_trip(
    trip_id: int,
    data: TripUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /{trip_id} instead."""
    service.update(trip_id, data.model_dump(exclude_unset=True))
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "updated"}


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: TripService = Depends(get_trip_service),
):
    service.delete(trip_id)
    return {"status": "deleted"}


@router.post("/conflicts/check")
def check_trip_conflicts(
    data: TripConflictCheckRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.conflict_service import TripConflictService
    svc = TripConflictService(db)
    conflicts = svc.check_conflicts(data.model_dump(exclude_unset=True))
    return {"conflicts": conflicts}


@router.get("/{trip_id}/documents")
def list_trip_documents(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List all documents linked to a trip (document_links + documents_attached)."""
    from services.document_automation.package_builder import PackageBuilder

    docs = PackageBuilder(db).list_trip_documents(trip_id)
    return {"items": docs, "total": len(docs)}


@router.get("/{trip_id}/package/zip", response_class=FileResponse)
def download_package_zip(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Download all trip documents as a ZIP archive."""
    import tempfile

    from services.document_automation.package_builder import PackageBuilder

    output_dir = os.path.join(tempfile.gettempdir(), "operion_packages")
    path = PackageBuilder(db).build_zip(trip_id, output_dir)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="No documents to package")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/zip")


@router.get("/{trip_id}/package/pdf", response_class=FileResponse)
def download_package_pdf(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Download all trip documents merged into a single PDF with cover page."""
    import tempfile

    from services.document_automation.package_builder import PackageBuilder

    output_dir = os.path.join(tempfile.gettempdir(), "operion_packages")
    path = PackageBuilder(db).build_combined_pdf(trip_id, output_dir)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="No PDF documents to merge")
    return FileResponse(path, filename=os.path.basename(path), media_type="application/pdf")


@router.get("/{trip_id}/export/pdf", response_class=FileResponse)
def export_trip_pdf(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
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
def export_trip_excel(
    trip_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
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
