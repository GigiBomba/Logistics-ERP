"""Mobile client endpoints (blueprint §6.3).

  - GET    /mobile/clients                        — paginated client list (search)
  - POST   /mobile/clients                        — create client        [can_create_client]
  - GET    /mobile/clients/{client_id}            — client detail (contacts + recent counts)
  - PATCH  /mobile/clients/{client_id}            — update client        [can_update_client]
  - POST   /mobile/clients/{client_id}/contacts   — add contact          [can_update_client]
  - POST   /mobile/clients/merge                  — multi-source merge   [can_merge_clients — ADMIN-only]

Every handler is company-scoped (404 for another company's client).  The first
business-logic line of every mutation is the PermissionService gate (403 on
denial).

The multi-source merge runs in ONE dialect-aware transaction with row-level
locking (``ClientService.merge_clients_multi`` / ``ClientRepository.
merge_clients_multi``) and hard-deletes the source rows.

NOTE (§8.3 vs real code): blueprint §8.3 implies a manager may merge clients,
but the REAL ``PermissionService.can_merge_clients`` matrix is admin-only —
real code wins; manager/dispatcher/driver are 403 here.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.mobile import (
    ClientContactCreateRequest,
    ClientContactOut,
    ClientCreateRequest,
    ClientDetailOut,
    ClientMergeRequest,
    ClientMergeResult,
    ClientOut,
    ClientUpdateRequest,
)
from repositories.client_repository import ClientRepository
from repositories.contact_repository import ContactRepository
from services.client_service import ClientService
from services.permission_service import PermissionService

router = APIRouter(prefix="/clients", tags=["mobile_clients"])


def _check_permission(db: DatabaseManager, user_id: int, perm_check: str) -> None:
    """Gate-1: run the real PermissionService decision; 403 on denial.

    ``user_id`` 0 (env-configured admin) skips the check — the desktop
    convention for the system/internal admin (no users-table row).
    """
    if not user_id:
        return
    result = getattr(PermissionService(db), perm_check)(user_id)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Permission denied")


def _get_client_or_404(
    repo: ClientRepository, client_id: int, company_id: int
) -> Dict[str, Any]:
    client = repo.get_by_id(client_id, company_id=company_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def _to_client_out(client: Dict[str, Any], company_id: int) -> dict:
    return {
        "id": client["id"],
        "company_id": client.get("company_id") or company_id,
        "name": client.get("name") or "",
        "vat_number": client.get("vat_number") or "",
        "address": client.get("address") or "",
        "payment_terms_days": client.get("payment_terms_days") or 30,
        "rating": client.get("rating"),
        "is_active": bool(client.get("is_active", 1)),
        "created_at": client.get("created_at"),
        "updated_at": client.get("updated_at"),
    }


@router.post("/merge", response_model=ClientMergeResult)
def merge_clients(
    data: ClientMergeRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Merge multiple source clients into one target (gate: can_merge_clients — admin-only).

    Synchronous, single DB transaction, row-level locking; moves trips,
    invoices (via trips), contacts and tags to the target, then deletes the
    source rows.  A source that was already merged concurrently aborts with 404.
    """
    user_id = current_user.get("id") or 0
    _check_permission(db, user_id, "can_merge_clients")
    company_id = current_user["company_id"]
    try:
        result = ClientService(db).merge_clients_multi(
            data.target_id, list(data.source_ids), user_id=user_id, company_id=company_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ClientMergeResult(**result)


@router.get("", response_model=PaginatedResponse[ClientOut])
def list_clients(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str = "",
):
    """Paginated, company-scoped client list (search via search_advanced)."""
    company_id = current_user["company_id"]
    repo = ClientRepository(db)
    if search:
        rows = repo.search_advanced(
            search, include_inactive=False, limit=5000, company_id=company_id
        )
    else:
        rows = repo.get_all(include_inactive=False, company_id=company_id)
    items_all = [_to_client_out(c, company_id) for c in rows]
    total = len(items_all)
    offset = (page - 1) * page_size
    items = items_all[offset : offset + page_size]
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("", response_model=ClientOut, status_code=201)
def create_client(
    data: ClientCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a company-scoped client (gate: can_create_client)."""
    _check_permission(db, current_user.get("id") or 0, "can_create_client")
    company_id = current_user["company_id"]
    repo = ClientRepository(db)
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    fields["company_id"] = company_id
    client_id = repo.create(fields)
    return _to_client_out(_get_client_or_404(repo, client_id, company_id), company_id)


@router.get("/{client_id}", response_model=ClientDetailOut)
def get_client(
    client_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Company-scoped client detail: contacts + recent trip/invoice counts."""
    company_id = current_user["company_id"]
    repo = ClientRepository(db)
    client = _get_client_or_404(repo, client_id, company_id)

    contact_rows = ContactRepository(db).get_by_client(client_id)
    contacts = [
        ClientContactOut(
            id=c["id"],
            name=c.get("full_name") or "",
            role=c.get("title") or "",
            phone=c.get("phone") or "",
            email=c.get("email") or "",
        )
        for c in contact_rows
    ]

    recent_trip_count = repo.get_trip_count(client_id)
    inv = db.execute(
        "SELECT COUNT(*) AS cnt FROM invoices i JOIN trips t ON t.id = i.trip_id "
        "WHERE t.client_id = ?",
        (client_id,),
    ).fetchone()
    recent_invoice_count = inv["cnt"] if inv else 0

    out = _to_client_out(client, company_id)
    out["contacts"] = contacts
    out["recent_trip_count"] = recent_trip_count
    out["recent_invoice_count"] = recent_invoice_count
    return out


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    data: ClientUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update a client (gate: can_update_client)."""
    _check_permission(db, current_user.get("id") or 0, "can_update_client")
    company_id = current_user["company_id"]
    repo = ClientRepository(db)
    _get_client_or_404(repo, client_id, company_id)
    fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if fields:
        repo.update(client_id, fields)
    return _to_client_out(_get_client_or_404(repo, client_id, company_id), company_id)


@router.post("/{client_id}/contacts", response_model=ClientContactOut, status_code=201)
def add_client_contact(
    client_id: int,
    data: ClientContactCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Add a contact to a client (gate: can_update_client)."""
    _check_permission(db, current_user.get("id") or 0, "can_update_client")
    company_id = current_user["company_id"]
    repo = ClientRepository(db)
    _get_client_or_404(repo, client_id, company_id)
    fields = data.model_dump()
    fields["client_id"] = client_id
    contact_id = ContactRepository(db).create(fields, company_id=company_id)
    row = db.execute(
        "SELECT * FROM client_contacts WHERE id = ? AND company_id = ?",
        (contact_id, company_id),
    ).fetchone()
    row = dict(row) if row else fields
    return ClientContactOut(
        id=contact_id,
        name=row.get("full_name") or "",
        role=row.get("title") or "",
        phone=row.get("phone") or "",
        email=row.get("email") or "",
    )
