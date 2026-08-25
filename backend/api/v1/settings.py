from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.settings import CompanyConfigUpdateRequest, SettingUpdateRequest
from backend.db import DatabaseManager
from backend.desktop_config import Config
from services.encryption_service import decrypt_value, encrypt_value
from services.preferences import _SENSITIVE_KEYS

router = APIRouter(prefix="/settings", tags=["settings"])


# ── Fleet-tracking provider config ──────────────────────────────────
# Keys read by ``services.fleet_tracking_service`` from the settings table.
_TRACKING_SETTING_KEYS = [
    "tracking.platform",
    "tracking.token",
    "tracking.host",
    "tracking.username",
    "tracking.password",
    "tracking.account",
    "tracking.positions_path",
    "tracking.lat_field",
    "tracking.lng_field",
    "tracking.id_field",
    "tracking.interval",
    "tracking.enabled",
]

# ``tokens`` payload keys of GET/PUT /settings/tracking (flat setting name =
# ``tracking.<key>``). Credential keys are in ``_SENSITIVE_KEYS`` and are
# therefore encrypted at rest and decrypted on read.
_TRACKING_TOKEN_KEYS = [
    "token", "host", "username", "password", "account",
    "positions_path", "lat_field", "lng_field", "id_field",
]


class TrackingConfigUpdateRequest(BaseModel):
    """Body for PUT /settings/tracking."""

    model_config = {"extra": "forbid"}

    platform: str = ""
    tokens: Dict[str, str] = {}
    interval_seconds: int = 30
    enabled: bool = True


def _parse_tracking_interval(raw: str) -> int:
    try:
        return max(5, int(raw or 30))
    except (TypeError, ValueError):
        return 30


def _parse_tracking_enabled(raw: str) -> bool:
    return str(raw or "1").strip().lower() in ("1", "true", "yes", "on")


@router.get("/tracking")
def get_tracking_config(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return the fleet-tracking provider configuration (decrypted).

    Reads the same ``tracking.*`` settings keys ``FleetTrackingService``
    uses, so remote clients can configure GPS tracking exactly like the
    local settings table path. Missing settings fall back to the
    "not configured" defaults (empty platform → empty tokens).
    """
    # B4: company_id is passed EXPLICITLY — the tenant_context used by
    # db.get_settings is never populated in the HTTP path, so omitting it
    # would leak every company's settings (incl. decrypted credentials).
    values = db.get_settings(
        _TRACKING_SETTING_KEYS,
        company_id=current_user.get("company_id"),
    ) or {}

    def read(key: str, default: str = "") -> str:
        val = values.get(key)
        if val is None:
            return default
        if key in _SENSITIVE_KEYS:
            return decrypt_value(val)
        return val

    tokens = {k: read(f"tracking.{k}") for k in _TRACKING_TOKEN_KEYS}
    return {
        "platform": read("tracking.platform"),
        "tokens": tokens,
        "interval_seconds": _parse_tracking_interval(read("tracking.interval", "30")),
        "enabled": _parse_tracking_enabled(read("tracking.enabled", "1")),
    }


@router.put("/tracking")
def save_tracking_config(
    data: TrackingConfigUpdateRequest = Body(...),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Persist the fleet-tracking provider configuration to the settings table.

    Sensitive credential keys (``tracking.token`` / ``tracking.username`` /
    ``tracking.password`` / ``tracking.account``) are encrypted at rest,
    mirroring the existing ``PATCH /settings/{key}`` behaviour.
    """
    updates: Dict[str, str] = {}
    updates["tracking.platform"] = data.platform
    tokens = data.tokens or {}
    if isinstance(tokens, dict):
        for k in _TRACKING_TOKEN_KEYS:
            v = tokens.get(k)
            if v is not None:
                updates[f"tracking.{k}"] = str(v)
    updates["tracking.interval"] = str(int(data.interval_seconds or 30))
    updates["tracking.enabled"] = "1" if data.enabled else "0"

    for key, value in updates.items():
        stored = encrypt_value(value) if key in _SENSITIVE_KEYS else value
        # B4: explicit company_id — see get_tracking_config.
        db.save_setting(key, stored, company_id=current_user.get("company_id"))
    return {"status": "saved", "keys": sorted(updates.keys())}


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


@router.get("/bulk")
def get_settings_bulk(
    keys: str = Query(..., description="Comma-separated setting keys"),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return multiple settings at once (Phase D — settings sync).

    Company-scoped via the JWT (B4: company_id is passed EXPLICITLY — the
    tenant_context db.get_settings reads is never set in the HTTP path, so
    omitting it would leak every company's settings incl. decrypted SMTP
    credentials).  Missing keys come back as ``None`` (a 404 per key would
    make a multi-key pull need N round-trips).  Sensitive keys (SMTP
    password, fleet tracking credentials) are decrypted like the single-key
    GET.
    """
    key_list = [k.strip() for k in (keys or "").split(",") if k.strip()]
    if not key_list:
        return {"values": {}}
    values = db.get_settings(
        key_list, company_id=current_user.get("company_id"),
    ) or {}

    def read(key: str) -> Any:
        val = values.get(key)
        if val is None:
            return None
        if key in _SENSITIVE_KEYS:
            return decrypt_value(val)
        return val

    return {"values": {k: read(k) for k in key_list}}


@router.get("/{key}")
def get_setting(
    key: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    # B4: explicit company_id (see get_settings_bulk).
    value = db.get_setting(key, company_id=current_user.get("company_id"))
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
    # B4: explicit company_id (see get_settings_bulk).
    db.save_setting(key, value, company_id=current_user.get("company_id"))
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
    # B4: explicit company_id (see get_settings_bulk).
    db.save_setting(key, value, company_id=current_user.get("company_id"))
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "saved", "key": key, "value": data.value}
