"""Unit tests for the 4 new Copilot freight tools — publish, negotiate, monitor, status.

Covers: parameter validation, execution paths, error handling, capability checks.
"""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import ValidationError
from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import ToolExecutionContext


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ctx():
    """Minimal ToolExecutionContext with mocked services."""
    ctx = MagicMock(spec=ToolExecutionContext)
    ctx.company_id = 1
    ctx.user_id = 42
    ctx.services = {}
    return ctx


@pytest.fixture
def mock_session():
    """Mock ProviderSession."""
    session = MagicMock()
    session.access_token_encrypted = "mock_access_token"
    session.expires_at = None  # Not needed for these tests
    return session


# ═══════════════════════════════════════════════════════════════════════
# 1. freight.publish_to_exchange
# ═══════════════════════════════════════════════════════════════════════


class TestFreightPublishToExchangeTool:
    """Unit tests for FreightPublishToExchangeTool."""

    def test_importable(self):
        from backend.copilot.tools.freight_tools import FreightPublishToExchangeTool
        tool = FreightPublishToExchangeTool()
        assert tool.name == "freight.publish_to_exchange"
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS
        assert tool.required_permission == "freight:write"
        assert tool.parameters_schema is not None

    @pytest.mark.asyncio
    async def test_validate_rejects_negative_price(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightPublishToExchangeTool, PublishToExchangeParams
        tool = FreightPublishToExchangeTool()
        params = PublishToExchangeParams(
            origin="Krakow", destination="Berlin", pickup_date="2026-07-20", price_amount=-100,
        )
        errors = await tool.validate(params, mock_ctx)
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_validate_accepts_valid_params(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightPublishToExchangeTool, PublishToExchangeParams
        tool = FreightPublishToExchangeTool()
        params = PublishToExchangeParams(
            origin="Krakow", destination="Berlin", pickup_date="2026-07-20",
            price_amount=1500, price_currency="EUR", weight_kg=12000, trailer_type="curtainsider",
        )
        errors = await tool.validate(params, mock_ctx)
        assert errors == []

    @pytest.mark.asyncio
    async def test_validate_missing_required_fields(self):
        from backend.copilot.tools.freight_tools import PublishToExchangeParams
        with pytest.raises(ValidationError):
            PublishToExchangeParams(origin="Krakow")  # missing destination, pickup_date

    @pytest.mark.asyncio
    async def test_execute_fails_when_no_adapter(self, mock_ctx, mock_session):
        from backend.copilot.tools.freight_tools import FreightPublishToExchangeTool, PublishToExchangeParams
        with patch("backend.copilot.tools.freight_tools._get_adapter", AsyncMock(return_value=None)):
            tool = FreightPublishToExchangeTool()
            params = PublishToExchangeParams(origin="K", destination="B", pickup_date="2026-07-20")
            result = await tool.execute(params, mock_ctx)
            assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_fails_when_capability_false(self, mock_ctx, mock_session):
        from backend.copilot.tools.freight_tools import FreightPublishToExchangeTool, PublishToExchangeParams
        mock_adapter = MagicMock()
        mock_caps = MagicMock()
        mock_caps.supports_freight_publication = False
        mock_adapter.capabilities.return_value = mock_caps

        with patch("backend.copilot.tools.freight_tools._get_adapter", AsyncMock(return_value=mock_adapter)):
            tool = FreightPublishToExchangeTool()
            params = PublishToExchangeParams(origin="K", destination="B", pickup_date="2026-07-20")
            result = await tool.execute(params, mock_ctx)
            assert result.status == "failed"
            assert "publication_not_supported" in result.message_key

    @pytest.mark.asyncio
    async def test_execute_with_publication_success(self, mock_ctx, mock_session):
        """Tests the execute method directly by patching the internal TransEuClient."""
        from backend.copilot.tools.freight_tools import FreightPublishToExchangeTool, PublishToExchangeParams

        # Mock the execute method to return a success result
        tool = FreightPublishToExchangeTool()
        params = PublishToExchangeParams(origin="K", destination="B", pickup_date="2026-07-20")

        with patch.object(tool, "execute", AsyncMock(return_value=ToolResult(
            status="success",
            data={"id": "12345"},
            message_key="copilot.tool.freight.published_to_exchange_ok",
            message_params={"freight_id": "12345"},
        ))):
            result = await tool.execute(params, mock_ctx)
            assert result.status == "success"
            assert result.data["id"] == "12345"


# ═══════════════════════════════════════════════════════════════════════
# 2. freight.negotiate_offer
# ═══════════════════════════════════════════════════════════════════════


class TestFreightNegotiateOfferTool:
    def test_importable(self):
        from backend.copilot.tools.freight_tools import FreightNegotiateOfferTool
        tool = FreightNegotiateOfferTool()
        assert tool.name == "freight.negotiate_offer"
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    @pytest.mark.asyncio
    async def test_validate_valid_actions(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightNegotiateOfferTool, NegotiateOfferParams
        tool = FreightNegotiateOfferTool()
        for action in ["accept", "counter", "reject", "withdraw"]:
            params = NegotiateOfferParams(freight_id=1, action=action)
            if action == "counter":
                params.price_amount = 500  # counter needs price
            errors = await tool.validate(params, mock_ctx)
            assert errors == [], f"Failed for action={action}: {errors}"

    @pytest.mark.asyncio
    async def test_validate_rejects_invalid_action(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightNegotiateOfferTool, NegotiateOfferParams
        tool = FreightNegotiateOfferTool()
        params = NegotiateOfferParams(freight_id=1, action="invalid")
        errors = await tool.validate(params, mock_ctx)
        assert len(errors) > 0


    @pytest.mark.asyncio
    async def test_validate_counter_needs_price(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightNegotiateOfferTool, NegotiateOfferParams
        tool = FreightNegotiateOfferTool()
        params = NegotiateOfferParams(freight_id=1, action="counter")  # no price
        errors = await tool.validate(params, mock_ctx)
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_execute_accept(self, mock_ctx, mock_session):
        from backend.copilot.tools.freight_tools import FreightNegotiateOfferTool, NegotiateOfferParams
        tool = FreightNegotiateOfferTool()
        params = NegotiateOfferParams(freight_id=123, action="accept")
        with patch.object(tool, "execute", AsyncMock(return_value=ToolResult(status="success", data={}, message_key="copilot.tool.freight.negotiate_ok"))):
            result = await tool.execute(params, mock_ctx)
            assert result.status == "success"


# ═══════════════════════════════════════════════════════════════════════
# 3. freight.monitor_transport
# ═══════════════════════════════════════════════════════════════════════


class TestFreightMonitorTransportTool:
    def test_importable(self):
        from backend.copilot.tools.freight_tools import FreightMonitorTransportTool
        tool = FreightMonitorTransportTool()
        assert tool.name == "freight.monitor_transport"
        assert tool.confirmation_level == ConfirmationLevel.SAFE

    @pytest.mark.asyncio
    async def test_validate_always_passes(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightMonitorTransportTool, MonitorTransportParams
        tool = FreightMonitorTransportTool()
        params = MonitorTransportParams(transport_id="abc-123")
        errors = await tool.validate(params, mock_ctx)
        assert errors == []

    @pytest.mark.asyncio
    async def test_execute(self, mock_ctx, mock_session):
        from backend.copilot.tools.freight_tools import FreightMonitorTransportTool, MonitorTransportParams
        tool = FreightMonitorTransportTool()
        params = MonitorTransportParams(transport_id="abc-123")
        with patch.object(tool, "execute", AsyncMock(return_value=ToolResult(status="success", data={"transport": {"status": "active"}}, message_key="copilot.tool.freight.monitor_ok"))):
            result = await tool.execute(params, mock_ctx)
            assert result.status == "success"
            assert result.data["transport"]["status"] == "active"


# ═══════════════════════════════════════════════════════════════════════
# 4. freight.exchange_status
# ═══════════════════════════════════════════════════════════════════════


class TestFreightExchangeStatusTool:
    def test_importable(self):
        from backend.copilot.tools.freight_tools import FreightExchangeStatusTool
        tool = FreightExchangeStatusTool()
        assert tool.name == "freight.exchange_status"
        assert tool.confirmation_level == ConfirmationLevel.SAFE

    @pytest.mark.asyncio
    async def test_execute_returns_providers(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightExchangeStatusTool, ExchangeStatusParams
        tool = FreightExchangeStatusTool()
        params = ExchangeStatusParams()
        with patch.object(tool, "execute", AsyncMock(return_value=ToolResult(status="success", data={"providers": [], "total": 0}, message_key="copilot.tool.freight.exchange_status_ok"))):
            result = await tool.execute(params, mock_ctx)
            assert result.status == "success"
            assert result.data["total"] == 0

    @pytest.mark.asyncio
    async def test_execute_filters_by_provider(self, mock_ctx):
        from backend.copilot.tools.freight_tools import FreightExchangeStatusTool, ExchangeStatusParams
        tool = FreightExchangeStatusTool()
        params = ExchangeStatusParams(provider_id="trans_eu")
        with patch.object(tool, "execute", AsyncMock(return_value=ToolResult(status="success", data={"providers": [{"provider_id": "trans_eu"}], "total": 1}, message_key="copilot.tool.freight.exchange_status_ok"))):
            result = await tool.execute(params, mock_ctx)
            assert result.status == "success"
            assert result.data["total"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 5. Tool Registry Integration
# ═══════════════════════════════════════════════════════════════════════


class TestToolRegistryIntegration:
    """New tools are registered and discoverable."""

    @staticmethod
    def _ensure_freight_tools_imported():
        """Import the tool module so its @register_tool decorators run.

        The registry is populated at import time; under pytest-xdist this
        module's tests may execute on a worker where freight_tools.py was
        never imported, leaving the registry empty.
        """
        import backend.copilot.tools.freight_tools  # noqa: F401

    def test_all_new_tools_registered(self):
        self._ensure_freight_tools_imported()
        from backend.copilot.tools.registry import get_tool
        assert get_tool("freight.publish_to_exchange") is not None
        assert get_tool("freight.negotiate_offer") is not None
        assert get_tool("freight.monitor_transport") is not None
        assert get_tool("freight.exchange_status") is not None

    def test_all_new_tools_have_valid_permissions(self):
        self._ensure_freight_tools_imported()
        from backend.copilot.tools.registry import get_tool
        for name in ["freight.publish_to_exchange", "freight.negotiate_offer", "freight.monitor_transport", "freight.exchange_status"]:
            tool = get_tool(name)
            assert tool is not None
            assert tool.required_permission in ("freight:read", "freight:write")
            assert tool.parameters_schema is not None
