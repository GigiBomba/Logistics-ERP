import json
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from config import Config
from database.db_manager import DatabaseManager

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/company")
async def get_company_config(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
):
    import os
    config_path = os.path.join(
        os.environ.get("OPERION_REPORTS_DIR", ""),
        "company_config.json"
    ) if os.environ.get("OPERION_REPORTS_DIR") else ""
    if config_path and os.path.isfile(config_path):
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


@router.put("/company")
async def save_company_config(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    data: Dict[str, Any] = Body(...),
):
    import os
    reports_dir = Config.REPORTS_DIR
    config_path = os.path.join(reports_dir, "company_config.json")
    os.makedirs(reports_dir, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {"status": "saved"}


@router.get("/{key}")
async def get_setting(
    key: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    value = db.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"key": key, "value": value}


@router.put("/{key}")
async def save_setting(
    key: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    data: Dict[str, str] = Body(...),
    db: DatabaseManager = Depends(get_db),
):
    value = data.get("value", "")
    db.save_setting(key, value)
    return {"status": "saved", "key": key, "value": value}
