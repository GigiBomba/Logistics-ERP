"""Mobile invoicing endpoints (blueprint §6.6) — FINANCIAL.

  - GET    /mobile/invoices                      — paginated invoice list (status / client / search)
  - POST   /mobile/invoices                      — create invoice           [can_create_invoice]
  - GET    /mobile/invoices/{invoice_id}         — invoice detail (client + trip context)
  - PATCH  /mobile/invoices/{invoice_id}         — update invoice (draft only) [can_create_invoice]
  - POST   /mobile/invoices/{invoice_id}/transition — state-machine action  [per-action gates]
  - GET    /mobile/invoices/{invoice_id}/pdf     — InvoiceGenerator PDF (FileResponse)
  - POST   /mobile/invoices/{invoice_id}/cmr     — CMR generation for the invoice's trip [can_generate_cmr]

Money/legal rigor:
  * Totals are ALWAYS computed server-side through the REAL desktop
    ``InvoiceService._calculate_line_items`` path (``InvoiceService.create`` /
    ``update``).  The mobile never supplies subtotal/vat/gross.
  * ``status`` uses the REAL desktop status strings (draft/finalized/
    xml_generated/submitted_externally/queued/submitting/accepted/rejected/
    manual_review/cancelled/paid).  Every transition is validated against the
    REAL ``INVOICE_STATUS_TRANSITIONS`` machine via
    ``InvoiceService._validate_status_transition`` — illegal transitions are
    422 with a machine-readable ``error_code`` (``invalid_transition`` /
    ``empty_line_items`` / ``not_editable``), never 500.
  * ``generate_xml`` writes a REAL UBL-inspired CIUS-RO XML via
    ``services.invoicing.xml_export`` (seller from the company config) and
    stores ``efactura_xml_path``.  ``submit`` is an HONEST status-only stub:
    no ANAF call exists anywhere in the codebase — it transitions to
    ``submitted_externally`` and records a generated
    ``efactura_submission_reference`` (a client-generated ``EFAC-`` reference,
    never an ANAF submission id).  ``OPERION_ENABLE_ANAF_SUBMISSION``
    (default false) is the explicit opt-in: true without ANAF credentials
    returns 400 ``anaf_not_configured`` instead of faking a submission
    (Gate-29 A3).
  * Invoice PDFs come from the desktop ``InvoiceGenerator``.
  * CMR PDFs come from the desktop ``CMRGenerator``; the captured signature
    PNG is persisted to the documents table (``entity_type='cmr'``,
    ``entity_id=<trip_id>``) and the PDF is downloadable via a signed
    KIND_DOCUMENT token (Phase-2 signed-URL pattern).

Permission mapping (§8.4 vs real code):
  * finalize / generate_xml / submit / mark_paid  → ``can_finalize_invoice``.
    **``can_submit_invoice`` DOES NOT EXIST** in the real ``PermissionService``
    (grep 0) — submit is mapped to ``can_finalize_invoice`` (same matrix as
    finalize, manager+admin).  The state machine still validates that the
    invoice is in ``xml_generated`` before accepting the submit action.
  * cancel                                       → ``can_cancel_invoice``.
  * create / patch (draft edits)                 → ``can_create_invoice``.
  * CMR generation                               → ``can_generate_cmr``
    (dispatcher ALLOWED — real matrix, §8.3 row 4 ✓).
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.common import PaginatedResponse
from backend.schemas.mobile import (
    CmrOut,
    CmrRequest,
    InvoiceCreateRequest,
    InvoiceDetailOut,
    InvoiceOut,
    InvoiceTransitionRequest,
    InvoiceUpdateRequest,
)
from models.common import ErrorDetail
from models.invoice_models import (
    InvoiceCreate,
    InvoiceFinalizeRequest,
    InvoiceLineItem,
    InvoiceUpdate,
)
from repositories.invoice_repository import InvoiceRepository
from repositories.trip_repository import TripRepository
from services.invoicing.service import InvoiceService
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["mobile_invoicing"])


# ── Shared helpers (same pattern as fleet.py / clients.py) ──────────────


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


def _parse_date(val: Any) -> date:
    """Mirror desktop ``_row_to_invoice_result`` date parsing."""
    if isinstance(val, str) and val:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.fromisoformat(val).date()
            except ValueError:
                return date.today()
    if isinstance(val, date):
        return val
    return date.today()


def _fmt_dt(val: Any) -> Optional[str]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).isoformat()
    except ValueError:
        return str(val)


def _parse_line_items(row: Dict[str, Any]) -> List[dict]:
    raw = row.get("line_items_json")
    if not raw:
        return []
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
        return [InvoiceLineItem(**li).model_dump() for li in items]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _has_line_items(row: Dict[str, Any]) -> bool:
    """True when the invoice row carries at least one line item."""
    raw = row.get("line_items_json")
    if not raw:
        return False
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
        return bool(items)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False


def _invoice_row_to_out(row: Dict[str, Any]) -> dict:
    """Serialize a DB invoice row into the mobile InvoiceOut shape."""
    total_gross = float(row.get("total_gross") or row.get("total_amount") or 0)
    return {
        "id": row["id"],
        "invoice_number": row.get("invoice_number") or "",
        "client_id": row.get("client_id") or 0,
        "client_name": row.get("client_name") or "",
        "trip_id": row.get("trip_id"),
        "status": row.get("status") or "draft",
        "issue_date": _parse_date(row.get("issue_date")),
        "due_date": _parse_date(row.get("due_date")),
        "currency": row.get("currency") or "EUR",
        "subtotal_net": float(row.get("subtotal_net") or 0),
        "total_vat": float(row.get("total_vat") or 0),
        "total_gross": total_gross,
        "total_amount": float(row.get("total_amount") or total_gross),
        "currency": row.get("currency") or "EUR",
        "notes": row.get("notes") or "",
        "line_items": _parse_line_items(row),
        "efactura_status": row.get("efactura_status") or "",
        "efactura_xml_path": row.get("efactura_xml_path"),
        "efactura_submission_reference": row.get("efactura_submission_reference"),
        "created_at": _fmt_dt(row.get("created_at")),
        "updated_at": _fmt_dt(row.get("updated_at")),
    }


def _get_invoice_or_404(db: DatabaseManager, invoice_id: int, company_id: int) -> Dict[str, Any]:
    row = db.execute(
        "SELECT i.*, c.name AS client_name FROM invoices i "
        "LEFT JOIN clients c ON c.id = i.client_id "
        "WHERE i.id = ? AND i.company_id = ?",
        (invoice_id, company_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return dict(row)


def _raise_service_error(result) -> None:
    """Map an unsuccessful InvoiceService result to the correct HTTP status.

    Service errors carry a ``code``; ``invalid_status_transition`` and the
    immutable/not-found codes are translated to machine-readable ``error_code``
    values for the mobile client (422 / 404, never 500).
    """
    if result.success:
        return
    err = result.errors[0] if result.errors else ErrorDetail(message="Unknown error", code="error")
    code = (err.code or "").lower()
    if code == "permission_denied":
        raise HTTPException(status_code=403, detail=err.message)
    if code == "not_found":
        raise HTTPException(status_code=404, detail=err.message)
    if code == "invalid_status_transition":
        raise HTTPException(
            status_code=422,
            detail={"error_code": "invalid_transition", "detail": err.message},
        )
    if code == "immutable":
        raise HTTPException(
            status_code=422,
            detail={"error_code": "not_editable", "detail": err.message},
        )
    raise HTTPException(
        status_code=422,
        detail={"error_code": code or "invalid_transition", "detail": err.message},
    )


# ── List / Create ───────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[InvoiceOut])
def list_invoices(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str = Query("", description="Exact match on real invoice status string"),
    client_id: int = Query(0, ge=0, description="Filter by client id (0 = all)"),
    search: str = Query("", description="LIKE filter on invoice_number / client name"),
):
    """Paginated, company-scoped invoice list with status / client / search filters."""
    company_id = current_user["company_id"]
    conditions = ["i.company_id = ?"]
    params: list = [company_id]
    if status:
        conditions.append("i.status = ?")
        params.append(status)
    if client_id:
        conditions.append("i.client_id = ?")
        params.append(client_id)
    if search:
        like = f"%{search}%"
        conditions.append("(i.invoice_number LIKE ? OR COALESCE(c.name, '') LIKE ?)")
        params.extend([like, like])
    where = " AND ".join(conditions)

    cnt = db.execute(
        f"SELECT COUNT(*) AS cnt FROM invoices i LEFT JOIN clients c ON c.id = i.client_id "
        f"WHERE {where}",
        tuple(params),
    ).fetchone()
    total = cnt["cnt"] if cnt else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT i.*, c.name AS client_name FROM invoices i "
        f"LEFT JOIN clients c ON c.id = i.client_id "
        f"WHERE {where} ORDER BY i.issue_date DESC, i.id DESC LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    ).fetchall()

    items = [_invoice_row_to_out(dict(r)) for r in rows]
    return PaginatedResponse.from_items(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(
    data: InvoiceCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Create a draft invoice (gate: can_create_invoice).

    Totals are computed server-side by the REAL desktop calculator
    (``InvoiceService.create`` → ``_calculate_line_items``) — never trusted
    from the client.  Empty line items are rejected (422 ``empty_line_items``).
    """
    _check_permission(db, current_user.get("id") or 0, "can_create_invoice")
    company_id = current_user["company_id"]

    if not data.line_items:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "empty_line_items", "detail": "At least one line item is required"},
        )

    issue_date = data.issue_date or date.today()
    due_date = data.due_date or (issue_date + timedelta(days=30))
    if due_date < issue_date:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "invalid_dates", "detail": "Due date must be on or after issue date"},
        )

    request = InvoiceCreate(
        client_id=data.client_id,
        trip_id=data.trip_id,
        invoice_date=issue_date,
        due_date=due_date,
        currency=data.currency,
        exchange_rate=data.exchange_rate,
        invoice_type=data.invoice_type,
        line_items=data.line_items,
        notes=data.notes,
    )
    svc = InvoiceService(db)
    result = svc.create(request, user_id=current_user.get("id") or 0, company_id=company_id)
    if not result.success:
        _raise_service_error(result)
    return _invoice_row_to_out(_get_invoice_or_404(db, result.data.id, company_id))


@router.get("/{invoice_id}", response_model=InvoiceDetailOut)
def get_invoice(
    invoice_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Company-scoped invoice detail with client + trip context (404 for other companies)."""
    company_id = current_user["company_id"]
    row = _get_invoice_or_404(db, invoice_id, company_id)

    out = _invoice_row_to_out(row)

    # Client context
    client = None
    if row.get("client_id"):
        client = db.execute(
            "SELECT id, name, vat_number, address FROM clients WHERE id = ? AND company_id = ?",
            (row["client_id"], company_id),
        ).fetchone()
    if client:
        out["client_vat"] = client["vat_number"] or ""
        out["client_address"] = client["address"] or ""

    # Trip context
    if row.get("trip_id"):
        trip = db.execute(
            "SELECT id, cmr_number, place_of_loading, delivery_country, truck_number, "
            "driver_name FROM trips WHERE id = ? AND company_id = ?",
            (row["trip_id"], company_id),
        ).fetchone()
        if trip:
            out["trip_reference"] = trip["cmr_number"] or ""
            out["trip_origin"] = trip["place_of_loading"] or ""
            out["trip_destination"] = trip["delivery_country"] or ""
            out["truck_number"] = trip["truck_number"] or ""
            out["driver_name"] = trip["driver_name"] or ""
    return out


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: int,
    data: InvoiceUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Update a DRAFT invoice only (gate: can_create_invoice).

    Mirrors desktop ``update()`` immutability — any non-draft invoice is
    rejected with 422 ``not_editable``.  Line-item edits are recalculated by
    the REAL desktop calculator.
    """
    _check_permission(db, current_user.get("id") or 0, "can_create_invoice")
    company_id = current_user["company_id"]
    row = _get_invoice_or_404(db, invoice_id, company_id)

    if (row.get("status") or "") != "draft":
        raise HTTPException(
            status_code=422,
            detail={"error_code": "not_editable", "detail": "Only draft invoices can be edited"},
        )

    update = InvoiceUpdate(**data.model_dump(exclude_unset=True))
    svc = InvoiceService(db)
    result = svc.update(invoice_id, update, user_id=current_user.get("id") or 0)
    if not result.success:
        _raise_service_error(result)
    return _invoice_row_to_out(_get_invoice_or_404(db, invoice_id, company_id))


# ── State machine transitions ───────────────────────────────────────────


def _xml_path_for(invoice_number: str) -> str:
    """Bounded e-Factura XML storage path (per-invoice, sanitised filename)."""
    from utils.resource_path import data_path

    efactura_dir = data_path("data/efactura")
    os.makedirs(efactura_dir, exist_ok=True)
    safe = re.sub(r"[^\w\-.]+", "_", invoice_number) or f"invoice-{int(time.time())}"
    return os.path.join(efactura_dir, f"{safe}.xml")


def _generate_xml(
    db: DatabaseManager, svc: InvoiceService, invoice_id: int, user_id: int, company_id: int
):
    """Real e-Factura XML (UBL CIUS-RO) + status xml_generated.

    The transition itself is validated by the REAL state machine
    (``set_status`` → ``_validate_status_transition``), so generating XML on a
    non-finalized invoice returns 422 ``invalid_transition``.
    """
    result = svc.set_status(invoice_id, "xml_generated", user_id)
    if not result.success:
        return result

    get_result = svc.get(invoice_id)
    if not get_result.success:
        return get_result
    invoice = get_result.data

    # Buyer (AccountingCustomer) data — attached as private attrs, exactly the
    # way xml_export.py reads them.
    client = None
    if invoice.client_id:
        client = db.execute(
            "SELECT name, vat_number, address FROM clients WHERE id = ? AND company_id = ?",
            (invoice.client_id, company_id),
        ).fetchone()
    if client:
        setattr(invoice, "_buyer_name", client["name"] or "")
        setattr(invoice, "_buyer_cui", client["vat_number"] or "")
        setattr(invoice, "_buyer_address", client["address"] or "")
        setattr(invoice, "_buyer_county", "")
        setattr(invoice, "_buyer_city", "")
        setattr(invoice, "_buyer_country", "RO")

    from services.invoicing.config_manager import load_company_config
    from services.invoicing.xml_export import InvoiceXmlExport, SellerData

    exporter = InvoiceXmlExport(SellerData.from_company_config(load_company_config()))
    xml_path = _xml_path_for(invoice.invoice_number)
    exporter.export_to_file(invoice, xml_path)

    try:
        InvoiceRepository(db).update(invoice_id, {
            "efactura_xml_path": xml_path,
            "efactura_status": "generated",
        })
    except (ValueError, RuntimeError, TypeError) as exc:
        return InvoiceCreateResult_failed(f"Failed to store XML path: {exc}")
    return result


def _anaf_credentials_configured() -> bool:
    """True when e-Factura / ANAF credentials exist in the environment.

    No ANAF integration exists anywhere in this codebase — this check is the
    seam where real credentials would be validated.  Until a real integration
    lands, the answer is always False, which is exactly what makes
    ``OPERION_ENABLE_ANAF_SUBMISSION=true`` fail loudly (400
    ``anaf_not_configured``) instead of faking a submission.
    """
    return bool(
        os.environ.get("OPERION_ANAF_API_TOKEN")
        or os.environ.get("OPERION_ANAF_USERNAME")
        or os.environ.get("OPERION_ANAF_PASSWORD")
    )


def _submit(svc: InvoiceService, invoice_id: int, user_id: int, company_id: int, db: DatabaseManager):
    """Honest e-Factura submit — status-only transition (Gate-29 A3).

    EXTERNAL-INTEGRATION GAP (documented, honest):
    NO ANAF integration exists anywhere in this codebase.  The ``efactura_*``
    columns are storage-only: ``efactura_submission_reference`` holds a
    CLIENT-GENERATED reference (``EFAC-<invoice_id>-<uuid>``), never an ANAF
    submission id, and ``efactura_response_code`` / ``efactura_response_message``
    are RESERVED/DEAD columns that no code path writes.

    Behavior controlled by ``BackendSettings.enable_anaf_submission`` (env
    ``OPERION_ENABLE_ANAF_SUBMISSION``, default False):
      - False (default): the honest status-only transition proceeds — the
        invoice moves to ``submitted_externally`` (machine-validated: only
        from ``xml_generated``) and a generated reference is recorded.  A
        warning is logged on every call so operators cannot mistake it for a
        real submission.
      - True: the flag is the explicit opt-in that FORCES real ANAF
        integration.  Because no ANAF credentials exist yet, the handler
        returns 400 ``anaf_not_configured`` instead of faking success.  When
        a real integration + credentials are added, this branch must call it
        and only then transition the status.
    """
    from backend.config import BackendSettings

    settings = BackendSettings()
    if settings.enable_anaf_submission:
        if not _anaf_credentials_configured():
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "anaf_not_configured",
                    "detail": (
                        "ANAF integration is not configured. Set "
                        "OPERION_ENABLE_ANAF_SUBMISSION=true only after "
                        "e-Factura credentials are provided."
                    ),
                },
            )
        # Real ANAF submission goes here once the integration exists — the
        # status transition below must then only run on a confirmed ANAF
        # response (and write efactura_response_code/message).
    else:
        logger.warning(
            "e-Factura submit: OPERION_ENABLE_ANAF_SUBMISSION is False — "
            "status-only transition for invoice %s; NO ANAF submission occurs "
            "(honest stub).", invoice_id,
        )

    result = svc.set_status(invoice_id, "submitted_externally", user_id)
    if not result.success:
        return result
    submission_reference = f"EFAC-{invoice_id}-{uuid.uuid4().hex[:12].upper()}"
    try:
        InvoiceRepository(db).update(invoice_id, {
            "efactura_submission_reference": submission_reference,
            "efactura_submitted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "efactura_status": "submitted",
        })
    except (ValueError, RuntimeError, TypeError) as exc:
        return InvoiceCreateResult_failed(f"Failed to store submission reference: {exc}")
    return result


@router.post("/{invoice_id}/transition", response_model=InvoiceOut)
def transition_invoice(
    invoice_id: int,
    data: InvoiceTransitionRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Validate + apply one state-machine action (see module docstring for gates).

    Actions (REAL machine targets): finalize → finalized, generate_xml →
    xml_generated, submit → submitted_externally, mark_paid → paid,
    cancel → cancelled.  Every transition is validated against
    ``INVOICE_STATUS_TRANSITIONS``; illegal ones are 422 with a machine-
    readable ``error_code``, never 500.
    """
    user_id = current_user.get("id") or 0
    company_id = current_user["company_id"]
    action = data.action

    # Per-action gates (§8.4 → real PermissionService mapping, see module doc).
    if action == "cancel":
        _check_permission(db, user_id, "can_cancel_invoice")
    else:
        _check_permission(db, user_id, "can_finalize_invoice")

    row = _get_invoice_or_404(db, invoice_id, company_id)
    svc = InvoiceService(db)

    if action == "finalize":
        # Business rule (mobile): a finalized invoice must carry line items.
        if not _has_line_items(row):
            raise HTTPException(
                status_code=422,
                detail={"error_code": "empty_line_items",
                        "detail": "Cannot finalize an invoice with no line items"},
            )
        result = svc.finalize(InvoiceFinalizeRequest(invoice_id=invoice_id), user_id)
    elif action == "generate_xml":
        result = _generate_xml(db, svc, invoice_id, user_id, company_id)
    elif action == "submit":
        result = _submit(svc, invoice_id, user_id, company_id, db)
    elif action == "mark_paid":
        result = svc.set_status(invoice_id, "paid", user_id)
    else:  # cancel
        result = svc.cancel(invoice_id, user_id)

    _raise_service_error(result)
    return _invoice_row_to_out(_get_invoice_or_404(db, invoice_id, company_id))


# ── Invoice PDF ─────────────────────────────────────────────────────────


@router.get("/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Stream the desktop InvoiceGenerator PDF for this invoice."""
    company_id = current_user["company_id"]
    _get_invoice_or_404(db, invoice_id, company_id)

    svc = InvoiceService(db)
    result = svc.generate_pdf(invoice_id)
    if not result.success:
        _raise_service_error(result)
    path = getattr(result.data, "pdf_path", None)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Invoice PDF not found")
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))


# ── CMR generation (signature persistence + signed download) ────────────


def _register_document(
    db: DatabaseManager,
    file_path: str,
    title: str,
    category: str,
    entity_type: str,
    entity_id: int,
    company_id: int,
    tags: Optional[List[str]] = None,
    cmr_number: str = "",
    is_signed: int = 0,
) -> Optional[int]:
    """Register a stored file in the documents table (repo document pattern).

    Uses the real ``UploadService.register_existing`` (hash dedup, doc-number
    sequence, FTS triggers) with an explicit company_id so the Phase-2 signed
    download endpoint can serve it tenant-checked.
    """
    from repositories.document_repository import DocumentRepository
    from services.document.upload_service import UploadService

    return UploadService(db, DocumentRepository(db)).register_existing(
        file_path=file_path,
        title=title,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
        tags=tags or [],
        cmr_number=cmr_number,
        is_signed=is_signed,
        commit=True,
        company_id=company_id,
    )


def _save_signature_png(
    db: DatabaseManager, trip_id: int, raw: bytes, company_id: int
) -> str:
    """Persist the captured signature PNG (bounded storage + documents row)."""
    from utils.resource_path import data_path

    sig_dir = data_path(os.path.join("data", "documents", "cmr", str(trip_id)))
    os.makedirs(sig_dir, exist_ok=True)
    path = os.path.join(sig_dir, f"signature_{int(time.time() * 1000)}.png")
    with open(path, "wb") as fh:
        fh.write(raw)
    _register_document(
        db, path,
        title=f"CMR signature — trip {trip_id}",
        category="cmr", entity_type="cmr", entity_id=trip_id,
        company_id=company_id, tags=["cmr", "signature"], is_signed=1,
    )
    return path


@router.post("/{invoice_id}/cmr", response_model=CmrOut)
def generate_cmr(
    invoice_id: int,
    data: CmrRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Generate CMR PDFs for the invoice's trip (gate: can_generate_cmr).

    Reuses the desktop ``CMRGenerator`` (4 standard copies in
    ``data/documents/trips/{trip_id}``, trip ``cmr_number``/``cmr_status``
    updated).  The mobile-captured signature PNG is persisted to the documents
    table (``entity_type='cmr'``, ``entity_id=<trip_id>``) and embedded in the
    Sender copy.  Returns the CMR number + a short-lived signed PDF download
    URL (KIND_DOCUMENT token — Phase-2 signed-URL pattern).

    NOTE: the CMR number is pre-computed once and injected into the trip data
    so the PDF filenames, the trip row and the response all carry the SAME
    number (the desktop generator would otherwise allocate two consecutive
    sequence slots — a pre-existing quirk we avoid on the mobile path).
    """
    user_id = current_user.get("id") or 0
    _check_permission(db, user_id, "can_generate_cmr")
    company_id = current_user["company_id"]

    row = _get_invoice_or_404(db, invoice_id, company_id)
    trip_id = data.trip_id or row.get("trip_id")
    if not trip_id:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "no_trip", "detail": "Invoice has no associated trip"},
        )

    trip = TripRepository(db).get_by_id(trip_id, company_id=company_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # ── Persist the captured signature PNG (bounded) ──────────────────
    signature_path = None
    if data.signature_png_base64:
        try:
            raw = base64.b64decode(data.signature_png_base64, validate=True)
            if not raw:
                raise ValueError("empty payload")
            signature_path = _save_signature_png(db, trip_id, raw, company_id)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"error_code": "invalid_signature", "detail": "Invalid signature image"},
            ) from exc

    # ── Generate via the REAL desktop CMRGenerator (typed pydantic API) ──
    # ``CmrGenerateRequest`` + user_id: the generator re-validates the
    # permission (already gated above for the HTTP 403 mapping), re-fetches
    # the trip, allocates ONE sequence number, writes the 4 copies into
    # ``data/documents/trips/{trip_id}`` and updates the trip ``cmr_*``
    # fields — no deprecated dict API, no double sequence allocation.
    from models.cmr_models import CmrGenerateRequest
    from services.invoicing.cmr_generator import CMRGenerator

    request = CmrGenerateRequest(
        trip_id=trip_id,
        language=data.language,
        copies=data.copies,
        include_stamps=data.include_stamps,
        sender_name=data.sender_name,
        sender_address=data.sender_address,
        carrier_name=data.carrier_name,
        carrier_license=data.carrier_license,
        remarks=data.remarks,
        sig_sender_path=signature_path or "",
    )
    generator = CMRGenerator(db)
    result = generator.generate_all_copies(request, user_id)
    if not result.success:
        err = result.errors[0] if result.errors else None
        code = (err.code or "").upper() if err else ""
        message = err.message if err else "CMR generation failed"
        if code == "PERMISSION_DENIED":
            raise HTTPException(status_code=403, detail=message)
        if code in ("TRIP_NOT_FOUND", "NOT_FOUND"):
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=500, detail=message)

    cmr_number = result.data.cmr_number
    pdf_path = result.data.file_path
    if not cmr_number or not pdf_path or not os.path.isfile(pdf_path):
        raise HTTPException(status_code=500, detail="CMR PDF not generated")

    # ── Register the Sender copy in the documents table + signed URL ──
    pdf_doc_id = _register_document(
        db, pdf_path,
        title=f"CMR {cmr_number}",
        category="cmr", entity_type="cmr", entity_id=trip_id,
        company_id=company_id, tags=["cmr"],
        cmr_number=cmr_number,
    )
    if not pdf_doc_id:
        raise HTTPException(status_code=500, detail="Failed to register CMR document")

    from backend.services.local_download_service import KIND_DOCUMENT, create_download_token

    token = create_download_token(record_id=pdf_doc_id, company_id=company_id, kind=KIND_DOCUMENT)
    return CmrOut(
        cmr_number=cmr_number,
        pdf_url=f"/api/v1/mobile/company/export/download/{token}",
    )


def InvoiceCreateResult_failed(message: str):
    """Small helper: build a failed InvoiceCreateResult without circular import."""
    from models.invoice_models import InvoiceCreateResult

    return InvoiceCreateResult(
        success=False,
        errors=[ErrorDetail(message=message, code="update_failed")],
    )
