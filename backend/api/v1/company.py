"""Company information endpoints.

GET  /api/v1/company  — Return the current user's company profile.
PATCH /api/v1/company — Partially update company profile fields.
"""
from __future__ import annotations


import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.errors import ErrorCode
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/company", tags=["company"])


# ── Helper: map settings table keys to frontend Company fields ─────────
_EXTENDED_FIELDS = [
    ("vat_number", "company_vat"),
    ("address", "company_address"),
    ("city", "company_city"),
    ("country", "company_country"),
    ("postal_code", "company_postal_code"),
    ("phone", "company_phone"),
    ("website", "company_website"),
    ("logo_url", "company_logo_url"),
    ("industry", "company_industry"),
]


def _get_company(db: DatabaseManager, company_id: int) -> Dict[str, Any]:
    """Read company DB row and merge extended settings fields."""
    row = db.execute(
        "SELECT id, company_name, subscription_tier, is_active, created_at, updated_at "
        "FROM companies WHERE id = ?",
        (company_id,),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Company not found.",
            },
        )

    company = dict(row)

    # Merge extended fields from the settings table
    setting_keys = [sk for _, sk in _EXTENDED_FIELDS]
    stored = db.get_settings(setting_keys) if setting_keys else {}

    for field_name, setting_key in _EXTENDED_FIELDS:
        company[field_name] = stored.get(setting_key)

    # Add a `name` alias for `company_name` (frontend uses both)
    company["name"] = company["company_name"]

    return company


def _update_company(
    db: DatabaseManager,
    company_id: int,
    data: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    """Update company DB row and extended settings table fields.

    Only the fields present in *data* are updated.  A full company
    profile is returned after the update.
    """
    # ── Separate DB core fields from extended (settings-table) fields ──
    db_updates: Dict[str, Any] = {}
    setting_updates: Dict[str, Optional[str]] = {}

    core_fields = {"company_name"}

    for key, value in data.items():
        if value is None:
            continue
        if key == "name":
            db_updates["company_name"] = value
        elif key in core_fields:
            db_updates[key] = value
        else:
            # Map frontend field names to settings table keys
            setting_key = next(
                (sk for fn, sk in _EXTENDED_FIELDS if fn == key),
                None,
            )
            if setting_key:
                setting_updates[setting_key] = value

    # ── Apply DB updates ─────────────────────────────────────────────
    if db_updates:
        set_clause = ", ".join(f"{col} = ?" for col in db_updates)
        values = tuple(db_updates.values()) + (company_id,)
        db.execute(
            f"UPDATE companies SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )

    # ── Apply settings-table updates ─────────────────────────────────
    for setting_key, value in setting_updates.items():
        if value is not None:
            db.save_setting(setting_key, value)

    db.commit()

    return _get_company(db, company_id)


# ═══════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.get("")
def get_company(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return the current user's company profile.

    Combines core company data from the ``companies`` table with
    extended fields (address, VAT, phone, etc.) from the ``settings``
    table.
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "No company associated with this account.",
            },
        )
    return _get_company(db, company_id)


@router.patch("")
def update_company(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update the current user's company profile.

    Accepts any subset of Company fields:
      name, company_name, vat_number, address, city, country,
      postal_code, phone, website, logo_url, industry

    Core fields update the ``companies`` table; extended fields
    update the ``settings`` table.
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "No company associated with this account.",
            },
        )
    return _update_company(db, company_id, data)
