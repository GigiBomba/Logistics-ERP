"""Level-0 Co-Pilot tools for the Document domain.

Read-only document search capability exposed as AI-callable tools.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Parameters schema ───────────────────────────────────────────────────────

class DocumentSearchParams(BaseModel):
    """Parameters for document.search."""
    query: str = Field(default="", description="Full-text search query")
    category: str = Field(default="", description="Document category filter")
    entity_type: str = Field(
        default="",
        description="Entity type to filter by — values: trip, client, invoice",
    )
    entity_id: Optional[int] = Field(
        default=None,
        description="Entity ID to filter by (used together with entity_type)",
    )
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


# ── Tool implementations ────────────────────────────────────────────────────

@register_tool
class DocumentSearchTool(BaseTool):
    """Search documents across the system.

    Supports full-text search, filtering by category, entity type/ID, and
    pagination. Returns matching documents ordered by upload date descending.
    """

    name = "document.search"
    tool_version = "1.0.0"
    description = "Search documents with filters and pagination"
    required_permission = "documents:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = DocumentSearchParams

    async def validate(self, params: DocumentSearchParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        if params.entity_id is not None and not params.entity_type:
            errors.append("entity_type is required when entity_id is provided")
        return errors

    async def execute(self, params: DocumentSearchParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    data=None,
                    message_key="copilot.tool.db_unavailable",
                    message_params={"tool": self.name},
                )

            from backend.services.document_service import DocumentService

            service = DocumentService(db)
            # Service uses 0-based pages; tool interface is 1-based.
            result = service.search(
                query=params.query,
                category=params.category,
                entity_type=params.entity_type,
                entity_id=params.entity_id,
                order="uploaded_at DESC",
                page=params.page - 1,
                page_size=params.page_size,
            )

            items: List[dict[str, Any]] = result.get("items", [])
            total: int = result.get("total", 0)
            page: int = result.get("page", params.page - 1)
            total_pages: int = result.get("total_pages", 0)

            return ToolResult(
                status="success",
                data={
                    "items": items,
                    "total": total,
                    "page": page + 1,  # convert back to 1-based for caller
                    "total_pages": total_pages,
                },
                message_key="copilot.tool.document.search_ok",
                message_params={"total": total, "page": page + 1, "total_pages": total_pages},
            )

        except Exception as exc:
            logger.exception("document.search failed: %s", exc)
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.document.search_failed",
                message_params={"error": str(exc)},
            )


class DocumentAutoRenameParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: int = Field(..., gt=0, description="Document ID to rename")
    naming_pattern: str = Field(default="{client}_{date}_{type}", description="Naming pattern with variables")


@register_tool
class DocumentAutoRenameTool(BaseTool):
    """Auto-rename a document based on extracted OCR fields.

    NOTE: The underlying auto_rename() service method does not exist yet.
    This tool returns "unavailable" until DocumentService.auto_rename() is implemented.
    """
    name = "document.auto_rename"
    tool_version = "1.0.0"
    description = "Auto-rename a document based on extracted fields"
    required_permission = "documents:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    parameters_schema = DocumentAutoRenameParams

    async def validate(self, params: DocumentAutoRenameParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: DocumentAutoRenameParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    data=None,
                    message_key="copilot.tool.db_unavailable",
                    message_params={"tool": self.name},
                )

            from backend.services.document_service import DocumentService
            from repositories.client_repository import ClientRepository

            service = DocumentService(db)

            # 1. Fetch the document
            doc_result = service.get(params.document_id)
            if not doc_result.success or doc_result.data is None:
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.document.not_found",
                    message_params={"doc_id": str(params.document_id)},
                )

            doc = doc_result.data
            old_title = doc.title or ""

            # 2. Get linked entities to resolve {client}
            links = service.get_links(params.document_id)
            client_name = ""
            client_repo = ClientRepository(db)
            for link in links:
                if link.get("entity_type") == "client":
                    client_id = link.get("entity_id")
                    if client_id:
                        client = client_repo.get_by_id(int(client_id))
                        if client:
                            client_name = client.get("name", "")
                            break

            # 3. Resolve naming pattern variables
            now_str = datetime.now().strftime("%Y-%m-%d")
            new_title = params.naming_pattern
            new_title = new_title.replace("{client}", client_name)
            new_title = new_title.replace("{date}", now_str)
            new_title = new_title.replace("{type}", doc.category or "")
            new_title = new_title.replace("{filename}", doc.filename or "")

            # 4. Update metadata
            updated = service.update_metadata(params.document_id, title=new_title)
            if not updated:
                return ToolResult(
                    status="failed",
                    data=None,
                    message_key="copilot.tool.document.update_failed",
                    message_params={"doc_id": str(params.document_id)},
                )

            return ToolResult(
                status="success",
                data={
                    "document_id": params.document_id,
                    "old_title": old_title,
                    "new_title": new_title,
                },
                message_key="copilot.tool.document.auto_rename_ok",
                message_params={"doc_id": str(params.document_id)},
            )

        except Exception as exc:
            logger.exception("document.auto_rename failed")
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.document.auto_rename_failed",
                message_params={"error": str(exc)},
            )
