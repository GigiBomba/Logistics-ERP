from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.cache import get_cache
from backend.dependencies import get_db, get_fleet_service
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.fleet import GpsBatchRequest, GpsPing, GpsPosition, TruckResponse
from backend.db import DatabaseManager
from backend.services.fleet_service import FleetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fleet", tags=["fleet"])

# ── GPS batch queue bounds ───────────────────────────────────────────────────
# ``gps:batch:{company_id}`` is drained by the flush task
# (``backend.celery_app.tasks.ocr_tasks.flush_gps_batch_to_postgres``, beat
# every 30 s).  If that worker is down the list would grow forever, so every
# push (a) refreshes a TTL and (b) is skipped once the queue hits a hard cap —
# bounded memory even under a dead-worker / outage window.
GPS_BATCH_TTL_SECONDS = 3600
GPS_BATCH_MAX_LEN = 10000


class TruckListResponse(PaginatedResponse[TruckResponse]):
    """Paginated list of trucks."""


@router.get("/trucks", response_model=TruckListResponse)
def list_trucks(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    service: FleetService = Depends(get_fleet_service),
):
    """Return paginated list of trucks."""
    company_id = current_user.get("company_id", 0)
    trucks = service.get_trucks(company_id=company_id)
    return PaginatedResponse.from_items(
        items=[_truck_to_response(t) for t in trucks],
        total=len(trucks),
        page=page,
        page_size=page_size,
    )


def _truck_to_response(t: dict) -> TruckResponse:
    """Map a trucks-table row to ``TruckResponse``.

    DB columns differ from the schema names (``plate_number`` -> ``plate``,
    ``manufacturer`` -> ``brand``, ``active_status`` -> ``is_active``), and a
    NULL ``year`` must coerce to 0 so one incomplete row can't 422 the whole
    list (``TruckResponse(**row)`` would reject it).  Both naming conventions
    are accepted so mocks and callers using schema-shaped rows keep working.
    """
    return TruckResponse(
        id=t["id"],
        plate=t.get("plate_number") or t.get("plate") or "",
        brand=t.get("manufacturer") or t.get("brand") or "",
        year=t.get("year") or 0,
        is_active=bool(t.get("active_status", t.get("is_active", 1))),
    )


@router.get("/trucks/{truck_id}", response_model=TruckResponse)
def get_truck(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    company_id = current_user.get("company_id", 0)
    truck = service.get_truck(truck_id, company_id=company_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    return _truck_to_response(truck)


@router.post("/trucks", response_model=Dict[str, int])
def create_truck(
    data: dict,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    company_id = current_user.get("company_id", 0)
    truck_id = service.add_truck(data, company_id=company_id)
    return {"id": truck_id}


@router.patch("/trucks/{truck_id}")
def update_truck_partial(
    truck_id: int,
    data: dict,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    """Partially update a truck (PATCH)."""
    company_id = current_user.get("company_id", 0)
    service.update_truck(truck_id, data, company_id=company_id)
    return {"status": "updated"}


@router.put("/trucks/{truck_id}", deprecated=True)
def update_truck(
    truck_id: int,
    data: dict,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /trucks/{truck_id} instead."""
    company_id = current_user.get("company_id", 0)
    service.update_truck(truck_id, data, company_id=company_id)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "updated"}


@router.delete("/trucks/{truck_id}")
def delete_truck(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    company_id = current_user.get("company_id", 0)
    service.delete_truck(truck_id, company_id=company_id)
    return {"status": "deleted"}


@router.post("/gps/ingest", status_code=202)
def ingest_gps_ping(
    ping: GpsPing,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    # Tenant-scoped check: never store a ping for a truck outside the caller's company.
    company_id = current_user.get("company_id", 0)
    truck = service.get_truck(ping.truck_id, company_id=company_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    cache = get_cache()
    key = f"gps:live:{company_id}:{ping.truck_id}"
    cache.set(key, ping.model_dump(), ttl=120)
    batch_key = f"gps:batch:{company_id}"
    # Safety cap (least invasive: never deletes data, just stops appending
    # beyond the cap — the ping's live position is already stored).  The
    # flush worker drains the queue on the next beat and the TTL refresh
    # bounds the key even if that worker is down.  (``isinstance`` guard:
    # ``llen`` returns int on the real RedisCache; mock caches in tests
    # return non-int mocks and must keep taking the normal push path.)
    queue_len = cache.llen(batch_key)
    if isinstance(queue_len, int) and queue_len > GPS_BATCH_MAX_LEN:
        logger.warning(
            "gps:batch:%s length %d exceeds cap %d — skipping rpush",
            company_id, queue_len, GPS_BATCH_MAX_LEN,
        )
    else:
        cache.rpush(batch_key, ping.model_dump_json())
        cache.expire(batch_key, GPS_BATCH_TTL_SECONDS)
    return {"status": "accepted"}


@router.get("/gps/live/{truck_id}", response_model=GpsPosition)
def get_live_position(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    # Tenant-scoped check FIRST: never disclose live data for a truck outside
    # the caller's company.
    company_id = current_user.get("company_id", 0)
    truck = service.get_truck(truck_id, company_id=company_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    cache = get_cache()
    data = cache.get(f"gps:live:{company_id}:{truck_id}")
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
def ingest_gps_batch(
    pings: GpsBatchRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: FleetService = Depends(get_fleet_service),
):
    # Tenant-scoped check for EVERY truck in the batch BEFORE storing anything.
    # One bulk IN (...) lookup covers all unique ids; if any id is missing the
    # whole request is rejected so no foreign ping is ever stored.
    company_id = current_user.get("company_id", 0)
    truck_ids = list({ping.truck_id for ping in pings.root})
    owned = service.get_trucks_by_ids(truck_ids, company_id=company_id)
    if len(owned) != len(truck_ids):
        raise HTTPException(status_code=404, detail="Truck not found")
    cache = get_cache()
    batch_key = f"gps:batch:{company_id}"
    # Same bounded-queue guard as the single-ingest endpoint: check the cap
    # once for the whole batch (soft cap — live positions are still written).
    queue_len = cache.llen(batch_key)
    over_cap = isinstance(queue_len, int) and queue_len > GPS_BATCH_MAX_LEN
    if over_cap:
        logger.warning(
            "gps:batch:%s length %d exceeds cap %d — skipping %d rpush(es)",
            company_id, queue_len, GPS_BATCH_MAX_LEN, len(pings.root),
        )
    for ping in pings.root:
        key = f"gps:live:{company_id}:{ping.truck_id}"
        cache.set(key, ping.model_dump(), ttl=120)
        if over_cap:
            continue
        cache.rpush(batch_key, ping.model_dump_json())
        cache.expire(batch_key, GPS_BATCH_TTL_SECONDS)
    return {"status": "accepted", "count": len(pings.root)}


@router.get("/gps/history/{truck_id}", response_model=PaginatedResponse[dict])
def get_gps_history(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
    db: DatabaseManager = Depends(get_db),
    service: FleetService = Depends(get_fleet_service),
):
    """Return paginated GPS history for a truck."""
    # Tenant-scoped check FIRST: never read history for a foreign truck.
    company_id = current_user.get("company_id", 0)
    truck = service.get_truck(truck_id, company_id=company_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    rows = db.rows_to_dicts(
        db.execute(
            "SELECT * FROM gps_telemetry WHERE truck_id = ? "
            "AND company_id = ? "
            "ORDER BY recorded_at DESC LIMIT ?",
            (truck_id, company_id, page_size),
        ).fetchall()
    )
    return PaginatedResponse.from_items(items=rows, total=len(rows), page=page, page_size=page_size)
