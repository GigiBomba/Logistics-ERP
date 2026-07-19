"""Comprehensive unit tests for payment.* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance
- Tool execution with mocked PaymentBatchService
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


def _make_batch_result(
    success: bool = True,
    batch_id: int = 1,
    file_path: str = "/exports/payments/batch_001.csv",
    row_count: int = 10,
    total_amount: float = 15000.0,
    currency: str = "EUR",
) -> MagicMock:
    """Build a mock PaymentBatchService result."""
    result = MagicMock()
    result.success = success
    result.errors = [] if success else [MagicMock(message="Batch error")]

    mock_data = MagicMock()
    mock_data.batch_id = batch_id
    mock_data.file_path = file_path
    mock_data.row_count = row_count
    mock_data.total_amount = total_amount
    mock_data.currency = currency
    result.data = mock_data

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract
# ═══════════════════════════════════════════════════════════════════════════

PAYMENT_TOOL_NAMES = [
    "payment.generate_bulk_csv",
]


class TestPaymentToolContract:
    """The payment tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()
        assert tool.required_permission == "payments:write"

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_tool_confirmation_level(self, name):
        tool = get_tool(name)
        assert tool.confirmation_level == ConfirmationLevel.INFORMATIONAL

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_supports_undo_false(self, name):
        tool = get_tool(name)
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx):
        tool = get_tool(name)
        params = tool.parameters_schema(invoice_ids=[1, 2])
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", PAYMENT_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx):
        tool = get_tool(name)
        params = tool.parameters_schema(invoice_ids=[1, 2])
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════

class TestGenerateBulkCsvParams:
    """payment.generate_bulk_csv parameter schema edge cases."""

    def test_accepts_invoice_ids_only(self):
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(invoice_ids=[1, 2, 3])
        assert params.invoice_ids == [1, 2, 3]
        assert params.driver_ids == []
        assert params.bank_profile_id is None

    def test_accepts_driver_ids(self):
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(
            invoice_ids=[1],
            driver_ids=[10, 20],
        )
        assert params.driver_ids == [10, 20]

    def test_accepts_bank_profile_id(self):
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(
            invoice_ids=[1],
            bank_profile_id=5,
        )
        assert params.bank_profile_id == 5

    def test_rejects_empty_invoice_ids(self):
        tool = get_tool("payment.generate_bulk_csv")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_ids=[])

    def test_rejects_extra_fields(self):
        """ConfigDict(extra='forbid') — extra fields are rejected."""
        tool = get_tool("payment.generate_bulk_csv")
        with pytest.raises(ValidationError):
            tool.parameters_schema(invoice_ids=[1], extra_field="x")

    def test_validate_no_invoice_or_driver_ids(self, ctx):
        """validate() catches when both invoice_ids and driver_ids are empty."""
        tool = get_tool("payment.generate_bulk_csv")
        # Use model_construct to bypass Pydantic min_length=1
        params = tool.parameters_schema.model_construct(
            invoice_ids=[], driver_ids=[], bank_profile_id=None,
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("invoice_id" in e or "recipient" in e for e in errors)

    def test_validate_catches_too_many_ids(self, ctx):
        """validate() catches when total count exceeds 500."""
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(
            invoice_ids=list(range(1, 501)),
            driver_ids=[501],
        )
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("500" in e or "Maximum" in e for e in errors)

    def test_validate_passes_valid(self, ctx):
        """validate() returns [] for valid params."""
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(invoice_ids=[1, 2, 3])
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0

    def test_validate_passes_driver_ids_only(self, ctx):
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(invoice_ids=[1], driver_ids=[10])
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0

    def test_validate_passes_bank_profile(self, ctx):
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(invoice_ids=[1], bank_profile_id=3)
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  PaymentBatchService execution — mocked service layer
#  The execute() method imports PaymentBatchService inside the function body,
#  so we patch at the source module where it is defined.
# ═══════════════════════════════════════════════════════════════════════════

class TestGenerateBulkCsvExecution:
    """payment.generate_bulk_csv execute() with mocked PaymentBatchService."""

    @patch("backend.services.payment_batch_service.PaymentBatchService")
    def test_execute_bulk_csv_success(self, MockBatchService, ctx):
        tool = get_tool("payment.generate_bulk_csv")

        mock_service = MagicMock()
        mock_service.generate_batch.return_value = _make_batch_result(
            success=True,
            batch_id=42,
            file_path="/exports/batch_042.csv",
            row_count=15,
            total_amount=22500.0,
            currency="EUR",
        )
        MockBatchService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(
            invoice_ids=[1, 2, 3],
            driver_ids=[10],
            bank_profile_id=5,
        )
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["batch_id"] == 42
        assert result.data["file_path"] == "/exports/batch_042.csv"
        assert result.data["row_count"] == 15
        assert result.data["total_amount"] == 22500.0
        assert result.data["currency"] == "EUR"
        assert result.message_key == "copilot.payment.bulk_csv_ok"
        assert result.message_params["count"] == 15

        # Verify service was called with correct args
        mock_service.generate_batch.assert_called_once()
        call_args = mock_service.generate_batch.call_args
        assert call_args.kwargs["user_id"] == 42
        request = call_args.args[0]
        assert request.profile_id == 5
        assert request.invoice_ids == [1, 2, 3]
        assert request.driver_ids == [10]

    @patch("backend.services.payment_batch_service.PaymentBatchService")
    def test_execute_bulk_csv_without_bank_profile(self, MockBatchService, ctx):
        """bank_profile_id=None defaults to profile_id=0."""
        tool = get_tool("payment.generate_bulk_csv")

        mock_service = MagicMock()
        mock_service.generate_batch.return_value = _make_batch_result(success=True)
        MockBatchService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_ids=[1])
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        request = mock_service.generate_batch.call_args.args[0]
        assert request.profile_id == 0  # default when bank_profile_id is None

    @patch("backend.services.payment_batch_service.PaymentBatchService")
    def test_execute_bulk_csv_service_failure(self, MockBatchService, ctx):
        tool = get_tool("payment.generate_bulk_csv")

        mock_service = MagicMock()
        mock_service.generate_batch.return_value = _make_batch_result(success=False)
        MockBatchService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_ids=[1])
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.payment.bulk_csv_failed"

    @patch("backend.services.payment_batch_service.PaymentBatchService")
    def test_execute_bulk_csv_no_data(self, MockBatchService, ctx):
        """When result.data is None, default values should be used."""
        tool = get_tool("payment.generate_bulk_csv")

        mock_service = MagicMock()
        result_no_data = MagicMock()
        result_no_data.success = True
        result_no_data.errors = []
        result_no_data.data = None
        mock_service.generate_batch.return_value = result_no_data
        MockBatchService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_ids=[1])
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["batch_id"] is None
        assert result.data["file_path"] is None
        assert result.data["row_count"] == 0
        assert result.data["total_amount"] == 0.0
        assert result.data["currency"] == "EUR"

    def test_execute_no_db(self, ctx):
        tool = get_tool("payment.generate_bulk_csv")
        params = tool.parameters_schema(invoice_ids=[1])
        result = asyncio.run(tool.execute(params, ctx))  # empty ctx

        assert result.status == "unavailable"
        assert result.message_key == "copilot.error.no_db"

    @patch("backend.services.payment_batch_service.PaymentBatchService")
    def test_execute_exception(self, MockBatchService, ctx):
        tool = get_tool("payment.generate_bulk_csv")

        mock_service = MagicMock()
        mock_service.generate_batch.side_effect = RuntimeError("CSV generation crashed")
        MockBatchService.return_value = mock_service
        ctx.services["db"] = MagicMock()

        params = tool.parameters_schema(invoice_ids=[1])
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.error.unexpected"
