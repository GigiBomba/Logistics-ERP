"""Level 2 Co-Pilot CRUD tools for the Client domain — requires user confirmation.

Wraps ``ClientService.create()`` and ``ClientService.update()`` with typed
Pydantic models for safe AI-driven client mutations.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Parameters ──────────────────────────────────────────────────────────────


class ClientCreateParams(BaseModel):
    """Input parameters for ``client.create``."""

    model_config = {"extra": "forbid"}

    name: str = Field(..., min_length=1, description="Client name")
    company_code: str = Field("", description="Company registration code")
    vat_number: str = Field("", description="VAT number")
    address: str = Field("", description="Street address")
    city: str = Field("", description="City")
    country: str = Field("", description="Country")
    email: str = Field("", description="Email address")
    phone: str = Field("", description="Phone number")
    notes: str = Field("", description="Additional notes")


class ClientUpdateParams(BaseModel):
    """Input parameters for ``client.update``."""

    model_config = {"extra": "forbid"}

    client_id: int = Field(..., gt=0, description="Client ID to update")
    name: Optional[str] = Field(None, min_length=1, description="Client name")
    company_code: Optional[str] = Field(None, description="Company registration code")
    vat_number: Optional[str] = Field(None, description="VAT number")
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City")
    country: Optional[str] = Field(None, description="Country")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    notes: Optional[str] = Field(None, description="Additional notes")


# ── client.create (Level 2) ────────────────────────────────────────────────


@register_tool
class ClientCreateTool(BaseTool):
    """Create a new client.

    Wraps ``ClientService.create(request, user_id)`` with a typed
    ``ClientCreate`` model.  Requires ``clients:write`` permission and
    user confirmation.
    """

    name = "client.create"
    tool_version = "1.0.0"
    description = (
        "Create a new client with contact and company details"
    )
    required_permission = "clients:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = ClientCreateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ClientCreateParams:
        assert isinstance(params, ClientCreateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if not p.name.strip():
            errors.append("Client name is required")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.client_models import ClientCreate
            from models.common import ServiceResult
            from models.client_models import ClientResult
            from backend.services.client_service import ClientService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            request = ClientCreate(
                name=p.name,
                company_code=p.company_code,
                vat_number=p.vat_number,
                address=p.address,
                city=p.city,
                country=p.country,
                email=p.email,
                phone=p.phone,
                notes=p.notes,
            )

            svc = ClientService(db)
            result: ServiceResult[ClientResult] = svc.create(  # type: ignore[assignment]
                request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            client = result.data
            if client is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": "Client created but no data returned"},
                )
            return ToolResult(
                status="success",
                data={
                    "client_id": client.id,
                    "name": client.name,
                },
                message_key="copilot.client.create.success",
                message_params={"name": client.name},
            )

        except Exception as exc:
            logger.exception("client.create failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


# ── client.update (Level 2) ────────────────────────────────────────────────


@register_tool
class ClientUpdateTool(BaseTool):
    """Update an existing client.

    Wraps ``ClientService.update(client_id, request, user_id)`` with a typed
    ``ClientUpdate`` model.  Only the fields that are explicitly provided
    will be changed.
    """

    name = "client.update"
    tool_version = "1.0.0"
    description = (
        "Update an existing client's contact and company details"
    )
    required_permission = "clients:write"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    deprecated = False
    parameters_schema = ClientUpdateParams

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _assert_params(params: BaseModel) -> ClientUpdateParams:
        assert isinstance(params, ClientUpdateParams)
        return params

    # ── Validation ──────────────────────────────────────────────────────────

    async def validate(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> list[str]:
        p = self._assert_params(params)
        errors: list[str] = []
        if p.client_id <= 0:
            errors.append("client_id must be a positive integer")
        return errors

    # ── Execution ───────────────────────────────────────────────────────────

    async def execute(
        self,
        params: BaseModel,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        p = self._assert_params(params)
        try:
            from models.client_models import ClientResult, ClientUpdate
            from models.common import ServiceResult
            from backend.services.client_service import ClientService

            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            # Build update model with only explicitly provided fields
            request = ClientUpdate(
                name=p.name,
                company_code=p.company_code,
                vat_number=p.vat_number,
                address=p.address,
                city=p.city,
                country=p.country,
                email=p.email,
                phone=p.phone,
                notes=p.notes,
            )

            svc = ClientService(db)
            result: ServiceResult[ClientResult] = svc.update(  # type: ignore[assignment]
                p.client_id, request=request, user_id=ctx.user_id,
            )

            if not result.success:
                detail = result.errors[0].message if result.errors else "Unknown error"
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": detail},
                )

            client = result.data
            if client is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.error.service_error",
                    message_params={"detail": "Client updated but no data returned"},
                )
            return ToolResult(
                status="success",
                data={
                    "client_id": client.id,
                    "name": client.name,
                },
                message_key="copilot.client.update.success",
                message_params={"client_id": p.client_id},
            )

        except Exception as exc:
            logger.exception("client.update failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )
