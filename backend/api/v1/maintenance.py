from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_db
from database.db_manager import DatabaseManager
from repositories.fleet_repository import FleetRepository

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("/summary", response_model=Dict[str, Any])
async def get_maintenance_summary(
    db: DatabaseManager = Depends(get_db),
):
    repo = FleetRepository(db)
    from datetime import timedelta
    since_date = (__import__("datetime").date.today() - timedelta(days=365)).isoformat()
    truck_summary = repo.get_maintenance_truck_summary(since_date)
    cost_monthly = repo.get_maintenance_cost_monthly(since_date)
    return {
        "trucks": truck_summary,
        "cost_monthly": cost_monthly,
        "total_trucks": len(truck_summary),
    }


@router.get("/cost-monthly", response_model=Dict[str, Any])
async def get_maintenance_cost_monthly(
    since: str = Query(""),
    db: DatabaseManager = Depends(get_db),
):
    repo = FleetRepository(db)
    since_date = since or (__import__("datetime").date.today() - __import__("datetime").timedelta(days=365)).isoformat()
    return {"data": repo.get_maintenance_cost_monthly(since_date)}


@router.get("/cost-by-truck-monthly", response_model=Dict[str, Any])
async def get_maintenance_cost_by_truck_monthly(
    since: str = Query(""),
    db: DatabaseManager = Depends(get_db),
):
    repo = FleetRepository(db)
    since_date = since or (__import__("datetime").date.today() - __import__("datetime").timedelta(days=365)).isoformat()
    return {"data": repo.get_maintenance_cost_truck_monthly(since_date)}


@router.get("/truck-summary", response_model=Dict[str, Any])
async def get_maintenance_truck_summary(
    since: str = Query(""),
    db: DatabaseManager = Depends(get_db),
):
    repo = FleetRepository(db)
    since_date = since or (__import__("datetime").date.today() - __import__("datetime").timedelta(days=365)).isoformat()
    return {"data": repo.get_maintenance_truck_summary(since_date)}


@router.get("/top-categories", response_model=Dict[str, Any])
async def get_maintenance_top_categories(
    since: str = Query(""),
    db: DatabaseManager = Depends(get_db),
):
    repo = FleetRepository(db)
    since_date = since or (__import__("datetime").date.today() - __import__("datetime").timedelta(days=365)).isoformat()
    return {"data": repo.get_maintenance_most_expensive_category(since_date)}
