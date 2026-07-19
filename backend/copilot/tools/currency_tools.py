"""Level-0 Co-Pilot tools for the Currency domain.

Read-only currency exchange rate and conversion tools exposed as
AI-callable capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, List

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Parameters schemas ──────────────────────────────────────────────────────

class CurrencyGetRateParams(BaseModel):
    """Parameters for currency.get_rate."""
    code: str = Field(
        ..., min_length=1, max_length=10,
        description="Currency code (e.g. USD, RON, EUR)",
    )


class CurrencyConvertParams(BaseModel):
    """Parameters for currency.convert."""
    amount: float = Field(..., gt=0, description="Monetary amount to convert")
    from_currency: str = Field(
        ..., min_length=1, max_length=10,
        description="Source currency code (e.g. USD, EUR)",
    )
    to_currency: str = Field(
        ..., min_length=1, max_length=10,
        description="Target currency code (e.g. RON, GBP)",
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_currency_service() -> Any:
    """Return a CurrencyService instance.

    CurrencyService accepts an optional ``exchange_service`` parameter and
    defaults to ``ExchangeRateService()`` (which is a singleton via ``__new__``).
    """
    from services.currency_service import CurrencyService
    return CurrencyService()


# ── Tool implementations ────────────────────────────────────────────────────

@register_tool
class CurrencyGetRateTool(BaseTool):
    """Get the current exchange rate for a currency code relative to EUR.

    Returns the rate (float) indicating how much of the base currency (EUR)
    equals one unit of the requested currency.
    """

    name = "currency.get_rate"
    tool_version = "1.0.0"
    description = "Get exchange rate for a currency code vs EUR"
    required_permission = "currency:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = CurrencyGetRateParams

    async def validate(self, params: CurrencyGetRateParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: CurrencyGetRateParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            service = _get_currency_service()
            rate = service.get_rate(code=params.code.upper())

            return ToolResult(
                status="success",
                data={"rate": rate},
                message_key="copilot.tool.currency.get_rate_ok",
                message_params={"code": params.code.upper(), "rate": rate},
            )

        except Exception as exc:
            logger.exception("currency.get_rate failed: %s", exc)
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.currency.get_rate_failed",
                message_params={"code": params.code, "error": str(exc)},
            )


@register_tool
class CurrencyConvertTool(BaseTool):
    """Convert an amount from one currency to another.

    Uses live exchange rates relative to EUR. Both from_currency and
    to_currency must be valid ISO 4217 codes supported by the system.
    """

    name = "currency.convert"
    tool_version = "1.0.0"
    description = "Convert an amount from one currency to another"
    required_permission = "currency:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = CurrencyConvertParams

    async def validate(self, params: CurrencyConvertParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        if params.from_currency.upper() == params.to_currency.upper():
            errors.append("from_currency and to_currency must be different")
        return errors

    async def execute(self, params: CurrencyConvertParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            service = _get_currency_service()
            converted_amount = service.convert(
                amount=params.amount,
                from_currency=params.from_currency.upper(),
                to_currency=params.to_currency.upper(),
            )

            return ToolResult(
                status="success",
                data={"converted_amount": converted_amount},
                message_key="copilot.tool.currency.convert_ok",
                message_params={
                    "amount": params.amount,
                    "from": params.from_currency.upper(),
                    "to": params.to_currency.upper(),
                    "converted_amount": converted_amount,
                },
            )

        except Exception as exc:
            logger.exception("currency.convert failed: %s", exc)
            return ToolResult(
                status="failed",
                data=None,
                message_key="copilot.tool.currency.convert_failed",
                message_params={
                    "amount": params.amount,
                    "from": params.from_currency,
                    "to": params.to_currency,
                    "error": str(exc),
                },
            )
