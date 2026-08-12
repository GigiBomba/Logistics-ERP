"""License management endpoints.

GET    /api/v1/licenses                  — List company licenses.
GET    /api/v1/licenses/:id             — Get a single license.
GET    /api/v1/licenses/:id/devices     — Devices activated under a license.
DELETE /api/v1/licenses/:id/devices/:deviceId — Remove a device from a license.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.errors import ErrorCode
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.get("")
def list_licenses(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return all licenses for the current user's company."""
    company_id = current_user.get("company_id")
    if not company_id:
        return []

    rows = db.execute(
        "SELECT id, license_key, plan_tier, status, seats, seats_used, "
        "issued_at, expires_at, created_at "
        "FROM licenses WHERE company_id = ? "
        "ORDER BY created_at DESC",
        (company_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{license_id}")
def get_license(
    license_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return a single license by ID."""
    company_id = current_user.get("company_id")

    row = db.execute(
        "SELECT id, license_key, plan_tier, status, seats, seats_used, "
        "issued_at, expires_at, created_at "
        "FROM licenses WHERE id = ? AND company_id = ?",
        (license_id, company_id),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "License not found.",
            },
        )
    return dict(row)


@router.get("/{license_id}/devices")
def list_license_devices(
    license_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return devices activated under a license."""
    company_id = current_user.get("company_id")

    # Verify license belongs to company
    lic = db.execute(
        "SELECT id FROM licenses WHERE id = ? AND company_id = ?",
        (license_id, company_id),
    ).fetchone()
    if not lic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "License not found.",
            },
        )

    rows = db.execute(
        "SELECT id, name, os, ip, last_seen, activated_at "
        "FROM license_devices WHERE license_id = ? "
        "ORDER BY last_seen DESC",
        (license_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.delete("/{license_id}/devices/{device_id}")
def remove_license_device(
    license_id: int,
    device_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Remove a device from a license."""
    company_id = current_user.get("company_id")

    lic = db.execute(
        "SELECT id FROM licenses WHERE id = ? AND company_id = ?",
        (license_id, company_id),
    ).fetchone()
    if not lic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "License not found.",
            },
        )

    cursor = db.execute(
        "DELETE FROM license_devices WHERE id = ? AND license_id = ?",
        (device_id, license_id),
    )
    db.commit()

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Device not found.",
            },
        )

    # Decrement seats_used
    db.execute(
        "UPDATE licenses SET seats_used = MAX(0, seats_used - 1) WHERE id = ?",
        (license_id,),
    )
    db.commit()

    return {"status": "ok"}
