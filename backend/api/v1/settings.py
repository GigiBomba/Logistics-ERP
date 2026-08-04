import json
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.settings import CompanyConfigUpdateRequest, SettingUpdateRequest
from backend.db import DatabaseManager
from backend.desktop_config import Config
from services.encryption_service import decrypt_value, encrypt_value
from services.preferences import _SENSITIVE_KEYS

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/company")
def get_company_config(
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


@router.patch("/company")
def save_company_config_partial(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    data: CompanyConfigUpdateRequest = Body(...),
):
    """Partially update company configuration (PATCH)."""
    import os
    reports_dir = Config.REPORTS_DIR
    config_path = os.path.join(reports_dir, "company_config.json")
    os.makedirs(reports_dir, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(exclude_unset=True), f, indent=2)
    return {"status": "saved"}


@router.put("/company", deprecated=True)
def save_company_config(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    data: CompanyConfigUpdateRequest = Body(...),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /company instead."""
    import os
    reports_dir = Config.REPORTS_DIR
    config_path = os.path.join(reports_dir, "company_config.json")
    os.makedirs(reports_dir, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(exclude_unset=True), f, indent=2)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "saved"}


@router.get("/{key}")
def get_setting(
    key: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    value = db.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    if key in _SENSITIVE_KEYS:
        value = decrypt_value(value)
    return {"key": key, "value": value}


@router.patch("/{key}")
def save_setting_partial(
    key: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    data: SettingUpdateRequest = Body(...),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update a setting (PATCH)."""
    value = encrypt_value(data.value) if key in _SENSITIVE_KEYS else data.value
    db.save_setting(key, value)
    return {"status": "saved", "key": key, "value": data.value}


@router.put("/{key}", deprecated=True)
def save_setting(
    key: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    data: SettingUpdateRequest = Body(...),
    db: DatabaseManager = Depends(get_db),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /{key} instead."""
    value = encrypt_value(data.value) if key in _SENSITIVE_KEYS else data.value
    db.save_setting(key, value)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "saved", "key": key, "value": data.value}
