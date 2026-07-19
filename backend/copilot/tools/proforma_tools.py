"""Co-Pilot tools for the Proforma domain — create, convert to invoice, and availability check.

Level-1 (INFORMATIONAL) and Level-2 (BUSINESS) tools wrapping ProformaService.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from services.invoicing.proforma_service import ProformaService

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
#  Parameters
# ═════════════════════════════════════════════════════════════════════════════


class ProformaCreateParams(BaseModel):
    """Input parameters for proforma.create."""

    client_id: int = Field(..., gt=0, description="Client ID for the proforma")
    trip_id: int = Field(..., gt=0, description="Trip ID for the proforma")
    amount: float = Field(..., gt=0, description="Proforma amount")
    currency: str = Field(default="EUR", max_length=3, description="Currency code")


class ProformaUpdateParams(BaseModel):
    """Input parameters for proforma.update."""

    proforma_id: int = Field(..., gt=0, description="Proforma ID to update")
    notes: str = Field(default="", description="New notes text")
    currency: str = Field(default="", max_length=3, description="New currency code (e.g. EUR)")
    valid_until: str = Field(default="", description="New valid-until date (YYYY-MM-DD)")
    status: str = Field(default="", description="New status (e.g. Draft, Sent, Converted)")


class ProformaConvertToInvoiceParams(BaseModel):
    """Input parameters for proforma.convert_to_invoice."""

    proforma_id: int = Field(..., gt=0, description="Proforma ID to convert")


# ═════════════════════════════════════════════════════════════════════════════
#  proforma.create  (Level 1 — INFORMATIONAL)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class ProformaCreateTool(BaseTool):
    """Create a draft proforma invoice.

    Wraps ``ProformaService.create()`` with minimal required fields.
    Automatically sets issue_date (today), valid_until (30 days), and
    a single line item from the provided amount.
    """

    name = "proforma.create"
    tool_version = "1.0.0"
    description = "Create a new proforma invoice for a trip"
    required_permission = "proforma:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    deprecated = False
    parameters_schema = ProformaCreateParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ProformaCreateParams:
        assert isinstance(params, ProformaCreateParams)
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

            from models.proforma_models import ProformaCreate

            today = date.today()
            valid_until = today + timedelta(days=30)

            request = ProformaCreate(
                client_id=p.client_id,
                trip_id=p.trip_id,
                issue_date=today,
                valid_until=valid_until,
                currency=p.currency,
                items=[
                    {
                        "description": "Proforma service",
                        "amount": p.amount,
                        "quantity": 1,
                    }
                ],
                notes="",
            )

            service = ProformaService(db)
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
                    "proforma_id": result.data.id,
                    "proforma_number": result.data.proforma_number,
                }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.proforma.create.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("proforma.create failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
#  proforma.update  (Level 1 — INFORMATIONAL)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class ProformaUpdateTool(BaseTool):
    """Update an existing proforma invoice.

    Wraps ``ProformaService.update()`` to update notes, currency,
    valid-until date, or status on an existing proforma.
    """

    name = "proforma.update"
    tool_version = "1.0.0"
    description = "Update an existing proforma invoice — notes, currency, valid_until, or status"
    required_permission = "proforma:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    deprecated = False
    parameters_schema = ProformaUpdateParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ProformaUpdateParams:
        assert isinstance(params, ProformaUpdateParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.proforma_id <= 0:
            errors.append("proforma_id must be a positive integer")
        if p.currency and len(p.currency) != 3:
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

            service = ProformaService(db)

            # Build data dict with only the fields that were provided
            data: dict[str, Any] = {}
            if p.notes:
                data["notes"] = p.notes
            if p.currency:
                data["currency"] = p.currency
            if p.valid_until:
                data["valid_until"] = p.valid_until
            if p.status:
                data["status"] = p.status

            if not data:
                return ToolResult(
                    status="failed",
                    message_key="copilot.proforma.update.no_fields",
                    message_params={},
                )

            result = service.update(p.proforma_id, data, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            proforma_data: dict[str, Any] = {}
            if result.data:
                proforma_data = {
                    "proforma_id": result.data.id,
                    "proforma_number": result.data.proforma_number,
                    "status": result.data.status,
                    "currency": result.data.currency,
                    "notes": result.data.notes,
                    "valid_until": result.data.valid_until.isoformat()
                    if hasattr(result.data.valid_until, "isoformat")
                    else str(result.data.valid_until),
                }

            return ToolResult(
                status="success",
                data=proforma_data,
                message_key="copilot.proforma.update.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("proforma.update failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
#  proforma.convert_to_invoice  (Level 2 — BUSINESS)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class ProformaConvertToInvoiceTool(BaseTool):
    """Convert a proforma invoice to a real invoice.

    Wraps ``ProformaService.convert_to_invoice()``.  Requires user
    confirmation (BUSINESS level).  Returns the newly created invoice
    details.
    """

    name = "proforma.convert_to_invoice"
    tool_version = "1.0.0"
    description = "Convert a proforma invoice to a real invoice"
    required_permission = "proforma:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = ProformaConvertToInvoiceParams

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ProformaConvertToInvoiceParams:
        assert isinstance(params, ProformaConvertToInvoiceParams)
        return params

    # ── Validation ─────────────────────────────────────────────────────

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.proforma_id <= 0:
            errors.append("proforma_id must be a positive integer")
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

            service = ProformaService(db)
            result = service.convert_to_invoice(p.proforma_id, user_id=ctx.user_id)

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
                    "invoice_id": result.data.get("invoice_id"),
                    "invoice_number": result.data.get("invoice_number"),
                }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.proforma.convert_to_invoice.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("proforma.convert_to_invoice failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )
