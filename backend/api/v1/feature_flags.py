"""Feature flags management API (admin only)."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from services.feature_flags import FeatureFlagService, FEATURE_FLAGS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


@router.get("/")
async def list_flags(db=Depends(get_db), _=Depends(require_admin)):
    service = FeatureFlagService(db)
    return {"flags": service.list_flags()}


@router.get("/{flag_key}")
async def get_flag(flag_key: str, company_id: int = 0, db=Depends(get_db),
                   _=Depends(require_admin)):
    """Get feature flag status.

    Admin-only endpoint. When *company_id* is ``0`` (default) the global
    default is returned; pass a specific company_id to check per-company
    overrides.
    """
    flag = FEATURE_FLAGS.get(flag_key)
    if not flag:
        raise HTTPException(404, f"Unknown flag: {flag_key}")
    service = FeatureFlagService(db)
    return {
        "key": flag.key,
        "enabled": service.is_enabled(flag_key, company_id=company_id),
        "description": flag.description,
        "scope": flag.scope,
    }


@router.post("/{flag_key}/enable")
async def enable_flag(flag_key: str, company_id: int = 0, db=Depends(get_db),
                      _=Depends(require_admin)):
    """Enable a feature flag.

    Admin-only endpoint. When *company_id* is ``0`` (default) the override
    applies globally; pass a specific company_id to override for one
    company only.
    """
    if flag_key not in FEATURE_FLAGS:
        raise HTTPException(404, f"Unknown flag: {flag_key}")
    service = FeatureFlagService(db)
    service.set_override(flag_key, True, company_id=company_id)
    logger.info("Feature flag enabled: %s (company_id=%s)", flag_key, company_id)
    return {"status": "enabled", "flag": flag_key, "company_id": company_id}


@router.post("/{flag_key}/disable")
async def disable_flag(flag_key: str, company_id: int = 0, db=Depends(get_db),
                       _=Depends(require_admin)):
    """Disable a feature flag.

    Admin-only endpoint. When *company_id* is ``0`` (default) the override
    applies globally; pass a specific company_id to override for one
    company only.
    """
    if flag_key not in FEATURE_FLAGS:
        raise HTTPException(404, f"Unknown flag: {flag_key}")
    service = FeatureFlagService(db)
    service.set_override(flag_key, False, company_id=company_id)
    logger.info("Feature flag disabled: %s (company_id=%s)", flag_key, company_id)
    return {"status": "disabled", "flag": flag_key, "company_id": company_id}
