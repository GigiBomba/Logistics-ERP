"""Comprehensive unit tests for invoice.* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance for all 3 invoice tools
- Tool execution with mocked InvoiceService
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


def _make_invoice_result(
    success: bool = True,
    invoice_id: int = 1,
    invoice_number: str = "INV-001",
    status: str = "draft",
    data_attr: bool = True,
    pdf_path: str = "/invoices/inv-001.pdf",
):
    """Build a mock InvoiceService result."""
    result = MagicMock()
    result.success = success
    result.errors = [] if success else [MagicMock(message="Service error")]

    if data_attr:
        mock_data = MagicMock()
        mock_data.id = invoice_id
        mock_data.invoice_number = invoice_number
        mock_data.status = status
        mock_data.pdf_path = pdf_path
        result.data = mock_data
    else:
        result.data = None

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract — all invoice tools
# ═══════════════════════════════════════════════════════════════════════════

INVOICE_TOOL_NAMES = [
    "invoice.draft",
    "invoice.generate_pdf",
    "invoice.finalize",
]


class TestInvoiceToolContract:
    """Every invoice tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()

    def test_invoice_draft_permission(self):
        tool = get_tool("invoice.draft")
        assert tool.required_permission == "invoices:write"

    def test_invoice_generate_pdf_permission(self):
        tool = get_tool("invoice.generate_pdf")
        assert tool.required_permission == "invoices:read"

    def test_invoice_finalize_permission(self):
        tool = get_tool("invoice.finalize")
        assert tool.required_permission == "invoices:write"

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    def test_invoice_draft_confirmation_level(self):
        tool = get_tool("invoice.draft")
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    def test_invoice_generate_pdf_confirmation_level(self):
        tool = get_tool("invoice.generate_pdf")
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    def test_invoice_finalize_confirmation_level(self):
        tool = get_tool("invoice.finalize")
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_supports_undo_false(self, name):
        tool = get_tool(name)
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx):
        tool = get_tool(name)
        if name == "invoice.draft":
            params = tool.parameters_schema(client_id=1, trip_id=1, amount=100.0)
        elif name == "invoice.generate_pdf":
            params = tool.parameters_schema(invoice_id=1)
        elif name == "invoice.finalize":
            params = tool.parameters_schema(invoice_id=1)
        else:
            params = tool.parameters_schema()
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", INVOICE_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx):
        tool = get_tool(name)
        if name == "invoice.draft":
            params = tool.parameters_schema(client_id=1, trip_id=1, amount=100.0)
        elif name == "invoice.generate_pdf":
            params = tool.parameters_schema(invoice_id=1)
        elif name == "invoice.finalize":
            params = tool.parameters_schema(invoice_id=1)
        else:
            params = tool.parameters_schema()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════

class TestInvoiceDraftParams:
    """invoice.draft parameter schema edge cases."""

    def test_accepts_valid_params(self):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema(client_id=1, trip_id=10, amount=1500.0)
        assert params.client_id == 1
        assert params.trip_id == 10
        assert params.amount == 1500.0
        assert params.due_date is None

    def test_accepts_due_date(self):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema(
            client_id=1, trip_id=10, amount=1500.0, due_date="2026-08-15",
        )
        assert params.due_date == "2026-08-15"

    def test_rejects_client_id_zero(self):
        tool = get_tool("invoice.draft")
        with pytest.raises(ValidationError):
            tool.parameters_schema(client_id=0, trip_id=1, amount=100.0)

    def test_rejects_trip_id_zero(self):
        tool = get_tool("invoice.draft")
        with pytest.raises(ValidationError):
            tool.parameters_schema(client_id=1, trip_id=0, amount=100.0)

    def test_rejects_amount_zero(self):
        tool = get_tool("invoice.draft")
        with pytest.raises(ValidationError):
            tool.parameters_schema(client_id=1, trip_id=1, amount=0)

    def test_rejects_negative_amount(self):
        tool = get_tool("invoice.draft")
        with pytest.raises(ValidationError):
            tool.parameters_schema(client_id=1, trip_id=1, amount=-50)

    def test_accepts_any_due_date_string(self):
        """The due_date field is Optional[str] — no Pydantic format validation.
        Format validation only happens in validate()."""
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema(
            client_id=1, trip_id=1, amount=100.0, due_date="not-a-date",
        )
        assert params.due_date == "not-a-date"

    def test_validate_catches_zero_client_id(self, ctx):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema.model_construct(client_id=0, trip_id=1, amount=100.0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("client_id" in e for e in errors)

    def test_validate_catches_zero_trip_id(self, ctx):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema.model_construct(client_id=1, trip_id=0, amount=100.0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert any("trip_id" in e for e in errors)

    def test_validate_catches_zero_amount(self, ctx):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema.model_construct(client_id=1, trip_id=1, amount=0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert any("amount" in e for e in errors)

    def test_validate_catches_bad_due_date(self, ctx):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema.model_construct(
            client_id=1, trip_id=1, amount=100.0, due_date="bad-date",
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert any("due_date" in e for e in errors)

    def test_validate_passes_good_params(self, ctx):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema(client_id=1, trip_id=1, amount=100.0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


class TestInvoiceGeneratePdfParams:
    """invoice.generate_pdf parameter schema edge cases."""

    def test_accepts_invoice_id(self):
        tool = get_tool("invoice.generate_pdf")
        params = tool.parameters_schema(invoice_id=1)
        assert params.invoice_id == 1

    def test_rejects_invoice_id_zero(self):
        tool = get_tool("invoice.generate_pdf")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=0)

    def test_rejects_invoice_id_negative(self):
        tool = get_tool("invoice.generate_pdf")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=-1)

    def test_validate_catches_non_positive(self, ctx):
        tool = get_tool("invoice.generate_pdf")
        params = tool.parameters_schema.model_construct(invoice_id=0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_passes_good(self, ctx):
        tool = get_tool("invoice.generate_pdf")
        params = tool.parameters_schema(invoice_id=5)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


class TestInvoiceFinalizeParams:
    """invoice.finalize parameter schema edge cases."""

    def test_accepts_invoice_id(self):
        tool = get_tool("invoice.finalize")
        params = tool.parameters_schema(invoice_id=1)
        assert params.invoice_id == 1
        assert params.confirm is True

    def test_accepts_confirm_false(self):
        tool = get_tool("invoice.finalize")
        params = tool.parameters_schema(invoice_id=1, confirm=False)
        assert params.confirm is False

    def test_rejects_invoice_id_zero(self):
        tool = get_tool("invoice.finalize")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_id=0)

    def test_validate_catches_non_positive(self, ctx):
        tool = get_tool("invoice.finalize")
        params = tool.parameters_schema.model_construct(invoice_id=0)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0

    def test_validate_passes_good(self, ctx):
        tool = get_tool("invoice.finalize")
        params = tool.parameters_schema(invoice_id=5)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  InvoiceService execution — mocked service layer
#  The execute() methods import InvoiceService inside the function body,
#  so we patch at the source module where they are defined.
# ═══════════════════════════════════════════════════════════════════════════

class TestInvoiceDraftExecution:
    """invoice.draft execute() with mocked InvoiceService."""

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_draft_success(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.draft")

        mock_service = MagicMock()
        mock_service.create.return_value = _make_invoice_result(
            success=True, invoice_id=42, invoice_number="INV-042", status="draft",
        )
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(client_id=5, trip_id=10, amount=2500.0)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["invoice_id"] == 42
        assert result.data["invoice_number"] == "INV-042"
        assert result.data["status"] == "draft"
        assert result.message_key == "copilot.invoice.draft.success"

        # Verify service was called with correct args
        mock_service.create.assert_called_once()
        call_args = mock_service.create.call_args
        assert call_args.kwargs["user_id"] == 42
        # Verify the InvoiceCreate request
        request = call_args.args[0]
        assert request.client_id == 5
        assert request.trip_id == 10
        assert len(request.line_items) == 1
        assert request.line_items[0].unit_price == 2500.0

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_draft_with_due_date(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.draft")

        mock_service = MagicMock()
        mock_service.create.return_value = _make_invoice_result(
            success=True, invoice_id=1, invoice_number="INV-001", status="draft",
        )
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(
            client_id=1, trip_id=1, amount=100.0, due_date="2026-12-31",
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        request = mock_service.create.call_args.args[0]
        assert str(request.due_date) == "2026-12-31"

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_draft_service_failure(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.draft")

        mock_service = MagicMock()
        mock_service.create.return_value = _make_invoice_result(
            success=False, data_attr=False,
        )
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(client_id=1, trip_id=1, amount=100.0)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.service_error"

    def test_execute_draft_no_db(self, ctx):
        tool = get_tool("invoice.draft")
        params = tool.parameters_schema(client_id=1, trip_id=1, amount=100.0)
        result = asyncio.run(tool.execute(params, ctx))  # empty ctx

        assert result.status == "failed"
        assert result.message_key == "copilot.error.no_db"

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_draft_exception(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.draft")

        mock_service = MagicMock()
        mock_service.create.side_effect = RuntimeError("Service crashed")
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(client_id=1, trip_id=1, amount=100.0)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.internal"


class TestInvoiceGeneratePdfExecution:
    """invoice.generate_pdf execute() with mocked InvoiceService."""

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_generate_pdf_success(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.generate_pdf")

        mock_service = MagicMock()
        mock_service.generate_pdf.return_value = _make_invoice_result(
            success=True, invoice_id=1, pdf_path="/pdfs/inv-001.pdf",
        )
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["success"] is True
        assert result.data["file_path"] == "/pdfs/inv-001.pdf"
        assert result.message_key == "copilot.invoice.generate_pdf.success"
        mock_service.generate_pdf.assert_called_once_with(1)

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_generate_pdf_service_failure(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.generate_pdf")

        mock_service = MagicMock()
        mock_service.generate_pdf.return_value = _make_invoice_result(
            success=False, data_attr=False,
        )
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.service_error"

    def test_execute_generate_pdf_no_db(self, ctx):
        tool = get_tool("invoice.generate_pdf")
        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.no_db"

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_generate_pdf_exception(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.generate_pdf")

        mock_service = MagicMock()
        mock_service.generate_pdf.side_effect = RuntimeError("PDF generation failed")
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.internal"


class TestInvoiceFinalizeExecution:
    """invoice.finalize execute() with mocked InvoiceService."""

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_finalize_success(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.finalize")

        mock_service = MagicMock()
        mock_service.finalize.return_value = _make_invoice_result(
            success=True, invoice_id=1, invoice_number="INV-FINAL-001", status="finalized",
        )
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["invoice_number"] == "INV-FINAL-001"
        assert result.message_key == "copilot.invoice.finalize.success"
        mock_service.finalize.assert_called_once()

        # Verify the finalize request
        call_args = mock_service.finalize.call_args
        assert call_args.kwargs["user_id"] == 42
        request = call_args.args[0]
        assert request.invoice_id == 1
        assert request.send_email is False

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_finalize_service_failure(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.finalize")

        mock_service = MagicMock()
        mock_service.finalize.return_value = _make_invoice_result(
            success=False, data_attr=False,
        )
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.service_error"

    def test_execute_finalize_no_db(self, ctx):
        tool = get_tool("invoice.finalize")
        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.no_db"

    @patch("services.invoicing.service.InvoiceService")
    def test_execute_finalize_exception(self, MockInvoiceService, ctx):
        tool = get_tool("invoice.finalize")

        mock_service = MagicMock()
        mock_service.finalize.side_effect = RuntimeError("Finalize failed")
        MockInvoiceService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_id=1)
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.internal"
