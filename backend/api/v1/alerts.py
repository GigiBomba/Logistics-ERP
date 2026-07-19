from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.db import DatabaseManager

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=PaginatedResponse[dict])
def list_alerts(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=2000, description="Items per page"),
    db: DatabaseManager = Depends(get_db),
):
    """Return paginated list of active alerts."""
    company_id = current_user.get("company_id", 0)
    from services.operations.operations_engine import OperationsEngine
    from services.preferences import PreferencesManager
    prefs = PreferencesManager(db)
    ops = OperationsEngine(db, prefs=prefs)
    alerts = ops.get_active_alerts(company_id=company_id, limit=page_size)
    items = []
    for a in alerts:
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
