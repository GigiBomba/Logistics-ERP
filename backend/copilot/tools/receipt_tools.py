"""Co-Pilot tools for the Receipt domain — draft, PDF generation, and availability check.

Level-1 (INFORMATIONAL) and Level-2 (BUSINESS) tools wrapping ReceiptGenerator.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
#  Parameters
# ═════════════════════════════════════════════════════════════════════════════


class ReceiptDraftParams(BaseModel):
    """Input parameters for receipt.draft."""

    type: str = Field(
        default="customer_payment",
        description="Receipt type: customer_payment, advance, cash, reimbursement",
    )
    client_id: int = Field(..., gt=0, description="Client ID for the receipt")
    amount: float = Field(..., gt=0, description="Receipt amount")
    currency: str = Field(default="EUR", max_length=3, description="Currency code")
    notes: str = Field(default="", description="Optional notes")


class ReceiptGeneratePdfParams(BaseModel):
    """Input parameters for receipt.generate_pdf."""

    receipt_id: int = Field(..., gt=0, description="Receipt ID to generate PDF for")


class ReceiptFinalizeParams(BaseModel):
    """Input parameters for receipt.finalize (currently unavailable)."""

    receipt_id: int = Field(..., gt=0, description="Receipt ID to finalize")


# ═════════════════════════════════════════════════════════════════════════════
#  receipt.draft  (Level 1 — INFORMATIONAL)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class ReceiptDraftTool(BaseTool):
    """Create a draft receipt.

    Wraps ``ReceiptGenerator.create()`` with minimal required fields.
    Automatically sets receipt_date to today and builds a single line item
    from the provided amount.
    """

    name = "receipt.draft"
    tool_version = "1.0.0"
    description = "Create a new draft receipt for a client"
    required_permission = "receipts:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    deprecated = False
    parameters_schema = ReceiptDraftParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ReceiptDraftParams:
        assert isinstance(params, ReceiptDraftParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        valid_types = {"customer_payment", "advance", "cash", "reimbursement"}
        if p.type not in valid_types:
            errors.append(f"type must be one of: {', '.join(sorted(valid_types))}")
        if p.client_id <= 0:
            errors.append("client_id must be a positive integer")
        if p.amount <= 0:
            errors.append("amount must be greater than zero")
        if not p.currency or len(p.currency) != 3:
            errors.append("currency must be a 3-letter code (e.g. EUR)")
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

            from models.receipt_models import ReceiptCreate, ReceiptLineItem

            request = ReceiptCreate(
                client_id=p.client_id,
                receipt_date=date.today(),
                currency=p.currency,
                items=[
                    ReceiptLineItem(
                        description=f"Receipt ({p.type})",
                        amount=p.amount,
                        quantity=1,
                    )
                ],
                total_amount=p.amount,
                notes=p.notes,
            )

            from services.invoicing.receipt_generator import ReceiptGenerator

            service = ReceiptGenerator(db=db)
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
                    "receipt_id": result.data.id,
                    "receipt_number": result.data.receipt_number,
                }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.receipt.draft.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("receipt.draft failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
#  receipt.generate_pdf  (Level 1 — INFORMATIONAL)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class ReceiptGeneratePdfTool(BaseTool):
    """Generate a PDF for an existing receipt.

    Wraps ``ReceiptGenerator.generate_pdf()``.
    """

    name = "receipt.generate_pdf"
    tool_version = "1.0.0"
    description = "Generate a PDF for an existing receipt"
    required_permission = "receipts:read"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    deprecated = False
    parameters_schema = ReceiptGeneratePdfParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ReceiptGeneratePdfParams:
        assert isinstance(params, ReceiptGeneratePdfParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.receipt_id <= 0:
            errors.append("receipt_id must be a positive integer")
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

            from services.invoicing.receipt_generator import ReceiptGenerator

            service = ReceiptGenerator(db=db)
            result = service.generate_pdf(p.receipt_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            data: dict[str, Any] = {}
            if result.data:
                data["file_path"] = result.data.pdf_path or ""

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.receipt.generate_pdf.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("receipt.generate_pdf failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
#  receipt.finalize  (Level 2 — BUSINESS)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class ReceiptFinalizeTool(BaseTool):
    """Finalize a draft receipt.

    Wraps ``ReceiptGenerator.finalize()`` which checks the receipt
    exists in Draft status and transitions it to Finalized.
    """

    name = "receipt.finalize"
    tool_version = "1.0.0"
    description = "Finalize a draft receipt — transitions from Draft to Finalized status"
    required_permission = "receipts:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = ReceiptFinalizeParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ReceiptFinalizeParams:
        assert isinstance(params, ReceiptFinalizeParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.receipt_id <= 0:
            errors.append("receipt_id must be a positive integer")
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

            from services.invoicing.receipt_generator import ReceiptGenerator

            service = ReceiptGenerator(db=db)
            result = service.finalize(p.receipt_id, user_id=ctx.user_id)

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
                    "receipt_id": result.data.get("receipt_id"),
                    "receipt_number": result.data.get("receipt_number", ""),
                    "status": result.data.get("status", "Finalized"),
                }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.receipt.finalize.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("receipt.finalize failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )
