"""Receipt PDF generator using ReportLab.

Produces professional EU-compliant receipts suitable for logistics
companies, transport services, customer payments, employee reimbursements,
fuel expenses, toll expenses, and other business-related financial
transactions.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date, datetime
from typing import Optional

from reportlab.lib import colors

logger = logging.getLogger(__name__)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models.common import ErrorDetail, ServiceResult
from models.receipt_models import ReceiptCreate, ReceiptCreateResult, ReceiptLineItem, ReceiptResult
from services.i18n import _get_translations
from services.invoicing.config_manager import load_company_config
from utils.helpers import remove_accents
from utils.number_to_words import number_to_words
from utils.resource_path import data_path

_BASE_DIR = data_path("data/documents/receipts")


class ReceiptGenerator:
    """Generate professional receipt PDFs.

    Usage::

        gen = ReceiptGenerator()
        path = gen.generate(receipt_data)

    Typed methods (preferred)::

        gen = ReceiptGenerator(db)
        result = gen.create(request, user_id)
        result = gen.generate_pdf(receipt_id)
        result = gen.get(receipt_id)
        results = gen.list_all()
    """

    def __init__(self, db=None):
        os.makedirs(_BASE_DIR, exist_ok=True)
        self._db = db
        self.styles = getSampleStyleSheet()

    # ── Translation helper ─────────────────────────────────────────────

    @staticmethod
    def _tr(key: str, lang: str = "en") -> str:
        """Translate *key* to *lang* (client mode always English)."""
        result = _get_translations(lang).get(key, key)
        return str(result) if result is not None else key

    # ── Repository / Permission helpers ─────────────────────────────

    @property
    def _repo(self):
        """Lazy-init ReceiptRepository (requires db)."""
        if self._db is None:
            raise RuntimeError("ReceiptGenerator requires a db connection for repository access")
        from repositories.receipt_repository import ReceiptRepository
        return ReceiptRepository(self._db)

    @property
    def _perm(self):
        """Lazy-init PermissionService (requires db)."""
        if self._db is None:
            raise RuntimeError("ReceiptGenerator requires a db connection for permission checks")
        from services.permission_service import PermissionService
        return PermissionService(self._db)

    @property
    def _client_repo(self):
        """Lazy-init ClientRepository (requires db)."""
        if self._db is None:
            raise RuntimeError("ReceiptGenerator requires a db connection for client repository access")
        from repositories.client_repository import ClientRepository
        return ClientRepository(self._db)

    # ── Typed public API ─────────────────────────────────────────────

    def create(self, request: ReceiptCreate, user_id: int) -> ReceiptCreateResult:
        """Create a receipt record from a typed request.

        1. Permission check via ``PermissionService.can_create_receipt``
        2. Compute ``total_amount`` from ``items`` if not provided
        3. Generate receipt number
        4. Look up client info and save to DB
        5. Return ``ServiceResult[ReceiptResult]``
        """
        # ── 1. Permission check ──────────────────────────────────────
        try:
            perm = self._perm
            check = perm.can_create_receipt(user_id)
            if not check.allowed:
                logger.warning("Permission denied for user %s to create receipt: %s", user_id, check.reason)
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(field="permission", message=check.reason, code="FORBIDDEN")],
                )
        except RuntimeError:
            pass  # no db — skip permission check (backward compat)

        # ── 2. Compute total_amount from items ───────────────────────
        total_amount = request.total_amount
        if total_amount is None and request.items:
            total_amount = round(sum(item.amount * item.quantity for item in request.items), 2)
        elif total_amount is None:
            total_amount = 0.0

        # ── 3. Generate receipt number + DB access ────────────────────
        receipt_number = ""
        receipt_id = None
        client_name = ""
        client_address = ""
        client_vat = ""
        issue_date_str = request.receipt_date.isoformat()
        try:
            repo = self._repo
            receipt_number = repo.get_next_number()

            # ── 4. Look up client info ───────────────────────────────
            try:
                client = self._client_repo.get_by_id(request.client_id)
                if client:
                    client_name = client.get("name", "")
                    client_address = client.get("address", "")
                    client_vat = client.get("vat_number", "")
            except RuntimeError:
                pass

            # ── 5. Prepare items JSON ────────────────────────────────
            items_json = json.dumps([item.model_dump() for item in request.items])

            # ── 6. Save to DB ────────────────────────────────────────
            receipt_id = repo.create(
                receipt_number=receipt_number,
                issue_date=issue_date_str,
                payment_date=issue_date_str,
                currency=request.currency,
                amount=total_amount,
                total=total_amount,
                notes=request.notes,
                attachments_json=items_json,
                received_from_name=client_name,
                received_from_address=client_address,
                received_from_vat=client_vat,
                related_trip_id=request.trip_id,
                invoice_reference=str(request.invoice_id) if request.invoice_id else "",
                vehicle_id=request.vehicle_id,
                client_id=request.client_id,
                status="Draft",
            )

            if receipt_id is None:
                logger.error("Failed to create receipt for client_id=%s", request.client_id)
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message="Failed to create receipt record", code="DB_ERROR")],
                )
        except RuntimeError:
            logger.error("Cannot create receipt without database connection")
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message="Database connection required to create receipt", code="DB_ERROR")],
            )

        # ── 7. Build result ──────────────────────────────────────────
        pdf_path = self._compute_pdf_path(receipt_number)
        if pdf_path and not os.path.isfile(pdf_path):
            pdf_path = None

        result = ReceiptResult(
            id=receipt_id,
            receipt_number=receipt_number,
            client_id=request.client_id,
            client_name=client_name,
            trip_id=request.trip_id,
            invoice_id=request.invoice_id,
            vehicle_id=request.vehicle_id,
            vehicle_plate="",
            receipt_date=request.receipt_date,
            currency=request.currency,
            items=request.items,
            total_amount=total_amount,
            notes=request.notes,
            pdf_path=pdf_path,
            created_at=datetime.now(),
        )

        logger.info("Receipt created: id=%s number=%s client_id=%s", receipt_id, receipt_number, request.client_id)
        return ServiceResult(success=True, data=result)

    def generate_pdf(self, receipt_id: int) -> ReceiptCreateResult:
        """Generate a PDF for an existing receipt and update its ``pdf_path``."""
        try:
            repo = self._repo
        except RuntimeError as exc:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="DB_ERROR")],
            )

        row = repo.get_by_id(receipt_id)
        if not row:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=f"Receipt {receipt_id} not found", code="NOT_FOUND")],
            )

        try:
            pdf_path = self.generate(row)  # reuse existing PDF generator
            repo.update(receipt_id, pdf_path=pdf_path)
            row["pdf_path"] = pdf_path
            result = self._row_to_result(row)
            logger.info("PDF generated for receipt id=%s path=%s", receipt_id, pdf_path)
            return ServiceResult(success=True, data=result)
        except Exception as exc:
            logger.error("Failed to generate PDF for receipt %s: %s", receipt_id, exc)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="PDF_ERROR")],
            )

    def finalize(self, receipt_id: int, user_id: int) -> ServiceResult:
        """Finalize a draft receipt — set its status to **Finalized**.

        1. Permission check via ``PermissionService. can_update_receipt``
        2. Verify the receipt exists and is in ``Draft`` status
        3. Update status to ``Finalized``
        4. Return the updated receipt data
        """
        # ── 1. Permission check ──────────────────────────────────────
        try:
            perm = self._perm
            check = perm.can_update_receipt(user_id)
            if not check.allowed:
                logger.warning("Permission denied for user %s to finalize receipt: %s", user_id, check.reason)
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(field="permission", message=check.reason, code="FORBIDDEN")],
                )
        except RuntimeError:
            pass  # no db — skip permission check (backward compat)

        # ── 2. Verify existence and status ───────────────────────────
        try:
            repo = self._repo
        except RuntimeError as exc:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="DB_ERROR")],
            )

        row = repo.get_by_id(receipt_id)
        if not row:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=f"Receipt {receipt_id} not found", code="NOT_FOUND")],
            )

        current_status = (row.get("status") or "").lower()
        if current_status != "draft":
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    message=f"Receipt must be in Draft status, current: {row.get('status', '')}",
                    code="INVALID_STATUS",
                )],
            )

        # ── 3. Update to Finalized ──────────────────────────────────
        repo.update(receipt_id, status="Finalized")

        # ── 4. Build result ─────────────────────────────────────────
        result = self._row_to_result(row)
        # Override status with the new value
        return ServiceResult(
            success=True,
            data={
                "receipt_id": receipt_id,
                "receipt_number": result.receipt_number,
                "status": "Finalized",
            },
        )

    def get(self, receipt_id: int) -> ReceiptCreateResult:
        """Fetch a single receipt by ID."""
        try:
            repo = self._repo
        except RuntimeError as exc:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="DB_ERROR")],
            )

        row = repo.get_by_id(receipt_id)
        if not row:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=f"Receipt {receipt_id} not found", code="NOT_FOUND")],
            )
        result = self._row_to_result(row)
        return ServiceResult(success=True, data=result)

    def list_all(self) -> ServiceResult[list[ReceiptResult]]:
        """Return all receipts as typed results."""
        try:
            repo = self._repo
        except RuntimeError as exc:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="DB_ERROR")],
            )

        rows = repo.get_all()
        results = [self._row_to_result(row) for row in rows]
        return ServiceResult(success=True, data=results)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_pdf_path(receipt_number: str) -> Optional[str]:
        """Return the expected PDF file path for a receipt number."""
        if not receipt_number:
            return None
        return os.path.join(_BASE_DIR, f"{receipt_number}.pdf")

    @classmethod
    def _row_to_result(cls, row: dict) -> ReceiptResult:
        """Convert a repository dict row to a typed ``ReceiptResult``."""
        # Parse items from attachments_json
        items: list[ReceiptLineItem] = []
        attachments_json = row.get("attachments_json", "[]")
        if attachments_json:
            try:
                items_data = json.loads(attachments_json)
                for item in items_data:
                    if isinstance(item, dict):
                        items.append(ReceiptLineItem(**item))
            except (json.JSONDecodeError, TypeError):
                pass

        # Parse dates
        receipt_date_str = row.get("issue_date", "")
        try:
            receipt_date = date.fromisoformat(receipt_date_str) if receipt_date_str else date.today()
        except (ValueError, TypeError):
            receipt_date = date.today()

        created_at_str = row.get("created_at", "")
        created_at: Optional[datetime] = None
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except (ValueError, TypeError):
                pass

        # Try to parse invoice_id from invoice_reference string
        invoice_id: Optional[int] = None
        inv_ref = row.get("invoice_reference", "")
        if inv_ref and inv_ref.isdigit():
            invoice_id = int(inv_ref)

        receipt_number = row.get("receipt_number", "")
        pdf_path = cls._compute_pdf_path(receipt_number)
        if pdf_path and not os.path.isfile(pdf_path):
            pdf_path = None

        return ReceiptResult(
            id=row["id"],
            receipt_number=receipt_number,
            client_id=row.get("client_id", 0) or 0,
            client_name=row.get("received_from_name", ""),
            trip_id=row.get("related_trip_id"),
            invoice_id=invoice_id,
            vehicle_id=row.get("vehicle_id"),
            vehicle_plate="",
            receipt_date=receipt_date,
            currency=row.get("currency", "EUR"),
            items=items,
            total_amount=float(row.get("total", 0) or 0),
            notes=row.get("notes", ""),
            pdf_path=pdf_path,
            created_at=created_at,
        )

    # ── Main generation entry point ────────────────────────────────────

    def generate(self, receipt_data: dict) -> str:
        """Generate a receipt PDF and return the file path.

        .. deprecated::
            Use :meth:`create` + :meth:`generate_pdf` instead.

        *receipt_data* keys:
            receipt_number, receipt_type, issue_date, payment_date, currency,
            received_from_name, received_from_address,
            received_from_vat, received_from_reg, received_from_contact,
            received_by_name, received_by_address,
            received_by_vat, received_by_reg, received_by_contact,
            payment_method, reference_number, transaction_id,
            bank_reference, invoice_reference,
            related_trip, purpose,
            amount, vat_rate, vat_amount, total, amount_words,
            notes, logo_path, signature_path, stamp_path,
            pickup_location, delivery_location, route, dispatcher,
            language, company_*
        """
        receipt_number = receipt_data.get("receipt_number", "RCT-000000")
        language = receipt_data.get("language", "en")
        lang = language if language in ("en", "ro") else "en"

        # Resolve company config (data overrides defaults)
        conf = receipt_data.get("company_config", load_company_config())
        company_color_hex = receipt_data.get("company_color", "#6366f1")
        try:
            accent = colors.HexColor(company_color_hex)
        except Exception:
            accent = colors.HexColor("#6366f1")

        filename = f"{receipt_number}.pdf"
        full_path = os.path.join(_BASE_DIR, filename)

        logger.info("Generating receipt PDF: receipt_number=%s, type=%s, amount=%s, currency=%s",
                    receipt_number,
                    receipt_data.get("receipt_type", ""),
                    receipt_data.get("total", receipt_data.get("amount", 0)),
                    receipt_data.get("currency", "EUR"))

        story = []

        # ── Styles ─────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "RctTitle",
            parent=self.styles["Title"],
            fontSize=20,
            textColor=accent,
            alignment=1,
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "RctSubtitle",
            parent=self.styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#888888"),
            alignment=1,
            spaceAfter=12,
        )
        section_style = ParagraphStyle(
            "RctSection",
            parent=self.styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#444444"),
            spaceBefore=8,
            spaceAfter=4,
        )
        field_style = ParagraphStyle(
            "RctField",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=13,
        )
        value_style = ParagraphStyle(
            "RctValue",
            parent=self.styles["Normal"],
            fontSize=10,
            leading=14,
        )
        amount_style = ParagraphStyle(
            "RctAmount",
            parent=self.styles["Normal"],
            fontSize=12,
            leading=16,
            textColor=accent,
        )

        # ── Determine receipt type label ──────────────────────────
        rtype = receipt_data.get("receipt_type", "customer_payment")
        type_labels = {
            "customer_payment": "receipt.type_customer_payment",
            "cash_receipt": "receipt.type_cash_receipt",
            "driver_reimbursement": "receipt.type_driver_reimbursement",
            "employee_expense": "receipt.type_employee_expense",
            "fuel_reimbursement": "receipt.type_fuel_reimbursement",
            "toll_reimbursement": "receipt.type_toll_reimbursement",
            "miscellaneous": "receipt.type_miscellaneous",
            "refund": "receipt.type_refund",
            "deposit": "receipt.type_deposit",
            "advance_payment": "receipt.type_advance_payment",
            "other": "receipt.type_other",
        }
        type_display = self._tr(type_labels.get(rtype, "receipt.type_other"), lang)

        # ══════════════════════════════════════════════════════════════
        # HEADER — Logo + Company Info
        # ══════════════════════════════════════════════════════════════

        logo_path = receipt_data.get("logo_path", "") or conf.get("logo_path", "")
        header_parts = []

        if logo_path and os.path.isfile(logo_path):
            try:
                logo_img = Image(logo_path, width=2.5 * cm, height=2.5 * cm)
                logo_img.hAlign = "LEFT"
                header_parts.append(logo_img)
            except Exception:
                pass

        company_block = (
            f"<b>{remove_accents(conf.get('company_name', ''))}</b><br/>"
            f"{remove_accents(conf.get('address', ''))}<br/>"
            f"VAT: {conf.get('cui', '')}&nbsp;&nbsp;Reg: {conf.get('reg_number', '')}<br/>"
            f"Tel: {conf.get('phone', '')}&nbsp;&nbsp;Email: {conf.get('email', '')}"
        )
        company_para = Paragraph(company_block, field_style)

        if header_parts:
            hdr_table = Table(
                [[header_parts[0], company_para]],
                colWidths=[4 * cm, 14 * cm],
            )
        else:
            hdr_table = Table(
                [[company_para]],
                colWidths=[18 * cm],
            )
        hdr_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(hdr_table)
        story.append(Spacer(1, 0.2 * cm))

        # ── Accent line ───────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=2, color=accent, spaceAfter=8))

        # ══════════════════════════════════════════════════════════════
        # TITLE
        # ══════════════════════════════════════════════════════════════

        title_text = self._tr("receipt.title", lang)
        story.append(Paragraph(f"<b>{title_text}</b>", title_style))
        story.append(
            Paragraph(
                f"{type_display} — {receipt_number}",
                subtitle_style,
            )
        )

        # ══════════════════════════════════════════════════════════════
        # META ROW
        # ══════════════════════════════════════════════════════════════

        issue_date = receipt_data.get("issue_date", "")
        payment_date = receipt_data.get("payment_date", "")
        currency = receipt_data.get("currency", "EUR")

        meta_left = f"<b>{self._tr('receipt.number_label', lang)}:</b> {receipt_number}"
        meta_right = (
            f"<b>{self._tr('receipt.issue_date_label', lang)}:</b> {issue_date}"
            f"&nbsp;&nbsp;&nbsp;"
            f"<b>{self._tr('receipt.payment_date_label', lang)}:</b> {payment_date}"
            f"&nbsp;&nbsp;&nbsp;"
            f"<b>{self._tr('receipt.currency_label', lang)}:</b> {currency}"
        )
        meta_table = Table(
            [[Paragraph(meta_left, field_style), Paragraph(meta_right, field_style)]],
            colWidths=[5 * cm, 13 * cm],
        )
        meta_table.setStyle(
            TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")])
        )
        story.append(meta_table)
        story.append(Spacer(1, 0.4 * cm))

        # ── Divider ───────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=10))

        # ══════════════════════════════════════════════════════════════
        # PARTIES — Received From / Received By
        # ══════════════════════════════════════════════════════════════

        from_name = receipt_data.get("received_from_name", "")
        from_address = receipt_data.get("received_from_address", "")
        from_vat = receipt_data.get("received_from_vat", "")
        from_reg = receipt_data.get("received_from_reg", "")
        from_contact = receipt_data.get("received_from_contact", "")

        by_name = receipt_data.get("received_by_name", "") or conf.get("company_name", "")
        by_address = receipt_data.get("received_by_address", "") or conf.get("address", "")
        by_vat = receipt_data.get("received_by_vat", "") or conf.get("cui", "")
        by_reg = receipt_data.get("received_by_reg", "") or conf.get("reg_number", "")
        by_contact = receipt_data.get("received_by_contact", "") or conf.get("phone", "")

        from_block = (
            f"<b>{self._tr('receipt.received_from', lang)}</b><br/><br/>"
            f"{remove_accents(from_name)}<br/>"
            f"{remove_accents(from_address)}"
        )
        if from_vat:
            from_block += f"<br/>VAT: {from_vat}"
        if from_reg:
            from_block += f"<br/>Reg: {from_reg}"
        if from_contact:
            from_block += f"<br/>{remove_accents(from_contact)}"

        by_block = (
            f"<b>{self._tr('receipt.received_by', lang)}</b><br/><br/>"
            f"{remove_accents(by_name)}<br/>"
            f"{remove_accents(by_address)}"
        )
        if by_vat:
            by_block += f"<br/>VAT: {by_vat}"
        if by_reg:
            by_block += f"<br/>Reg: {by_reg}"
        if by_contact:
            by_block += f"<br/>{remove_accents(by_contact)}"

        parties_table = Table(
            [
                [
                    Paragraph(from_block, value_style),
                    Paragraph(by_block, value_style),
                ]
            ],
            colWidths=[9 * cm, 9 * cm],
        )
        parties_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ]
            )
        )
        story.append(parties_table)
        story.append(Spacer(1, 0.4 * cm))

        # ══════════════════════════════════════════════════════════════
        # PURPOSE
        # ══════════════════════════════════════════════════════════════

        purpose = receipt_data.get("purpose", "")
        if purpose:
            story.append(
                Paragraph(
                    f"<b>{self._tr('receipt.purpose_label', lang)}</b>",
                    section_style,
                )
            )
            story.append(
                Paragraph(remove_accents(purpose), value_style)
            )
            story.append(Spacer(1, 0.3 * cm))

        # ══════════════════════════════════════════════════════════════
        # PAYMENT DETAILS
        # ══════════════════════════════════════════════════════════════

        payment_method = receipt_data.get("payment_method", "")
        reference_number = receipt_data.get("reference_number", "")
        transaction_id = receipt_data.get("transaction_id", "")
        bank_reference = receipt_data.get("bank_reference", "")
        invoice_reference = receipt_data.get("invoice_reference", "")

        if any([payment_method, reference_number, transaction_id, bank_reference, invoice_reference]):
            story.append(
                Paragraph(
                    f"<b>{self._tr('receipt.payment_details_label', lang)}</b>",
                    section_style,
                )
            )
            pmt_rows = []
            if payment_method:
                pmt_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.payment_method_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(payment_method, field_style),
                    ]
                )
            if reference_number:
                pmt_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.reference_number_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(reference_number, field_style),
                    ]
                )
            if transaction_id:
                pmt_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.transaction_id_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(transaction_id, field_style),
                    ]
                )
            if bank_reference:
                pmt_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.bank_reference_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(bank_reference, field_style),
                    ]
                )
            if invoice_reference:
                pmt_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.invoice_reference_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(invoice_reference, field_style),
                    ]
                )
            if pmt_rows:
                pmt_table = Table(pmt_rows, colWidths=[5 * cm, 13 * cm])
                pmt_table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("TOPPADDING", (0, 0), (-1, -1), 1),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                        ]
                    )
                )
                story.append(pmt_table)
                story.append(Spacer(1, 0.3 * cm))

        # ══════════════════════════════════════════════════════════════
        # FINANCIAL TABLE
        # ══════════════════════════════════════════════════════════════

        amount = float(receipt_data.get("amount", 0))
        vat_rate = float(receipt_data.get("vat_rate", 0))
        vat_amount = float(receipt_data.get("vat_amount", amount * vat_rate / 100))
        total = float(receipt_data.get("total", amount + vat_amount))

        fin_rows = [
            [
                Paragraph(f"<b>{self._tr('receipt.amount_label', lang)}</b>", field_style),
                Paragraph(f"{amount:,.2f} {currency}", field_style),
            ],
        ]
        if vat_rate > 0:
            fin_rows.append(
                [
                    Paragraph(
                        f"<b>{self._tr('receipt.vat_rate_label', lang)}</b>",
                        field_style,
                    ),
                    Paragraph(f"{vat_rate:.1f}%", field_style),
                ]
            )
            fin_rows.append(
                [
                    Paragraph(
                        f"<b>{self._tr('receipt.vat_amount_label', lang)}</b>",
                        field_style,
                    ),
                    Paragraph(f"{vat_amount:,.2f} {currency}", field_style),
                ]
            )
        fin_rows.append(
            [
                Paragraph(
                    f"<b>{self._tr('receipt.total_label', lang)}</b>",
                    amount_style,
                ),
                Paragraph(
                    f"<b>{total:,.2f} {currency}</b>",
                    amount_style,
                ),
            ]
        )

        fin_table = Table(fin_rows, colWidths=[12 * cm, 6 * cm])
        fin_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, -1), (-1, -1), 1.5, accent),
                ]
            )
        )
        story.append(fin_table)
        story.append(Spacer(1, 0.4 * cm))

        # ══════════════════════════════════════════════════════════════
        # AMOUNT IN WORDS
        # ══════════════════════════════════════════════════════════════

        amount_words = receipt_data.get("amount_words", "")
        if not amount_words and total > 0:
            try:
                amount_words = number_to_words(total, currency, lang)
            except ValueError:
                amount_words = "[amount too large to convert to words]"
            except (KeyError, Exception):
                amount_words = ""
        if amount_words:
            words_style = ParagraphStyle(
                "RctWords",
                parent=self.styles["Normal"],
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#555555"),
                fontName="Helvetica-Oblique",
                spaceBefore=4,
                spaceAfter=8,
            )
            story.append(
                Paragraph(
                    f"<b>{self._tr('receipt.amount_words_label', lang)}:</b>",
                    section_style,
                )
            )
            story.append(Paragraph(amount_words, words_style))
            story.append(Spacer(1, 0.2 * cm))

        # ══════════════════════════════════════════════════════════════
        # LOGISTICS INTEGRATION (optional)
        # ══════════════════════════════════════════════════════════════

        trip_info = receipt_data.get("related_trip", "")
        pickup = receipt_data.get("pickup_location", "")
        delivery = receipt_data.get("delivery_location", "")
        route_text = receipt_data.get("route", "")
        dispatcher = receipt_data.get("dispatcher", "")

        if any([trip_info, pickup, delivery, route_text, dispatcher]):
            story.append(
                Paragraph(
                    f"<b>{self._tr('receipt.logistics_label', lang)}</b>",
                    section_style,
                )
            )
            log_rows = []
            if pickup:
                log_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.pickup_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(remove_accents(pickup), field_style),
                    ]
                )
            if delivery:
                log_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.delivery_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(remove_accents(delivery), field_style),
                    ]
                )
            if route_text:
                log_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.route_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(remove_accents(route_text), field_style),
                    ]
                )
            if dispatcher:
                log_rows.append(
                    [
                        Paragraph(
                            f"<b>{self._tr('receipt.dispatcher_label', lang)}:</b>",
                            field_style,
                        ),
                        Paragraph(remove_accents(dispatcher), field_style),
                    ]
                )
            if log_rows:
                log_table = Table(log_rows, colWidths=[5 * cm, 13 * cm])
                log_table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("TOPPADDING", (0, 0), (-1, -1), 1),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                        ]
                    )
                )
                story.append(log_table)
                story.append(Spacer(1, 0.3 * cm))

        # ══════════════════════════════════════════════════════════════
        # NOTES
        # ══════════════════════════════════════════════════════════════

        notes = receipt_data.get("notes", "")
        if notes:
            story.append(
                Paragraph(
                    f"<b>{self._tr('receipt.notes_label', lang)}</b>",
                    section_style,
                )
            )
            story.append(Paragraph(remove_accents(notes), field_style))
            story.append(Spacer(1, 0.5 * cm))

        # ══════════════════════════════════════════════════════════════
        # SIGNATURES & STAMP
        # ══════════════════════════════════════════════════════════════

        sig_path = receipt_data.get("signature_path", "") or conf.get("signature_path", "")
        stamp_path = receipt_data.get("stamp_path", "") or conf.get("stamp_path", "")

        sig_table_data = []
        # Left block: Company signature
        left_block = Paragraph(
            f"<b>{self._tr('receipt.company_signature_label', lang)}</b><br/>"
            f"_________________________<br/>"
            f"{remove_accents(conf.get('company_name', ''))}",
            field_style,
        )
        if sig_path and os.path.isfile(sig_path):
            try:
                sig_img = Image(sig_path, width=4 * cm, height=1.5 * cm)
                left_block = sig_img
            except Exception:
                pass
        sig_table_data.append(left_block)

        # Right block: Recipient + Stamp
        right_block = Paragraph(
            f"<b>{self._tr('receipt.recipient_signature_label', lang)}</b><br/>"
            f"_________________________<br/>"
            f"{remove_accents(from_name)}",
            field_style,
        )
        if stamp_path and os.path.isfile(stamp_path):
            try:
                stamp_img = Image(stamp_path, width=3 * cm, height=3 * cm)
                right_block = stamp_img
            except Exception:
                pass

        sig_table_data.append(right_block)
        sig_table = Table([sig_table_data], colWidths=[9 * cm, 9 * cm])
        sig_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ]
            )
        )
        story.append(sig_table)
        story.append(Spacer(1, 0.5 * cm))

        # ══════════════════════════════════════════════════════════════
        # COMPANY STAMP PLACEHOLDER (if no stamp image)
        # ══════════════════════════════════════════════════════════════

        if not stamp_path or not os.path.isfile(stamp_path):
            # Use a Table with BOX styling (ReportLab ignores border* on ParagraphStyle)
            stamp_cell = Paragraph(
                f"[ {self._tr('receipt.company_stamp_label', lang)} ]",
                ParagraphStyle(
                    "StampPlaceholder",
                    parent=self.styles["Normal"],
                    fontSize=8,
                    textColor=colors.HexColor("#aaaaaa"),
                    alignment=1,
                ),
            )
            stamp_table = Table([[stamp_cell]], colWidths=[6 * cm])
            stamp_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(stamp_table)
            story.append(Spacer(1, 0.5 * cm))

        # ══════════════════════════════════════════════════════════════
        # FOOTER
        # ══════════════════════════════════════════════════════════════

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=4))
        footer_text = (
            f"{self._tr('receipt.generated_by', lang)} — "
            f"{remove_accents(conf.get('company_name', ''))} | "
            f"Tel: {conf.get('phone', '')} | "
            f"Email: {conf.get('email', '')}"
        )
        story.append(
            Paragraph(
                footer_text,
                ParagraphStyle(
                    "RctFooter",
                    parent=self.styles["Italic"],
                    fontSize=8,
                    textColor=colors.HexColor("#999999"),
                    alignment=1,
                ),
            )
        )

        # ── Atomic write ─────────────────────────────────────────────
        tmp_fd, tmp_path = tempfile.mkstemp(dir=_BASE_DIR, suffix=".pdf")
        try:
            doc = SimpleDocTemplate(
                tmp_path,
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm,
            )
            doc.build(story)
            os.close(tmp_fd)
            tmp_fd = -1  # mark closed to avoid double-close in except block
            os.replace(tmp_path, full_path)
        except Exception:
            if tmp_fd >= 0:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            logger.error("Failed to generate receipt PDF: receipt_number=%s, path=%s",
                         receipt_number, full_path, exc_info=True)
            raise

        logger.info("Receipt PDF generated successfully: path=%s, receipt_number=%s", full_path, receipt_number)
        return full_path
