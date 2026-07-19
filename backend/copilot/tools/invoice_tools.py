"""Co-Pilot tools for the Invoice domain — draft, finalize, and PDF generation.

Level-1 (INFORMATIONAL) and Level-2 (BUSINESS) tools wrapping InvoiceService.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
#  Parameters
# ═════════════════════════════════════════════════════════════════════════════


class InvoiceDraftParams(BaseModel):
    """Input parameters for invoice.draft."""

    client_id: int = Field(..., gt=0, description="Client ID for the invoice")
    trip_id: int = Field(..., gt=0, description="Trip ID to invoice")
    amount: float = Field(..., gt=0, description="Invoice amount in EUR")
    due_date: Optional[str] = Field(
        None, description="Due date (YYYY-MM-DD); defaults to 30 days from now"
    )


class InvoiceGeneratePdfParams(BaseModel):
    """Input parameters for invoice.generate_pdf."""

    invoice_id: int = Field(..., gt=0, description="Invoice ID to generate PDF for")


class InvoiceFinalizeParams(BaseModel):
    """Input parameters for invoice.finalize."""

    invoice_id: int = Field(..., gt=0, description="Invoice ID to finalize")
    confirm: bool = Field(
        True, description="Confirmation flag; executor must resolve to True before execution"
    )


# ═════════════════════════════════════════════════════════════════════════════
#  invoice.draft  (Level 1 — INFORMATIONAL)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class InvoiceDraftTool(BaseTool):
    """Create a draft invoice.

    Wraps ``InvoiceService.create()`` with minimal required fields.
    Automatically computes invoice_date (today), due_date (30 days), and
    a single line item from the provided amount.
    """

    name = "invoice.draft"
    tool_version = "1.0.0"
    description = "Create a new draft invoice for a trip"
    required_permission = "invoices:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    deprecated = False
    parameters_schema = InvoiceDraftParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> InvoiceDraftParams:
        assert isinstance(params, InvoiceDraftParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.client_id <= 0:
            errors.append("client_id must be a positive integer")
        if p.trip_id <= 0:
            errors.append("trip_id must be a positive integer")
        if p.amount <= 0:
            errors.append("amount must be greater than zero")
        if p.due_date:
            try:
                date.fromisoformat(p.due_date)
            except (ValueError, TypeError):
                errors.append("due_date must be in YYYY-MM-DD format")
        return errors

    # ── Execution ──────────────────────────────────────────────────────

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            from models.invoice_models import InvoiceCreate, InvoiceLineItem

            # Build dates
            today = date.today()
            due = date.fromisoformat(p.due_date) if p.due_date else today + timedelta(days=30)

            request = InvoiceCreate(
                client_id=p.client_id,
                trip_id=p.trip_id,
                invoice_date=today,
                due_date=due,
                currency="EUR",
                line_items=[
                    InvoiceLineItem(
                        description="Invoice service",
                        quantity=1,
                        unit_price=p.amount,
                    )
                ],
                notes="",
            )

            from services.invoicing.service import InvoiceService

            service = InvoiceService(db)
            result = service.create(request, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            data: dict[str, Any] = {}
            if result.data:
                data = {
                    "invoice_id": result.data.id,
                    "invoice_number": result.data.invoice_number,
                    "status": result.data.status,
                }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.invoice.draft.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("invoice.draft failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
#  invoice.generate_pdf  (Level 1 — INFORMATIONAL)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class InvoiceGeneratePdfTool(BaseTool):
    """Generate a PDF for an existing invoice.

    Wraps ``InvoiceService.generate_pdf()``.
    """

    name = "invoice.generate_pdf"
    tool_version = "1.0.0"
    description = "Generate a PDF for an existing invoice"
    required_permission = "invoices:read"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    deprecated = False
    parameters_schema = InvoiceGeneratePdfParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> InvoiceGeneratePdfParams:
        assert isinstance(params, InvoiceGeneratePdfParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.invoice_id <= 0:
            errors.append("invoice_id must be a positive integer")
        return errors

    # ── Execution ──────────────────────────────────────────────────────

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            from services.invoicing.service import InvoiceService

            service = InvoiceService(db)
            result = service.generate_pdf(p.invoice_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            data: dict[str, Any] = {"success": True}
            if result.data:
                data["file_path"] = result.data.pdf_path or ""

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.invoice.generate_pdf.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("invoice.generate_pdf failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
#  invoice.finalize  (Level 2 — BUSINESS)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class InvoiceFinalizeTool(BaseTool):
    """Finalize (lock) a draft invoice.

    Wraps ``InvoiceService.finalize()``.  Requires user confirmation
    (BUSINESS level).  Returns the locked fiscal invoice number.
    """

    name = "invoice.finalize"
    tool_version = "1.0.0"
    description = "Finalize a draft invoice — locks the fiscal invoice number"
    required_permission = "invoices:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = InvoiceFinalizeParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> InvoiceFinalizeParams:
        assert isinstance(params, InvoiceFinalizeParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.invoice_id <= 0:
            errors.append("invoice_id must be a positive integer")
        return errors

    # ── Execution ──────────────────────────────────────────────────────

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            from models.invoice_models import InvoiceFinalizeRequest

            request = InvoiceFinalizeRequest(
                invoice_id=p.invoice_id,
                send_email=False,
                email_recipient="",
            )

            from services.invoicing.service import InvoiceService

            service = InvoiceService(db)
            result = service.finalize(request, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            data: dict[str, Any] = {}
            if result.data:
                data = {
                    "invoice_number": result.data.invoice_number,
                }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.invoice.finalize.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("invoice.finalize failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )
