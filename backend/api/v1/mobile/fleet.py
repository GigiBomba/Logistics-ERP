"""Mobile fleet endpoints (blueprint §6.1).

  - GET    /mobile/fleet                          — paginated, searchable truck list
  - POST   /mobile/fleet                          — create truck            [can_create_vehicle]
  - GET    /mobile/fleet/{truck_id}               — truck detail
  - PATCH  /mobile/fleet/{truck_id}               — update truck            [can_update_vehicle]
  - DELETE /mobile/fleet/{truck_id}               — SOFT delete (status='Inactive') [can_delete_vehicle — admin-only]
  - GET    /mobile/fleet/{truck_id}/maintenance   — maintenance records for a truck
  - POST   /mobile/fleet/{truck_id}/maintenance   — record maintenance      [can_schedule_maintenance — admin+manager only]

Every handler is company-scoped (404 for another company's truck).  The first
business-logic line of every mutation is the PermissionService gate (403 on
denial).  Maintenance records map to the existing ``maintenance_records``
table (category ← maintenance_type, vendor ← service_provider); the table was
found in ``database/schema.py`` (TABLE_MAINTENANCE_RECORDS) so no new table
was created.

NOTE (§8.3 vs real code): blueprint §8.3 implies a dispatcher may record
maintenance, but the REAL ``PermissionService.can_schedule_maintenance``
matrix is admin + manager only — real code wins; dispatcher is 403 here.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.mobile import (
    MaintenanceCreateRequest,
    MaintenanceRecordOut,
    MobileTruckCreate,
    MobileTruckOut,
    MobileTruckUpdate,
)
from repositories.fleet_repository import FleetRepository
from services.permission_service import PermissionService

router = APIRouter(prefix="/fleet", tags=["mobile_fleet"])


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


def _get_truck_or_404(repo: FleetRepository, truck_id: int, company_id: int) -> Dict[str, Any]:
    truck = repo.get_by_id(truck_id, company_id=company_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    return truck


def _to_truck_out(
    row: Dict[str, Any],
    db: DatabaseManager,
    company_id: int,
    health_scores: Dict[int, int] | None = None,
    assignments: Dict[int, int] | None = None,
) -> dict:
    truck_id = row["id"]
    if health_scores is None:
        health = db.execute(
            "SELECT score FROM truck_health_scores WHERE truck_id = ?", (truck_id,)
        ).fetchone()
        health_scores = {truck_id: health["score"]} if health else {}
    if assignments is None:
        a = db.execute(
            "SELECT driver_id FROM driver_truck_assignments "
            "WHERE truck_id = ? AND active = 1",
            (truck_id,),
        ).fetchone()
        assignments = {truck_id: a["driver_id"]} if a else {}
    return {
        "id": truck_id,
        "company_id": row.get("company_id") or company_id,
        "plate": row.get("plate_number") or "",
        "brand": row.get("manufacturer") or "",
        "model": row.get("model") or "",
        "vin": row.get("vin") or "",
        "year": row.get("year"),
        "status": row.get("status") or "",
        "health_score": health_scores.get(truck_id),
        "current_driver_id": assignments.get(truck_id),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@router.get("", response_model=PaginatedResponse[MobileTruckOut])
def list_fleet(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str = Query("", description="LIKE filter on plate/model/manufacturer"),
    status: str = Query("", description="Exact match on real truck status"),
):
    """Paginated, company-scoped truck list with optional search + status filter."""
    company_id = current_user["company_id"]
    conditions = ["company_id = ?"]
    params: list = [company_id]
    if status:
        conditions.append("status = ?")
        params.append(status)
    if search:
        like = f"%{search}%"
        conditions.append("(plate_number LIKE ? OR model LIKE ? OR manufacturer LIKE ?)")
        params.extend([like, like, like])
    where = " AND ".join(conditions)

    cnt = db.execute(
        f"SELECT COUNT(*) AS cnt FROM trucks WHERE {where}", tuple(params)
    ).fetchone()
    total = cnt["cnt"] if cnt else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM trucks WHERE {where} ORDER BY plate_number ASC LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    ).fetchall()

    truck_ids = [r["id"] for r in rows]
    health_scores: Dict[int, int] = {}
    assignments: Dict[int, int] = {}
    if truck_ids:
        in_clause = ", ".join(["?"] * len(truck_ids))
        for h in db.execute(
            f"SELECT truck_id, score FROM truck_health_scores WHERE truck_id IN ({in_clause})",
            tuple(truck_ids),
        ).fetchall():
            health_scores[h["truck_id"]] = h["score"]
        for a in db.execute(
            f"SELECT truck_id, driver_id FROM driver_truck_assignments "
            f"WHERE truck_id IN ({in_clause}) AND active = 1",
            tuple(truck_ids),
        ).fetchall():
            assignments[a["truck_id"]] = a["driver_id"]

    items = [
        _to_truck_out(dict(r), db, company_id, health_scores, assignments) for r in rows
    ]
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("", response_model=MobileTruckOut, status_code=201)
def create_truck(
    data: MobileTruckCreate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a company-scoped truck (gate: can_create_vehicle)."""
    _check_permission(db, current_user.get("id") or 0, "can_create_vehicle")
    company_id = current_user["company_id"]
    repo = FleetRepository(db)
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    truck_id = repo.create(fields, company_id=company_id)
    return _to_truck_out(_get_truck_or_404(repo, truck_id, company_id), db, company_id)


@router.get("/{truck_id}", response_model=MobileTruckOut)
def get_truck(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Company-scoped truck detail (404 for missing / other-company trucks)."""
    company_id = current_user["company_id"]
    return _to_truck_out(_get_truck_or_404(FleetRepository(db), truck_id, company_id), db, company_id)


@router.patch("/{truck_id}", response_model=MobileTruckOut)
def update_truck(
    truck_id: int,
    data: MobileTruckUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update a truck (gate: can_update_vehicle)."""
    _check_permission(db, current_user.get("id") or 0, "can_update_vehicle")
    company_id = current_user["company_id"]
    repo = FleetRepository(db)
    _get_truck_or_404(repo, truck_id, company_id)
    fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if fields:
        repo.update(truck_id, fields, company_id=company_id)
    return _to_truck_out(_get_truck_or_404(repo, truck_id, company_id), db, company_id)


@router.delete("/{truck_id}", status_code=204)
def delete_truck(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """SOFT-delete a truck (status='Inactive') — gate: can_delete_vehicle (admin-only)."""
    _check_permission(db, current_user.get("id") or 0, "can_delete_vehicle")
    company_id = current_user["company_id"]
    repo = FleetRepository(db)
    _get_truck_or_404(repo, truck_id, company_id)
    repo.update(truck_id, {"status": "Inactive"}, company_id=company_id)
    return Response(status_code=204)


@router.get("/{truck_id}/maintenance", response_model=PaginatedResponse[MaintenanceRecordOut])
def list_maintenance(
    truck_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Company-scoped maintenance records for a truck (404 if truck is not theirs)."""
    company_id = current_user["company_id"]
    repo = FleetRepository(db)
    _get_truck_or_404(repo, truck_id, company_id)

    cnt = db.execute(
        "SELECT COUNT(*) AS cnt FROM maintenance_records WHERE truck_id = ? AND company_id = ?",
        (truck_id, company_id),
    ).fetchone()
    total = cnt["cnt"] if cnt else 0
    offset = (page - 1) * page_size
    rows = db.execute(
        "SELECT * FROM maintenance_records WHERE truck_id = ? AND company_id = ? "
        "ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
        (truck_id, company_id, page_size, offset),
    ).fetchall()
    items = [
        MaintenanceRecordOut(
            id=r["id"],
            truck_id=r["truck_id"],
            date=r["date"] or "",
            category=r["maintenance_type"] or "",
            cost=r["cost"],
            vendor=r["service_provider"] or "",
            notes=r["notes"] or "",
        )
        for r in (dict(r) for r in rows)
    ]
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("/{truck_id}/maintenance", response_model=MaintenanceRecordOut, status_code=201)
def create_maintenance(
    truck_id: int,
    data: MaintenanceCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Record maintenance for a truck (gate: can_schedule_maintenance — admin+manager only)."""
    _check_permission(db, current_user.get("id") or 0, "can_schedule_maintenance")
    company_id = current_user["company_id"]
    repo = FleetRepository(db)
    _get_truck_or_404(repo, truck_id, company_id)

    record_id = repo.add_maintenance_record(
        truck_id=truck_id,
        maint_type=data.category,
        date=data.date,
        cost=data.cost,
        notes=data.notes,
        provider=data.vendor,
        company_id=company_id,
    )
    row = db.execute(
        "SELECT * FROM maintenance_records WHERE id = ? AND company_id = ?",
        (record_id, company_id),
    ).fetchone()
    row = dict(row) if row else {"id": record_id, "truck_id": truck_id, "date": data.date,
                                 "maintenance_type": data.category, "cost": data.cost,
                                 "service_provider": data.vendor, "notes": data.notes}
    return MaintenanceRecordOut(
        id=row["id"],
        truck_id=row["truck_id"],
        date=row["date"] or "",
        category=row["maintenance_type"] or "",
        cost=row["cost"],
        vendor=row["service_provider"] or "",
        notes=row["notes"] or "",
    )
