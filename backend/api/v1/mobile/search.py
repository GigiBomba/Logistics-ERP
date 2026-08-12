"""Mobile global search endpoint (blueprint §6.11).

  GET /mobile/search?q=&types=trips,clients,drivers,trucks,documents
      -> {trips: {items ≤5, total_count}, clients, drivers, trucks, documents}

Gate: require_dispatcher (no finer-grained permission exists for search).

Implementation is LIKE-based (dialect-safe): the repo has no cross-table FTS
or pgvector index — only documents_fts (SQLite FTS5), which the documents
section reuses via ``DocumentRepository.fts_search``.  Every LIKE pattern
escapes ``\\``/``%``/``_`` and uses ``ESCAPE '\\'`` so a literal ``%`` in the
query cannot become a wildcard.  Each result type is capped at 5 items and
carries the true ``total_count``.

Company scoping: trips/drivers/trucks queries scope explicitly on the JWT
``company_id``; clients reuse ``search_advanced(company_id=...)``; documents
use ``DocumentRepository.fts_search`` which derives its filter from the
tenant context — we pin it with ``set_company_context`` so every mobile user
(any role) is scoped to their own company.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.mobile import GlobalSearchResponse, SearchSection
from database.tenant_context import set_company_context
from repositories.client_repository import ClientRepository
from repositories.document_repository import DocumentRepository

router = APIRouter(prefix="/search", tags=["mobile_search"])

_VALID_TYPES = {"trips", "clients", "drivers", "trucks", "documents"}
_CAP = 5


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards (``\\``, ``%``, ``_``) for ``ESCAPE '\\'``."""
    return (
        value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


def _like_param(query: str) -> str:
    return f"%{_escape_like(query)}%"


def _search_trips(db: DatabaseManager, query: str, company_id: int) -> SearchSection:
    like = _like_param(query)
    rows = db.execute(
        "SELECT id, client_name, truck_number, driver_name, place_of_loading, "
        "delivery_country, status "
        "FROM trips "
        "WHERE company_id = ? AND "
        "(client_name LIKE ? ESCAPE '\\' OR truck_number LIKE ? ESCAPE '\\' "
        " OR driver_name LIKE ? ESCAPE '\\' OR place_of_loading LIKE ? ESCAPE '\\' "
        " OR delivery_country LIKE ? ESCAPE '\\') "
        "ORDER BY start_date DESC, id DESC LIMIT ?",
        (company_id, like, like, like, like, like, _CAP),
    ).fetchall()
    items = [dict(r) for r in rows]

    cnt = db.execute(
        "SELECT COUNT(*) AS cnt FROM trips "
        "WHERE company_id = ? AND "
        "(client_name LIKE ? ESCAPE '\\' OR truck_number LIKE ? ESCAPE '\\' "
        " OR driver_name LIKE ? ESCAPE '\\' OR place_of_loading LIKE ? ESCAPE '\\' "
        " OR delivery_country LIKE ? ESCAPE '\\')",
        (company_id, like, like, like, like, like),
    ).fetchone()
    return SearchSection(items=items, total_count=dict(cnt)["cnt"] if cnt else 0)


def _search_clients(db: DatabaseManager, query: str, company_id: int) -> SearchSection:
    rows = ClientRepository(db).search_advanced(
        query, include_inactive=False, limit=5000, company_id=company_id
    )
    all_rows = [dict(r) for r in rows]
    return SearchSection(items=all_rows[:_CAP], total_count=len(all_rows))


def _search_drivers(db: DatabaseManager, query: str, company_id: int) -> SearchSection:
    like = _like_param(query)
    rows = db.execute(
        "SELECT id, name, phone, email, license_number, is_active, company_id "
        "FROM drivers "
        "WHERE company_id = ? AND "
        "(name LIKE ? ESCAPE '\\' OR license_number LIKE ? ESCAPE '\\' "
        " OR phone LIKE ? ESCAPE '\\') "
        "ORDER BY name ASC LIMIT ?",
        (company_id, like, like, like, _CAP),
    ).fetchall()
    items = [dict(r) for r in rows]

    cnt = db.execute(
        "SELECT COUNT(*) AS cnt FROM drivers "
        "WHERE company_id = ? AND "
        "(name LIKE ? ESCAPE '\\' OR license_number LIKE ? ESCAPE '\\' "
        " OR phone LIKE ? ESCAPE '\\')",
        (company_id, like, like, like),
    ).fetchone()
    return SearchSection(items=items, total_count=dict(cnt)["cnt"] if cnt else 0)


def _search_trucks(db: DatabaseManager, query: str, company_id: int) -> SearchSection:
    like = _like_param(query)
    rows = db.execute(
        "SELECT id, plate_number, manufacturer, model, status, year, company_id "
        "FROM trucks "
        "WHERE company_id = ? AND "
        "(plate_number LIKE ? ESCAPE '\\' OR model LIKE ? ESCAPE '\\' "
        " OR manufacturer LIKE ? ESCAPE '\\') "
        "ORDER BY plate_number ASC LIMIT ?",
        (company_id, like, like, like, _CAP),
    ).fetchall()
    items = [dict(r) for r in rows]

    cnt = db.execute(
        "SELECT COUNT(*) AS cnt FROM trucks "
        "WHERE company_id = ? AND "
        "(plate_number LIKE ? ESCAPE '\\' OR model LIKE ? ESCAPE '\\' "
        " OR manufacturer LIKE ? ESCAPE '\\')",
        (company_id, like, like, like),
    ).fetchone()
    return SearchSection(items=items, total_count=dict(cnt)["cnt"] if cnt else 0)


def _search_documents(db: DatabaseManager, query: str, company_id: int) -> SearchSection:
    # fts_search derives its company filter from the tenant context.
    set_company_context(company_id)
    try:
        rows = DocumentRepository(db).fts_search(query, limit=_CAP)
        items = [dict(r) for r in rows]
        total = DocumentRepository(db).fts_search_count(query)
        return SearchSection(items=items, total_count=total)
    except Exception as exc:  # FTS5 unavailable / empty index → fall back safely
        return _search_documents_fallback(db, query, company_id, exc)


def _search_documents_fallback(db: DatabaseManager, query: str, company_id: int,
                               exc: Exception) -> SearchSection:
    """Fallback ILIKE/LIKE document search when FTS is unavailable."""
    like = _like_param(query)
    rows = db.execute(
        "SELECT id, title, file_name, category, entity_type, company_id "
        "FROM documents "
        "WHERE company_id = ? AND is_archived = 0 AND "
        "(title LIKE ? ESCAPE '\\' OR file_name LIKE ? ESCAPE '\\' "
        " OR description LIKE ? ESCAPE '\\' OR text_content LIKE ? ESCAPE '\\') "
        "ORDER BY uploaded_at DESC LIMIT ?",
        (company_id, like, like, like, like, _CAP),
    ).fetchall()
    items = [dict(r) for r in rows]
    cnt = db.execute(
        "SELECT COUNT(*) AS cnt FROM documents "
        "WHERE company_id = ? AND is_archived = 0 AND "
        "(title LIKE ? ESCAPE '\\' OR file_name LIKE ? ESCAPE '\\' "
        " OR description LIKE ? ESCAPE '\\' OR text_content LIKE ? ESCAPE '\\')",
        (company_id, like, like, like, like),
    ).fetchone()
    return SearchSection(items=items, total_count=dict(cnt)["cnt"] if cnt else 0)


@router.get("", response_model=GlobalSearchResponse)
def global_search(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    q: str = Query(..., min_length=1, description="Search query (min 1 char)"),
    types: str = Query("", description="Comma-separated types; empty = all five"),
):
    """Global LIKE search across trips/clients/drivers/trucks/documents."""
    company_id = current_user["company_id"]
    query = q.strip()
    if not query:
        return GlobalSearchResponse()

    wanted = _VALID_TYPES if not types.strip() else {
        t.strip() for t in types.split(",") if t.strip()
    }
    invalid = wanted - _VALID_TYPES
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown search types: {sorted(invalid)}",
        )

    sections: Dict[str, SearchSection] = {}
    if "trips" in wanted:
        sections["trips"] = _search_trips(db, query, company_id)
    if "clients" in wanted:
        sections["clients"] = _search_clients(db, query, company_id)
    if "drivers" in wanted:
        sections["drivers"] = _search_drivers(db, query, company_id)
    if "trucks" in wanted:
        sections["trucks"] = _search_trucks(db, query, company_id)
    if "documents" in wanted:
        sections["documents"] = _search_documents(db, query, company_id)

    return GlobalSearchResponse(**sections)
