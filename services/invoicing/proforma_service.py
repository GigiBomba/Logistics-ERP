"""Proforma service — proforma invoice lifecycle: create, generate PDF, convert to invoice.

Provides both typed (Pydantic) and backward-compatible dict-based methods.
All write operations include permission checks via ``PermissionService``.
"""
from __future__ import annotations

import json
import logging
import os
import warnings
from datetime import date, datetime
from typing import Any, Optional

from models.common import ErrorDetail, ServiceResult
from models.proforma_models import ProformaCreate, ProformaCreateResult, ProformaResult
from repositories.client_repository import ClientRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.proforma_repository import (
    DEFAULT_PROFORMA_FORMAT_KEY,
    PROFORMA_NUMBER_FORMATS,
    ProformaRepository,
)
from services.invoicing.config_manager import load_company_config
from services.invoicing.generator import InvoiceGenerator
from services.operations.event_bus import PROFORMA_CREATED, EventBus
from services.operations.notification_center import NotificationCenter
from services.permission_service import PermissionService
from utils.resource_path import data_path

logger = logging.getLogger(__name__)


class ProformaService:
    """Proforma operations: legacy PDF workflow + typed CRUD with permission checks."""

    def __init__(self, db, prefs=None):
        self.db = db
        self.prefs = prefs
        self.generator = InvoiceGenerator()
        self._event_bus = EventBus()
        self._client_repo = ClientRepository(db)
        self._proforma_repo = ProformaRepository(db)
        self._invoice_repo = InvoiceRepository(db)
        self._perm = PermissionService(db)
        self._drafts_dir = data_path("proforma_drafts")
        if not os.path.exists(self._drafts_dir):
            os.makedirs(self._drafts_dir)

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_permission_service(self) -> PermissionService:
        return PermissionService(self.db)

    def _check(self, result, label=None):
        """Convert a PermissionCheckResult into an error ServiceResult, or return None."""
        if not result.allowed:
            msg = result.reason or "Permission denied"
            return ProformaCreateResult(
                success=False,
                errors=[ErrorDetail(message=msg, code="permission_denied")],
            )
        return None

    @staticmethod
    def _parse_date(val: Any) -> Optional[date]:
        """Parse a date string or return the value as-is if already a date."""
        if isinstance(val, date):
            return val
        if isinstance(val, str) and val:
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _parse_datetime(val: Any) -> Optional[datetime]:
        """Parse a datetime string or return the value as-is."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, str) and val:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None

    def _row_to_proforma_result(self, row: dict[str, Any]) -> Optional[ProformaResult]:
        """Convert a DB row dict to a ProformaResult."""
        if not row:
            return None

        # Resolve client_id from client_name
        client_id = 0
        client_name = row.get("client_name", "") or ""
        if client_name:
            client = self._client_repo.get_by_name(client_name)
            if client:
                client_id = client.get("id", 0)

        issue_date = self._parse_date(row.get("issue_date")) or date.today()
        valid_until = self._parse_date(row.get("valid_until")) or date.today()
        created_at = self._parse_datetime(row.get("created_at"))

        return ProformaResult(
            id=row["id"],
            proforma_number=row.get("proforma_number", ""),
            client_id=client_id,
            client_name=client_name,
            trip_id=row.get("trip_id") or None,
            issue_date=issue_date,
            valid_until=valid_until,
            currency=row.get("currency", "EUR"),
            total_amount=float(row.get("grand_total", row.get("total_amount", 0))),
            status=row.get("status", "Draft"),
            notes=row.get("notes", ""),
            pdf_path=row.get("pdf_path"),
            created_at=created_at,
        )

    # ── Format key ─────────────────────────────────────────────────────

    def get_format_key(self) -> str:
        if self.prefs:
            return self.prefs.get_setting("proforma_number_format") or DEFAULT_PROFORMA_FORMAT_KEY
        return DEFAULT_PROFORMA_FORMAT_KEY

    def set_format_key(self, fmt_key: str) -> None:
        if self.prefs and fmt_key in PROFORMA_NUMBER_FORMATS:
            self.prefs.save_setting("proforma_number_format", fmt_key)

    # ═══════════════════════════════════════════════════════════════════
    #  NEW TYPED CRUD METHODS
    # ═══════════════════════════════════════════════════════════════════

    # ── 1. create ─────────────────────────────────────────────────────

    def create(
        self,
        request: "ProformaCreate | dict[str, Any]",
        user_id: int = 0,
    ) -> ProformaCreateResult:
        """Create a new proforma invoice.

        Accepts ``ProformaCreate`` (preferred) or a plain dict (deprecated).

        Permission check: ``can_create_proforma(user_id)``
        """
        if isinstance(request, dict):
            warnings.warn(
                "dict for create() is deprecated, use ProformaCreate model",
                DeprecationWarning,
                stacklevel=2,
            )
            request = ProformaCreate(**request)

        # Permission check
        perm = self._get_permission_service()
        err = self._check(perm.can_create_proforma(user_id))
        if err:
            return err

        # Look up client
        client = self._client_repo.get_by_id(request.client_id)
        if not client:
            return ProformaCreateResult(
                success=False,
                errors=[ErrorDetail(
                    message=f"Client with id {request.client_id} not found",
                    code="CLIENT_NOT_FOUND",
                )],
            )

        # Calculate totals from items
        total_amount = 0.0
        for item in request.items:
            qty = float(item.get("quantity", 1))
            price = float(item.get("total", item.get("amount", item.get("unit_price", 0))))
            total_amount += qty * price
        total_amount = round(total_amount, 2)

        # Generate proforma number
        pf_number = self._proforma_repo.get_next_number(self.get_format_key())
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        # Persist to DB
        try:
            pf_id = self._proforma_repo.create(
                proforma_number=pf_number,
                issue_date=request.issue_date.isoformat(),
                valid_until=request.valid_until.isoformat(),
                client_name=client.get("name", ""),
                client_address=client.get("address", ""),
                client_vat=client.get("vat_number", ""),
                client_phone=client.get("phone", ""),
                client_email=client.get("email", ""),
                description="",
                notes=request.notes,
                line_items=request.items,
                subtotal=total_amount,
                grand_total=total_amount,
                currency=request.currency,
                status="Draft",
            )
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to create proforma: %s", exc, exc_info=True)
            return ProformaCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="create_failed")],
            )

        if pf_id is None:
            return ProformaCreateResult(
                success=False,
                errors=[ErrorDetail(message="Failed to create proforma in database", code="create_failed")],
            )

        logger.info("Proforma %s (id=%s) created by user %s", pf_number, pf_id, user_id)

        # Publish event
        self._event_bus.publish(PROFORMA_CREATED, {
            "proforma_id": pf_id,
            "proforma_number": pf_number,
            "grand_total": total_amount,
            "client_name": client.get("name", ""),
        })

        # Build result
        result = ProformaResult(
            id=pf_id,
            proforma_number=pf_number,
            client_id=request.client_id,
            client_name=client.get("name", ""),
            trip_id=request.trip_id,
            issue_date=request.issue_date,
            valid_until=request.valid_until,
            currency=request.currency,
            total_amount=total_amount,
            status="Draft",
            notes=request.notes,
            pdf_path=None,
            created_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
        )
        return ProformaCreateResult(success=True, data=result)

    # ── 2. get ────────────────────────────────────────────────────────

    def get(self, proforma_id: int) -> ProformaCreateResult:
        """Fetch a single proforma by ID."""
        try:
            row = self._proforma_repo.get_by_id(proforma_id)
            if not row:
                return ProformaCreateResult(
                    success=False,
                    errors=[ErrorDetail(message="Proforma not found", code="NOT_FOUND")],
                )
            result = self._row_to_proforma_result(row)
            return ProformaCreateResult(success=True, data=result)
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.exception("Error fetching proforma %s", proforma_id)
            return ProformaCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="FETCH_ERROR")],
            )

    # ── 3. list_all ───────────────────────────────────────────────────

    def list_all(self) -> "ServiceResult[list[ProformaResult]]":
        """Return all proformas as a typed list result."""
        try:
            rows = self._proforma_repo.get_all()
            items: list[ProformaResult] = []
            for row in rows:
                r = self._row_to_proforma_result(row)
                if r is not None:
                    items.append(r)
            return ServiceResult(success=True, data=items)
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.exception("Error listing proformas")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="LIST_ERROR")],
            )

    # ── 4. update ──────────────────────────────────────────────────────

    def update(self, proforma_id: int, data: dict[str, Any], user_id: int) -> ServiceResult:
        """Update an existing proforma invoice's editable fields.

        Permission check: ``can_update_proforma(user_id)``

        Supported fields: ``notes``, ``currency``, ``valid_until``, ``status``.
        """
        # Permission check
        perm = self._get_permission_service()
        err = self._check(perm.can_update_proforma(user_id))
        if err:
            return err

        # Check existence
        row = self._proforma_repo.get_by_id(proforma_id)
        if not row:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Proforma not found", code="NOT_FOUND")],
            )

        # Build updates dict with only allowed fields
        updates: dict[str, Any] = {}
        if "notes" in data:
            updates["notes"] = str(data["notes"])
        if "currency" in data:
            updates["currency"] = str(data["currency"]).upper()
        if "valid_until" in data:
            valid_until = self._parse_date(data["valid_until"])
            updates["valid_until"] = valid_until.isoformat() if valid_until else str(data["valid_until"])
        if "status" in data:
            updates["status"] = str(data["status"])

        if not updates:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="No updateable fields provided", code="NO_UPDATES")],
            )

        ok = self._proforma_repo.update(proforma_id, **updates)
        if not ok:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Failed to update proforma in database", code="UPDATE_FAILED")],
            )

        logger.info("Proforma %s updated by user %s — fields: %s", proforma_id, user_id, list(updates.keys()))

        # Return refreshed proforma data
        return self.get(proforma_id)

    # ── 5. generate_pdf ───────────────────────────────────────────────

    def generate_pdf(self, proforma_id: int) -> ProformaCreateResult:
        """Generate a PDF for the given proforma and store the path."""
        row = self._proforma_repo.get_by_id(proforma_id)
        if not row:
            return ProformaCreateResult(
                success=False,
                errors=[ErrorDetail(message="Proforma not found", code="NOT_FOUND")],
            )

        # Build data dict for the legacy generator
        client_name = row.get("client_name", "")
        proforma_data: dict[str, Any] = {
            "proforma_number": row.get("proforma_number", ""),
            "issue_date": row.get("issue_date", ""),
            "valid_until": row.get("valid_until", ""),
            "grand_total": float(row.get("grand_total", row.get("total_amount", 0))),
            "currency": row.get("currency", "EUR"),
            "notes": row.get("notes", ""),
            "client": {
                "name": client_name,
                "address": row.get("client_address", ""),
                "vat_number": row.get("client_vat", ""),
                "phone": row.get("client_phone", ""),
                "email": row.get("client_email", ""),
            },
            "mode": row.get("mode", "client"),
            "logo_path": row.get("logo_path", ""),
            "signature_path": row.get("signature_path", ""),
            "stamp_path": row.get("stamp_path", ""),
            "company_color": row.get("company_color", "#6366f1"),
        }

        # Add line items
        line_items_json = row.get("line_items_json")
        if line_items_json:
            try:
                items = json.loads(line_items_json) if isinstance(line_items_json, str) else line_items_json
                proforma_data["line_items"] = items
            except (json.JSONDecodeError, TypeError):
                pass

        try:
            pdf_path = self.generator.generate_rich(proforma_data, document_type="proforma")
        except (ValueError, RuntimeError, OSError) as exc:
            logger.error("Failed to generate PDF for proforma %s: %s", proforma_id, exc, exc_info=True)
            return ProformaCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="PDF_GENERATION_FAILED")],
            )

        logger.info("PDF generated for proforma %s at %s", proforma_id, pdf_path)

        # Store pdf_path
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            self._proforma_repo.update(proforma_id, pdf_path=pdf_path, updated_at=now)
        except (ValueError, RuntimeError, OSError) as exc:
            logger.warning("Failed to store pdf_path for proforma %s: %s", proforma_id, exc)

        # Register in Document Center
        if os.path.isfile(pdf_path):
            try:
                from services.document_service import DocumentService
                ds = DocumentService(self.db)
                ds.register_existing(
                    file_path=pdf_path,
                    title=f"Proforma {os.path.basename(pdf_path)}",
                    category="proformas",
                    tags=["proforma"],
                )
            except (ValueError, OSError, RuntimeError):
                logger.warning("Failed to register proforma PDF in Document Center", exc_info=True)

        # Build result
        result = self._row_to_proforma_result(row)
        if result:
            result.pdf_path = pdf_path
        return ProformaCreateResult(success=True, data=result)

    # ── 5. convert_to_invoice ─────────────────────────────────────────

    def convert_to_invoice(self, proforma_id: int, user_id: int) -> ServiceResult:
        """Convert a proforma to an actual invoice.

        Permission check: ``can_create_invoice(user_id)``
        """
        # Permission check
        perm = self._get_permission_service()
        err = self._check(perm.can_create_invoice(user_id))
        if err:
            return err

        # Fetch proforma
        row = self._proforma_repo.get_by_id(proforma_id)
        if not row:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Proforma not found", code="NOT_FOUND")],
            )

        current_status = row.get("status", "").lower()
        if current_status == "converted":
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    message="Proforma has already been converted to an invoice",
                    code="ALREADY_CONVERTED",
                )],
            )

        # Resolve client_id from client_name
        client_name = row.get("client_name", "") or ""
        client_id = 0
        if client_name:
            client = self._client_repo.get_by_name(client_name)
            if client:
                client_id = client.get("id", 0)

        # Generate invoice number
        inv_number = self._invoice_repo.get_next_number()
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        # Build invoice data
        invoice_data: dict[str, Any] = {
            "invoice_number": inv_number,
            "issue_date": row.get("issue_date", ""),
            "due_date": row.get("valid_until", ""),
            "total_amount": float(row.get("grand_total", row.get("total_amount", 0))),
            "status": "draft",
            "client_id": client_id,
            "currency": row.get("currency", "EUR"),
            "notes": f"Converted from proforma #{row.get('proforma_number', '')}. {row.get('notes', '')}",
            "line_items_json": row.get("line_items_json", "[]"),
            "subtotal_net": float(row.get("subtotal", 0)),
            "total_vat": float(row.get("tax_amount", 0)),
            "total_gross": float(row.get("grand_total", row.get("total_amount", 0))),
            "created_at": now,
            "updated_at": now,
        }

        try:
            invoice_id = self._invoice_repo.create(invoice_data)
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to create invoice from proforma %s: %s", proforma_id, exc, exc_info=True)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="INVOICE_CREATE_FAILED")],
            )

        # Update proforma status
        try:
            self._proforma_repo.update_status(proforma_id, "Converted")
            self._proforma_repo.update(proforma_id, updated_at=now)
        except (ValueError, RuntimeError) as exc:
            logger.warning("Failed to update proforma %s status after conversion: %s", proforma_id, exc)

        logger.info(
            "Proforma %s (id=%s) converted to invoice %s (id=%s) by user %s",
            row.get("proforma_number", ""), proforma_id,
            inv_number, invoice_id, user_id,
        )

        # Publish event
        self._event_bus.publish(PROFORMA_CREATED, {
            "proforma_id": proforma_id,
            "proforma_number": row.get("proforma_number", ""),
            "converted_to_invoice_id": invoice_id,
            "invoice_number": inv_number,
        })

        return ServiceResult(
            success=True,
            data={
                "invoice_id": invoice_id,
                "invoice_number": inv_number,
                "proforma_id": proforma_id,
                "proforma_number": row.get("proforma_number", ""),
            },
        )

    # ═══════════════════════════════════════════════════════════════════
    #  LEGACY METHODS (backward-compatible, with deprecation warnings)
    # ═══════════════════════════════════════════════════════════════════

    def generate(self, proforma_data: dict[str, Any], mode: str = "client") -> str:
        """Generate a proforma invoice PDF (does not persist to DB or Document Center).

        .. deprecated::
            Use :meth:`create` with a ``ProformaCreate`` model instead.
        """
        warnings.warn(
            "generate() is deprecated — use create(request, user_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.generator.generate_rich(proforma_data, document_type="proforma")

    def generate_and_record(self, proforma_data: dict[str, Any]) -> str:
        """Generate proforma PDF, persist to DB, register in Document Center, publish event.

        .. deprecated::
            Use :meth:`create` with a ``ProformaCreate`` model and user_id instead.
        """
        warnings.warn(
            "generate_and_record() is deprecated — use create(request, user_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        mode = proforma_data.get("mode", "client")

        # Resolve proforma number
        pf_number = proforma_data.get("proforma_number", "")
        if not pf_number:
            pf_number = self._proforma_repo.get_next_number()
            proforma_data["proforma_number"] = pf_number

        # Set issue_date if missing
        if not proforma_data.get("issue_date"):
            proforma_data["issue_date"] = datetime.now().strftime("%Y-%m-%d")

        # Generate PDF
        path = self.generator.generate_rich(proforma_data, document_type="proforma")

        # Persist to DB
        client = proforma_data.get("client", {})
        line_items = proforma_data.get("addon_items") or proforma_data.get("line_items", [])

        pf_id = self._proforma_repo.create(
            proforma_number=pf_number,
            issue_date=proforma_data.get("issue_date", ""),
            valid_until=proforma_data.get("valid_until", ""),
            client_name=client.get("name", ""),
            client_address=client.get("address", ""),
            client_vat=client.get("vat_number", ""),
            client_phone=client.get("phone", ""),
            client_email=client.get("email", ""),
            description=proforma_data.get("description", ""),
            notes=proforma_data.get("notes", ""),
            line_items=line_items,
            subtotal=proforma_data.get("subtotal", 0),
            discount_type=proforma_data.get("discount_type", ""),
            discount_value=proforma_data.get("discount_value", 0),
            discount_amount=proforma_data.get("discount", 0),
            tax_rate=proforma_data.get("tax_rate", 0),
            tax_amount=proforma_data.get("total_tax", 0),
            grand_total=proforma_data.get("grand_total", 0),
            currency=proforma_data.get("currency", "EUR"),
            mode=mode,
            status="Draft",
            logo_path=proforma_data.get("logo_path", ""),
            signature_path=proforma_data.get("signature_path", ""),
            stamp_path=proforma_data.get("stamp_path", ""),
            company_color=proforma_data.get("company_color", "#6366f1"),
        )

        if pf_id is not None:
            proforma_data["_record_id"] = pf_id
            self._event_bus.publish(PROFORMA_CREATED, {
                "proforma_id": pf_id,
                "proforma_number": pf_number,
                "grand_total": proforma_data.get("grand_total", 0),
                "client_name": client.get("name", ""),
            })
        else:
            logger.warning("Proforma DB record creation failed — PDF exists at %s without DB entry", path)

        # Register in Document Center
        if os.path.isfile(path):
            try:
                from services.document_service import DocumentService
                ds = DocumentService(self.db)
                ds.register_existing(
                    file_path=path,
                    title=f"Proforma {os.path.basename(path)}",
                    category="proformas",
                    tags=["proforma", mode],
                )
            except (ValueError, OSError, RuntimeError):
                logger.warning("Failed to register proforma in Document Center", exc_info=True)

        return path

    def save_draft(self, data: dict[str, Any], name: str) -> bool:
        """Save a proforma draft JSON file.

        .. deprecated::
            Use :meth:`create` with a ``ProformaCreate`` model instead.
        """
        warnings.warn(
            "save_draft() is deprecated — use create(request, user_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        if not name.strip():
            return False
        draft = dict(data)
        draft["_draft_saved_at"] = datetime.now().isoformat()
        path = os.path.join(self._drafts_dir, f"{name.strip()}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(draft, f, ensure_ascii=False, indent=2)
            return True
        except (OSError, TypeError):
            logger.warning("Failed to save draft: %s", path)
            return False

    def load_draft(self, name: str) -> Optional[dict[str, Any]]:
        """Load a proforma draft by name (without .json).

        .. deprecated::
            Use :meth:`get` with a proforma ID instead.
        """
        warnings.warn(
            "load_draft() is deprecated — use get(proforma_id) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        path = os.path.join(self._drafts_dir, f"{name}.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to load draft: %s", path)
            return None

    def list_drafts(self) -> list[str]:
        """Return draft names sorted newest-first.

        .. deprecated::
            Use :meth:`list_all` instead.
        """
        warnings.warn(
            "list_drafts() is deprecated — use list_all() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        if not os.path.isdir(self._drafts_dir):
            return []
        try:
            drafts = []
            for fn in os.listdir(self._drafts_dir):
                if fn.endswith(".json"):
                    drafts.append(fn[:-5])
            return sorted(drafts, reverse=True)
        except (OSError, PermissionError):
            logger.warning("Failed to list drafts in %s", self._drafts_dir)
            return []

    def send_email(
        self,
        proforma_id: int,
        recipient: str,
        smtp_config: Optional[dict[str, str]] = None,
        proforma_data: Optional[dict[str, Any]] = None,
        include_linked_docs: bool = False,
        skip_generate: bool = False,
    ) -> bool:
        """Send the proforma PDF by email. Optionally include linked CMR/invoice documents.

        .. deprecated::
            Will be replaced with a typed email method in a future release.
        """
        warnings.warn(
            "send_email() is deprecated and will be replaced with a typed method",
            DeprecationWarning,
            stacklevel=2,
        )
        data = proforma_data or {}
        if not recipient:
            raise ValueError("Recipient email address is required")

        if smtp_config is None and self.prefs:
            smtp_config = self.prefs.get_smtp_config()
        if not smtp_config or not smtp_config.get("smtp_server") or not smtp_config.get("smtp_user"):
            raise ValueError("SMTP not configured")

        if skip_generate:
            path = data.get("_generated_path", "")
        else:
            path = self.generate_and_record(data)
            data["_generated_path"] = path
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Proforma PDF not found: {path}")

        nc = NotificationCenter(self.db)
        nc.configure_smtp(
            smtp_config.get("smtp_server", ""),
            int(smtp_config.get("smtp_port", "587")),
            smtp_config.get("smtp_user", ""),
            smtp_config.get("smtp_password", ""),
        )

        attachments = [path]

        if include_linked_docs and proforma_id:
            try:
                from repositories.document_repository import DocumentRepository
                doc_repo = DocumentRepository(self.db)
                linked_docs = doc_repo.get_documents_for_entity("proforma", proforma_id)
                for ld in linked_docs:
                    fp = ld.get("file_path", "")
                    if fp and os.path.isfile(fp):
                        attachments.append(fp)
            except (ValueError, RuntimeError, TypeError):
                logger.warning("Failed to fetch linked docs for proforma %s", proforma_id, exc_info=True)

        conf = load_company_config()
        client_name = data.get("client", {}).get("name", "")
        pf_number = data.get("proforma_number", "Proforma")
        grand_total = data.get("grand_total", 0)
        valid_until = data.get("valid_until", "")

        subject = f"Proforma {pf_number} — {client_name}" if client_name else f"Proforma {pf_number}"
        body = (
            f"Dear Sir/Madam,\n\n"
            f"Please find attached proforma {pf_number}.\n"
        )
        if grand_total:
            body += f"Total amount: {grand_total:.2f} {data.get('currency', 'EUR')}\n"
        if valid_until:
            body += f"Valid until: {valid_until}\n"
        body += (
            f"\nThank you for your business.\n\n"
            f"Best regards,\n"
            f"{conf.get('company_name', '')}"
        )

        if nc.send_email(recipient, subject, body, attachments=attachments):
            try:
                self._proforma_repo.update_status(proforma_id, "Sent")
            except (ValueError, RuntimeError):
                logger.warning("Failed to update proforma status to Sent")
            return True
        return False
