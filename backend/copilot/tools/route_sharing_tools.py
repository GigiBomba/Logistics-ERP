"""Route Sharing and Persistence Co-Pilot tools.

Tools:
- route.save_plan          — Persist a calculated route to history (Level 1)
- route.export_file        — Export route as .operionroute binary file (Level 1)
- route.import_file        — Import route from .operionroute binary file (Level 1)
- route.create_share_link  — Build a shareable URL for a route (Level 1)
- route.create             — Create a new route record (Level 2, may be unavailable)
- route.update             — Update an existing route record (Level 2, currently unavailable)
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Parameter Schemas
# ──────────────────────────────────────────────────────────────────────────────


class SavePlanParams(BaseModel):
    route_json: dict = Field(
        ...,
        description="Serialised route data including distance_km, duration_min, geometry, stops.",
    )
    profile: str = Field(
        "truck",
        description="Routing profile key (e.g. 'truck', 'car', 'foot', 'bike').",
    )
    truck_id: Optional[int] = Field(
        None,
        description="Vehicle ID to associate with the saved route. "
        "Used to look up consumption and truck metadata.",
    )
    stops_state: list[dict] = Field(
        default_factory=list,
        description="Current stops state from the planner — each item has type, address, lat, lon.",
    )
    stop_addresses: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of stop id -> resolved address string.",
    )
    excluded_countries: list[str] = Field(
        default_factory=list,
        description="ISO 3166-1 alpha-2 country codes excluded from routing.",
    )
    cost_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Cost breakdown dictionary (fuel_cost, toll_cost, driver_cost, total_cost, etc.).",
    )


class ExportFileParams(BaseModel):
    stops: list[dict] = Field(
        ...,
        description="Stop dicts with ``lat`` and ``lon`` keys (as produced by stops_state or route result).",
    )
    profile: str = Field("truck", description="Routing profile key.")
    truck_id: Optional[str] = Field(
        None,
        description="Truck database id (string) embedded in the file for re-import.",
    )
    geometry: Optional[list] = Field(
        None,
        description="Route geometry as a list of coordinate pairs.",
    )
    distance_km: Optional[float] = Field(
        None,
        description="Total route distance in kilometres.",
    )
    duration_min: Optional[float] = Field(
        None,
        description="Total route duration in minutes.",
    )


class ImportFileParams(BaseModel):
    file_data: str = Field(
        ...,
        description="Base64-encoded content of a .operionroute file.",
    )


class CreateShareLinkParams(BaseModel):
    stops: list[dict] = Field(
        ...,
        description="Stop dicts with ``lat`` and ``lon`` keys.",
    )
    profile: str = Field("truck", description="Routing profile key.")
    truck_id: Optional[str] = Field(
        None,
        description="Truck database id (string) to embed in the share URL.",
    )
    truck_label: Optional[str] = Field(
        None,
        description="Human-readable truck label (e.g. plate number) to embed in the URL.",
    )


class CreateRouteParams(BaseModel):
    stops: list[dict] = Field(
        ...,
        description="Stops snapshot — list of dicts with lat, lon, address, type, resolved keys.",
    )
    geometry: Optional[list] = Field(
        None,
        description="Route geometry as a list of coordinate pairs.",
    )
    total_distance_km: Optional[float] = Field(
        None,
        description="Total route distance in kilometres.",
    )
    duration_min: Optional[float] = Field(
        None,
        description="Total route duration in minutes.",
    )
    truck_id: Optional[str] = Field(
        None,
        description="Truck database id (string).",
    )
    truck_label: Optional[str] = Field(
        None,
        description="Human-readable truck label (plate number).",
    )
    truck: Optional[dict] = Field(
        None,
        description="Full truck payload (id, plate_number, model).",
    )
    profile: Optional[str] = Field(
        "truck",
        description="Routing profile key.",
    )
    excluded_countries: list[str] = Field(
        default_factory=list,
        description="ISO 3166-1 alpha-2 country codes excluded from the route.",
    )
    countries_traversed: list[str] = Field(
        default_factory=list,
        description="Country codes detected on the route.",
    )
    metadata_version: int = Field(
        1,
        description="Route history metadata format version.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _try_resolve_truck(db, truck_id: int) -> dict[str, Any]:
    """Try to resolve a numeric *truck_id* to a truck dict.

    Uses ``FleetService.get()`` when available.  Returns ``{}`` on any
    failure so the caller can still proceed with an empty truck payload.
    """
    try:
        from backend.services.fleet_service import FleetService

        fleet = FleetService(db)
        result = fleet.get(truck_id)
        if result.success and result.data is not None:
            return result.data.model_dump()
    except Exception:
        logger.debug("Failed to resolve truck_id=%s via FleetService", truck_id, exc_info=True)
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# Tool 1: route.save_plan  (Level 1 — INFORMATIONAL, "routes:write")
# ──────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteSavePlanTool(BaseTool):
    """Persist a calculated route to history.

    Wraps ``RoutePersistenceService(db).save_calculated_route()``.

    ``RoutePersistenceService`` requires three collaborator services:
    ``RouteHistoryService``, ``RouteStateManager``, and optionally
    ``CostEngineService``.  The tool tries to obtain these from
    ``ctx.services`` first; if any are missing it attempts to construct
    them from a raw ``db`` session (also from ``ctx.services``).
    """

    name = "route.save_plan"
    tool_version = "1.0.0"
    description = (
        "Save a calculated route to the route history table. Stores "
        "geometry, distance, duration, stops, truck assignment, and "
        "cost information. Returns the new ``route_id``."
    )
    required_permission = "routes:write"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    parameters_schema = SavePlanParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: SavePlanParams = params  # type: ignore[assignment]
        try:
            # ── Resolve collaborator services ───────────────────────────
            history_svc = ctx.services.get("route_history_service")
            state_mgr = ctx.services.get("route_state_manager")
            cost_engine = ctx.services.get("cost_engine_service")
            db = ctx.services.get("db")

            # Try to construct missing services from db
            if history_svc is None or state_mgr is None:
                if db is None:
                    return ToolResult(
                        status="unavailable",
                        message_key="copilot.route.save_plan_unavailable",
                        data={
                            "reason": (
                                "Neither pre-instantiated route services nor a db "
                                "session are available in the execution context."
                            ),
                        },
                    )
                from services.route_history_service import RouteHistoryService
                from services.route_state import RouteStateManager

                if history_svc is None:
                    history_svc = RouteHistoryService(db)
                if state_mgr is None:
                    state_mgr = RouteStateManager(db)

            if cost_engine is None:
                from services.cost_engine import CostEngineService

                cost_engine = CostEngineService()

            from services.route_persistence import RoutePersistenceService

            persistence = RoutePersistenceService(
                history_service=history_svc,
                route_state=state_mgr,
                cost_engine=cost_engine,
            )

            # ── Resolve truck object from optional truck_id ─────────────
            truck: dict[str, Any] = {}
            if p.truck_id is not None:
                truck = _try_resolve_truck(db, p.truck_id)

            # ── Persist ─────────────────────────────────────────────────
            route_id = persistence.save_calculated_route(
                route=p.route_json,
                truck=truck,
                profile=p.profile,
                stops_state=p.stops_state,
                stop_addresses=p.stop_addresses,
                excluded_countries=p.excluded_countries,
                cost_info=p.cost_info,
            )

            return ToolResult(
                status="success",
                data={"route_id": route_id},
                message_key="copilot.route.save_plan.success",
                message_params={"route_id": str(route_id)},
            )

        except Exception as exc:
            logger.exception("route.save_plan failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 2: route.export_file  (Level 1 — INFORMATIONAL, "routes:read")
# ──────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteExportFileTool(BaseTool):
    """Export route state to a portable .operionroute binary file.

    Wraps the module-level ``encode_route_file()`` from the route
    sharing service.  Returns the file content as a base64-encoded
    string suitable for download or transfer.
    """

    name = "route.export_file"
    tool_version = "1.0.0"
    description = (
        "Export the current route state to a shareable .operionroute "
        "binary file. Returns the file content as a base64 string."
    )
    required_permission = "routes:read"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    parameters_schema = ExportFileParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p: ExportFileParams = params  # type: ignore[assignment]
        if not p.stops:
            return ["route.error.no_stops"]
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: ExportFileParams = params  # type: ignore[assignment]
        try:
            from services.route_sharing_service import encode_route_file

            data = encode_route_file(
                stops=p.stops,
                profile=p.profile,
                truck_id=p.truck_id,
                geometry=p.geometry,
                distance_km=p.distance_km,
                duration_min=p.duration_min,
            )

            encoded = base64.b64encode(data).decode("utf-8")

            return ToolResult(
                status="success",
                data={
                    "file_data": encoded,
                    "filename": "route.operionroute",
                },
                message_key="copilot.route.export_file.success",
            )

        except Exception as exc:
            logger.exception("route.export_file failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 3: route.import_file  (Level 1 — INFORMATIONAL, "routes:read")
# ──────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteImportFileTool(BaseTool):
    """Import a route from a portable .operionroute binary file.

    Wraps the module-level ``decode_route_file()`` from the route
    sharing service.  Accepts a base64-encoded file string and returns
    the parsed route data (stops, geometry, distance, duration, etc.).
    """

    name = "route.import_file"
    tool_version = "1.0.0"
    description = (
        "Import a route from a .operionroute binary file (base64-encoded). "
        "Returns the full route state including stops, geometry, distance, "
        "and duration."
    )
    required_permission = "routes:read"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    parameters_schema = ImportFileParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p: ImportFileParams = params  # type: ignore[assignment]
        if not p.file_data:
            return ["route.error.empty_file_data"]
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: ImportFileParams = params  # type: ignore[assignment]
        try:
            from services.route_sharing_service import decode_route_file

            raw = base64.b64decode(p.file_data)
            route_data = decode_route_file(raw)

            return ToolResult(
                status="success",
                data={"route_data": route_data},
                message_key="copilot.route.import_file.success",
            )

        except Exception as exc:
            # base64 decode errors and .operionroute format errors both
            # produce ValueError; catch broadly for safety.
            logger.exception("route.import_file failed")
            return ToolResult(
                status="failed",
                message_key="route.error.invalid_file",
                message_params={"error": str(exc)},
            )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 4: route.create_share_link  (Level 1 — INFORMATIONAL, "routes:read")
# ──────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteCreateShareLinkTool(BaseTool):
    """Build a shareable URL for a route.

    Wraps the module-level ``build_share_url()`` from the route sharing
    service.  Returns a link that can be opened in Operion to reproduce
    the route.
    """

    name = "route.create_share_link"
    tool_version = "1.0.0"
    description = (
        "Create a shareable Operion route URL that encodes all stops, "
        "the routing profile, and optional truck info. Recipients open "
        "the link in Operion to load the route."
    )
    required_permission = "routes:read"
    confirmation_level = ConfirmationLevel.INFORMATIONAL
    supports_undo = False
    parameters_schema = CreateShareLinkParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p: CreateShareLinkParams = params  # type: ignore[assignment]
        if not p.stops:
            return ["route.error.no_stops"]
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: CreateShareLinkParams = params  # type: ignore[assignment]
        try:
            from services.route_sharing_service import build_share_url

            share_url = build_share_url(
                stops=p.stops,
                profile=p.profile,
                truck_id=p.truck_id,
                truck_label=p.truck_label,
            )

            return ToolResult(
                status="success",
                data={"share_url": share_url},
                message_key="copilot.route.create_share_link.success",
            )

        except Exception as exc:
            logger.exception("route.create_share_link failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 5: route.create  (Level 2 — BUSINESS, "routes:write")
# ──────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteCreateTool(BaseTool):
    """Create a new route history record.

    Delegates to ``RouteHistoryService.save_route()`` which builds a
    deterministic fingerprint, inserts the record, and returns the
    new ``route_id``.

    Requires either a pre-instantiated ``route_history_service`` or
    a ``db`` session in the execution context.  If neither is available
    the tool returns ``unavailable``.
    """

    name = "route.create"
    tool_version = "1.0.0"
    description = (
        "Create a new route record in route history. Accepts route "
        "metadata (stops, geometry, distance, duration, truck) and "
        "returns the new ``route_id``."
    )
    required_permission = "routes:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    parameters_schema = CreateRouteParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p: CreateRouteParams = params  # type: ignore[assignment]
        if not p.stops:
            return ["route.error.no_stops"]
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: CreateRouteParams = params  # type: ignore[assignment]
        try:
            from services.route_history_service import RouteHistoryRecord, RouteHistoryService

            # Resolve service — prefer pre-instantiated, fall back to db
            history_svc: Optional[RouteHistoryService] = ctx.services.get("route_history_service")
            if history_svc is None:
                db = ctx.services.get("db")
                if db is None:
                    return ToolResult(
                        status="unavailable",
                        message_key="copilot.route.create_unavailable",
                        data={
                            "reason": (
                                "Neither route_history_service nor db "
                                "are available in the execution context."
                            ),
                        },
                    )
                history_svc = RouteHistoryService(db)

            record = RouteHistoryRecord(
                stops=p.stops,
                geometry=p.geometry or [],
                total_distance_km=p.total_distance_km,
                duration_min=p.duration_min,
                truck_id=p.truck_id,
                truck_label=p.truck_label,
                truck=p.truck or {},
                profile=p.profile,
                excluded_countries=p.excluded_countries,
                countries_traversed=p.countries_traversed,
                metadata_version=p.metadata_version,
            )

            route_id = history_svc.save_route(record)

            return ToolResult(
                status="success",
                data={"route_id": route_id},
                message_key="copilot.route.create.success",
                message_params={"route_id": str(route_id)},
            )

        except Exception as exc:
            logger.exception("route.create failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )


class UpdateRouteParams(BaseModel):
    """Input parameters for route.update."""

    route_id: int = Field(
        ..., gt=0, description="Route history record ID to update",
    )
    stops: list[dict] = Field(
        default_factory=list,
        description="Updated stops — list of dicts with lat, lon, address, type keys.",
    )
    geometry: Optional[list] = Field(
        None, description="Updated route geometry as list of coordinate pairs.",
    )
    total_distance_km: Optional[float] = Field(
        None, description="Updated total distance in kilometres.",
    )
    duration_min: Optional[float] = Field(
        None, description="Updated total duration in minutes.",
    )
    truck_id: Optional[str] = Field(
        None, description="Truck database id (string).",
    )
    truck_label: Optional[str] = Field(
        None, description="Human-readable truck label (plate number).",
    )
    truck: Optional[dict] = Field(
        None, description="Full truck payload (id, plate_number, model).",
    )
    profile: Optional[str] = Field(
        None, description="Routing profile key.",
    )
    excluded_countries: list[str] = Field(
        default_factory=list,
        description="ISO 3166-1 alpha-2 country codes excluded from the route.",
    )
    countries_traversed: list[str] = Field(
        default_factory=list,
        description="Country codes detected on the route.",
    )
    metadata_version: int = Field(
        1, description="Route history metadata format version.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 6: route.update  (Level 2 — BUSINESS, "routes:write")
# ──────────────────────────────────────────────────────────────────────────────


@register_tool
class RouteUpdateTool(BaseTool):
    """Update an existing route history record.

    Wraps ``RouteHistoryService.update_route()`` which verifies the
    route exists, normalises the incoming data, and persists changes
    via ``RouteRepository.update()``.
    """

    name = "route.update"
    tool_version = "1.0.0"
    description = "Update an existing route history record — stops, geometry, distance, duration, truck, or profile"
    required_permission = "routes:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    parameters_schema = UpdateRouteParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> list[str]:
        p: UpdateRouteParams = params  # type: ignore[assignment]
        errors: list[str] = []
        if p.route_id <= 0:
            errors.append("route_id must be a positive integer")
        return errors

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: UpdateRouteParams = params  # type: ignore[assignment]
        try:
            from services.route_history_service import RouteHistoryRecord, RouteHistoryService

            # Resolve service — prefer pre-instantiated, fall back to db
            history_svc: Optional[RouteHistoryService] = ctx.services.get("route_history_service")
            if history_svc is None:
                db = ctx.services.get("db")
                if db is None:
                    return ToolResult(
                        status="unavailable",
                        message_key="copilot.route.update_unavailable",
                        data={
                            "reason": (
                                "Neither route_history_service nor db "
                                "are available in the execution context."
                            ),
                        },
                    )
                history_svc = RouteHistoryService(db)

            record = RouteHistoryRecord(
                stops=p.stops,
                geometry=p.geometry or [],
                total_distance_km=p.total_distance_km,
                duration_min=p.duration_min,
                truck_id=p.truck_id,
                truck_label=p.truck_label,
                truck=p.truck or {},
                profile=p.profile,
                excluded_countries=p.excluded_countries,
                countries_traversed=p.countries_traversed,
                metadata_version=p.metadata_version,
            )

            ok = history_svc.update_route(p.route_id, record)
            if not ok:
                return ToolResult(
                    status="failed",
                    data={"route_id": p.route_id},
                    message_key="copilot.route.update_not_found",
                    message_params={"route_id": str(p.route_id)},
                )

            return ToolResult(
                status="success",
                data={"route_id": p.route_id},
                message_key="copilot.route.update.success",
                message_params={"route_id": str(p.route_id)},
            )

        except Exception as exc:
            logger.exception("route.update failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.internal",
                message_params={"error": str(exc)},
            )
