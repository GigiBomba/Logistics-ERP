"""Level 1-2 Co-Pilot tools for the CMR (waybill) domain.

CMR document generation capability exposed as an AI-callable tool.
Wraps ``CMRGenerator`` with typed Pydantic contracts.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from models.cmr_models import CmrGenerateRequest

logger = logging.getLogger(__name__)


class GenerateCmrParams(BaseModel):
    """Parameters for ``document.generate_cmr``."""

    trip_id: int = Field(..., gt=0, description="Trip ID to generate the CMR for")
    language: str = Field(
        default="en",
        description="Document language code (en, ro, de, fr)",
    )
    copies: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Number of physical copies to generate",
    )
    include_efti: bool = Field(
        default=True,
        description="Include eFTI XML attachment for digital compliance",
    )
    adr_class: Optional[str] = Field(
        default=None,
        description="ADR class for dangerous goods (e.g. '3', '6.1')",
    )
    adr_un_number: Optional[str] = Field(
        default=None,
        description="ADR UN number for dangerous goods (e.g. 'UN1203')",
    )


@register_tool
class GenerateCmrTool(BaseTool):
    """Generate a CMR (Consignment Note) for international road transport.

    Wraps ``CMRGenerator.generate()`` to produce professional A4 CMR
    documents per the UN Convention (Geneva, 1956) with bilingual labels,
    multi-copy support, and optional eFTI XML embedding.

    Uses the typed ``CmrGenerateRequest`` path when possible, falling
    back to legacy kwargs for backward compatibility.
    """

    name = "document.generate_cmr"
    tool_version = "1.0.0"
    description = (
        "Generate a CMR waybill document for a trip, returning the "
        "generated PDF file path(s) and CMR number"
    )
    required_permission = "documents:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    parameters_schema = GenerateCmrParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> GenerateCmrParams:
        assert isinstance(params, GenerateCmrParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        supported = {"en", "ro", "de", "fr"}
        if p.language not in supported:
            errors.append(
                f"Unsupported language '{p.language}'. "
                f"Must be one of: {', '.join(sorted(supported))}"
            )
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

            from services.invoicing.cmr_generator import CMRGenerator
            from models.common import ServiceResult

            service = CMRGenerator(db=db)

            # Build typed request — CmrGenerateRequest does not currently
            # expose adr_class / adr_un_number fields, so those are reserved
            # for future use when the model is extended.
            request = CmrGenerateRequest(
                trip_id=p.trip_id,
                language=p.language,
                copies=p.copies,
            )

            # ── Dual-interface dispatch ──────────────────────────────
            # Prefer the typed path (CmrGenerateRequest + user_id).
            # The generator internally checks isinstance(request, CmrGenerateRequest)
            # and falls back to legacy dict-based handling if not.
            # The return type is a union: str (legacy) | CmrGenerateResult (typed).
            raw = service.generate(request, ctx.user_id)

            # Guard: typed path returns a ServiceResult, legacy returns str.
            if not isinstance(raw, ServiceResult):
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.document.generate_cmr_failed",
                    message_params={"error": "Generator fell back to legacy path unexpectedly"},
                )

            if not raw.success:
                error_detail = raw.errors[0] if raw.errors else None
                error_msg = error_detail.message if error_detail else "CMR generation returned an unsuccessful result"
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.document.generate_cmr_failed",
                    message_params={"error": error_msg},
                )

            if raw.data is None:
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.document.generate_cmr_failed",
                    message_params={"error": "Generator returned success but no data"},
                )

            return ToolResult(
                status="success",
                data={
                    "file_paths": [raw.data.file_path],
                    "cmr_number": raw.data.cmr_number,
                },
                message_key="copilot.tool.document.generate_cmr_ok",
                message_params={
                    "cmr_number": raw.data.cmr_number,
                    "copies": p.copies,
                    "file_path": raw.data.file_path,
                },
            )

        except Exception as exc:
            logger.exception("document.generate_cmr failed: %s", exc)
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.document.generate_cmr_failed",
                message_params={"error": str(exc)},
            )
