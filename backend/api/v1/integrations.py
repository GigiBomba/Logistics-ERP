"""Integration health check endpoints."""
from __future__ import annotations

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends
from backend.dependencies import get_db
from backend.dependencies_security import require_admin, require_dispatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status")
async def integration_status(db=Depends(get_db), _=Depends(require_dispatcher)):
    """Get status of all registered integrations.
    
    Returns connectivity status for each external service partner.
    """
    from services.integration_health_service import IntegrationHealthService
    service = IntegrationHealthService(db)
    return service.get_all_statuses()


@router.get("/status/{integration_name}")
async def integration_detail(integration_name: str, db=Depends(get_db), _=Depends(require_dispatcher)):
    """Get detailed status for a specific integration."""
    from services.integration_health_service import IntegrationHealthService
    service = IntegrationHealthService(db)
    return service.get_status(integration_name)


@router.post("/status/{integration_name}/check")
async def integration_check(integration_name: str, db=Depends(get_db),
                            _=Depends(require_admin)):
    """Force an immediate health check for an integration."""
    from services.integration_health_service import IntegrationHealthService
    service = IntegrationHealthService(db)
    return service.check_now(integration_name)
