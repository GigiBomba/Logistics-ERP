"""Level 3 destructive-action tools — irreversible actions requiring typed confirmation.

Blueprint: §9.1 — Level 3, §21 Phase 3.

All tools in this module require the user to type the exact entity id/code
to confirm before the destructive action is executed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 1. trip.delete
# ═══════════════════════════════════════════════════════════════════════════


class TripDeleteParams(BaseModel):
    """Input parameters for ``trip.delete``."""

    model_config = ConfigDict(extra="forbid")

    trip_id: int = Field(..., gt=0, description="Trip ID to delete")
    confirmation_phrase: str = Field(
        ..., min_length=1, description="Type the trip ID to confirm deletion"
    )


@register_tool
class TripDeleteTool(BaseTool):
    """Permanently delete a trip. IRREVERSIBLE — requires typed confirmation.

    The user must type the exact trip ID to confirm.
    Wraps ``TripService.delete(trip_id, user_id)``.
    """

    name = "trip.delete"
    tool_version = "1.0.0"
    description = "Permanently delete a trip — requires typed confirmation"
    required_permission = "trips:delete"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    deprecated = False
    parameters_schema = TripDeleteParams

    @staticmethod
    def _assert_params(params: BaseModel) -> TripDeleteParams:
        assert isinstance(params, TripDeleteParams)
        return params

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.trip_id <= 0:
            errors.append("trip_id must be a positive integer")
        if not p.confirmation_phrase.strip():
            errors.append("confirmation_phrase is required")
        return errors

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            from backend.services.trip_service import TripService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            svc = TripService(db)
            result = svc.delete(p.trip_id, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.trip.delete_failed",
                    message_params={"error": detail},
                )

            return ToolResult(
                status="success",
                data={"trip_id": p.trip_id},
                message_key="copilot.trip.deleted",
                message_params={"trip_id": p.trip_id},
            )

        except Exception as exc:
            logger.exception("trip.delete failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ═══════════════════════════════════════════════════════════════════════════
# 2. vehicle.delete
# ═══════════════════════════════════════════════════════════════════════════


class VehicleDeleteParams(BaseModel):
    """Input parameters for ``vehicle.delete``."""

    model_config = ConfigDict(extra="forbid")

    vehicle_id: int = Field(..., gt=0, description="Vehicle ID to delete")
    confirmation_phrase: str = Field(
        ..., min_length=1, description="Type the vehicle ID to confirm deletion"
    )


@register_tool
class VehicleDeleteTool(BaseTool):
    """Permanently delete a vehicle. IRREVERSIBLE — requires typed confirmation.

    The user must type the exact vehicle ID to confirm.
    Wraps ``FleetService.delete(vehicle_id, user_id)``.
    """

    name = "vehicle.delete"
    tool_version = "1.0.0"
    description = "Permanently delete a vehicle — requires typed confirmation"
    required_permission = "fleet:delete"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    deprecated = False
    parameters_schema = VehicleDeleteParams

    @staticmethod
    def _assert_params(params: BaseModel) -> VehicleDeleteParams:
        assert isinstance(params, VehicleDeleteParams)
        return params

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.vehicle_id <= 0:
            errors.append("vehicle_id must be a positive integer")
        if not p.confirmation_phrase.strip():
            errors.append("confirmation_phrase is required")
        return errors

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            from backend.services.fleet_service import FleetService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            svc = FleetService(db)
            result = svc.delete(p.vehicle_id, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.vehicle.delete_failed",
                    message_params={"error": detail},
                )

            return ToolResult(
                status="success",
                data={"vehicle_id": p.vehicle_id},
                message_key="copilot.vehicle.deleted",
                message_params={"vehicle_id": p.vehicle_id},
            )

        except Exception as exc:
            logger.exception("vehicle.delete failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3. driver.remove
# ═══════════════════════════════════════════════════════════════════════════


class DriverRemoveParams(BaseModel):
    """Input parameters for ``driver.remove``."""

    model_config = ConfigDict(extra="forbid")

    driver_id: int = Field(..., gt=0, description="Driver ID to remove")
    confirmation_phrase: str = Field(
        ..., min_length=1, description="Type the driver ID to confirm removal"
    )


@register_tool
class DriverRemoveTool(BaseTool):
    """Permanently remove a driver. IRREVERSIBLE — requires typed confirmation.

    The user must type the exact driver ID to confirm.
    Wraps ``DriverTruckService.delete_driver(driver_id, user_id)``.

    NOTE: The tool is named ``driver.remove`` (not ``driver.delete``) per
    blueprint §9.1 naming conventions.
    """

    name = "driver.remove"
    tool_version = "1.0.0"
    description = "Permanently remove a driver — requires typed confirmation"
    required_permission = "drivers:delete"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    deprecated = False
    parameters_schema = DriverRemoveParams

    @staticmethod
    def _assert_params(params: BaseModel) -> DriverRemoveParams:
        assert isinstance(params, DriverRemoveParams)
        return params

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.driver_id <= 0:
            errors.append("driver_id must be a positive integer")
        if not p.confirmation_phrase.strip():
            errors.append("confirmation_phrase is required")
        return errors

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            from backend.services.driver_truck_service import DriverTruckService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            svc = DriverTruckService(db)
            result = svc.delete_driver(p.driver_id, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.driver.remove_failed",
                    message_params={"error": detail},
                )

            return ToolResult(
                status="success",
                data={"driver_id": p.driver_id},
                message_key="copilot.driver.removed",
                message_params={"driver_id": p.driver_id},
            )

        except Exception as exc:
            logger.exception("driver.remove failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ═══════════════════════════════════════════════════════════════════════════
# 4. client.delete
# ═══════════════════════════════════════════════════════════════════════════


class ClientDeleteParams(BaseModel):
    """Input parameters for ``client.delete``."""

    model_config = ConfigDict(extra="forbid")

    client_id: int = Field(..., gt=0, description="Client ID to delete")
    confirmation_phrase: str = Field(
        ..., min_length=1, description="Type the client ID to confirm deletion"
    )


@register_tool
class ClientDeleteTool(BaseTool):
    """Deactivate (soft-delete) a client. IRREVERSIBLE — requires typed confirmation.

    The user must type the exact client ID to confirm.
    Wraps ``ClientService.delete(client_id, user_id)`` which performs a soft-delete.
    """

    name = "client.delete"
    tool_version = "1.0.0"
    description = "Deactivate (soft-delete) a client — requires typed confirmation"
    required_permission = "clients:delete"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    deprecated = False
    parameters_schema = ClientDeleteParams

    @staticmethod
    def _assert_params(params: BaseModel) -> ClientDeleteParams:
        assert isinstance(params, ClientDeleteParams)
        return params

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.client_id <= 0:
            errors.append("client_id must be a positive integer")
        if not p.confirmation_phrase.strip():
            errors.append("confirmation_phrase is required")
        return errors

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            from backend.services.client_service import ClientService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            svc = ClientService(db)
            result = svc.delete(p.client_id, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.client.delete_failed",
                    message_params={"error": detail},
                )

            return ToolResult(
                status="success",
                data={"client_id": p.client_id},
                message_key="copilot.client.deleted",
                message_params={"client_id": p.client_id},
            )

        except Exception as exc:
            logger.exception("client.delete failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ═══════════════════════════════════════════════════════════════════════════
# 5. invoice.delete
# ═══════════════════════════════════════════════════════════════════════════


class InvoiceDeleteParams(BaseModel):
    """Input parameters for ``invoice.delete``."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: int = Field(..., gt=0, description="Invoice ID to delete")
    confirmation_phrase: str = Field(
        ..., min_length=1, description="Type the invoice ID to confirm deletion"
    )


@register_tool
class InvoiceDeleteTool(BaseTool):
    """Delete an invoice. IRREVERSIBLE — requires typed confirmation.

    The user must type the exact invoice ID to confirm.
    Wraps ``InvoiceService.delete(invoice_id, user_id)``.

    Per blueprint §9.1, invoice deletion is only permitted pre-finalization
    per existing fiscal rules. The service layer handles this check internally.
    """

    name = "invoice.delete"
    tool_version = "1.0.0"
    description = "Delete an invoice — requires typed confirmation (pre-finalization only)"
    required_permission = "invoices:delete"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    deprecated = False
    parameters_schema = InvoiceDeleteParams

    @staticmethod
    def _assert_params(params: BaseModel) -> InvoiceDeleteParams:
        assert isinstance(params, InvoiceDeleteParams)
        return params

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.invoice_id <= 0:
            errors.append("invoice_id must be a positive integer")
        if not p.confirmation_phrase.strip():
            errors.append("confirmation_phrase is required")
        return errors

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            from services.invoicing.service import InvoiceService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            svc = InvoiceService(db)
            result = svc.delete(p.invoice_id, user_id=ctx.user_id)

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.invoice.delete_failed",
                    message_params={"error": detail},
                )

            return ToolResult(
                status="success",
                data={"invoice_id": p.invoice_id},
                message_key="copilot.invoice.deleted",
                message_params={"invoice_id": p.invoice_id},
            )

        except Exception as exc:
            logger.exception("invoice.delete failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ═══════════════════════════════════════════════════════════════════════════
# 6. route.delete
# ═══════════════════════════════════════════════════════════════════════════


class RouteDeleteParams(BaseModel):
    """Input parameters for ``route.delete``."""

    model_config = ConfigDict(extra="forbid")

    route_id: int = Field(..., gt=0, description="Route history ID to delete")
    confirmation_phrase: str = Field(
        ..., min_length=1, description="Type the route ID to confirm deletion"
    )


@register_tool
class RouteDeleteTool(BaseTool):
    """Discard/delete a route history record. IRREVERSIBLE — requires typed confirmation.

    The user must type the exact route ID to confirm.

    Tries, in order:
    1. ``RouteHistoryService.discard_route(route_id)`` — soft-discard (sets is_committed = -1)
    2. ``RouteRepository.delete(route_id)`` — hard-delete fallback
    3. Returns ``unavailable`` if neither method is available.
    """

    name = "route.delete"
    tool_version = "1.0.0"
    description = "Discard or delete a route history record — requires typed confirmation"
    required_permission = "routes:delete"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    deprecated = False
    parameters_schema = RouteDeleteParams

    @staticmethod
    def _assert_params(params: BaseModel) -> RouteDeleteParams:
        assert isinstance(params, RouteDeleteParams)
        return params

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        p = self._assert_params(params)
        errors: List[str] = []
        if p.route_id <= 0:
            errors.append("route_id must be a positive integer")
        if not p.confirmation_phrase.strip():
            errors.append("confirmation_phrase is required")
        return errors

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p = self._assert_params(params)
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            # Strategy 1: RouteHistoryService.discard_route (soft-discard)
            try:
                from backend.services.route_history_service import RouteHistoryService

                svc = RouteHistoryService(db)
                discard_method = getattr(svc, "discard_route", None)
                if discard_method is not None:
                    ok = discard_method(p.route_id)
                    if ok:
                        return ToolResult(
                            status="success",
                            data={"route_id": p.route_id, "action": "discarded"},
                            message_key="copilot.route.deleted",
                            message_params={"route_id": p.route_id},
                        )
                    return ToolResult(
                        status="failed",
                        message_key="copilot.route.delete_failed",
                        message_params={"route_id": p.route_id, "error": "discard returned False"},
                    )
            except (AttributeError, ImportError):
                logger.info(
                    "RouteHistoryService.discard_route not available, "
                    "falling back to RouteRepository.delete"
                )

            # Strategy 2: RouteRepository.delete (hard-delete fallback)
            try:
                from backend.repositories.route_repository import RouteRepository

                repo = RouteRepository(db)
                delete_method = getattr(repo, "delete", None)
                if delete_method is not None:
                    delete_method(p.route_id)
                    return ToolResult(
                        status="success",
                        data={"route_id": p.route_id, "action": "hard_deleted"},
                        message_key="copilot.route.deleted",
                        message_params={"route_id": p.route_id},
                    )
            except (AttributeError, ImportError):
                logger.info("RouteRepository.delete not available either")

            # Neither method available
            return ToolResult(
                status="unavailable",
                message_key="copilot.route.delete_unavailable",
                message_params={"route_id": p.route_id},
            )

        except Exception as exc:
            logger.exception("route.delete failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )
