"""Level 1-2 Co-Pilot tools for the Export domain.

PDF and Excel report generation capabilities exposed as AI-callable tools.
Wraps ``ExportService`` with typed Pydantic contracts.
"""

from __future__ import annotations

import logging
from typing import Any, List

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from models.export_models import ExportRequest

logger = logging.getLogger(__name__)


class ExportParams(BaseModel):
    """Shared parameters for both ``export.generate_pdf_report`` and
    ``export.generate_excel``."""

    entity_type: str = Field(
        ...,
        description=(
            "Type of entity to export — values: trip, invoice, receipt, cmr, "
            "dispatch_board, analytics"
        ),
    )
    entity_ids: List[int] = Field(
        default_factory=list,
        description="Specific entity IDs to include (empty = all entities)",
    )
    template: str = Field(
        default="default",
        description="Report template name (e.g. 'default', 'detailed', 'cmr')",
    )
    language: str = Field(
        default="en",
        description="Report language code (en, ro)",
    )
    include_logo: bool = Field(
        default=True,
        description="Include company logo in the report header",
    )


# ── PDF export tool ──────────────────────────────────────────────────────────


@register_tool
class ExportPdfReportTool(BaseTool):
    """Generate a PDF report for trips, invoices, receipts, or CMR documents.

    Wraps ``ExportService.export()`` with ``format="pdf"`` to produce a
    professional PDF document from the selected entity data.
    """

    name = "export.generate_pdf_report"
    tool_version = "1.0.0"
    description = (
        "Generate a PDF report for trips, invoices, receipts, or CMR documents"
    )
    required_permission = "export:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    parameters_schema = ExportParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ExportParams:
        assert isinstance(params, ExportParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        supported = {"trip", "invoice", "receipt", "cmr", "dispatch_board", "analytics"}
        if p.entity_type not in supported:
            errors.append(
                f"Unsupported entity_type '{p.entity_type}'. "
                f"Must be one of: {', '.join(sorted(supported))}"
            )
        if p.language not in ("en", "ro"):
            errors.append(f"Unsupported language '{p.language}'. Must be 'en' or 'ro'")
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
                    status="unavailable",
                    data=None,
                    message_key="copilot.tool.db_unavailable",
                    message_params={"tool": self.name},
                )

            from backend.services.export_service import ExportService

            service = ExportService(db=db)

            request = ExportRequest(
                format="pdf",
                entity_type=p.entity_type,
                entity_ids=p.entity_ids,
                template=p.template,
                language=p.language,
                include_logo=p.include_logo,
            )

            result = service.export(request, ctx.user_id)

            if not result.success:
                error_detail = result.errors[0] if result.errors else None
                error_msg = error_detail.message if error_detail else "PDF export returned an unsuccessful result"
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.export.generate_pdf_failed",
                    message_params={"error": error_msg},
                )

            if result.data is None:
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.export.generate_pdf_failed",
                    message_params={"error": "Export returned success but no data"},
                )

            return ToolResult(
                status="success",
                data={
                    "file_path": result.data.file_path,
                    "format": "pdf",
                },
                message_key="copilot.tool.export.generate_pdf_ok",
                message_params={
                    "file_path": result.data.file_path,
                    "entity_type": p.entity_type,
                },
            )

        except Exception as exc:
            logger.exception("export.generate_pdf_report failed: %s", exc)
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.export.generate_pdf_failed",
                message_params={"error": str(exc)},
            )


# ── Excel export tool ────────────────────────────────────────────────────────


@register_tool
class ExportExcelTool(BaseTool):
    """Generate an Excel (XLSX) report for trips, invoices, receipts, or CMR documents.

    Wraps ``ExportService.export()`` with ``format="excel"`` to produce a
    structured spreadsheet from the selected entity data.
    """

    name = "export.generate_excel"
    tool_version = "1.0.0"
    description = (
        "Generate an Excel spreadsheet for trips, invoices, receipts, or CMR documents"
    )
    required_permission = "export:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    parameters_schema = ExportParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ExportParams:
        assert isinstance(params, ExportParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        supported = {"trip", "invoice", "receipt", "cmr", "dispatch_board", "analytics"}
        if p.entity_type not in supported:
            errors.append(
                f"Unsupported entity_type '{p.entity_type}'. "
                f"Must be one of: {', '.join(sorted(supported))}"
            )
        if p.language not in ("en", "ro"):
            errors.append(f"Unsupported language '{p.language}'. Must be 'en' or 'ro'")
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
                    status="unavailable",
                    data=None,
                    message_key="copilot.tool.db_unavailable",
                    message_params={"tool": self.name},
                )

            from backend.services.export_service import ExportService

            service = ExportService(db=db)

            request = ExportRequest(
                format="excel",
                entity_type=p.entity_type,
                entity_ids=p.entity_ids,
                template=p.template,
                language=p.language,
                include_logo=p.include_logo,
            )

            result = service.export(request, ctx.user_id)

            if not result.success:
                error_detail = result.errors[0] if result.errors else None
                error_msg = error_detail.message if error_detail else "Excel export returned an unsuccessful result"
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.export.generate_excel_failed",
                    message_params={"error": error_msg},
                )

            if result.data is None:
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.export.generate_excel_failed",
                    message_params={"error": "Export returned success but no data"},
                )

            return ToolResult(
                status="success",
                data={
                    "file_path": result.data.file_path,
                    "format": "excel",
                },
                message_key="copilot.tool.export.generate_excel_ok",
                message_params={
                    "file_path": result.data.file_path,
                    "entity_type": p.entity_type,
                },
            )

        except Exception as exc:
            logger.exception("export.generate_excel failed: %s", exc)
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.export.generate_excel_failed",
                message_params={"error": str(exc)},
            )
