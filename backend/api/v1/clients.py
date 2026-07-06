from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_client_service
from backend.schemas.client import ClientResponse
from services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=Dict[str, Any])
async def list_clients(
    query: str = Query("", description="Search query"),
    include_inactive: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
    service: ClientService = Depends(get_client_service),
):
    if query:
        items = service.search_advanced(query, include_inactive=include_inactive, limit=limit)
    else:
        items = service.get_all(include_inactive=include_inactive)
    return {"items": items, "total": len(items)}


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    service: ClientService = Depends(get_client_service),
):
    client = service.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientResponse(**client)


@router.post("/", response_model=Dict[str, int])
async def create_client(
    name: str,
    data: Dict[str, Any],
    service: ClientService = Depends(get_client_service),
):
    client_id = service.create(name=name, **data)
    return {"id": client_id}


@router.put("/{client_id}")
async def update_client(
    client_id: int,
    data: Dict[str, Any],
    service: ClientService = Depends(get_client_service),
):
    service.update(client_id, **data)
    return {"status": "updated"}


@router.get("/{client_id}/dashboard")
async def get_client_dashboard(
    client_id: int,
    service: ClientService = Depends(get_client_service),
):
    return service.get_client_dashboard(client_id)


@router.get("/{client_id}/trips")
async def get_client_trips(
    client_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: ClientService = Depends(get_client_service),
):
    items = service.get_client_trips(client_id, limit=limit, offset=offset)
    return {"items": items, "total": len(items)}


@router.get("/{client_id}/invoices")
async def get_client_invoices(
    client_id: int,
    limit: int = Query(100, ge=1, le=500),
    service: ClientService = Depends(get_client_service),
):
    items = service.get_client_invoices(client_id, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/{client_id}/trip-count")
async def get_client_trip_count(
    client_id: int,
    service: ClientService = Depends(get_client_service),
):
    return {"count": service.get_trip_count(client_id)}


@router.post("/{client_id}/deactivate")
async def deactivate_client(
    client_id: int,
    service: ClientService = Depends(get_client_service),
):
    service.deactivate(client_id)
    return {"status": "deactivated"}


@router.get("/{client_id}/contacts")
async def get_client_contacts(
    client_id: int,
    service: ClientService = Depends(get_client_service),
):
    items = service.get_contacts(client_id)
    return {"items": items, "total": len(items)}


@router.post("/{client_id}/contacts", status_code=201)
async def add_client_contact(
    client_id: int,
    data: Dict[str, Any],
    service: ClientService = Depends(get_client_service),
):
    contact_id = service.add_contact(client_id, **data)
    return {"id": contact_id}


@router.get("/{client_id}/tags")
async def get_client_tags(
    client_id: int,
    service: ClientService = Depends(get_client_service),
):
    tags = service.get_tags(client_id)
    return {"tags": tags}


@router.post("/{client_id}/tags")
async def add_client_tag(
    client_id: int,
    data: Dict[str, str],
    service: ClientService = Depends(get_client_service),
):
    tag = data.get("tag", "")
    if tag:
        service.add_tag(client_id, tag)
    return {"status": "tag_added"}


@router.get("/{client_id}/payment-summary")
async def get_payment_summary(
    client_id: int,
    service: ClientService = Depends(get_client_service),
):
    return service.get_payment_summary(client_id)


@router.get("/{client_id}/revenue-history")
async def get_client_revenue_history(
    client_id: int,
    months: int = Query(12, ge=1, le=60),
    service: ClientService = Depends(get_client_service),
):
    return service.get_client_revenue_history(client_id, months=months)
