from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.route import RouteResponse
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("/history", response_model=Dict[str, Any])
async def list_route_history(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    limit: int = Query(50, ge=1, le=500),
    db: DatabaseManager = Depends(get_db),
):
    try:
        from repositories.route_repository import RouteRepository
        repo = RouteRepository(db)
        rows = repo.get_all(limit=limit)
        return {"items": rows, "total": len(rows)}
    except Exception as exc:
        return {"items": [], "total": 0, "error": str(exc)}


@router.get("/history/statistics")
async def get_route_statistics(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.route_history_service import RouteHistoryService
    svc = RouteHistoryService(db)
    stats = svc.get_statistics()
    return {"data": stats}


@router.get("/history/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from repositories.route_repository import RouteRepository
    repo = RouteRepository(db)
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteResponse(**route)


@router.post("/calculate")
async def calculate_route(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.route_service import RouteService

    points = data.get("points", [])
    if not points or len(points) < 2:
        raise HTTPException(status_code=400, detail="At least 2 points (start + end) are required")

    profile = data.get("profile", "truck")
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

        result = route_svc.calculate_route(stops=geocoded, profile=profile, stops_are_coordinates=True)
        return {"status": "ok", "route": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/history/{route_id}/duplicate")
async def duplicate_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.route_history_service import RouteHistoryService
    svc = RouteHistoryService(db)
    status = svc.duplicate_route(route_id)
    return {"status": "duplicated", "new_route_id": status}


@router.post("/history/{route_id}/archive")
async def archive_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from repositories.route_repository import RouteRepository
    repo = RouteRepository(db)
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    repo.archive(route_id)
    return {"status": "archived"}


@router.delete("/history/{route_id}")
async def delete_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from repositories.route_repository import RouteRepository
    repo = RouteRepository(db)
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    repo.delete(route_id)
    return {"status": "deleted"}


@router.get("/history/{route_id}/export")
async def export_route(
    route_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    fmt: str = Query("json", pattern="^(json|csv)$"),
    db: DatabaseManager = Depends(get_db),
):
    from repositories.route_repository import RouteRepository
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
