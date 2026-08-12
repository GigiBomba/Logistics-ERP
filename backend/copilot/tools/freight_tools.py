"""Freight Exchange tools — wrap the provider-agnostic freight exchange subsystem.

Blueprint: §17 — Freight Exchange Integration (Co-Pilot Tool Wrapping Only).
Built provider-agnostic — provider_id is optional on each tool.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Helper: get services from context (or build on demand) ───────────────────

async def _get_search_engine(ctx):
    """Get or create a SearchEngineService from context."""
    svc = ctx.services.get("search_engine")
    if svc:
        return svc
    db = ctx.services.get("db")
    if db is None:
        return None
    from services.freight_exchange.search import SearchEngineService
    return SearchEngineService(db, cache=ctx.services.get("cache"))


async def _get_evaluation_engine(ctx):
    """Get or create an EvaluationEngineService from context."""
    svc = ctx.services.get("evaluation_engine")
    if svc:
        return svc
    db = ctx.services.get("db")
    if db is None:
        return None
    from services.freight_exchange.evaluation import EvaluationEngineService
    return EvaluationEngineService(db)


async def _get_fleet_matcher(ctx):
    """Get or create a FleetMatcherService from context."""
    svc = ctx.services.get("fleet_matcher")
    if svc:
        return svc
    db = ctx.services.get("db")
    if db is None:
        return None
    from services.freight_exchange.fleet_matcher import FleetMatcherService
    return FleetMatcherService(db)


async def _get_import_pipeline(ctx):
    """Get or create an ImportPipelineService from context."""
    svc = ctx.services.get("import_pipeline")
    if svc:
        return svc
    db = ctx.services.get("db")
    if db is None:
        return None
    from services.freight_exchange.import_pipeline import ImportPipelineService
    return ImportPipelineService(db)


async def _get_conn_mgr(ctx):
    """Get ConnectionManagerService for listing providers."""
    svc = ctx.services.get("connection_manager")
    if svc:
        return svc
    db = ctx.services.get("db")
    if db is None:
        return None
    from services.freight_exchange.connection_manager import ConnectionManagerService
    return ConnectionManagerService(db)


# ── Helper: build LoadSearchFilters from simple params ──────────────────────

def _build_search_filters(
    origin: str,
    destination: str = "",
    pickup_date: str = "",
    load_type: str = "",
    weight_kg: Optional[float] = None,
) -> Any:
    """Build a ``LoadSearchFilters`` instance from simple tool parameters.

    Fields that have no direct analogue in the model (e.g. ``length_m``)
    are intentionally omitted — they are not yet supported by the search
    engine filters.
    """
    from models.freight_exchange_models import GeoFilter, LoadSearchFilters

    # Date defaults: today → today + 7 days
    today = date.today()
    if pickup_date:
        try:
            dt = date.fromisoformat(pickup_date)
            pickup_from = dt
            pickup_to = dt
        except (ValueError, TypeError):
            pickup_from = today
            pickup_to = today + timedelta(days=7)
    else:
        pickup_from = today
        pickup_to = today + timedelta(days=7)

    filters = LoadSearchFilters(
        origin=GeoFilter(location=origin, radius_km=50.0) if origin else None,
        destination=GeoFilter(location=destination, radius_km=30.0) if destination else None,
        pickup_date_from=pickup_from,
        pickup_date_to=pickup_to,
        weight_kg_max=weight_kg,
    )

    if load_type:
        lt = load_type.strip().lower()
        if lt in ("ftl", "ltl"):
            filters.loading_type = lt
        else:
            filters.loading_type_list = [lt]

    return filters


# ═════════════════════════════════════════════════════════════════════════════
# Parameter Schemas
# ═════════════════════════════════════════════════════════════════════════════


class SearchLoadsParams(BaseModel):
    """Parameters for ``freight.search_loads``."""

    origin: str = Field(..., description="Loading place (city or address)")
    destination: str = Field("", description="Unloading place (city or address)")
    pickup_date: str = Field("", description="Pickup date (ISO 8601, e.g. 2026-07-20). "
                               "Defaults to today if empty.")
    load_type: str = Field("", description="Loading type — 'ftl', 'ltl', or empty (any)")
    weight_kg: Optional[float] = Field(None, ge=0, description="Maximum load weight in kg")
    length_m: Optional[float] = Field(None, ge=0,
                                       description="Maximum load length in metres (not yet supported as a filter)")
    provider_ids: Optional[List[str]] = Field(None, description="Specific provider IDs to search. "
                                               "If omitted, searches all connected providers.")
    max_results: int = Field(25, ge=1, le=500, description="Maximum number of results to return")


class GetLoadParams(BaseModel):
    """Parameters for ``freight.get_load``."""

    provider_id: str = Field(..., description="Provider ID (e.g. 'timocom', 'teleroute')")
    provider_load_id: str = Field(..., description="Provider-specific load identifier")


class SaveSearchParams(BaseModel):
    """Parameters for ``freight.save_search``."""

    origin: str = Field(..., description="Loading place (city or address)")
    destination: str = Field("", description="Unloading place (city or address)")
    pickup_date: str = Field("", description="Pickup date (ISO 8601)")
    load_type: str = Field("", description="Loading type — 'ftl', 'ltl', or empty (any)")
    weight_kg: Optional[float] = Field(None, ge=0, description="Maximum load weight in kg")
    length_m: Optional[float] = Field(None, ge=0, description="Maximum load length in metres")
    provider_ids: Optional[List[str]] = Field(None, description="Provider IDs to include in the saved search")
    label: str = Field(..., min_length=1, max_length=200, description="Human-readable label for the saved search")


class RefreshSearchParams(BaseModel):
    """Parameters for ``freight.refresh_search``."""

    saved_search_id: str = Field(..., description="Saved search ID to re-run")


class EvaluateLoadParams(BaseModel):
    """Parameters for ``freight.evaluate_load``."""

    provider_id: str = Field(..., description="Provider ID (e.g. 'timocom', 'teleroute')")
    provider_load_id: str = Field(..., description="Provider-specific load identifier")
    vehicle_id: Optional[int] = Field(None, gt=0, description="Optional vehicle ID for compatibility check")


class FindBestTrucksParams(BaseModel):
    """Parameters for ``freight.find_best_trucks``."""

    provider_id: str = Field(..., description="Provider ID (e.g. 'timocom', 'teleroute')")
    provider_load_id: str = Field(..., description="Provider-specific load identifier")
    top_n: int = Field(5, ge=1, le=20, description="Number of top truck matches to return")


class ImportLoadParams(BaseModel):
    """Parameters for ``freight.import_load``."""

    provider_id: str = Field(..., description="Provider ID (e.g. 'timocom', 'teleroute')")
    provider_load_id: str = Field(..., description="Provider-specific load identifier to import as a trip")


class RecommendDispatchParams(BaseModel):
    """Parameters for ``freight.recommend_dispatch``.

    Orchestrates evaluate → find best trucks → import if the load is viable.
    """

    provider_id: str = Field(..., description="Provider ID (e.g. 'timocom', 'teleroute')")
    provider_load_id: str = Field(..., description="Provider-specific load identifier")
    top_n: int = Field(5, ge=1, le=20, description="Number of top truck matches to consider")


class ListConnectedProvidersParams(BaseModel):
    """Parameters for ``freight.list_connected_providers``."""


# ═════════════════════════════════════════════════════════════════════════════
# Tool 1: freight.search_loads  (Level 0 — SAFE)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightSearchLoadsTool(BaseTool):
    """Search freight loads across connected providers.

    Runs the search in parallel across all (or specified) providers and
    returns a merged result set.  Down or incompatible providers are
    silently skipped with a status note.
    """

    name = "freight.search_loads"
    tool_version = "1.0.0"
    description = "Search freight loads across connected freight exchange providers"
    required_permission = "freight:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = SearchLoadsParams

    async def validate(self, params: SearchLoadsParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        if not params.origin:
            errors.append("Origin is required")
        return errors

    async def execute(self, params: SearchLoadsParams, ctx: ToolExecutionContext) -> ToolResult:
        from models.freight_exchange_models import LoadSearchFilters

        try:
            svc = await _get_search_engine(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "search_engine"},
                )

            filters = _build_search_filters(
                origin=params.origin,
                destination=params.destination,
                pickup_date=params.pickup_date,
                load_type=params.load_type,
                weight_kg=params.weight_kg,
            )

            result_set = await svc.search_loads(
                company_id=ctx.company_id,
                filters=filters,
                provider_ids=params.provider_ids,
            )

            # Apply max_results
            all_results = result_set.results
            if len(all_results) > params.max_results:
                all_results = all_results[:params.max_results]

            data = {
                "results": [r.model_dump(mode="json") for r in all_results],
                "total_results": len(all_results),
                "providers_queried": result_set.total_providers_queried,
                "providers_skipped": result_set.total_providers_skipped,
                "provider_statuses": [
                    {"provider_id": ps.provider_id, "status": ps.status, "error": getattr(ps, "error", "")}
                    for ps in result_set.provider_statuses
                ],
            }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.tool.freight.search_loads_ok",
                message_params={"count": len(all_results)},
            )

        except Exception as exc:
            logger.exception("freight.search_loads failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.search_loads_failed",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 2: freight.get_load  (Level 0 — SAFE)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightGetLoadTool(BaseTool):
    """Fetch a single load by provider and load ID.

    Returns the full load detail including price, route, and cargo info.
    """

    name = "freight.get_load"
    tool_version = "1.0.0"
    description = "Get a single freight load by provider and load ID"
    required_permission = "freight:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = GetLoadParams

    async def validate(self, params: GetLoadParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: GetLoadParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            svc = await _get_search_engine(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "search_engine"},
                )

            load = await svc.get_load(
                company_id=ctx.company_id,
                provider_id=params.provider_id,
                provider_load_id=params.provider_load_id,
            )

            if load is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.tool.freight.get_load_not_found",
                    message_params={
                        "provider_id": params.provider_id,
                        "load_id": params.provider_load_id,
                    },
                )

            return ToolResult(
                status="success",
                data=load.model_dump(mode="json"),
                message_key="copilot.tool.freight.get_load_ok",
                message_params={"load_id": params.provider_load_id},
            )

        except Exception as exc:
            logger.exception("freight.get_load failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.get_load_failed",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 3: freight.save_search  (Level 1 — INFORMATIONAL)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightSaveSearchTool(BaseTool):
    """Save a search for later recall.

    Stores the filter parameters under a human-readable label so the
    dispatcher can quickly re-run the same search later.
    """

    name = "freight.save_search"
    tool_version = "1.0.0"
    description = "Save a freight search with a label for later recall"
    required_permission = "freight:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    parameters_schema = SaveSearchParams

    async def validate(self, params: SaveSearchParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        if not params.origin:
            errors.append("Origin is required")
        if not params.label:
            errors.append("Label is required")
        return errors

    async def execute(self, params: SaveSearchParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            svc = await _get_search_engine(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "search_engine"},
                )

            filters = _build_search_filters(
                origin=params.origin,
                destination=params.destination,
                pickup_date=params.pickup_date,
                load_type=params.load_type,
                weight_kg=params.weight_kg,
            )

            saved = await svc.save_search(
                company_id=ctx.company_id,
                user_id=ctx.user_id,
                filters=filters,
                label=params.label,
                provider_ids=params.provider_ids,
            )

            return ToolResult(
                status="success",
                data=saved.model_dump(mode="json"),
                message_key="copilot.tool.freight.save_search_ok",
                message_params={"label": params.label},
            )

        except Exception as exc:
            logger.exception("freight.save_search failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.save_search_failed",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 4: freight.refresh_search  (Level 0 — SAFE)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightRefreshSearchTool(BaseTool):
    """Re-run a saved search and return fresh results."""

    name = "freight.refresh_search"
    tool_version = "1.0.0"
    description = "Re-run a saved freight search by its ID"
    required_permission = "freight:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = RefreshSearchParams

    async def validate(self, params: RefreshSearchParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: RefreshSearchParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            svc = await _get_search_engine(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "search_engine"},
                )

            result_set = await svc.refresh_search(
                company_id=ctx.company_id,
                saved_search_id=params.saved_search_id,
            )

            data = {
                "results": [r.model_dump(mode="json") for r in result_set.results],
                "total_results": len(result_set.results),
                "providers_queried": result_set.total_providers_queried,
                "providers_skipped": result_set.total_providers_skipped,
                "provider_statuses": [
                    {"provider_id": ps.provider_id, "status": ps.status, "error": getattr(ps, "error", "")}
                    for ps in result_set.provider_statuses
                ],
            }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.tool.freight.refresh_search_ok",
                message_params={"count": len(result_set.results)},
            )

        except ValueError as exc:
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.refresh_search_not_found",
                message_params={"search_id": params.saved_search_id, "error": str(exc)},
            )
        except Exception as exc:
            logger.exception("freight.refresh_search failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.refresh_search_failed",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 5: freight.evaluate_load  (Level 0 — SAFE)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightEvaluateLoadTool(BaseTool):
    """Evaluate a load's profitability, cost breakdown, and risk.

    Returns estimated revenue, fuel/toll/driver costs, expected profit,
    profit margin, risk score, and optional vehicle/driver compatibility
    if a candidate vehicle ID is provided.
    """

    name = "freight.evaluate_load"
    tool_version = "1.0.0"
    description = "Evaluate a freight load's profitability, costs, and risk"
    required_permission = "freight:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = EvaluateLoadParams

    async def validate(self, params: EvaluateLoadParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: EvaluateLoadParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            svc = await _get_evaluation_engine(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "evaluation_engine"},
                )

            evaluation = await svc.evaluate_load(
                company_id=ctx.company_id,
                provider_id=params.provider_id,
                provider_load_id=params.provider_load_id,
                candidate_vehicle_id=params.vehicle_id,
            )

            return ToolResult(
                status="success",
                data=evaluation.model_dump(mode="json"),
                message_key="copilot.tool.freight.evaluate_load_ok",
                message_params={"load_id": params.provider_load_id},
            )

        except ValueError as exc:
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.evaluate_load_not_found",
                message_params={
                    "provider_id": params.provider_id,
                    "load_id": params.provider_load_id,
                    "error": str(exc),
                },
            )
        except Exception as exc:
            logger.exception("freight.evaluate_load failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.evaluate_load_failed",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 6: freight.find_best_trucks  (Level 0 — SAFE)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightFindBestTrucksTool(BaseTool):
    """Find the best trucks for a given freight load.

    Scores every available truck against the load using proximity, profit
    potential, driver hours, maintenance health, trailer compatibility,
    historical reliability, and positioning.  Returns the top N ranked
    matches with deterministic reasons.
    """

    name = "freight.find_best_trucks"
    tool_version = "1.0.0"
    description = "Find the best trucks for a freight load ranked by match score"
    required_permission = "freight:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = FindBestTrucksParams

    async def validate(self, params: FindBestTrucksParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: FindBestTrucksParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            svc = await _get_fleet_matcher(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "fleet_matcher"},
                )

            matches = await svc.find_best_trucks(
                company_id=ctx.company_id,
                provider_id=params.provider_id,
                provider_load_id=params.provider_load_id,
                top_n=params.top_n,
            )

            data = {
                "matches": [m.model_dump(mode="json") for m in matches],
                "total_matches": len(matches),
            }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.tool.freight.find_best_trucks_ok",
                message_params={"count": len(matches)},
            )

        except ValueError as exc:
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.find_best_trucks_not_found",
                message_params={
                    "provider_id": params.provider_id,
                    "load_id": params.provider_load_id,
                    "error": str(exc),
                },
            )
        except Exception as exc:
            logger.exception("freight.find_best_trucks failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.find_best_trucks_failed",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 7: freight.import_load  (Level 2 — BUSINESS, requires confirmation)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightImportLoadTool(BaseTool):
    """Import a freight exchange load as an Operion trip.

    This creates a real business record (trip) and therefore requires user
    confirmation.  The load is fetched from the provider, mapped to a trip,
    and persisted via the standard TripService.
    """

    name = "freight.import_load"
    tool_version = "1.0.0"
    description = "Import a freight exchange load as a new trip (requires confirmation)"
    required_permission = "freight:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    parameters_schema = ImportLoadParams

    async def validate(self, params: ImportLoadParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: ImportLoadParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            svc = await _get_import_pipeline(ctx)
            if svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "import_pipeline"},
                )

            result = await svc.import_load(
                company_id=ctx.company_id,
                provider_id=params.provider_id,
                provider_load_id=params.provider_load_id,
                user_id=ctx.user_id,
            )

            return ToolResult(
                status="success",
                data=result.model_dump(mode="json"),
                message_key="copilot.tool.freight.import_load_ok",
                message_params={
                    "trip_id": result.trip_id,
                    "provider_id": params.provider_id,
                },
            )

        except Exception as exc:
            logger.exception("freight.import_load failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.import_load_failed",
                message_params={
                    "provider_id": params.provider_id,
                    "load_id": params.provider_load_id,
                    "error": str(exc),
                },
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 8: freight.recommend_dispatch  (Level 2 — BUSINESS)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightRecommendDispatchTool(BaseTool):
    """Orchestrate a complete dispatch recommendation for a freight load.

    Workflow:
    1. Evaluate the load (profitability, costs, risk)
    2. Find the best matching trucks
    3. If the evaluation shows a positive expected profit, import the load
       as a new trip automatically

    Returns the combined evaluation + best trucks + optional import result.
    """

    name = "freight.recommend_dispatch"
    tool_version = "1.0.0"
    description = "Get a complete dispatch recommendation: evaluate + match + import if viable"
    required_permission = "freight:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    parameters_schema = RecommendDispatchParams

    async def validate(self, params: RecommendDispatchParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: RecommendDispatchParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            # ── Step 1: Evaluate the load ─────────────────────────────────
            eval_svc = await _get_evaluation_engine(ctx)
            if eval_svc is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "evaluation_engine"},
                )

            evaluation = await eval_svc.evaluate_load(
                company_id=ctx.company_id,
                provider_id=params.provider_id,
                provider_load_id=params.provider_load_id,
            )

            # ── Step 2: Find best trucks ──────────────────────────────────
            matcher_svc = await _get_fleet_matcher(ctx)
            best_trucks: list = []
            if matcher_svc is not None:
                best_trucks = await matcher_svc.find_best_trucks(
                    company_id=ctx.company_id,
                    provider_id=params.provider_id,
                    provider_load_id=params.provider_load_id,
                    top_n=params.top_n,
                )

            # ── Step 3: Import if viable ──────────────────────────────────
            import_result = None
            if evaluation.expected_profit is not None and evaluation.expected_profit.amount > 0:
                try:
                    pipeline_svc = await _get_import_pipeline(ctx)
                    if pipeline_svc is not None:
                        import_result = await pipeline_svc.import_load(
                            company_id=ctx.company_id,
                            provider_id=params.provider_id,
                            provider_load_id=params.provider_load_id,
                            user_id=ctx.user_id,
                        )
                except Exception as imp_exc:
                    logger.warning("Auto-import failed (load still dispatched manually): %s", imp_exc)
                    # Non-fatal — the user can import manually later

            data = {
                "evaluation": evaluation.model_dump(mode="json"),
                "best_trucks": [m.model_dump(mode="json") for m in best_trucks],
                "import_result": import_result.model_dump(mode="json") if import_result else None,
                "load_viable": evaluation.expected_profit is not None and evaluation.expected_profit.amount > 0,
            }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.tool.freight.recommend_dispatch_ok",
                message_params={
                    "load_id": params.provider_load_id,
                    "imported": import_result is not None,
                },
            )

        except ValueError as exc:
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.recommend_dispatch_not_found",
                message_params={
                    "provider_id": params.provider_id,
                    "load_id": params.provider_load_id,
                    "error": str(exc),
                },
            )
        except Exception as exc:
            logger.exception("freight.recommend_dispatch failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.recommend_dispatch_failed",
                message_params={"error": str(exc)},
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tool 9: freight.list_connected_providers  (Level 0 — SAFE)
# ═════════════════════════════════════════════════════════════════════════════


@register_tool
class FreightListConnectedProvidersTool(BaseTool):
    """List all connected freight exchange providers with status and capabilities.

    Returns connection status, health check info, session expiry, and
    filter capabilities for each connected provider.
    """

    name = "freight.list_connected_providers"
    tool_version = "1.0.0"
    description = "List connected freight exchange providers with status and capabilities"
    required_permission = "freight:read"
    confirmation_level = ConfirmationLevel.SAFE
    parameters_schema = ListConnectedProvidersParams

    async def validate(self, params: ListConnectedProvidersParams, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: ListConnectedProvidersParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            conn_mgr = await _get_conn_mgr(ctx)
            if conn_mgr is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.tool.freight.service_unavailable",
                    message_params={"service": "connection_manager"},
                )

            # list_connected_providers is SYNCHRONOUS
            providers = conn_mgr.list_connected_providers(ctx.company_id)

            data = {
                "providers": providers,
                "total": len(providers),
            }

            return ToolResult(
                status="success",
                data=data,
                message_key="copilot.tool.freight.list_connected_providers_ok",
                message_params={"count": len(providers)},
            )

        except Exception as exc:
            logger.exception("freight.list_connected_providers failed: %s", exc)
            return ToolResult(
                status="failed",
                message_key="copilot.tool.freight.list_connected_providers_failed",
                message_params={"error": str(exc)},
            )
