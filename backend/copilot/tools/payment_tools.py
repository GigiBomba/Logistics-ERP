"""Bulk Payment CSV Generation tool — Level 1 (file generation, no direct financial movement).

Blueprint: §9.1 — Bulk Payment CSV Maker, §22 item 7 (bank profile support).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


class GenerateBulkCsvParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_ids: List[int] = Field(
        ..., min_length=1,
        description="Invoice IDs to include in the payment batch",
    )
    driver_ids: List[int] = Field(
        default=[],
        description="Driver IDs to include in the payment batch",
    )
    bank_profile_id: Optional[int] = Field(
        None,
        description="Bank profile ID for country-specific CSV format (§22 item 7)",
    )


@register_tool
class GenerateBulkCsvTool(BaseTool):
    """Generate a bank-upload-ready bulk payment CSV file.

    Level 1: File generation with no direct financial movement inside Operion,
    but flagged as sensitive — the file itself triggers real money movement
    when uploaded to a bank portal.
    """
    name = "payment.generate_bulk_csv"
    tool_version = "1.0.0"
    description = "Generate a bank-upload-ready bulk payment CSV file"
    required_permission = "payments:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    parameters_schema = GenerateBulkCsvParams

    async def validate(self, params: GenerateBulkCsvParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        total_ids = len(params.invoice_ids) + len(params.driver_ids)
        if total_ids == 0:
            errors.append("At least one invoice_id or driver_id is required")
        if total_ids > 500:
            errors.append("Maximum 500 recipients per batch")
        return errors

    async def execute(self, params: GenerateBulkCsvParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(status="unavailable", message_key="copilot.error.no_db")

            from models.payment_models import PaymentBatchRequest
            from backend.services.payment_batch_service import PaymentBatchService

            svc = PaymentBatchService(db)

            request = PaymentBatchRequest(
                profile_id=params.bank_profile_id or 0,
                invoice_ids=params.invoice_ids,
                driver_ids=params.driver_ids,
            )

            result = svc.generate_batch(request, user_id=ctx.user_id)

            if not result.success:
                err_msg = (result.errors[0].message if result.errors else "Unknown error")
                return ToolResult(
                    status="failed",
                    message_key="copilot.payment.bulk_csv_failed",
                    message_params={"error": err_msg},
                )

            data = result.data
            return ToolResult(
                status="success",
                data={
                    "batch_id": data.batch_id if data else None,
                    "file_path": data.file_path if data else None,
                    "row_count": data.row_count if data else 0,
                    "total_amount": data.total_amount if data else 0.0,
                    "currency": data.currency if data else "EUR",
                },
                message_key="copilot.payment.bulk_csv_ok",
                message_params={"count": data.row_count if data else 0},
            )
        except Exception as e:
            logger.exception("payment.generate_bulk_csv failed: %s", e)
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )
