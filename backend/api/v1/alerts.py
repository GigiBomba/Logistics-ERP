from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.db import DatabaseManager

router = APIRouter(prefix="/alerts", tags=["alerts"])

# ── Alert kind grouping (maintenance-control panel) ─────────────────────
# Maps the panel's coarse groups to the concrete ``AlertType`` values that
# are produced locally by the maintenance/tacho/workflow engines.
_ALERT_KINDS: Dict[str, set[str]] = {
    "tacho": {
        "tachograph_expiry",
        "driver_hours_weekly",
        "driver_hours_daily",
        "compliance_warning",
        "compliance_risk",
        "policy_violation",
    },
    "maintenance": {
        "maintenance",
        "inspection",
        "insurance",
        "inactive_truck",
        "contract_expiry",
        "document_expiry",
    },
    "workflow": {
        "trip_delay",
        "overdue_invoice",
        "route_issue",
    },
}


@router.get("/", response_model=PaginatedResponse[dict])
def list_alerts(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=2000, description="Items per page"),
    kind: str = Query("", description="Filter by group: tacho, maintenance, workflow"),
    db: DatabaseManager = Depends(get_db),
):
    """Return paginated list of active alerts, optionally filtered by kind."""
    company_id = current_user.get("company_id", 0)
    kind_types = _ALERT_KINDS.get(kind) if kind else None
    if kind and kind_types is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid kind '{kind}'. Allowed: {', '.join(sorted(_ALERT_KINDS))}",
        )
    from services.operations.operations_engine import OperationsEngine
    from services.preferences import PreferencesManager
    prefs = PreferencesManager(db)
    ops = OperationsEngine(db, prefs=prefs)
    # Fetch extra rows when filtering so page_size isn't drained by excluded kinds.
    fetch_limit = page_size * 4 if kind_types is not None else page_size
    alerts = ops.get_active_alerts(company_id=company_id, limit=fetch_limit)
    items = []
    for a in alerts:
        if kind_types is not None:
            atype = getattr(a, "alert_type", None)
            if atype is None:
                atype = getattr(a, "type", "")
            atype_val = atype.value if hasattr(atype, "value") else str(atype)
            if atype_val not in kind_types:
                continue
        items.append({
            "id": a.id if hasattr(a, 'id') else str(a),
            "type": getattr(a, 'alert_type', a.type if hasattr(a, 'type') else ''),
            "message": getattr(a, 'message', str(a)),
            "status": getattr(a, 'status', 'active'),
        })
    return PaginatedResponse.from_items(items=items, total=len(items), page=page, page_size=page_size)


@router.get("/count")
def get_alert_count(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    company_id = current_user.get("company_id", 0)
    from services.operations.operations_engine import OperationsEngine
    from services.preferences import PreferencesManager
    prefs = PreferencesManager(db)
    ops = OperationsEngine(db, prefs=prefs)
    return {"count": ops.get_active_alert_count(company_id=company_id)}


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    company_id = current_user.get("company_id", 0)
    from services.operations.operations_engine import OperationsEngine
    from services.preferences import PreferencesManager
    prefs = PreferencesManager(db)
    ops = OperationsEngine(db, prefs=prefs)
    result = ops.resolve_alert(alert_id, company_id=company_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "resolved"}
