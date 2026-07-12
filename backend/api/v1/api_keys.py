"""API key management endpoints (admin only).

All routes require the caller to be authenticated as an admin user.
See ``backend.dependencies_security.require_admin``.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_db
from backend.dependencies_security import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("/")
async def list_api_keys(
    partner: Optional[str] = None,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Return all API keys, optionally filtered by partner slug."""
    from repositories.api_key_repository import ApiKeyRepository

    repo = ApiKeyRepository(db)
    keys = repo.list_keys(partner)
    return {"keys": keys, "total": len(keys)}


@router.post("/")
async def create_api_key(
    body: dict,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Create a new API key and return the plaintext key exactly once.

    Required fields in ``body``:
      - ``name`` (str): Human-readable label.
      - ``partner`` (str): Partner slug (e.g. ``"timocom"``).

    Optional fields:
      - ``scopes`` (list[str]): Allowed scopes (default ``[]``).
      - ``created_by`` (int): User ID.
      - ``expires_at`` (str): ISO-8601 expiry timestamp.
    """
    name = body.get("name")
    partner = body.get("partner")
    if not name or not partner:
        raise HTTPException(status_code=422, detail="'name' and 'partner' are required")

    from repositories.api_key_repository import ApiKeyRepository

    repo = ApiKeyRepository(db)
    raw_key, key_id = repo.create_key(
        name=name,
        partner=partner,
        scopes=body.get("scopes", []),
        created_by=body.get("created_by", 0),
        expires_at=body.get("expires_at"),
    )
    return {
        "key": raw_key,
        "id": key_id,
        "warning": "Store this key securely — it will not be shown again",
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Revoke an API key by its id (soft-delete)."""
    from repositories.api_key_repository import ApiKeyRepository

    repo = ApiKeyRepository(db)
    ok = repo.revoke_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found or already revoked")
    return {"status": "revoked", "id": key_id}
