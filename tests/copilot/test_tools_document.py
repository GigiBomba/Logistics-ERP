"""Comprehensive unit tests for document.* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance for both document tools
- Tool execution with mocked DocumentService
- Parameter schema validation (Pydantic level)
- Tool-level validate() logic
- Error handling (service failure, no DB, exceptions)

Blueprint: §9 — Registry enforcement.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult
from backend.copilot.tools.base import ToolExecutionContext
from backend.copilot.tools.registry import get_tool, run_startup_validation


# ── Module-level setup ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def _ensure_registry():
    run_startup_validation()
    yield


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    return ToolExecutionContext(
        company_id=1,
        user_id=42,
        role="dispatcher",
        session_context=SessionContext(),
        services={},
    )


@pytest.fixture
def ctx_with_db():
    return ToolExecutionContext(
        company_id=1,
        user_id=42,
        role="dispatcher",
        session_context=SessionContext(),
        services={"db": MagicMock()},
    )


def _make_document(**kwargs) -> MagicMock:
    """Build a minimal mock document object."""
    doc = MagicMock()
    doc.id = kwargs.get("id", 1)
    doc.title = kwargs.get("title", "original_name.pdf")
    doc.filename = kwargs.get("filename", "original_name.pdf")
    doc.category = kwargs.get("category", "invoice")
    doc.success = kwargs.get("success", True)
    doc.data = kwargs.get("data", doc)
    return doc


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract — both document tools
# ═══════════════════════════════════════════════════════════════════════════

DOCUMENT_TOOL_NAMES = [
    "document.search",
    "document.auto_rename",
]


class TestDocumentToolContract:
    """Every document tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()

    def test_document_search_permission(self):
        tool = get_tool("document.search")
        assert tool.required_permission == "documents:read"

    def test_document_auto_rename_permission(self):
        tool = get_tool("document.auto_rename")
        assert tool.required_permission == "documents:write"

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    def test_document_search_confirmation_level(self):
        tool = get_tool("document.search")
        assert tool.confirmation_level == ConfirmationLevel.SAFE

    def test_document_auto_rename_confirmation_level(self):
        tool = get_tool("document.auto_rename")
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_tool_supports_undo_correct(self, name):
        tool = get_tool(name)
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx):
        tool = get_tool(name)
        if name == "document.search":
            params = tool.parameters_schema()
        elif name == "document.auto_rename":
            params = tool.parameters_schema(document_id=1)
        else:
            params = tool.parameters_schema()
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", DOCUMENT_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx):
        tool = get_tool(name)
        if name == "document.search":
            params = tool.parameters_schema()
        elif name == "document.auto_rename":
            params = tool.parameters_schema(document_id=1)
        else:
            params = tool.parameters_schema()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════

class TestDocumentSearchParams:
    """document.search parameter schema edge cases."""

    def test_accepts_empty_defaults(self):
        """All fields on document.search have defaults — schemas() works."""
        tool = get_tool("document.search")
        params = tool.parameters_schema()
        assert params.query == ""
        assert params.category == ""
        assert params.entity_type == ""
        assert params.entity_id is None
        assert params.page == 1
        assert params.page_size == 20

    def test_accepts_query_and_category(self):
        tool = get_tool("document.search")
        params = tool.parameters_schema(query="invoice", category="financial")
        assert params.query == "invoice"
        assert params.category == "financial"

    def test_accepts_entity_type_and_id(self):
        tool = get_tool("document.search")
        params = tool.parameters_schema(entity_type="trip", entity_id=5)
        assert params.entity_type == "trip"
        assert params.entity_id == 5

    def test_rejects_page_below_one(self):
        tool = get_tool("document.search")
        with pytest.raises(ValidationError):
            tool.parameters_schema(page=0)

    def test_rejects_page_size_below_one(self):
        tool = get_tool("document.search")
        with pytest.raises(ValidationError):
            tool.parameters_schema(page_size=0)

    def test_rejects_page_size_above_100(self):
        tool = get_tool("document.search")
        with pytest.raises(ValidationError):
            tool.parameters_schema(page_size=200)

    def test_validate_entity_id_requires_entity_type(self, ctx):
        """validate() catches entity_id provided without entity_type."""
        tool = get_tool("document.search")
        params = tool.parameters_schema(entity_id=5)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("entity_type" in e for e in errors)

    def test_validate_passes_with_entity_type_and_id(self, ctx):
        tool = get_tool("document.search")
        params = tool.parameters_schema(entity_type="trip", entity_id=5)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


class TestDocumentAutoRenameParams:
    """document.auto_rename parameter schema edge cases."""

    def test_accepts_document_id(self):
        tool = get_tool("document.auto_rename")
        params = tool.parameters_schema(document_id=1)
        assert params.document_id == 1
        assert params.naming_pattern == "{client}_{date}_{type}"

    def test_accepts_custom_pattern(self):
        tool = get_tool("document.auto_rename")
        params = tool.parameters_schema(
            document_id=1,
            naming_pattern="{type}_{date}",
        )
        assert params.naming_pattern == "{type}_{date}"

    def test_rejects_document_id_zero(self):
        tool = get_tool("document.auto_rename")
        with pytest.raises(ValidationError):
            tool.parameters_schema(document_id=0)

    def test_rejects_document_id_negative(self):
        tool = get_tool("document.auto_rename")
        with pytest.raises(ValidationError):
            tool.parameters_schema(document_id=-1)

    def test_rejects_extra_fields(self):
        """ConfigDict(extra='forbid') — extra fields are rejected."""
        tool = get_tool("document.auto_rename")
        with pytest.raises(ValidationError):
            tool.parameters_schema(document_id=1, extra_field="x")

    def test_validate_always_returns_empty(self, ctx):
        """document.auto_rename validate() always returns []. No custom validation."""
        tool = get_tool("document.auto_rename")
        params = tool.parameters_schema(document_id=1)
        errors = asyncio.run(tool.validate(params, ctx))
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════
#  DocumentService execution — mocked service layer
#  The execute() methods import DocumentService/ClientRepository inside the
#  function body, so we patch the source module where they are defined.
# ═══════════════════════════════════════════════════════════════════════════

class TestDocumentSearchExecution:
    """document.search execute() with mocked DocumentService."""

    @patch("backend.services.document_service.DocumentService")
    def test_execute_search_success(self, MockDocService, ctx):
        """Successful document search with paginated results."""
        tool = get_tool("document.search")

        mock_service = MagicMock()
        mock_service.search.return_value = {
            "items": [
                {"id": 1, "title": "Invoice.pdf", "category": "financial"},
                {"id": 2, "title": "CMR.pdf", "category": "transport"},
            ],
            "total": 2,
            "page": 0,
            "total_pages": 1,
        }
        MockDocService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(query="invoice", category="financial", page=1, page_size=20)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["total"] == 2
        assert result.data["page"] == 1  # converted back to 1-based
        assert len(result.data["items"]) == 2
        mock_service.search.assert_called_once_with(
            query="invoice",
            category="financial",
            entity_type="",
            entity_id=None,
            order="uploaded_at DESC",
            page=0,  # 0-based internally
            page_size=20,
        )

    @patch("backend.services.document_service.DocumentService")
    def test_execute_search_with_filters(self, MockDocService, ctx):
        """Search with entity_type and entity_id filters."""
        tool = get_tool("document.search")

        mock_service = MagicMock()
        mock_service.search.return_value = {
            "items": [{"id": 10, "title": "TripDoc.pdf"}],
            "total": 1,
            "page": 0,
            "total_pages": 1,
        }
        MockDocService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(entity_type="trip", entity_id=42)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        mock_service.search.assert_called_once()
        call_kwargs = mock_service.search.call_args[1]
        assert call_kwargs["entity_type"] == "trip"
        assert call_kwargs["entity_id"] == 42

    def test_execute_search_no_db(self, ctx):
        """When no db in context, returns unavailable."""
        tool = get_tool("document.search")
        params = tool.parameters_schema()
        result = asyncio.run(tool.execute(params, ctx))  # empty services
        assert result.status == "unavailable"
        assert result.message_key == "copilot.tool.db_unavailable"

    @patch("backend.services.document_service.DocumentService")
    def test_execute_search_exception(self, MockDocService, ctx):
        """Service exception is caught and returned as failed ToolResult."""
        tool = get_tool("document.search")
        mock_service = MagicMock()
        mock_service.search.side_effect = RuntimeError("Search index unavailable")
        MockDocService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(query="test")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.search_failed"


class TestDocumentAutoRenameExecution:
    """document.auto_rename execute() with mocked service."""

    @patch("repositories.client_repository.ClientRepository")
    @patch("backend.services.document_service.DocumentService")
    def test_execute_auto_rename_success(
        self, MockDocService, MockClientRepo, ctx
    ):
        tool = get_tool("document.auto_rename")

        # Mock document fetch
        mock_doc = MagicMock()
        mock_doc.title = "old_name.pdf"
        mock_doc.filename = "old_name.pdf"
        mock_doc.category = "invoice"
        mock_doc.success = True
        mock_doc.data = mock_doc

        mock_service = MagicMock()
        mock_service.get.return_value = mock_doc
        mock_service.get_links.return_value = [
            {"entity_type": "client", "entity_id": "5"},
        ]
        mock_service.update_metadata.return_value = True
        MockDocService.return_value = mock_service

        # Mock client repo
        mock_client = MagicMock()
        mock_client.get_by_id.return_value = {"name": "ACME Corp"}
        MockClientRepo.return_value = mock_client

        ctx.services["db"] = MagicMock()
        params = tool.parameters_schema(document_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["document_id"] == 1
        assert result.data["old_title"] == "old_name.pdf"
        assert "ACME Corp" in result.data["new_title"]
        mock_service.get.assert_called_once_with(1)
        mock_service.get_links.assert_called_once_with(1)
        mock_service.update_metadata.assert_called_once()
        mock_client.get_by_id.assert_called_once_with(5)

    @patch("backend.services.document_service.DocumentService")
    def test_execute_auto_rename_document_not_found(self, MockDocService, ctx):
        tool = get_tool("document.auto_rename")

        mock_service = MagicMock()
        mock_doc = MagicMock()
        mock_doc.success = False
        mock_doc.data = None
        mock_service.get.return_value = mock_doc
        MockDocService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(document_id=999)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.not_found"

    @patch("repositories.client_repository.ClientRepository")
    @patch("backend.services.document_service.DocumentService")
    def test_execute_auto_rename_update_failed(
        self, MockDocService, MockClientRepo, ctx
    ):
        tool = get_tool("document.auto_rename")

        mock_doc = MagicMock()
        mock_doc.title = "old.pdf"
        mock_doc.filename = "old.pdf"
        mock_doc.category = "invoice"
        mock_doc.success = True
        mock_doc.data = mock_doc

        mock_service = MagicMock()
        mock_service.get.return_value = mock_doc
        mock_service.get_links.return_value = []
        mock_service.update_metadata.return_value = False
        MockDocService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(document_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.update_failed"

    @patch("repositories.client_repository.ClientRepository")
    @patch("backend.services.document_service.DocumentService")
    def test_execute_auto_rename_custom_pattern(
        self, MockDocService, MockClientRepo, ctx
    ):
        """Custom naming pattern is resolved correctly."""
        tool = get_tool("document.auto_rename")

        mock_doc = MagicMock()
        mock_doc.title = "old.pdf"
        mock_doc.filename = "scan001.pdf"
        mock_doc.category = "contract"
        mock_doc.success = True
        mock_doc.data = mock_doc

        mock_service = MagicMock()
        mock_service.get.return_value = mock_doc
        mock_service.get_links.return_value = []
        mock_service.update_metadata.return_value = True
        MockDocService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(
            document_id=1,
            naming_pattern="{filename}_{type}",
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert "scan001" in result.data["new_title"]
        assert "contract" in result.data["new_title"]

    def test_execute_auto_rename_no_db(self, ctx):
        tool = get_tool("document.auto_rename")
        params = tool.parameters_schema(document_id=1)
        result = asyncio.run(tool.execute(params, ctx))  # empty ctx

        assert result.status == "unavailable"
        assert result.message_key == "copilot.tool.db_unavailable"

    @patch("backend.services.document_service.DocumentService")
    def test_execute_auto_rename_exception(self, MockDocService, ctx):
        tool = get_tool("document.auto_rename")
        mock_service = MagicMock()
        mock_service.get.side_effect = RuntimeError("DB connection lost")
        MockDocService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(document_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.document.auto_rename_failed"
