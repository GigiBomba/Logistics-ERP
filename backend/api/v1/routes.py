from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.route import RouteCalculateRequest, RouteResponse
from backend.db import DatabaseManager

router = APIRouter(prefix="/routes", tags=["routes"])


class RouteHistoryListResponse(PaginatedResponse[RouteResponse]):
    """Paginated list of route history."""


@router.get("/history", response_model=RouteHistoryListResponse)
def list_route_history(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: DatabaseManager = Depends(get_db),
):
    """Return paginated list of route history."""
    try:
        from backend.repositories.route_repository import RouteRepository
        repo = RouteRepository(db)
        rows = repo.get_all(limit=page_size)
        return PaginatedResponse.from_items(
            items=[RouteResponse(**r) for r in rows],
            total=len(rows),
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        return PaginatedResponse.from_items(items=[], total=0, page=page, page_size=page_size)


@router.get("/history/statistics")
def get_route_statistics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return route statistics."""
    from backend.services.route_history_service import RouteHistoryService
    svc = RouteHistoryService(db)
    return svc.get_statistics()


@router.get("/history/{route_id}", response_model=RouteResponse)
def get_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.repositories.route_repository import RouteRepository
    repo = RouteRepository(db)
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteResponse(**route)


@router.post("/calculate")
def calculate_route(
    data: RouteCalculateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.services.route_service import RouteService

    points = data.points
    if not points or len(points) < 2:
        raise HTTPException(status_code=400, detail="At least 2 points (start + end) are required")

    profile = data.profile
    route_svc = RouteService()

    try:
        from services.geocode_nominatim import geocode_place

        geocoded = []
        for pt in points:
            if isinstance(pt, dict) and "lat" in pt and "lng" in pt:
                geocoded.append((pt["lat"], pt["lng"]))
            elif isinstance(pt, str):
                coords = geocode_place(pt)
                if coords:
                    geocoded.append(coords)
                else:
                    raise HTTPException(status_code=400, detail=f"Cannot geocode: {pt}")
            else:
                raise HTTPException(status_code=400, detail=f"Invalid point format: {pt}")

        result = route_svc.calculate_route(
            stops=geocoded, profile=profile, stops_are_coordinates=True,
            avoid_countries=data.excluded_countries,
        )
        return {"status": "ok", "route": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/history/{route_id}/duplicate")
def duplicate_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.services.route_history_service import RouteHistoryService
    svc = RouteHistoryService(db)
    status = svc.duplicate_route(route_id)
    return {"status": "duplicated", "new_route_id": status}


@router.post("/history/{route_id}/archive")
def archive_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.repositories.route_repository import RouteRepository
    repo = RouteRepository(db)
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    repo.archive(route_id)
    return {"status": "archived"}


@router.delete("/history/{route_id}")
def delete_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from backend.repositories.route_repository import RouteRepository
    repo = RouteRepository(db)
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    repo.delete(route_id)
    return {"status": "deleted"}


@router.get("/history/{route_id}/export")
def export_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    fmt: str = Query("json", pattern="^(json|csv)$"),
    db: DatabaseManager = Depends(get_db),
):
    from backend.repositories.route_repository import RouteRepository
    repo = RouteRepository(db)
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    if fmt == "json":
        return route
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(route.keys())
    writer.writerow(route.values())
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=output.getvalue(),
                             media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=route_{route_id}.csv"})
