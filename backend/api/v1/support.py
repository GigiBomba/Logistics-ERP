"""Support endpoint — proxies client support messages to the operion-ops
support-service over an internal-only path.

See Operion_Ops_Blueprint.md §41.2 for the full contract.
"""
from __future__ import annotations

import logging
import json
from typing import Any, Dict, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.config import BackendSettings
from backend.dependencies_security import get_current_user
from backend.errors import ErrorCode

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

    # Settings (loaded fresh per-request so env changes are picked up promptly)
    settings = BackendSettings()

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
