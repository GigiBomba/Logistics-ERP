"""Invoice service — PDF generation, email, and typed CRUD operations."""
from __future__ import annotations

import json
import logging
import os
import warnings
from datetime import datetime, timedelta
from typing import Any, Optional

from repositories.client_repository import ClientRepository
from repositories.invoice_repository import (
    DEFAULT_INVOICE_FORMAT_KEY,
    INVOICE_NUMBER_FORMATS,
    InvoiceRepository,
)
from services.audit_service import AuditService
from services.i18n import t
from services.invoicing.config_manager import load_company_config
from services.invoicing.generator import InvoiceGenerator
from services.operations.event_bus import INVOICE_CREATED, INVOICE_EMAILED, EventBus
from services.operations.notification_center import NotificationCenter
from services.permission_service import PermissionService

from models.common import ErrorDetail, ServiceResult
from models.invoice_models import (
    INVOICE_STATUS_TRANSITIONS,
    InvoiceCreate,
    InvoiceCreateResult,
    InvoiceFinalizeRequest,
    InvoiceLineItem,
    InvoiceListResult,
    InvoiceResult,
    InvoiceUpdate,
)

logger = logging.getLogger(__name__)


class InvoiceService:
    """Invoice operations: legacy PDF workflow + typed CRUD with permission checks."""

    def __init__(self, db, prefs=None):
        self.db = db
        self.prefs = prefs
        self.generator = InvoiceGenerator()
        self._event_bus = EventBus()
        self._client_repo = ClientRepository(db)
        self._invoice_repo = InvoiceRepository(db)

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_permission_service(self) -> PermissionService:
        return PermissionService(self.db)

    def _check(self, result, label=None):
        """Convert a PermissionCheckResult into an error ServiceResult, or return None."""
        if not result.allowed:
            msg = result.reason or "Permission denied"
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=msg, code="permission_denied")],
            )
        return None

    def _calculate_line_items(
        self, items: list[InvoiceLineItem]
    ) -> tuple[list[InvoiceLineItem], float, float, float]:
        """Fill in computed totals for each line item and return aggregates.

        Romanian-compliant calculation:
            taxable_amount = (qty * unit_price) - discount_amount
            vat_amount = taxable_amount * vat_rate / 100
            line_total = taxable_amount + vat_amount
        """
        calculated: list[InvoiceLineItem] = []
        for li in items:
            qty = li.quantity or 1.0
            price = li.unit_price or 0.0
            gross_value = round(qty * price, 2)

            # Discount
            discount_pct = li.discount_percent or 0.0
            discount_amt = li.discount_amount or 0.0
            if discount_amt == 0 and discount_pct > 0:
                discount_amt = round(gross_value * discount_pct / 100, 2)
            if discount_amt > gross_value:
                discount_amt = gross_value

            taxable_amount = li.taxable_amount if li.taxable_amount is not None else round(gross_value - discount_amt, 2)
            vat_rate = li.vat_rate or 0.0
            vat_amount = li.vat_amount if li.vat_amount is not None else round(taxable_amount * vat_rate / 100, 2)
            line_total = li.line_total if li.line_total is not None else round(taxable_amount + vat_amount, 2)

            calculated.append(
                InvoiceLineItem(
                    description=li.description,
                    quantity=qty,
                    unit_of_measure=li.unit_of_measure or "buc",
                    unit_price=price,
                    discount_percent=discount_pct,
                    discount_amount=discount_amt,
                    taxable_amount=taxable_amount,
                    vat_rate=vat_rate,
                    vat_amount=vat_amount,
                    line_total=line_total,
                )
            )
        subtotal_net = round(sum(float(li.taxable_amount or 0) for li in calculated), 2)
        total_vat = round(sum(float(li.vat_amount or 0) for li in calculated), 2)
        total_gross = round(sum(float(li.line_total or 0) for li in calculated), 2)
        return calculated, subtotal_net, total_vat, total_gross

    def _row_to_invoice_result(self, row: dict[str, Any]) -> InvoiceResult:
        """Convert a DB row dict to an InvoiceResult, deserializing line items."""
        line_items: list[InvoiceLineItem] = []
        raw_json = row.get("line_items_json")
        if raw_json:
            try:
                raw_items = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                line_items = [InvoiceLineItem(**li) for li in raw_items]
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("Failed to deserialize line_items_json for invoice %s", row.get("id"))

        invoice_date = row.get("issue_date", "")
        due_date = row.get("due_date", "")

        def _parse_date(val: Any):
            if isinstance(val, str) and val:
                try:
                    return datetime.strptime(val, "%Y-%m-%d").date()
                except ValueError:
                    return datetime.fromisoformat(val).date()
            return val

        client_name = ""
        client_id = row.get("client_id")
        if client_id:
            client = self._client_repo.get_by_id(client_id)
            if client:
                client_name = client.get("name") or client.get("company_name") or ""

        trip_reference = ""

        created_at = row.get("created_at")
        if isinstance(created_at, str) and created_at:
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                pass
        updated_at = row.get("updated_at")
        if isinstance(updated_at, str) and updated_at:
            try:
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except ValueError:
                pass

        return InvoiceResult(
            id=row["id"],
            invoice_number=row.get("invoice_number", ""),
            client_id=row.get("client_id") or 0,
            client_name=client_name,
            trip_id=row.get("trip_id"),
            trip_reference=trip_reference,
            invoice_date=_parse_date(invoice_date) if invoice_date else datetime.now().date(),
            due_date=_parse_date(due_date) if due_date else datetime.now().date(),
            currency=row.get("currency", "EUR"),
            exchange_rate=float(row.get("exchange_rate", 1.0)),
            invoice_type=row.get("invoice_type", "invoice"),
            line_items=line_items,
            subtotal_net=float(row.get("subtotal_net", row.get("total_amount", 0))),
            total_vat=float(row.get("total_vat", 0)),
            total_gross=float(row.get("total_gross", row.get("total_amount", 0))),
            amount_paid=float(row.get("amount_paid", 0)),
            amount_remaining=float(row.get("amount_remaining", row.get("total_amount", 0))),
            status=row.get("status", "draft"),
            notes=row.get("notes", ""),
            pdf_path=row.get("pdf_path"),
            efactura_status=row.get("efactura_status", ""),
            efactura_xml_path=row.get("efactura_xml_path"),
            efactura_submission_id=row.get("efactura_submission_id"),
            efactura_response_code=row.get("efactura_response_code", ""),
            efactura_response_message=row.get("efactura_response_message", ""),
            created_at=created_at,
            updated_at=updated_at,
        )

    # ── Format key (unchanged) ─────────────────────────────────────────

    def get_format_key(self) -> str:
        if self.prefs:
            return self.prefs.get_setting("invoice_number_format") or DEFAULT_INVOICE_FORMAT_KEY
        return DEFAULT_INVOICE_FORMAT_KEY

    def set_format_key(self, fmt_key: str) -> None:
        if self.prefs and fmt_key in INVOICE_NUMBER_FORMATS:
            self.prefs.save_setting("invoice_number_format", fmt_key)

    # ── Legacy helpers (unchanged) ─────────────────────────────────────

    def _enrich_trip_with_client(self, trip_data: dict[str, Any]) -> dict[str, Any]:
        client_id = trip_data.get("client_id")
        if not client_id:
            return trip_data
        client = self._client_repo.get_by_id(client_id)
        if not client:
            return trip_data
        enriched = dict(trip_data)
        enriched["client_vat"] = client.get("vat_number") or ""
        enriched["client_address"] = client.get("address") or ""
        enriched["client_phone"] = client.get("phone") or ""
        enriched["client_email"] = client.get("email") or ""
        enriched["client_contact"] = client.get("contact_person") or ""
        return enriched

    def generate(self, trip_data: dict[str, Any], mode: str = "client") -> str:
        enriched = self._enrich_trip_with_client(trip_data)
        return self.generator.generate(enriched, mode=mode)

    def create_record(self, trip_id: int, inv_number: str, amount: float, due_date: str) -> None:
        self.db.create_invoice_record(trip_id, inv_number, amount, due_date)

    def generate_and_record(self, trip_data: dict[str, Any], mode: str = "client", company_id=None) -> str:
        path = self.generate(trip_data, mode=mode)
        if mode == "client":
            due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            trip_id = trip_data.get("id", 0)
            inv_number = f"INV-{datetime.now().year}-{trip_id:04d}"
            total_price = trip_data.get("total_price_eur", 0) or 0
            try:
                self.create_record(
                    trip_id=trip_id,
                    inv_number=inv_number,
                    amount=total_price,
                    due_date=due_date,
                )
                self._event_bus.publish(INVOICE_CREATED, {
                    "trip_id": trip_id,
                    "invoice_number": inv_number,
                    "amount": total_price,
                    "due_date": due_date,
                })
            except (ValueError, RuntimeError, OSError) as exc:
                logger.warning("Invoice record creation failed (PDF already exists at %s): %s", path, exc)
        if os.path.isfile(path):
            try:
                from services.document_service import DocumentService
                ds = DocumentService(self.db)
                ds.register_existing(
                    file_path=path,
                    title=f"Invoice {os.path.basename(path)}",
                    category="invoices",
                    entity_type="trip",
                    entity_id=trip_data.get("id", 0),
                    tags=["invoice", mode],
                )
            except (ValueError, OSError, RuntimeError):
                logger.warning("Failed to register invoice in Document Center", exc_info=True)
        return path

    def send_invoice_email(
        self,
        trip_id: int,
        recipient: str,
        smtp_config: Optional[dict[str, str]] = None,
        trip_data: Optional[dict[str, Any]] = None,
        mode: str = "client",
        company_id=None,
    ) -> bool:
        trip = trip_data or {}
        if not recipient:
            raise ValueError("Recipient email address is required")

        if smtp_config is None and self.prefs:
            smtp_config = self.prefs.get_smtp_config()
        if not smtp_config or not smtp_config.get("smtp_server") or not smtp_config.get("smtp_user"):
            raise ValueError("SMTP not configured")

        path = self.generate_and_record(trip, mode=mode)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Invoice PDF not found: {path}")

        nc = NotificationCenter(self.db)
        nc.configure_smtp(
            smtp_config.get("smtp_server", ""),
            int(smtp_config.get("smtp_port", "587")),
            smtp_config.get("smtp_user", ""),
            smtp_config.get("smtp_password", ""),
        )

        conf = load_company_config()
        client_name = trip.get("client_name", t("invoice.default_client"))
        filename = os.path.basename(path)
        subject = t("email.invoice_subject").format(filename=filename, client=client_name)
        body = t("email.invoice_body").format(
            trip_id=trip_id,
            company=conf.get("company_name", ""),
        )

        if nc.send_email(recipient, subject, body, attachments=[path]):
            self._event_bus.publish(INVOICE_EMAILED, {
                "trip_id": trip_id,
                "invoice_number": filename.replace(".pdf", ""),
                "recipient": recipient,
            })
            return True
        return False

    # ═══════════════════════════════════════════════════════════════════
    #  NEW TYPED CRUD METHODS
    # ═══════════════════════════════════════════════════════════════════

    # ── 1. create ─────────────────────────────────────────────────────

    def create(
        self,
        request: "InvoiceCreate | dict[str, Any]",
        user_id: int = 0,
        company_id: Optional[int] = None,
    ) -> InvoiceCreateResult:
        """Create a new invoice.

        Accepts ``InvoiceCreate`` (preferred) or a plain dict (deprecated).

        ``company_id`` (JWT-derived, mobile path) is injected into the insert
        when provided; when omitted the request-context tenant scoping applies
        (desktop behaviour — unchanged).
        """
        if isinstance(request, dict):
            warnings.warn(
                "dict for create() is deprecated, use InvoiceCreate model",
                DeprecationWarning,
                stacklevel=2,
            )
            request = InvoiceCreate(**request)

        # Permission check
        perm = self._get_permission_service()
        err = self._check(perm.can_create_invoice(user_id))
        if err:
            return err

        # Calculate line item totals
        calculated_items, subtotal_net, total_vat, total_gross = (
            self._calculate_line_items(request.line_items)
        )

        # Generate invoice number
        inv_number = self._invoice_repo.get_next_number(self.get_format_key())
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        data: dict[str, Any] = {
            "invoice_number": inv_number,
            "issue_date": request.invoice_date.isoformat(),
            "due_date": request.due_date.isoformat(),
            "total_amount": total_gross,
            "status": "draft",
            "client_id": request.client_id,
            "trip_id": request.trip_id,
            "currency": request.currency,
            "exchange_rate": request.exchange_rate,
            "invoice_type": request.invoice_type,
            "notes": request.notes,
            "subtotal_net": subtotal_net,
            "total_vat": total_vat,
            "total_gross": total_gross,
            "amount_paid": 0.0,
            "amount_remaining": total_gross,
            "created_at": now,
            "updated_at": now,
        }
        if calculated_items:
            data["line_items_json"] = json.dumps(
                [li.model_dump() for li in calculated_items]
            )
        if company_id is not None:
            data["company_id"] = company_id

        try:
            invoice_id = self._invoice_repo.create(data)
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to create invoice: %s", exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="create_failed")],
            )

        # Publish event
        self._event_bus.publish(INVOICE_CREATED, {
            "invoice_id": invoice_id,
            "invoice_number": inv_number,
        })

        # Audit log
        AuditService(self.db).log(
            event_type="invoice.created",
            entity_type="invoice",
            entity_id=str(invoice_id),
            data={
                "invoice_number": inv_number,
                "client_id": request.client_id,
                "trip_id": request.trip_id,
                "total_gross": total_gross,
                "currency": request.currency,
            },
            user_id=user_id,
        )

        # Build result
        result = InvoiceResult(
            id=invoice_id,
            invoice_number=inv_number,
            client_id=request.client_id,
            client_name="",
            trip_id=request.trip_id,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            currency=request.currency,
            exchange_rate=request.exchange_rate,
            invoice_type=request.invoice_type,
            line_items=calculated_items,
            subtotal_net=subtotal_net,
            total_vat=total_vat,
            total_gross=total_gross,
            amount_paid=0.0,
            amount_remaining=total_gross,
            status="draft",
            notes=request.notes,
            pdf_path=None,
            created_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
        )
        return InvoiceCreateResult(success=True, data=result)

    # ── 2. update ─────────────────────────────────────────────────────

    def update(
        self,
        invoice_id: int,
        request: "InvoiceUpdate | dict[str, Any]",
        user_id: int = 0,
    ) -> InvoiceCreateResult:
        """Update an existing invoice.

        Accepts ``InvoiceUpdate`` (preferred) or a plain dict (deprecated).
        """
        if isinstance(request, dict):
            warnings.warn(
                "dict for update() is deprecated, use InvoiceUpdate model",
                DeprecationWarning,
                stacklevel=2,
            )
            request = InvoiceUpdate(**request)

        # Permission check (skip for system/internal user_id=0, matching TripService behaviour)
        if user_id:
            perm = self._get_permission_service()
            err = self._check(perm.can_create_invoice(user_id))
            if err:
                return err

        # Fetch existing
        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        # Immutable archival: finalized invoices cannot be edited
        current_status = row.get("status", "")
        if current_status in ("finalized", "accepted", "paid", "cancelled"):
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(
                    message=f"Cannot update invoice with status '{current_status}'",
                    code="immutable",
                )],
            )

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        update_data: dict[str, Any] = {"updated_at": now}

        # Map scalar fields
        field_map = {
            "client_id": "client_id",
            "trip_id": "trip_id",
            "currency": "currency",
            "exchange_rate": "exchange_rate",
            "invoice_type": "invoice_type",
            "notes": "notes",
            "status": "status",
            "amount_paid": "amount_paid",
        }
        for model_field, db_field in field_map.items():
            val = getattr(request, model_field, None)
            if val is not None:
                update_data[db_field] = val

        if request.invoice_date is not None:
            update_data["issue_date"] = (
                request.invoice_date.isoformat()
                if hasattr(request.invoice_date, "isoformat")
                else request.invoice_date
            )
        if request.due_date is not None:
            update_data["due_date"] = (
                request.due_date.isoformat()
                if hasattr(request.due_date, "isoformat")
                else request.due_date
            )

        # Recalculate line items if provided
        if request.line_items is not None:
            calculated_items, subtotal_net, total_vat, total_gross = (
                self._calculate_line_items(request.line_items)
            )
            update_data["subtotal_net"] = subtotal_net
            update_data["total_vat"] = total_vat
            update_data["total_gross"] = total_gross
            update_data["total_amount"] = total_gross
            update_data["line_items_json"] = json.dumps(
                [li.model_dump() for li in calculated_items]
            )
        else:
            # Keep existing line items (deserialize for result)
            raw_json = row.get("line_items_json")
            if raw_json:
                try:
                    existing_items = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                    calculated_items = [InvoiceLineItem(**li) for li in existing_items]
                except (json.JSONDecodeError, TypeError, ValueError):
                    calculated_items = []
            else:
                calculated_items = []

        try:
            self._invoice_repo.update(invoice_id, update_data)
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to update invoice %s: %s", invoice_id, exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="update_failed")],
            )

        # Re-read for the return result
        updated_row = self._invoice_repo.get_by_id(invoice_id)
        if updated_row:
            result = self._row_to_invoice_result(updated_row)
        else:
            result = self._row_to_invoice_result(row)
            # Patch updated fields in-memory as fallback
            for k, v in update_data.items():
                if k == "issue_date":
                    result.invoice_date = (
                        request.invoice_date if request.invoice_date else result.invoice_date
                    )
                elif k == "due_date":
                    result.due_date = request.due_date if request.due_date else result.due_date
                elif k == "line_items_json":
                    pass
                elif k != "updated_at":
                    setattr(result, k, v) if hasattr(result, k) else None

        return InvoiceCreateResult(success=True, data=result)

    # ── 3. get ────────────────────────────────────────────────────────

    def get(self, invoice_id: int) -> InvoiceCreateResult:
        """Fetch a single invoice by ID."""
        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )
        result = self._row_to_invoice_result(row)
        return InvoiceCreateResult(success=True, data=result)

    # ── 4. list_all ───────────────────────────────────────────────────

    def list_all(self, limit: int = 500) -> InvoiceListResult:
        """Return all invoices as a typed list result."""
        rows = self._invoice_repo.get_all(limit=limit)
        items = [self._row_to_invoice_result(r) for r in rows]
        return InvoiceListResult(success=True, data=items)

    # ── Status transition validation ──────────────────────────────────

    def _validate_status_transition(
        self, current_status: str, new_status: str
    ) -> Optional[ErrorDetail]:
        """Check if *new_status* is a valid transition from *current_status*.

        Returns an ``ErrorDetail`` if the transition is invalid, or ``None``.
        """
        allowed = INVOICE_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            return ErrorDetail(
                message=(
                    f"Cannot transition invoice from '{current_status}' "
                    f"to '{new_status}'. Allowed transitions: "
                    f"{allowed or '(none — terminal status)'}"
                ),
                code="invalid_status_transition",
            )
        return None

    def _log_status_transition(
        self, invoice_id: int, from_status: str, to_status: str, user_id: int
    ) -> None:
        """Record a status transition in the status history table."""
        from datetime import datetime
        try:
            self._invoice_repo._execute(
                "INSERT INTO invoice_status_history "
                "(invoice_id, from_status, to_status, changed_by, changed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (invoice_id, from_status, to_status, user_id, datetime.utcnow().isoformat()),
                commit=True,
            )
        except Exception as exc:
            logger.warning("Failed to log status transition for invoice %s: %s", invoice_id, exc)

    # ── 5. finalize ───────────────────────────────────────────────────

    def finalize(
        self,
        request: InvoiceFinalizeRequest,
        user_id: int,
    ) -> InvoiceCreateResult:
        """Finalize (approve) an invoice."""
        # Permission check (skip for system/internal user_id=0, matching TripService behaviour)
        if user_id:
            perm = self._get_permission_service()
            err = self._check(perm.can_finalize_invoice(user_id))
            if err:
                return err

        invoice_id = request.invoice_id
        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        # Business validation using status machine
        current_status = row.get("status", "")
        trans_error = self._validate_status_transition(current_status, "finalized")
        if trans_error:
            return InvoiceCreateResult(
                success=False,
                errors=[trans_error],
            )

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            self._invoice_repo.update(invoice_id, {
                "status": "finalized",
                "updated_at": now,
            })
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to finalize invoice %s: %s", invoice_id, exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="finalize_failed")],
            )

        # Status transition log
        self._log_status_transition(invoice_id, current_status, "finalized", user_id)

        # Audit log
        AuditService(self.db).log(
            event_type="invoice.finalized",
            entity_type="invoice",
            entity_id=str(invoice_id),
            data={"status": "finalized", "invoice_number": row.get("invoice_number", "")},
            user_id=user_id,
        )

        # Optionally send email
        if request.send_email and request.email_recipient:
            try:
                self._event_bus.publish(INVOICE_EMAILED, {
                    "invoice_id": invoice_id,
                    "recipient": request.email_recipient,
                })
            except (ValueError, RuntimeError) as exc:
                logger.warning("Failed to send finalize email for invoice %s: %s", invoice_id, exc)

        # Return updated invoice
        updated_row = self._invoice_repo.get_by_id(invoice_id)
        result = self._row_to_invoice_result(updated_row or row)
        return InvoiceCreateResult(success=True, data=result)

    # ── 6. cancel ─────────────────────────────────────────────────────

    def cancel(self, invoice_id: int, user_id: int) -> InvoiceCreateResult:
        """Cancel an invoice."""
        # Permission check (skip for system/internal user_id=0, matching TripService behaviour)
        if user_id:
            perm = self._get_permission_service()
            err = self._check(perm.can_cancel_invoice(user_id))
            if err:
                return err

        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        current_status = row.get("status", "")
        trans_error = self._validate_status_transition(current_status, "cancelled")
        if trans_error:
            return InvoiceCreateResult(
                success=False,
                errors=[trans_error],
            )

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            self._invoice_repo.update(invoice_id, {
                "status": "cancelled",
                "updated_at": now,
            })
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to cancel invoice %s: %s", invoice_id, exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="cancel_failed")],
            )

        # Status transition log
        self._log_status_transition(invoice_id, current_status, "cancelled", user_id)

        # Audit log
        AuditService(self.db).log(
            event_type="invoice.cancelled",
            entity_type="invoice",
            entity_id=str(invoice_id),
            data={"status": "cancelled", "invoice_number": row.get("invoice_number", "")},
            user_id=user_id,
        )

        updated_row = self._invoice_repo.get_by_id(invoice_id)
        result = self._row_to_invoice_result(updated_row or row)
        return InvoiceCreateResult(success=True, data=result)

    # ── 6b. set_status ────────────────────────────────────────────────

    def set_status(
        self, invoice_id: int, new_status: str, user_id: int
    ) -> InvoiceCreateResult:
        """Transition an invoice to *new_status* with validation against the state machine."""
        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        current_status = row.get("status", "")
        trans_error = self._validate_status_transition(current_status, new_status)
        if trans_error:
            return InvoiceCreateResult(
                success=False,
                errors=[trans_error],
            )

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            self._invoice_repo.update(invoice_id, {
                "status": new_status,
                "updated_at": now,
            })
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to set status for invoice %s: %s", invoice_id, exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="status_update_failed")],
            )

        self._log_status_transition(invoice_id, current_status, new_status, user_id)

        AuditService(self.db).log(
            event_type=f"invoice.status_changed",
            entity_type="invoice",
            entity_id=str(invoice_id),
            data={"from_status": current_status, "to_status": new_status},
            user_id=user_id,
        )

        updated_row = self._invoice_repo.get_by_id(invoice_id)
        result = self._row_to_invoice_result(updated_row or row)
        return InvoiceCreateResult(success=True, data=result)

    # ── 7. generate_pdf ───────────────────────────────────────────────

    def generate_pdf(self, invoice_id: int) -> InvoiceCreateResult:
        """Generate a PDF for the given invoice and store the path."""
        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        # Build trip-like dict for the legacy generator
        trip_data: dict[str, Any] = {
            "id": row.get("trip_id") or invoice_id,
            "client_name": "",
            "total_price_eur": float(row.get("total_gross", row.get("total_amount", 0))),
            "currency": row.get("currency", "EUR"),
        }

        client_id = row.get("client_id")
        if client_id:
            client = self._client_repo.get_by_id(client_id)
            if client:
                trip_data["client_name"] = client.get("name") or client.get("company_name") or ""
                trip_data["client_vat"] = client.get("vat_number") or ""
                trip_data["client_address"] = client.get("address") or ""
                trip_data["client_phone"] = client.get("phone") or ""
                trip_data["client_email"] = client.get("email") or ""

        try:
            pdf_path = self.generator.generate(trip_data, mode="client")
        except (ValueError, RuntimeError, OSError) as exc:
            logger.error("Failed to generate PDF for invoice %s: %s", invoice_id, exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="pdf_generation_failed")],
            )

        # Store pdf_path
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            self._invoice_repo.update(invoice_id, {
                "pdf_path": pdf_path,
                "updated_at": now,
            })
        except (ValueError, RuntimeError, OSError) as exc:
            logger.warning("Failed to store pdf_path for invoice %s: %s", invoice_id, exc)

        # Build result
        result = self._row_to_invoice_result(row)
        result.pdf_path = pdf_path
        return InvoiceCreateResult(success=True, data=result)

    # ── 8. recalculate ────────────────────────────────────────────────

    def recalculate(self, invoice_id: int) -> InvoiceCreateResult:
        """Recalculate VAT, subtotals, and totals from stored line items."""
        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        # Deserialize line items
        raw_json = row.get("line_items_json")
        if not raw_json:
            return InvoiceCreateResult(
                success=False,
                errors=[
                    ErrorDetail(
                        message="Invoice has no line items to recalculate",
                        code="no_line_items",
                    )
                ],
            )

        try:
            raw_items = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            items = [InvoiceLineItem(**li) for li in raw_items]
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=f"Invalid line items: {exc}", code="invalid_line_items")],
            )

        calculated_items, subtotal_net, total_vat, total_gross = (
            self._calculate_line_items(items)
        )

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            self._invoice_repo.update(invoice_id, {
                "subtotal_net": subtotal_net,
                "total_vat": total_vat,
                "total_gross": total_gross,
                "total_amount": total_gross,
                "line_items_json": json.dumps(
                    [li.model_dump() for li in calculated_items]
                ),
                "updated_at": now,
            })
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to recalculate invoice %s: %s", invoice_id, exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="recalculate_failed")],
            )

        updated_row = self._invoice_repo.get_by_id(invoice_id)
        result = self._row_to_invoice_result(updated_row or row)
        return InvoiceCreateResult(success=True, data=result)

    # ── 9. validate_complete ──────────────────────────────────────────

    def validate_complete(self, invoice_id: int) -> ServiceResult[bool]:
        """Validate that an invoice has all required fields filled."""
        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return ServiceResult[bool](
                success=False,
                data=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        errors: list[ErrorDetail] = []

        # Required fields
        if not row.get("client_id"):
            errors.append(ErrorDetail(field="client_id", message="Client is required", code="missing_field"))
        if not row.get("invoice_number"):
            errors.append(ErrorDetail(field="invoice_number", message="Invoice number is required", code="missing_field"))
        if not row.get("issue_date"):
            errors.append(ErrorDetail(field="issue_date", message="Issue date is required", code="missing_field"))
        if not row.get("due_date"):
            errors.append(ErrorDetail(field="due_date", message="Due date is required", code="missing_field"))
        if not row.get("line_items_json"):
            errors.append(ErrorDetail(field="line_items", message="At least one line item is required", code="missing_field"))

        if errors:
            return ServiceResult[bool](
                success=False,
                data=False,
                errors=errors,
            )

        return ServiceResult[bool](success=True, data=True)

    # ── 10. delete ────────────────────────────────────────────────────

    def delete(self, invoice_id: int, user_id: int) -> InvoiceCreateResult:
        """Delete an invoice."""
        # Permission check — use can_cancel_invoice as proxy for delete (skip for user_id=0)
        if user_id:
            perm = self._get_permission_service()
            err = self._check(perm.can_cancel_invoice(user_id))
            if err:
                return err

        row = self._invoice_repo.get_by_id(invoice_id)
        if not row:
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message="Invoice not found", code="not_found")],
            )

        # Immutable archival: finalized invoices cannot be deleted
        current_status = row.get("status", "")
        if current_status in ("finalized", "accepted", "paid", "cancelled"):
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(
                    message=f"Cannot delete invoice with status '{current_status}'",
                    code="immutable",
                )],
            )

        try:
            self._invoice_repo.delete(invoice_id)
        except (ValueError, RuntimeError, TypeError) as exc:
            logger.error("Failed to delete invoice %s: %s", invoice_id, exc, exc_info=True)
            return InvoiceCreateResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="delete_failed")],
            )

        # Audit log
        AuditService(self.db).log(
            event_type="invoice.deleted",
            entity_type="invoice",
            entity_id=str(invoice_id),
            data={"invoice_number": row.get("invoice_number", "")},
            user_id=user_id,
        )

        # Return the deleted invoice data as confirmation
        result = self._row_to_invoice_result(row)
        return InvoiceCreateResult(success=True, data=result)
