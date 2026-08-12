from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.dependencies import get_client_service
from backend.schemas.client import (
    ClientContactAddRequest,
    ClientCreateRequest,
    ClientResponse,
    ClientTagAddRequest,
    ClientUpdateRequest,
)
from backend.schemas.common import PaginatedResponse
from services.client_service import ClientService

from backend.dependencies_security import require_dispatcher

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientListResponse(PaginatedResponse[ClientResponse]):
    """Paginated list of clients."""


@router.get("/", response_model=ClientListResponse)
def list_clients(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    query: str = Query("", description="Search query"),
    include_inactive: bool = Query(False),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    service: ClientService = Depends(get_client_service),
):
    """Return paginated list of clients."""
    if query:
        items = service.search_advanced(query, include_inactive=include_inactive, limit=page_size)
    else:
        items = service.get_all(include_inactive=include_inactive)
    return PaginatedResponse.from_items(
        items=[ClientResponse(**c) for c in items],
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    client = service.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientResponse(**client)


@router.post("/", response_model=Dict[str, int])
def create_client(
    data: ClientCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    client_id = service.create(data.name, **data.model_dump(exclude={"name"}))
    return {"id": client_id}


@router.patch("/{client_id}")
def update_client_partial(
    client_id: int,
    data: ClientUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    """Partially update a client (PATCH)."""
    service.update(client_id, **data.model_dump(exclude_unset=True))
    return {"status": "updated"}


@router.put("/{client_id}", deprecated=True)
def update_client(
    client_id: int,
    data: ClientUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /{client_id} instead."""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    service.update(client_id, **data.model_dump(exclude_unset=True))
    return {"status": "updated"}


@router.get("/{client_id}/dashboard")
def get_client_dashboard(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    return service.get_client_dashboard(client_id)


@router.get("/{client_id}/trips", response_model=PaginatedResponse[dict])
def get_client_trips(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    service: ClientService = Depends(get_client_service),
):
    """Return paginated trips for a client."""
    items = service.get_client_trips(client_id, limit=page_size, offset=(page - 1) * page_size)
    return PaginatedResponse.from_items(items=items, total=len(items), page=page, page_size=page_size)


@router.get("/{client_id}/invoices", response_model=PaginatedResponse[dict])
def get_client_invoices(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    service: ClientService = Depends(get_client_service),
):
    """Return paginated invoices for a client."""
    items = service.get_client_invoices(client_id, limit=page_size)
    return PaginatedResponse.from_items(items=items, total=len(items), page=page, page_size=page_size)


@router.get("/{client_id}/trip-count")
def get_client_trip_count(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    return {"count": service.get_trip_count(client_id)}


@router.post("/{client_id}/deactivate")
def deactivate_client(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    service.deactivate(client_id)
    return {"status": "deactivated"}


@router.get("/{client_id}/contacts", response_model=PaginatedResponse[dict])
def get_client_contacts(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    """Return contacts for a client."""
    items = service.get_contacts(client_id)
    return PaginatedResponse.from_items(items=items, total=len(items), page=1, page_size=len(items) or 20)


@router.post("/{client_id}/contacts", status_code=201)
def add_client_contact(
    client_id: int,
    data: ClientContactAddRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    contact_id = service.add_contact(client_id, **data.model_dump())
    return {"id": contact_id}


@router.get("/{client_id}/tags")
def get_client_tags(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    tags = service.get_tags(client_id)
    return {"tags": tags}


@router.post("/{client_id}/tags")
def add_client_tag(
    client_id: int,
    data: ClientTagAddRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    if data.tag:
        service.add_tag(client_id, data.tag)
    return {"status": "tag_added"}


@router.get("/{client_id}/payment-summary")
def get_payment_summary(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: ClientService = Depends(get_client_service),
):
    return service.get_payment_summary(client_id)


@router.get("/{client_id}/revenue-history")
def get_client_revenue_history(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    months: int = Query(12, ge=1, le=60),
    service: ClientService = Depends(get_client_service),
):
    return service.get_client_revenue_history(client_id, months=months)
