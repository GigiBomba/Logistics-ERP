from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=Dict[str, Any])
async def list_alerts(
    limit: int = Query(50, ge=1, le=2000),
    db: DatabaseManager = Depends(get_db),
):
    from services.operations.operations_engine import OperationsEngine
    from services.preferences import PreferencesManager
    prefs = PreferencesManager(db)
    ops = OperationsEngine(db, prefs=prefs)
    alerts = ops.get_active_alerts(limit=limit)
    items = []
    for a in alerts:
        items.append({
            "id": a.id if hasattr(a, 'id') else str(a),
            "type": getattr(a, 'alert_type', a.type if hasattr(a, 'type') else ''),
            "message": getattr(a, 'message', str(a)),
            "status": getattr(a, 'status', 'active'),
        })
    return {"items": items, "total": len(items)}


@router.get("/count")
async def get_alert_count(
    db: DatabaseManager = Depends(get_db),
):
    from services.operations.operations_engine import OperationsEngine
    from services.preferences import PreferencesManager
    prefs = PreferencesManager(db)
    ops = OperationsEngine(db, prefs=prefs)
    return {"count": ops.get_active_alert_count()}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    db: DatabaseManager = Depends(get_db),
):
    from services.operations.operations_engine import OperationsEngine
    from services.preferences import PreferencesManager
    prefs = PreferencesManager(db)
    ops = OperationsEngine(db, prefs=prefs)
    result = ops.resolve_alert(alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "resolved"}
