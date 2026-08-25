"""SLO/SLA status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from backend.dependencies_security import require_admin
from backend.services.slo_service import get_slo_service

router = APIRouter(tags=["slo"])


@router.get("/slo/report")
async def slo_report(_=Depends(require_admin)):
    """Get detailed SLO report (admin only)."""
    slo = get_slo_service()
    return slo.get_report()


@router.get("/status")
async def public_status():
    """Public status page — no auth required."""
    slo = get_slo_service()
    return slo.get_status_page()
