"""Level 1-2 Co-Pilot tools for the Tachograph domain.

Tachograph file import capability exposed as an AI-callable tool.
Wraps ``TachoService`` with typed Pydantic contracts.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from models.tacho_models import TachoImportRequest

logger = logging.getLogger(__name__)


class TachoImportParams(BaseModel):
    """Parameters for ``tahograf.import_file``."""

    file_path: str = Field(
        ...,
        min_length=1,
        description="Absolute path to the tachograph file (.ddd, .c1b, .esm)",
    )
    driver_id: Optional[int] = Field(
        default=None,
        description="Driver ID to associate with the import (auto-detected if omitted)",
    )
    vehicle_id: Optional[int] = Field(
        default=None,
        description="Vehicle ID to associate with the import (auto-detected if omitted)",
    )


@register_tool
class TachoImportFileTool(BaseTool):
    """Import a tachograph file (.DDD, .C1B, .ESM) into the system.

    Wraps ``TachoService.import_file()`` to parse driver/vehicle activity
    data from digital tachograph files, store the results, and return an
    analysis summary including driving hours and any compliance warnings.

    Requires admin or manager role.
    """

    name = "tahograf.import_file"
    tool_version = "1.0.0"
    description = (
        "Import a tachograph file and analyse driver hours for EU compliance"
    )
    required_permission = "tacho:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    parameters_schema = TachoImportParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> TachoImportParams:
        assert isinstance(params, TachoImportParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if not p.file_path.strip():
            errors.append("file_path must not be empty")
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

            from backend.services.tacho_service import TachoService

            service = TachoService(db)

            request = TachoImportRequest(
                file_path=p.file_path,
                driver_id=p.driver_id,
                vehicle_id=p.vehicle_id,
            )

            result = service.import_file(request, ctx.user_id)

            if not result.success:
                error_detail = result.errors[0] if result.errors else None
                error_msg = error_detail.message if error_detail else "Tacho import returned an unsuccessful result"
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.tacho.import_file_failed",
                    message_params={"error": error_msg},
                )

            if result.data is None:
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.tacho.import_file_failed",
                    message_params={"error": "Import returned success but no data"},
                )

            return ToolResult(
                status="success",
                data={
                    "import_id": result.data.import_id,
                    "driver_hours_analyzed": result.data.driver_activities,
                    "warnings": result.data.warnings,
                },
                message_key="copilot.tool.tacho.import_file_ok",
                message_params={
                    "import_id": result.data.import_id,
                    "driver_activities": result.data.driver_activities,
                    "warnings_count": len(result.data.warnings),
                },
            )

        except Exception as exc:
            logger.exception("tahograf.import_file failed: %s", exc)
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.tacho.import_file_failed",
                message_params={"error": str(exc)},
            )
