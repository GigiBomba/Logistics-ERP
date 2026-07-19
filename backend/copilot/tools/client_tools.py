"""Co-Pilot tools for the Client domain — payment summaries and client info.

Level-0 tools wrapping ClientService for AI-driven client queries.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from backend.services.client_service import ClientService

logger = logging.getLogger(__name__)


class PaymentSummaryParams(BaseModel):
    """Input parameters for client.payment_summary."""

    client_id: int = Field(..., gt=0, description="Client ID to query")


@register_tool
class PaymentSummaryTool(BaseTool):
    """Get a payment summary for a client.

    Wraps ``ClientService.get_payment_summary()`` to return aggregated
    billing and payment figures for a single client.
    """

    name = "client.payment_summary"
    tool_version = "1.0.0"
    description = (
        "Get payment summary for a client including total billed, "
        "total paid, unpaid, overdue, and invoice count"
    )
    required_permission = "clients:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    deprecated = False
    parameters_schema = PaymentSummaryParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> PaymentSummaryParams:
        assert isinstance(params, PaymentSummaryParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.client_id <= 0:
            errors.append("client_id must be a positive integer")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.no_db",
                    message_params={},
                )

            service = ClientService(db)
            summary: dict[str, Any] = service.get_payment_summary(
                p.client_id
            )

            return ToolResult(
                status="success",
                data={
                    "total_billed": summary.get("total_billed", 0),
                    "total_paid": summary.get("total_paid", 0),
                    "unpaid": summary.get("unpaid", 0),
                    "overdue": summary.get("overdue", 0),
                    "invoice_count": summary.get("invoice_count", 0),
                },
                message_key="copilot.client.payment_summary.success",
                message_params={},
            )

        except Exception as exc:
            logger.exception("client.payment_summary failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )
