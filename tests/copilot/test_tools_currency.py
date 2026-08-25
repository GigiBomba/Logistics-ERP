"""Comprehensive unit tests for currency.* Co-Pilot tools.

Tests cover:
- BaseTool contract compliance for both currency tools
- Tool execution with mocked CurrencyService
- Parameter schema validation (Pydantic level)
- Tool-level validate() logic
- Error handling (service failure, exceptions)

Blueprint: §9 — Registry enforcement.
"""
from __future__ import annotations


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


# ═══════════════════════════════════════════════════════════════════════════
#  BaseTool contract — both currency tools
# ═══════════════════════════════════════════════════════════════════════════

CURRENCY_TOOL_NAMES = [
    "currency.get_rate",
    "currency.convert",
]


class TestCurrencyToolContract:
    """Every currency tool must satisfy the BaseTool contract."""

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_registered(self, name):
        tool = get_tool(name)
        assert tool is not None, f"Tool '{name}' not found in registry"

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_has_name(self, name):
        tool = get_tool(name)
        assert tool.name == name

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_has_semver_version(self, name):
        tool = get_tool(name)
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", tool.tool_version)

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_has_description(self, name):
        tool = get_tool(name)
        assert tool.description and tool.description.strip()

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_has_permission(self, name):
        tool = get_tool(name)
        assert tool.required_permission and tool.required_permission.strip()
        assert tool.required_permission == "currency:read"

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_has_parameters_schema(self, name):
        tool = get_tool(name)
        from pydantic import BaseModel
        assert issubclass(tool.parameters_schema, BaseModel)

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_not_deprecated(self, name):
        tool = get_tool(name)
        assert not tool.deprecated

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_confirmation_level(self, name):
        tool = get_tool(name)
        assert tool.confirmation_level == ConfirmationLevel.SAFE

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_tool_supports_undo_correct(self, name):
        tool = get_tool(name)
        assert tool.supports_undo is False

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_validate_returns_list(self, name, ctx):
        tool = get_tool(name)
        if name == "currency.get_rate":
            params = tool.parameters_schema(code="USD")
        elif name == "currency.convert":
            params = tool.parameters_schema(amount=100, from_currency="USD", to_currency="EUR")
        else:
            params = tool.parameters_schema()
        errors = asyncio.run(tool.validate(params, ctx))
        assert isinstance(errors, list)

    @pytest.mark.parametrize("name", CURRENCY_TOOL_NAMES)
    def test_execute_returns_tool_result(self, name, ctx):
        tool = get_tool(name)
        if name == "currency.get_rate":
            params = tool.parameters_schema(code="USD")
        elif name == "currency.convert":
            params = tool.parameters_schema(amount=100, from_currency="USD", to_currency="EUR")
        else:
            params = tool.parameters_schema()
        result = asyncio.run(tool.execute(params, ctx))
        assert isinstance(result, ToolResult)
        assert result.status in ("success", "failed", "unavailable", "permission_denied", "needs_confirmation")
        assert result.message_key and result.message_key.strip()


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter schema validation
# ═══════════════════════════════════════════════════════════════════════════


class TestCurrencyGetRateParams:
    """currency.get_rate parameter schema edge cases."""

    def test_accepts_valid_code(self):
        tool = get_tool("currency.get_rate")
        params = tool.parameters_schema(code="USD")
        assert params.code == "USD"

    def test_accepts_lowercase(self):
        tool = get_tool("currency.get_rate")
        params = tool.parameters_schema(code="eur")
        assert params.code == "eur"

    def test_rejects_empty_code(self):
        tool = get_tool("currency.get_rate")
        with pytest.raises(ValidationError):
            tool.parameters_schema(code="")

    def test_validate_always_empty(self, ctx):
        tool = get_tool("currency.get_rate")
        params = tool.parameters_schema(code="GBP")
        errors = asyncio.run(tool.validate(params, ctx))
        assert errors == []


class TestCurrencyConvertParams:
    """currency.convert parameter schema edge cases."""

    def test_accepts_valid_params(self):
        tool = get_tool("currency.convert")
        params = tool.parameters_schema(amount=100.50, from_currency="USD", to_currency="EUR")
        assert params.amount == 100.50
        assert params.from_currency == "USD"
        assert params.to_currency == "EUR"

    def test_rejects_zero_amount(self):
        tool = get_tool("currency.convert")
        with pytest.raises(ValidationError):
            tool.parameters_schema(amount=0, from_currency="USD", to_currency="EUR")

    def test_rejects_negative_amount(self):
        tool = get_tool("currency.convert")
        with pytest.raises(ValidationError):
            tool.parameters_schema(amount=-10, from_currency="USD", to_currency="EUR")

    def test_rejects_empty_from_currency(self):
        tool = get_tool("currency.convert")
        with pytest.raises(ValidationError):
            tool.parameters_schema(amount=100, from_currency="", to_currency="EUR")

    def test_rejects_empty_to_currency(self):
        tool = get_tool("currency.convert")
        with pytest.raises(ValidationError):
            tool.parameters_schema(amount=100, from_currency="USD", to_currency="")

    def test_validate_rejects_same_currency(self, ctx):
        tool = get_tool("currency.convert")
        params = tool.parameters_schema(amount=100, from_currency="USD", to_currency="usd")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) > 0
        assert any("different" in e.lower() for e in errors)

    def test_validate_accepts_different_currencies(self, ctx):
        tool = get_tool("currency.convert")
        params = tool.parameters_schema(amount=100, from_currency="USD", to_currency="EUR")
        errors = asyncio.run(tool.validate(params, ctx))
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Execution — mocked CurrencyService
#  Currency tools use _get_currency_service() helper which creates CurrencyService
#  directly, so we patch CurrencyService at its source.
# ═══════════════════════════════════════════════════════════════════════════


class TestCurrencyGetRateExecution:
    """currency.get_rate execute() with mocked CurrencyService."""

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_success(self, MockGetService, ctx):
        """Successful rate lookup."""
        tool = get_tool("currency.get_rate")

        mock_service = MagicMock()
        mock_service.get_rate.return_value = 0.92  # 1 USD = 0.92 EUR
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(code="USD")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["rate"] == 0.92
        assert result.message_key == "copilot.tool.currency.get_rate_ok"
        mock_service.get_rate.assert_called_once_with(code="USD")

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_uppercases_code(self, MockGetService, ctx):
        """Code is uppercased before calling service."""
        tool = get_tool("currency.get_rate")

        mock_service = MagicMock()
        mock_service.get_rate.return_value = 4.97
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(code="ron")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        mock_service.get_rate.assert_called_once_with(code="RON")

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_service_failure(self, MockGetService, ctx):
        """Service exception is caught and returned as failed."""
        tool = get_tool("currency.get_rate")

        mock_service = MagicMock()
        mock_service.get_rate.side_effect = ValueError("Unknown currency: XYZ")
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(code="XYZ")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.currency.get_rate_failed"

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_exception(self, MockGetService, ctx):
        """Generic exception is caught."""
        tool = get_tool("currency.get_rate")

        mock_service = MagicMock()
        mock_service.get_rate.side_effect = RuntimeError("Service unavailable")
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(code="USD")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"


class TestCurrencyConvertExecution:
    """currency.convert execute() with mocked CurrencyService."""

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_success(self, MockGetService, ctx):
        """Successful conversion."""
        tool = get_tool("currency.convert")

        mock_service = MagicMock()
        mock_service.convert.return_value = 85.00  # 100 USD -> 85 EUR
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(amount=100, from_currency="USD", to_currency="EUR")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        assert result.data["converted_amount"] == 85.00
        assert result.message_key == "copilot.tool.currency.convert_ok"
        mock_service.convert.assert_called_once_with(
            amount=100, from_currency="USD", to_currency="EUR",
        )

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_uppercases_currencies(self, MockGetService, ctx):
        """Currency codes are uppercased before calling service."""
        tool = get_tool("currency.convert")

        mock_service = MagicMock()
        mock_service.convert.return_value = 497.0
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(amount=100, from_currency="eur", to_currency="ron")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "success"
        mock_service.convert.assert_called_once_with(
            amount=100, from_currency="EUR", to_currency="RON",
        )

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_service_failure(self, MockGetService, ctx):
        """Service exception is caught and returned as failed."""
        tool = get_tool("currency.convert")

        mock_service = MagicMock()
        mock_service.convert.side_effect = ValueError("Conversion rate not found")
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(amount=100, from_currency="GBP", to_currency="XYZ")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.currency.convert_failed"

    @patch("backend.copilot.tools.currency_tools._get_currency_service")
    def test_execute_exception(self, MockGetService, ctx):
        """Generic exception is caught."""
        tool = get_tool("currency.convert")

        mock_service = MagicMock()
        mock_service.convert.side_effect = RuntimeError("Rate provider down")
        MockGetService.return_value = mock_service

        params = tool.parameters_schema(amount=100, from_currency="USD", to_currency="EUR")
        result = asyncio.run(tool.execute(params, ctx))

        assert result.status == "failed"
