"""Mobile company settings endpoints (blueprint §6.10, Phase 4A).

  - GET  /mobile/settings/company
          -> CompanySettingsOut                    [can_view_company_settings]
        NEVER serializes secret values — ``smtp_password`` / ``tracking_api_key``
        are exposed only as ``*_is_set`` booleans.
  - PATCH /mobile/settings/company {…}             [can_manage_company_settings]
        write-only semantics for secrets: field OMITTED -> unchanged;
        explicit "" -> cleared (``*_is_set`` false); non-empty -> stored
        encrypted via PreferencesManager's sensitive path (is_set true).
  - POST /mobile/settings/test-email {recipient?}  [can_manage_company_settings]
        bounded smtplib send using ``PreferencesManager.get_smtp_config()``.

Settings are stored in the tenant-scoped ``settings`` table
(PK (key, company_id)).  Real key names from the desktop (services/preferences.py
``_SMTP_KEYS``/``_SENSITIVE_KEYS``, ui/views/settings_view) are reused:
``smtp_server``/``smtp_port``/``smtp_user``/``smtp_password``,
``tracking.platform``/``tracking.token``, ``alert_days_ahead``/``tacho_warning``/
``tacho_critical``.  The identity block (legal_name / vat_number / address /
invoice_footer) uses additive keys in the same table so the endpoint stays
tenant-scoped (the desktop keeps legal identity in company_config.json — a
single global file — which is NOT multi-tenant safe for the API; documented).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.schemas.mobile import (
    CompanySettingsOut,
    CompanySettingsUpdateRequest,
    TestEmailRequest,
    TRACKING_API_KEY_KEY,
    TRACKING_PROVIDER_KEY,
)
from database.tenant_context import set_company_context
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["mobile_settings"])

# Secret setting keys — NEVER returned as values, only as ``*_is_set``.
_SECRET_SETTING_KEYS = {"smtp_password", TRACKING_API_KEY_KEY}

_MAINTENANCE_THRESHOLD_KEYS = {
    "maintenance_alert_days_ahead": ("alert_days_ahead", 30),
    "tacho_warning_days": ("tacho_warning", 45),
    "tacho_critical_days": ("tacho_critical", 15),
}


def _check_permission(db: DatabaseManager, user_id: int, permission: str) -> None:
    """Gate with the real PermissionService (imperative, 403)."""
    if not user_id:
        return
    result = getattr(PermissionService(db), permission)(user_id)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Permission denied")


def _safe_int(value: Optional[str], default: int) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _get_company_settings(db: DatabaseManager, company_id: int) -> CompanySettingsOut:
    """Read every company setting; secrets surface only as ``*_is_set``."""
    set_company_context(company_id)
    from services.preferences import PreferencesManager

    prefs = PreferencesManager(db)
    smtp = prefs.get_smtp_config()

    # All read-only fields we need (identity block + tracking provider + thresholds).
    plain_keys = [
        "legal_name", "vat_number", "address", "invoice_footer",
        TRACKING_PROVIDER_KEY,
        "alert_days_ahead", "tacho_warning", "tacho_critical",
    ]
    vals = prefs.get_settings(plain_keys)

    thresholds = {}
    for out_key, (setting_key, default) in _MAINTENANCE_THRESHOLD_KEYS.items():
        thresholds[out_key] = _safe_int(vals.get(setting_key), default)

    return CompanySettingsOut(
        legal_name=vals.get("legal_name", "") or "",
        vat_number=vals.get("vat_number", "") or "",
        address=vals.get("address", "") or "",
        invoice_footer=vals.get("invoice_footer", "") or "",
        smtp_server=smtp.get("smtp_server", "") or "",
        smtp_port=smtp.get("smtp_port", "") or "",
        smtp_user=smtp.get("smtp_user", "") or "",
        smtp_password_is_set=bool(smtp.get("smtp_password")),
        tracking_provider=vals.get(TRACKING_PROVIDER_KEY, "") or "",
        tracking_api_key_is_set=bool(prefs.get_setting(TRACKING_API_KEY_KEY)),
        maintenance_alert_days_ahead=thresholds["maintenance_alert_days_ahead"],
        tacho_warning_days=thresholds["tacho_warning_days"],
        tacho_critical_days=thresholds["tacho_critical_days"],
    )


def _apply_settings_update(
    db: DatabaseManager, company_id: int, data: CompanySettingsUpdateRequest,
) -> None:
    """Write-only PATCH semantics.

    - sensitive keys (smtp_password, tracking_api_key):
        absent -> unchanged; "" -> cleared; else encrypted via PreferencesManager.
    - plain keys: absent -> unchanged; present -> saved verbatim.
    """
    set_company_context(company_id)
    from services.preferences import PreferencesManager

    prefs = PreferencesManager(db)
    payload = data.model_dump(exclude_unset=True)

    # Sensitive fields (write-only — stored encrypted, never read back).
    secret_mappings = {"smtp_password": "smtp_password", "tracking_api_key": TRACKING_API_KEY_KEY}
    for field_name, setting_key in secret_mappings.items():
        if field_name not in payload:
            continue
        value = payload[field_name]
        if value is None:
            continue  # explicit null -> unchanged (write-only semantics)
        prefs.save_setting(setting_key, value if value != "" else "")

    # Plain fields.
    plain_mappings = {
        "legal_name": "legal_name",
        "vat_number": "vat_number",
        "address": "address",
        "invoice_footer": "invoice_footer",
        "smtp_server": "smtp_server",
        "smtp_port": "smtp_port",
        "smtp_user": "smtp_user",
        "tracking_provider": TRACKING_PROVIDER_KEY,
    }
    for field_name, setting_key in plain_mappings.items():
        if field_name in payload and payload[field_name] is not None:
            prefs.save_setting(setting_key, str(payload[field_name]))

    for out_key, (setting_key, _default) in _MAINTENANCE_THRESHOLD_KEYS.items():
        if out_key in payload and payload[out_key] is not None:
            prefs.save_setting(setting_key, str(payload[out_key]))


@router.get("/company", response_model=CompanySettingsOut)
def get_company_settings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Return company settings — secret values are never serialized."""
    _check_permission(db, current_user.get("id") or 0, "can_view_company_settings")
    return _get_company_settings(db, current_user["company_id"])


@router.patch("/company", response_model=CompanySettingsOut)
def patch_company_settings(
    data: CompanySettingsUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update company settings (write-only semantics for secrets)."""
    _check_permission(db, current_user.get("id") or 0, "can_manage_company_settings")
    _apply_settings_update(db, current_user["company_id"], data)
    return _get_company_settings(db, current_user["company_id"])


@router.post("/test-email", status_code=200)
def send_test_email(
    body: TestEmailRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    """Send a plain test email through the configured SMTP settings.

    Uses ``PreferencesManager.get_smtp_config()`` (the same source as the
    desktop email paths).  ``recipient`` defaults to the SMTP user.  Returns
    400/502 with a clear message when SMTP is not configured or the send fails.
    """
    _check_permission(db, current_user.get("id") or 0, "can_manage_company_settings")
    set_company_context(current_user["company_id"])

    from services.preferences import PreferencesManager

    cfg = PreferencesManager(db).get_smtp_config()
    smtp_server = cfg.get("smtp_server") or ""
    smtp_user = cfg.get("smtp_user") or ""
    smtp_password = cfg.get("smtp_password") or ""

    if not smtp_server or not smtp_user:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "smtp_not_configured",
                "detail": "SMTP is not configured (smtp_server and smtp_user are required).",
            },
        )

    recipient = (body.recipient or "").strip().lower() or smtp_user

    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(
        "This is a test email from Operion. If you received this, "
        "your SMTP configuration is working."
    )
    msg["Subject"] = "Operion test email"
    msg["From"] = smtp_user
    msg["To"] = recipient

    try:
        with smtplib.SMTP(smtp_server, int(cfg.get("smtp_port") or 587), timeout=15) as s:
            s.starttls()
            if smtp_password:
                s.login(smtp_user, smtp_password)
            s.sendmail(smtp_user, [recipient], msg.as_string())
    except smtplib.SMTPException as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "smtp_send_failed",
                "detail": f"SMTP send failed: {exc}",
            },
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "smtp_connection_failed",
                "detail": f"Could not connect to SMTP server: {exc}",
            },
        ) from exc

    return {"status": "ok", "detail": f"Test email sent to {recipient}."}
