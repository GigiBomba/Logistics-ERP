"""Support endpoint — proxies client support messages to the operion-ops
support-service over an internal-only path.

See Operion_Ops_Blueprint.md §41.2 for the full contract.
"""
from __future__ import annotations

import hashlib
import logging
import json
import os
import secrets
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.db import DatabaseManager
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.errors import ErrorCode
from backend.schemas.support import (
    AnonymousErrorReportRequest,
    AnonymousErrorReportResponse,
    CreateTicketRequest,
    TicketResponse,
)

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


# ── Anonymous error reports (lightweight non-Sentry channel) ─────────────
# Accepts a PII-free fatal-error digest from UNAUTHENTICATED visitors.  The
# request is rate-limited per IP and stored locally in
# ``anonymous_error_reports`` for later review — it is deliberately NOT
# proxied to the internal support service (there is no authenticated user to
# attribute a ticket to).

_ANON_ERROR_MAX = 10        # reports per IP per window
_ANON_ERROR_WINDOW = 3600   # 1 hour

# Salt for IP hashing (generated once at module load)
_ANON_IP_SALT = os.environ.get("OPERION_IP_HASH_SALT", secrets.token_hex(16))


def _anon_hash_ip(ip: str) -> str:
    """SHA-256 hash of the IP with salt — never store a raw IP."""
    return hashlib.sha256(f"{ip}:{_ANON_IP_SALT}".encode()).hexdigest()


def _anon_sanitize_url(url: Optional[str]) -> Optional[str]:
    """Drop query/fragment from a reported URL — query strings may carry PII."""
    if not url:
        return url
    return url.split("?", 1)[0].split("#", 1)[0]


@router.post(
    "/anonymous-error",
    response_model=AnonymousErrorReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def record_anonymous_error(
    body: AnonymousErrorReportRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db),
) -> AnonymousErrorReportResponse:
    """Record a PII-free fatal-error digest from an unauthenticated visitor.

    No authentication is required.  The request is rate-limited per IP
    (10/hour), the digest must match the URL-encoded shape built by
    ``error-reporting.ts`` (``buildReportDigest``), and the row is stored
    locally in ``anonymous_error_reports`` — never proxied to the support
    service.
    """
    # ── Rate limit (per IP, via the shared Redis/in-memory helper) ──────
    from backend.utils.rate_limit import check_rate_limit

    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For", "")
    real_ip = forwarded.split(",")[0].strip() or client_ip

    if not check_rate_limit(
        "support:anonymous-error", real_ip, _ANON_ERROR_MAX, _ANON_ERROR_WINDOW
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many error reports. Please try again later.",
            headers={"Retry-After": str(_ANON_ERROR_WINDOW)},
        )

    # ── Sanitize + persist ─────────────────────────────────────────────
    ip_hash = _anon_hash_ip(real_ip)
    url = _anon_sanitize_url(body.url)

    try:
        db.execute(
            """INSERT INTO anonymous_error_reports
               (digest, component_stack, url, ip_hash)
               VALUES (?, ?, ?, ?)""",
            (body.digest, body.component_stack, url, ip_hash),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record the error report.",
        )

    logger.info(
        "Anonymous error report recorded: ip_hash=%s… digest_bytes=%d",
        ip_hash[:8],
        len(body.digest),
    )
    return AnonymousErrorReportResponse(status="recorded")
