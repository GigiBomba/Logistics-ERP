"""Freight Exchange API endpoints -- REST interface for the freight exchange subsystem.

All endpoints enforce multi-tenant isolation: ``company_id`` is derived
from the JWT, never trusted from the client request body.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.db import DatabaseManager
from models.freight_exchange_models import (
    GeoFilter,
    LoadSearchFilters,
    ProviderCredentials,
)
from repositories.freight_negotiation_repository import FreightNegotiationRepository
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


class FreightLoadListItem(BaseModel):
    """Provider-agnostic load-board list item (blueprint §6.3).

    Mirrors the mobile ``FreightLoad`` model in ``freight_load.dart`` field
    for field — NO provider-specific field names (no TIMOCOM/Trans.eu
    identifiers leak into this contract).  ``distance_km`` is a string to
    match the Dart model's ``String? distanceKm`` parsing exactly.
    """

    id: str
    origin: str = ""
    destination: str = ""
    cargo_type: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    pickup_date: Optional[str] = None
    deadline_date: Optional[str] = None
    weight_kg: Optional[float] = None
    distance_km: Optional[str] = None


def _to_freight_load_item(load) -> FreightLoadListItem:
    """Map a provider ``LoadSearchResult`` to the provider-agnostic list item."""
    price = load.price
    pickup_window = getattr(load, "pickup_window", None) or ()
    delivery_window = getattr(load, "delivery_window", None) or ()
    pickup_date = (
        pickup_window[0].isoformat() if pickup_window else (load.loading_date or None)
    )
    deadline_date = (
        delivery_window[1].isoformat() if delivery_window else (load.unloading_date or None)
    )
    distance_km = getattr(load, "distance_km", None)
    return FreightLoadListItem(
        id=load.result_id or f"{load.provider_id}:{load.provider_load_id}",
        origin=load.origin or "",
        destination=load.destination or "",
        cargo_type=getattr(load, "trailer_type", None) or None,
        price=float(price.amount) if price is not None else None,
        currency=price.currency if price is not None else None,
        pickup_date=pickup_date,
        deadline_date=deadline_date,
        weight_kg=getattr(load, "weight_kg", 0.0) or None,
        distance_km=(str(round(distance_km, 1)) if distance_km else None),
    )


class SaveSearchRequest(BaseModel):
    label: str
    filters: dict
    provider_ids: Optional[list[str]] = None


class ConnectTransEuRequest(BaseModel):
    """Request to connect a user's Trans.eu account via OAuth authorization_code."""
    authorization_code: str
    redirect_uri: str


class NegotiationActionRequest(BaseModel):
    """One negotiation action for a freight load.

    ``counter`` requires ``amount_eur`` (the handler returns 422
    ``amount_required`` when it is missing); ``accept`` / ``reject`` are
    terminal records and may carry an optional amount.
    """

    action: Literal["accept", "reject", "counter"]
    amount_eur: Optional[float] = Field(None, ge=0, description="Counter-offer / agreed amount (EUR)")
    counterparty_name: Optional[str] = None


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


@router.delete("/searches/{search_id}")
async def delete_search(
    search_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Delete a saved search (owner-only: company + user scoped).

    ``search_id`` must belong to the JWT's company AND the JWT's user —
    otherwise 404 (never leaks which part failed).
    """
    company_id = current_user["company_id"]
    user_id = current_user["id"]

    row = db.execute(
        "SELECT id FROM saved_searches WHERE id = ? AND company_id = ? AND user_id = ?",
        (search_id, company_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Saved search not found")

    db.execute(
        "DELETE FROM saved_searches WHERE id = ? AND company_id = ? AND user_id = ?",
        (search_id, company_id, user_id),
    )
    db.commit()
    return {"status": "deleted"}


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
# Load-board LIST (blueprint §6.3 — provider-agnostic mobile contract)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/loads", response_model=list[FreightLoadListItem])
async def list_loads(
    origin: Optional[str] = Query(None, description="Loading place filter"),
    destination: Optional[str] = Query(None, description="Unloading place filter"),
    date: Optional[str] = Query(None, description="Single pickup date filter (ISO YYYY-MM-DD)"),
    cargo_type: Optional[str] = Query(None, description="Trailer/cargo type filter"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """List freight loads across connected providers (provider-agnostic).

    Mobile load-board contract (§6.3): every item is a ``FreightLoadListItem``
    with provider-agnostic fields mirroring the mobile ``FreightLoad`` model —
    no TIMOCOM/Trans.eu-specific field names ever reach this response.

    Company-scoped: ``company_id`` comes from the JWT only, never from query
    params or the body.  Filters (origin, destination, date, cargo_type) are
    all optional; when no ``date`` is given the pickup window defaults to a
    3-week rolling window around today so the load board is never empty.
    """
    from datetime import date as _date_type  # noqa: A004 (param shadows module)

    company_id = current_user["company_id"]

    today = _date_type.today()
    if date:
        try:
            filter_from = _date_type.fromisoformat(date)
            filter_to = filter_from
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid 'date' filter — expected ISO YYYY-MM-DD.",
            )
    else:
        from datetime import timedelta

        filter_from = today - timedelta(days=7)
        filter_to = today + timedelta(days=14)

    filters = LoadSearchFilters(
        origin=GeoFilter(location=origin, radius_km=50) if origin else None,
        destination=GeoFilter(location=destination, radius_km=30) if destination else None,
        pickup_date_from=filter_from,
        pickup_date_to=filter_to,
        trailer_type=[cargo_type] if cargo_type else None,
    )

    search_svc = SearchEngineService(db)
    result_set = await search_svc.search_loads(company_id=company_id, filters=filters)

    return [_to_freight_load_item(r) for r in result_set.results[:limit]]


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


# ═══════════════════════════════════════════════════════════════════════════
# Negotiation threads (Tier-2) — LOCAL provider-agnostic records
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/loads/{provider_id}/{load_id}/negotiation")
async def get_negotiation(
    provider_id: str,
    load_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Return the negotiation thread for a freight load (oldest → newest).

    Company-scoped: ``company_id`` comes from the JWT only.  An empty thread
    returns ``{"thread": []}`` (HTTP 200) — the load simply has no negotiation
    records yet.
    """
    company_id = current_user["company_id"]
    repo = FreightNegotiationRepository(db)
    thread = repo.get_thread(company_id, provider_id, load_id)
    return {"thread": thread}


@router.post("/loads/{provider_id}/{load_id}/negotiation")
async def create_negotiation_action(
    provider_id: str,
    load_id: str,
    body: NegotiationActionRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Append one action to a freight-load negotiation thread.

    The thread is a LOCAL provider-agnostic record — there is NO external
    TransEu/TIMOCOM call (no adapter method exists; the push can come later).
    Semantics:
      * the FIRST action on an empty thread is the provider's base offer
        (``direction='inbound'``, status per action, no parent);
      * every subsequent action is our reply (``direction='outbound'``) and is
        chained to the latest record via ``parent_negotiation_id``;
      * ``counter`` requires ``amount_eur`` (422 ``amount_required``);
      * ``accept`` / ``reject`` append terminal records (no further-machine
        enforcement yet — the client controls the thread).
    """
    company_id = current_user["company_id"]
    user_id = current_user.get("id") or 0
    repo = FreightNegotiationRepository(db)

    if body.action == "counter" and body.amount_eur is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "amount_required",
                "detail": "A counter-offer requires amount_eur.",
            },
        )

    latest = repo.latest(company_id, provider_id, load_id)
    direction = "outbound" if latest else "inbound"
    parent_id = latest["id"] if latest else None

    record_id = repo.create({
        "company_id": company_id,
        "provider_id": provider_id,
        "provider_load_id": load_id,
        "direction": direction,
        "status": {"accept": "accepted", "reject": "rejected", "counter": "countered"}[body.action],
        "amount_eur": body.amount_eur,
        "currency": "EUR",
        "counterparty_name": body.counterparty_name
        or (latest["counterparty_name"] if latest else "")
        or "",
        "counterparty_id": (latest["counterparty_id"] if latest else "") or "",
        "parent_negotiation_id": parent_id,
        "created_by": user_id,
    })

    record = repo.get_by_id(record_id, company_id=company_id)
    return {"negotiation": record}
