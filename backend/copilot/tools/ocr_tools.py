"""OCR pipeline tools — Level 1-2 Co-Pilot tools for document processing.

Blueprint: §9.1 — Documents & OCR.
Uses the existing dual-engine OCR pipeline (PaddleOCR for printed,
self-hosted Gemma 3:4B for handwritten) via the pipeline service.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


class OcrImportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str = Field(..., min_length=1, description="Path to the document to OCR")
    document_type: str = Field(default="auto", description="Document type hint: invoice, cmr, receipt, contract, or auto")
    language: str = Field(default="auto", description="Document language: auto, ro, en")
    client_id: Optional[int] = Field(None, description="Optional client ID for matching")


@register_tool
class OcrImportTool(BaseTool):
    """Import and OCR a document — routes to PaddleOCR (printed) or self-hosted Gemma 3:4B (handwritten).

    The OCR pipeline service internally classifies each document and routes
    to the correct engine. Output is a normalized field-extraction result.
    Level 1: produces a draft match, does not attach to a live record.
    """
    name = "document.ocr_import"
    tool_version = "1.0.0"
    description = "Import a document for OCR processing — routes printed text to PaddleOCR, handwritten to Gemma 3:4B"
    required_permission = "documents:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    parameters_schema = OcrImportParams

    async def validate(self, params: OcrImportParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        if not os.path.isfile(params.file_path):
            errors.append(f"File not found: {params.file_path}")
        return errors

    async def execute(self, params: OcrImportParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(status="unavailable", message_key="copilot.error.no_db")

            from backend.services.document_service import DocumentService

            doc_svc = DocumentService(db)

            # Upload / register the document — copies the file into the
            # managed documents directory and creates the DB record.
            doc_id = doc_svc.upload_legacy(
                source_path=params.file_path,
                title=os.path.basename(params.file_path),
                entity_id=params.client_id,
                uploaded_by=str(ctx.user_id),
            )

            if not doc_id:
                return ToolResult(
                    status="failed",
                    message_key="copilot.tool.document.create_failed",
                )

            # Run the full OCR pipeline synchronously.
            from services.document_automation.pipeline import run_for_existing_document

            try:
                result = run_for_existing_document(db, doc_id)
            except Exception as pipe_exc:
                logger.warning(
                    "Full OCR pipeline failed for doc %d: %s — falling back to basic extraction",
                    doc_id, pipe_exc,
                )
                # Fallback: basic text extraction via OcrService.
                doc = doc_svc.get_by_id(doc_id)
                if doc:
                    mime_type = doc.get("mime_type", "")
                    file_path = doc.get("file_path", "")
                    text = doc_svc.extract_text(file_path, mime_type)
                    return ToolResult(
                        status="success",
                        data={
                            "document_id": doc_id,
                            "text": text[:500] if text else "",
                            "status": "extracted",
                        },
                        message_key="copilot.tool.document.ocr_import_ok",
                        message_params={"doc_id": doc_id},
                    )
                raise

            return ToolResult(
                status="success",
                data={
                    "document_id": doc_id,
                    "extracted_data": result.get("extracted", {}),
                    "confidence": result.get("confidence", 0.0),
                    "status": "completed",
                },
                message_key="copilot.tool.document.ocr_import_ok",
                message_params={"doc_id": doc_id},
            )

        except Exception as e:
            logger.exception("OCR import failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )


class OcrConfirmMatchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: int = Field(..., gt=0, description="Document ID from ocr_import result")
    matched_entity_type: str = Field(..., description="Entity type: client, trip, invoice")
    matched_entity_id: int = Field(..., gt=0, description="Entity ID to attach to")


@register_tool
class OcrConfirmMatchTool(BaseTool):
    """Confirm an OCR match and attach the document to a business entity.

    Level 2: mutates business data (attaches document to a specific
    client/trip/invoice). Requires user confirmation.
    """
    name = "document.ocr_confirm_match"
    tool_version = "1.0.0"
    description = "Confirm an OCR match and attach the document to a client, trip, or invoice"
    required_permission = "documents:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    parameters_schema = OcrConfirmMatchParams

    async def validate(self, params: OcrConfirmMatchParams, ctx: ToolExecutionContext) -> List[str]:
        valid_types = ("client", "trip", "invoice")
        if params.matched_entity_type not in valid_types:
            return [f"Invalid entity type: {params.matched_entity_type}. Must be one of: {', '.join(valid_types)}"]
        return []

    async def execute(self, params: OcrConfirmMatchParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(status="unavailable", message_key="copilot.error.no_db")

            from backend.services.document_service import DocumentService

            doc_svc = DocumentService(db)

            if params.matched_entity_type == "trip":
                # Use DocumentGrouper for trip linking (handles CMR metadata,
                # transaction safety, and related-document tracking).
                from services.document_automation.document_grouper import DocumentGrouper
                grouper = DocumentGrouper(db)
                success = grouper.link_existing_document_to_trip(
                    doc_id=params.document_id,
                    trip_id=params.matched_entity_id,
                    extracted={},
                )
            else:
                # Use DocumentService.link_document for client/invoice linking.
                success = doc_svc.link_document(
                    params.document_id,
                    params.matched_entity_type,
                    params.matched_entity_id,
                )

            if success:
                return ToolResult(
                    status="success",
                    data={
                        "document_id": params.document_id,
                        "linked_to_type": params.matched_entity_type,
                        "linked_to_id": params.matched_entity_id,
                    },
                    message_key="copilot.tool.document.ocr_match_ok",
                    message_params={
                        "doc_id": params.document_id,
                        "entity_type": params.matched_entity_type,
                        "entity_id": params.matched_entity_id,
                    },
                )

            return ToolResult(
                status="failed",
                message_key="copilot.tool.document.ocr_match_failed",
            )

        except Exception as e:
            logger.exception("OCR confirm match failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )
