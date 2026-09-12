"""Support endpoint — proxies client support messages to the operion-ops
support-service over an internal-only path.

See Operion_Ops_Blueprint.md §41.2 for the full contract.
"""
from __future__ import annotations

import logging
import json
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.dependencies_security import get_current_user
from backend.errors import ErrorCode
from backend.schemas.support import CreateTicketRequest, TicketResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


# ── Request / response schemas ───────────────────────────────────────────


class SupportMessageRequest(BaseModel):
    conversation_id: Optional[str] = Field(
        None,
        description="Existing conversation ID to resume, or null to start a new one.",
    )
    message: str = Field(
        ..., min_length=1, description="The customer's support message."
    )
    channel: Literal["chat", "in_app"] = "chat"


class SupportMessageResponse(BaseModel):
    conversation_id: str = Field(..., description="Conversation ID for persistence.")
    reply: str = Field(..., description="The ARGO Support reply text.")
    requires_action: bool = Field(
        False,
        description="True if ARGO needs clarification (async channels should pause).",
    )
    escalated: bool = Field(
        False,
        description="True if the issue was escalated to the founder.",
    )


# ── Endpoint ─────────────────────────────────────────────────────────────


@router.post("/messages", response_model=SupportMessageResponse)
async def proxy_support_message(
    body: SupportMessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> SupportMessageResponse:
    """Receive a client support message and forward it to the operion-ops
    support-service over the internal-only network path.

    The JWT is validated first; then `company_id` / `customer_id` are
    extracted from the authenticated user (never client-supplied) and
    forwarded as internal headers alongside the shared internal auth secret.
    """
    company_id = current_user.get("company_id")
    customer_id = current_user.get("id")
    if customer_id is None:
        customer_id = ""

    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.FORBIDDEN.value,
                "detail": "No company association — support is available to company members only.",
            },
        )

    # Settings (cached process-global instance; see backend.config.get_settings)
    settings = get_settings()

    # Build the downstream request
    downstream_payload: Dict[str, Any] = {
        "conversation_id": body.conversation_id,
        "message": body.message,
        "channel": body.channel,
    }

    downstream_url = f"{settings.support_service_url.rstrip('/')}/v1/messages"
    downstream_headers = {
        "X-Internal-Auth": settings.support_internal_auth,
        "X-Company-Id": str(company_id),
        "X-Customer-Id": str(customer_id),
        "Content-Type": "application/json",
    }

    logger.info(
        "Proxying support message: company_id=%s customer_id=%s channel=%s",
        company_id,
        customer_id,
        body.channel,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                downstream_url,
                json=downstream_payload,
                headers=downstream_headers,
            )
            resp.raise_for_status()
            try:
                data = resp.json()
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=502,
                    detail="Invalid JSON response from support service",
                )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Support-service returned %s: %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "detail": "Support service returned an unexpected response. Please try again.",
            },
        )
    except httpx.RequestError as exc:
        logger.error("Support-service unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": ErrorCode.SERVICE_UNAVAILABLE.value,
                "detail": "Support service is temporarily unavailable. Please try again later.",
            },
        )

    return SupportMessageResponse(
        conversation_id=data.get("conversation_id", ""),
        reply=data.get("reply", ""),
        requires_action=data.get("requires_action", False),
        escalated=data.get("escalated", False),
    )


# ── Shared downstream forwarding (mirrors the error mapping above) ────────


async def _proxy_to_support_service(
    method: str,
    url: str,
    headers: Dict[str, str],
    json_body: Optional[Dict[str, Any]] = None,
) -> Any:
    """Forward a request to the operion-ops support-service and apply the
    standard error mapping used across this router (502 on unexpected HTTP
    responses, 503 when the service is unreachable)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, json=json_body, headers=headers)
            resp.raise_for_status()
            try:
                return resp.json()
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=502,
                    detail="Invalid JSON response from support service",
                )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Support-service returned %s: %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "detail": "Support service returned an unexpected response. Please try again.",
            },
        )
    except httpx.RequestError as exc:
        logger.error("Support-service unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": ErrorCode.SERVICE_UNAVAILABLE.value,
                "detail": "Support service is temporarily unavailable. Please try again later.",
            },
        )


def _ticket_response_from_data(data: Dict[str, Any]) -> TicketResponse:
    """Map a support-service ticket payload onto the public TicketResponse."""
    return TicketResponse(
        id=str(data.get("id", "")),
        subject=data.get("subject", ""),
        status=data.get("status", "open"),
        priority=data.get("priority"),
        category=data.get("category"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )


# ── Support tickets ───────────────────────────────────────────────────────


@router.post("/tickets", response_model=TicketResponse)
async def create_support_ticket(
    body: CreateTicketRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TicketResponse:
    """File a support ticket and forward it to the operion-ops support-service
    over the internal-only network path.

    Mirrors ``POST /support/messages``: the JWT is validated first; then
    ``company_id`` / ``customer_id`` are extracted from the authenticated user
    (never client-supplied) and forwarded as internal headers alongside the
    shared internal auth secret.
    """
    company_id = current_user.get("company_id")
    customer_id = current_user.get("id")
    if customer_id is None:
        customer_id = ""

    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.FORBIDDEN.value,
                "detail": "No company association — support is available to company members only.",
            },
        )

    # Settings (cached process-global instance; see backend.config.get_settings)
    settings = get_settings()

    # Build the downstream request
    downstream_payload: Dict[str, Any] = {
        "subject": body.subject,
        "description": body.description,
    }
    if body.priority is not None:
        downstream_payload["priority"] = body.priority
    if body.category is not None:
        downstream_payload["category"] = body.category

    downstream_url = f"{settings.support_service_url.rstrip('/')}/v1/tickets"
    downstream_headers = {
        "X-Internal-Auth": settings.support_internal_auth,
        "X-Company-Id": str(company_id),
        "X-Customer-Id": str(customer_id),
        "Content-Type": "application/json",
    }

    logger.info(
        "Creating support ticket: company_id=%s customer_id=%s category=%s",
        company_id,
        customer_id,
        body.category,
    )

    data = await _proxy_to_support_service(
        "POST", downstream_url, downstream_headers, json_body=downstream_payload
    )

    return _ticket_response_from_data(data)


@router.get("/tickets", response_model=List[TicketResponse])
async def list_support_tickets(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[TicketResponse]:
    """List the authenticated company's support tickets from the support-service."""
    company_id = current_user.get("company_id")
    customer_id = current_user.get("id")
    if customer_id is None:
        customer_id = ""

    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.FORBIDDEN.value,
                "detail": "No company association — support is available to company members only.",
            },
        )

    settings = get_settings()

    downstream_url = f"{settings.support_service_url.rstrip('/')}/v1/tickets"
    downstream_headers = {
        "X-Internal-Auth": settings.support_internal_auth,
        "X-Company-Id": str(company_id),
        "X-Customer-Id": str(customer_id),
    }

    logger.info(
        "Listing support tickets: company_id=%s customer_id=%s",
        company_id,
        customer_id,
    )

    data = await _proxy_to_support_service("GET", downstream_url, downstream_headers)

    if not isinstance(data, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "detail": "Support service returned an unexpected response. Please try again.",
            },
        )

    return [_ticket_response_from_data(ticket) for ticket in data]


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_support_ticket(
    ticket_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TicketResponse:
    """Fetch a single support ticket by ID from the support-service."""
    company_id = current_user.get("company_id")
    customer_id = current_user.get("id")
    if customer_id is None:
        customer_id = ""

    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ErrorCode.FORBIDDEN.value,
                "detail": "No company association — support is available to company members only.",
            },
        )

    settings = get_settings()

    downstream_url = f"{settings.support_service_url.rstrip('/')}/v1/tickets/{ticket_id}"
    downstream_headers = {
        "X-Internal-Auth": settings.support_internal_auth,
        "X-Company-Id": str(company_id),
        "X-Customer-Id": str(customer_id),
    }

    logger.info(
        "Fetching support ticket: company_id=%s customer_id=%s ticket_id=%s",
        company_id,
        customer_id,
        ticket_id,
    )

    data = await _proxy_to_support_service(
        "GET", downstream_url, downstream_headers
    )

    return _ticket_response_from_data(data)
