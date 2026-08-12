"""Co-Pilot tools for the Analytics domain — domain-routed query facade.
Blueprint: §9.1 — Analytics, Level 0.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool


# ── Parameters ──────────────────────────────────────────────────────────────


class AnalyticsQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = Field(
        ...,
        description=(
            "Analytics domain to query. One of: "
            "financial, fleet, driver, client, route_profitability, trip_status, "
            "cost_breakdown, monthly_volume, revenue_quarterly, maintenance, "
            "truck_utilization, invoice_aging, overdue, summary."
        ),
    )
    date_from: Optional[str] = Field(None, description="Start date (YYYY-MM-DD).")
    date_to: Optional[str] = Field(None, description="End date (YYYY-MM-DD).")
    months: Optional[int] = Field(None, description="Number of months for time-series queries.", ge=1)
    quarters: Optional[int] = Field(None, description="Number of quarters for quarterly queries.", ge=1)
    limit: Optional[int] = Field(None, description="Result limit for queries that support it.", ge=1)
    source_provider: Optional[str] = Field(
        None,
        description="Filter results by source provider ID (e.g. 'trans_eu', 'timocom'). "
                    "Use 'freight_exchange' for all exchange-sourced trips, or omit for all.",
    )


# ── Valid domain set ────────────────────────────────────────────────────────

VALID_DOMAINS: frozenset = frozenset({
    "financial",
    "fleet",
    "driver",
    "client",
    "route_profitability",
    "trip_status",
    "cost_breakdown",
    "monthly_volume",
    "revenue_quarterly",
    "maintenance",
    "truck_utilization",
    "invoice_aging",
    "overdue",
    "summary",
})


# ── Tool: analytics.query ───────────────────────────────────────────────────


@register_tool
class AnalyticsQueryTool(BaseTool):
    name = "analytics.query"
    tool_version = "1.0.0"
    description = (
        "Query analytics data across multiple domains (financial, fleet, driver, "
        "client, route profitability, etc.). Use the `domain` parameter to select "
        "the analytics category and optional date/months/quarters/limit/source_provider filters."
    )
    required_permission = "analytics:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = AnalyticsQueryParams

    async def validate(self, params: AnalyticsQueryParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        if params.domain not in VALID_DOMAINS:
            errors.append(f"copilot.error.unknown_analytics_domain:{params.domain}")
        return errors

    async def execute(self, params: AnalyticsQueryParams, ctx: ToolExecutionContext) -> ToolResult:
        if params.domain not in VALID_DOMAINS:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unknown_analytics_domain",
                message_params={"domain": params.domain},
            )

        try:
            from backend.services.analytics_service import AnalyticsService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": "Database service not available"},
                )

            service = AnalyticsService(db)
            data = self._route(service, params)

            return ToolResult(
                status="success",
                data={"data": data},
                message_key="copilot.step.analytics_query_done",
                message_params={"domain": params.domain},
            )
        except Exception as e:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(e)},
            )

    # ── Domain routing ───────────────────────────────────────────────────

    def _route(self, service, params: AnalyticsQueryParams) -> Any:
        """Dispatch to the correct AnalyticsService method based on domain."""
        domain = params.domain
        date_from = params.date_from
        date_to = params.date_to
        months = params.months
        quarters = params.quarters
        limit = params.limit
        source_provider = params.source_provider

        if domain == "financial":
            return service.get_financial(date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "fleet":
            return service.get_fleet(date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "driver":
            return service.get_driver(date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "client":
            return service.get_client_analytics(date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "route_profitability":
            return service.get_route_profitability(date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "trip_status":
            return service.get_trip_status_distribution(date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "cost_breakdown":
            return service.get_cost_breakdown(months=months or 12, date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "monthly_volume":
            return service.get_monthly_trip_volume(months=months or 12, date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "revenue_quarterly":
            return service.get_revenue_quarterly(quarters=quarters or 8, date_from=date_from, date_to=date_to, source_provider=source_provider)
        elif domain == "maintenance":
            return service.get_maintenance_alerts()
        elif domain == "truck_utilization":
            return service.get_truck_utilization()
        elif domain == "invoice_aging":
            return service.get_invoice_aging()
        elif domain == "overdue":
            alerts, total_amount = service.get_overdue_data()
            return {"alerts": alerts, "total_overdue_amount": total_amount}
        elif domain == "summary":
            return service.get_data(date_from=date_from, date_to=date_to, source_provider=source_provider)

        # Should never reach here due to validate() guard
        raise ValueError(f"Unknown analytics domain: {domain}")
