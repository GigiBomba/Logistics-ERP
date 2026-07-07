from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from backend.cache import get_cache
from backend.dependencies import get_db, get_fleet_service
from backend.dependencies_security import require_dispatcher
from backend.schemas.fleet import GpsPing, GpsPosition, TruckResponse
from database.db_manager import DatabaseManager
from services.fleet_service import FleetService

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/trucks", response_model=Dict[str, Any])
async def list_trucks(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    trucks = service.get_trucks()
    return {"items": trucks, "total": len(trucks)}


@router.get("/trucks/{truck_id}", response_model=TruckResponse)
async def get_truck(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    truck = service.get_truck(truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    return TruckResponse(**truck)


@router.post("/trucks", response_model=Dict[str, int])
async def create_truck(
    data: dict,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    truck_id = service.add_truck(data)
    return {"id": truck_id}


@router.put("/trucks/{truck_id}")
async def update_truck(
    truck_id: int,
    data: dict,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    service.update_truck(truck_id, data)
    return {"status": "updated"}


@router.delete("/trucks/{truck_id}")
async def delete_truck(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    service.delete_truck(truck_id)
    return {"status": "deleted"}


@router.post("/gps/ingest", status_code=202)
async def ingest_gps_ping(
    ping: GpsPing,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
):
    cache = get_cache()
    key = f"gps:live:{ping.truck_id}"
    cache.set(key, ping.model_dump(), ttl=120)
    cache.rpush("gps:batch_queue", ping.model_dump_json())
    return {"status": "accepted"}


@router.get("/gps/live/{truck_id}", response_model=GpsPosition)
async def get_live_position(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
):
    cache = get_cache()
    data = cache.get(f"gps:live:{truck_id}")
    if data:
        return GpsPosition(
            truck_id=data["truck_id"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            speed_kmh=data.get("speed_kmh", 0),
            heading=data.get("heading", 0),
            recorded_at=data.get("timestamp", ""),
            driver_id=data.get("driver_id"),
        )
    raise HTTPException(status_code=404, detail="No live data for this truck")


@router.post("/gps/batch", status_code=202)
async def ingest_gps_batch(
    pings: List[GpsPing],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
):
    cache = get_cache()
    for ping in pings:
        key = f"gps:live:{ping.truck_id}"
        cache.set(key, ping.model_dump(), ttl=120)
        cache.rpush("gps:batch_queue", ping.model_dump_json())
    return {"status": "accepted", "count": len(pings)}


@router.get("/gps/history/{truck_id}")
async def get_gps_history(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    limit: int = 100,
    db: DatabaseManager = Depends(get_db),
):
    rows = db.rows_to_dicts(
        db.conn.execute(
            "SELECT * FROM gps_telemetry WHERE truck_id = ? "
            "ORDER BY recorded_at DESC LIMIT ?",
            (truck_id, limit),
        ).fetchall()
    )
    return {"items": rows, "total": len(rows)}
