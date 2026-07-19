"""Freight Exchange API endpoints -- REST interface for the freight exchange subsystem.

All endpoints enforce multi-tenant isolation: ``company_id`` is derived
from the JWT, never trusted from the client request body.
"""
import logging
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.db import DatabaseManager
from models.freight_exchange_models import (
    GeoFilter,
    LoadSearchFilters,
    ProviderCredentials,
)
from services.freight_exchange.connection_manager import ConnectionManagerService
from services.freight_exchange.evaluation import EvaluationEngineService
from services.freight_exchange.fleet_matcher import FleetMatcherService
from services.freight_exchange.import_pipeline import ImportError, ImportPipelineService
from services.freight_exchange.search import SearchEngineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/freight", tags=["freight_exchange"])

# ── Schemas ────────────────────────────────────────────────────────────────
# Minimal request/response Pydantic models for the API layer.
# Full domain models live in models/freight_exchange_models.py;
# these are the API contracts only.

from pydantic import BaseModel, Field


class ConnectProviderRequest(BaseModel):
    provider_id: str
    client_id: str
    client_secret: str
    scope: list[str] = []


class SearchRequest(BaseModel):
    origin_location: str = Field(..., description="Loading place")
    origin_radius_km: float = Field(50.0, ge=0, description="Loading radius (km)")
    destination_location: str = Field(..., description="Unloading place")
    destination_radius_km: float = Field(30.0, ge=0, description="Unloading radius (km)")
    pickup_date_from: str = Field(..., description="Pickup date from (ISO date)")
    pickup_date_to: str = Field(..., description="Pickup date to (ISO date)")
    delivery_date_from: Optional[str] = None
    delivery_date_to: Optional[str] = None
    trailer_type: Optional[list[str]] = None
    adr_required: Optional[bool] = None
    weight_kg_min: Optional[float] = None
    weight_kg_max: Optional[float] = None
    price_min: Optional[float] = None
    distance_km_max: Optional[float] = None
    provider_ids: Optional[list[str]] = None
    loading_type: Optional[str] = None
    loading_country: Optional[str] = None
    delivery_country: Optional[str] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"
    min_trucks: Optional[int] = None


class SaveSearchRequest(BaseModel):
    label: str
    filters: dict
    provider_ids: Optional[list[str]] = None


class ConnectTransEuRequest(BaseModel):
    """Request to connect a user's Trans.eu account via OAuth authorization_code."""
    authorization_code: str
    redirect_uri: str


# ═══════════════════════════════════════════════════════════════════════════
# Provider Management
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/providers")
async def list_providers(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List all connected providers with status and capabilities."""
    company_id = current_user["company_id"]
    conn_mgr = ConnectionManagerService(db)
    providers = conn_mgr.list_connected_providers(company_id)
    return {"providers": providers}


@router.post("/providers/connect")
async def connect_provider(
    body: ConnectProviderRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Connect to a freight exchange provider."""
    company_id = current_user["company_id"]
    conn_mgr = ConnectionManagerService(db)

    credentials = ProviderCredentials(
        company_id=company_id,
        provider_id=body.provider_id,
        client_id=body.client_id,
        client_secret_encrypted=body.client_secret,
        scope=body.scope,
    )

    try:
        result = await conn_mgr.connect_provider(company_id, body.provider_id, credentials)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to connect to %s: %s", body.provider_id, e)
        raise HTTPException(status_code=500, detail=f"Connection failed: {e}")


@router.post("/providers/{provider_id}/disconnect")
async def disconnect_provider(
    provider_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Disconnect from a freight exchange provider."""
    company_id = current_user["company_id"]
    conn_mgr = ConnectionManagerService(db)
    await conn_mgr.disconnect_provider(company_id, provider_id)
    return {"status": "disconnected", "provider_id": provider_id}


@router.post("/providers/{provider_id}/test")
async def test_provider_connection(
    provider_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Test the connection to a freight exchange provider."""
    company_id = current_user["company_id"]
    conn_mgr = ConnectionManagerService(db)
    health = await conn_mgr.test_connection(company_id, provider_id)
    if health is None:
        raise HTTPException(status_code=404, detail="No active connection found")
    return health.model_dump(mode="json")


@router.post("/providers/connect_trans_eu")
async def connect_trans_eu(
    body: ConnectTransEuRequest,
    current_user: dict = Depends(require_dispatcher),
    db=Depends(get_db),
):
    """Connect current user to Trans.eu via OAuth authorization_code.

    Exchanges the authorization_code for access + refresh tokens,
    stores them encrypted, and returns connection status.
    """
    from services.freight_exchange.adapters.trans_eu import TransEuAdapter
    from backend.config import BackendSettings

    settings = BackendSettings()
    company_id = current_user["company_id"]
    user_id = current_user["user_id"]

    conn_mgr = ConnectionManagerService(db)

    # Build credentials using app-level config
    creds = ProviderCredentials(
        company_id=company_id,
        provider_id="trans_eu",
        client_id=getattr(settings, "trans_eu_client_id", ""),
        client_secret_encrypted=getattr(settings, "trans_eu_client_secret", ""),
        grant_type="authorization_code",
        authorization_code=body.authorization_code,
        redirect_uri=body.redirect_uri,
        api_key=getattr(settings, "trans_eu_api_key", ""),
    )

    try:
        session = await conn_mgr.connect_trans_eu_user(company_id, user_id, creds)
        return {
            "status": "connected",
            "provider_id": "trans_eu",
            "user_id": user_id,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to connect Trans.eu for user %d", user_id)
        raise HTTPException(status_code=500, detail=f"Failed to connect Trans.eu: {e}")


@router.get("/providers/trans_eu/status")
async def get_trans_eu_status(
    current_user: dict = Depends(require_dispatcher),
    db=Depends(get_db),
):
    """Get Trans.eu connection status for the current user."""
    company_id = current_user["company_id"]
    user_id = current_user["user_id"]

    conn_mgr = ConnectionManagerService(db)
    session = conn_mgr.get_trans_eu_session_for_user(company_id, user_id)

    if session is None:
        return {
            "provider_id": "trans_eu",
            "status": "disconnected",
        }

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    ttl = (session.expires_at - now).total_seconds() if session.expires_at else 0

    return {
        "provider_id": "trans_eu",
        "status": "connected",
        "user_id": user_id,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "ttl_seconds": int(ttl),
        "needs_refresh": ttl < 300 if ttl > 0 else False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Search
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/search")
async def search_loads(
    body: SearchRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Search freight loads across connected providers."""
    company_id = current_user["company_id"]

    filters = LoadSearchFilters(
        origin=GeoFilter(location=body.origin_location, radius_km=body.origin_radius_km),
        destination=GeoFilter(location=body.destination_location, radius_km=body.destination_radius_km),
        pickup_date_from=date.fromisoformat(body.pickup_date_from),
        pickup_date_to=date.fromisoformat(body.pickup_date_to),
        delivery_date_from=date.fromisoformat(body.delivery_date_from) if body.delivery_date_from else None,
        delivery_date_to=date.fromisoformat(body.delivery_date_to) if body.delivery_date_to else None,
        trailer_type=body.trailer_type,
        adr_required=body.adr_required,
        weight_kg_min=body.weight_kg_min,
        weight_kg_max=body.weight_kg_max,
        price_min=body.price_min,
        distance_km_max=body.distance_km_max,
        loading_type=body.loading_type,
        loading_country=body.loading_country,
        delivery_country=body.delivery_country,
        sort_by=body.sort_by,
        sort_order=body.sort_order or "asc",
        min_trucks=body.min_trucks,
    )

    search_svc = SearchEngineService(db)
    result_set = await search_svc.search_loads(
        company_id=company_id,
        filters=filters,
        provider_ids=body.provider_ids,
    )

    from backend.posthog_client import get_posthog
    _ph = get_posthog()
    if _ph:
        _ph.capture("freight_search_performed", distinct_id=current_user.get("email", ""), properties={
            "company_id": company_id,
            "result_count": len(result_set.results),
            "providers_queried": result_set.total_providers_queried,
            "loading_country": body.loading_country,
            "delivery_country": body.delivery_country,
        })
    return {
        "results": [r.model_dump(mode="json") for r in result_set.results],
        "providers_queried": result_set.total_providers_queried,
        "providers_skipped": result_set.total_providers_skipped,
        "provider_statuses": [
            {"provider_id": ps.provider_id, "status": ps.status, "error": ps.error}
            for ps in result_set.provider_statuses
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Saved Searches
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/searches")
async def get_recent_searches(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent saved searches."""
    company_id = current_user["company_id"]
    user_id = current_user["id"]
    search_svc = SearchEngineService(db)
    saved = await search_svc.get_recent_searches(company_id, user_id, limit)
    return {"searches": [s.model_dump(mode="json") for s in saved]}


@router.post("/searches")
async def save_search(
    body: SaveSearchRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Save a search for later recall."""
    company_id = current_user["company_id"]
    user_id = current_user["id"]

    filters = LoadSearchFilters(**body.filters)

    search_svc = SearchEngineService(db)
    saved = await search_svc.save_search(
        company_id=company_id,
        user_id=user_id,
        filters=filters,
        label=body.label,
        provider_ids=body.provider_ids,
    )
    return saved.model_dump(mode="json")


@router.post("/searches/{search_id}/refresh")
async def refresh_search(
    search_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Re-run a saved search."""
    company_id = current_user["company_id"]
    search_svc = SearchEngineService(db)
    try:
        result_set = await search_svc.refresh_search(company_id, search_id)
        return {
            "results": [r.model_dump(mode="json") for r in result_set.results],
            "providers_queried": result_set.total_providers_queried,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Load Operations
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/loads/{provider_id}/{load_id}")
async def get_load(
    provider_id: str,
    load_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Get a single load by provider and load ID."""
    company_id = current_user["company_id"]
    search_svc = SearchEngineService(db)
    load = await search_svc.get_load(company_id, provider_id, load_id)
    if load is None:
        raise HTTPException(status_code=404, detail="Load not found")
    return load.model_dump(mode="json")


@router.post("/loads/{provider_id}/{load_id}/import")
async def import_load(
    provider_id: str,
    load_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Import a freight exchange load as an Operion trip."""
    company_id = current_user["company_id"]
    user_id = current_user["id"]

    pipeline = ImportPipelineService(db)
    try:
        result = await pipeline.import_load(
            company_id=company_id,
            provider_id=provider_id,
            provider_load_id=load_id,
            user_id=user_id,
        )
        return result.model_dump(mode="json")
    except ImportError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Import failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


@router.get("/loads/{provider_id}/{load_id}/evaluate")
async def evaluate_load(
    provider_id: str,
    load_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    candidate_vehicle_id: Optional[int] = Query(None, description="Optional vehicle ID for compatibility check"),
):
    """Evaluate a load's profitability and risk."""
    company_id = current_user["company_id"]

    engine = EvaluationEngineService(db)
    try:
        evaluation = await engine.evaluate_load(
            company_id=company_id,
            provider_id=provider_id,
            provider_load_id=load_id,
            candidate_vehicle_id=candidate_vehicle_id,
        )
        return evaluation.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/loads/{provider_id}/{load_id}/match")
async def match_trucks(
    provider_id: str,
    load_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    top_n: int = Query(5, ge=1, le=20, description="Number of top matches to return"),
):
    """Find the best trucks for a given load."""
    company_id = current_user["company_id"]

    matcher = FleetMatcherService(db)
    try:
        ranked = await matcher.find_best_trucks(
            company_id=company_id,
            provider_id=provider_id,
            provider_load_id=load_id,
            top_n=top_n,
        )
        return {"matches": [r.model_dump(mode="json") for r in ranked]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
