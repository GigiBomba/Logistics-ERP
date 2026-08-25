"""Prometheus metrics endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from backend.dependencies_security import require_admin
from backend.metrics import get_metrics_response

router = APIRouter(tags=["metrics"])

@router.get("/metrics")
async def metrics(_=Depends(require_admin)):
    """Prometheus metrics endpoint."""
    return get_metrics_response()
