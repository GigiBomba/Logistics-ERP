"""Contact API — public contact form submissions.

POST /api/v1/contact  — Public contact form (Phase 1)
Admin/read endpoints come in Phase 2.
"""
from __future__ import annotations


import hashlib
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.dependencies import get_db
from backend.schemas.contact import ContactRequest, ContactResponse
from backend.services.email_provider import get_email_provider
from backend.services.turnstile import require_turnstile
from backend.utils.rate_limit import check_rate_limit
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact", tags=["contact"])

# ── Rate limiting (contact-specific: 3 per IP per 10 min) ────────────
# Redis-backed across workers (backend/utils/rate_limit.py); in-memory
# fallback when Redis is unavailable.
_CONTACT_MAX = 3
_CONTACT_WINDOW = 600  # 10 minutes

# Salt for IP hashing (generated once at module load)
_IP_SALT = os.environ.get("OPERION_IP_HASH_SALT", secrets.token_hex(16))


def _check_rate_limit(ip: str) -> None:
    if not check_rate_limit("contact", _hash_ip(ip), _CONTACT_MAX, _CONTACT_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages. Please try again in a few minutes.",
            headers={"Retry-After": str(_CONTACT_WINDOW)},
        )


def _hash_ip(ip: str) -> str:
    """SHA-256 hash of IP with salt — never store raw IP."""
    return hashlib.sha256(f"{ip}:{_IP_SALT}".encode()).hexdigest()


# ── Phase 1: Public contact form ──────────────────────────────────────

@router.post("", response_model=ContactResponse, status_code=201)
def submit_contact(
    data: ContactRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Public contact form submission — no authentication required."""

    # ── Honeypot check ─────────────────────────────────────────────────
    if data.hp_field:
        # Bot detected — fake success response, don't reveal it was caught
        logger.info("Contact honeypot triggered from IP: %s",
                    request.client.host if request.client else "unknown")
        return {"status": "received"}

    # ── Turnstile validation (bot protection) ─────────────────────────────
    # Validated when a token is present; pass-through when absent unless
    # REQUIRE_TURNSTILE=1 is set (see backend.services.turnstile).
    require_turnstile(
        data.turnstile_token,
        request.client.host if request.client else None,
    )

    # ── Rate limit check ───────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Normalize email ────────────────────────────────────────────────
    email = data.email.strip().lower()

    # ── Gather abuse-detection metadata ────────────────────────────────
    forwarded = request.headers.get("X-Forwarded-For", "")
    real_ip = forwarded.split(",")[0].strip() or client_ip
    ip_hash = _hash_ip(real_ip)

    # ── Insert row (duplicate detection is NOT needed) ─────────────────
    try:
        db.conn.execute(
            """INSERT INTO contact_messages
               (name, email, subject, message, source_ip)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data.name.strip(),
                email,
                data.subject.strip(),
                data.message.strip(),
                ip_hash,
            ),
        )
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Message could not be sent. Please try again.",
        )

    logger.info(
        "Contact message: name='%s' email=%s subject='%s'",
        data.name, email, data.subject,
    )

    # ── Forward message to support inbox (best-effort) ────────────────────
    # LoggingEmailProvider logs everything in dev; ResendProvider delivers in
    # production. ResendProvider renders the body from variables["body"] (or
    # variables["html"]), so build the plain-text body here. Email failure
    # never fails the client request.
    try:
        body = (
            "New contact message\n"
            f"From: {data.name.strip()} <{email}>\n"
            f"Subject: {data.subject.strip()}\n\n"
            f"{data.message.strip()}"
        )
        get_email_provider().send(
            to="support@operionerp.xyz",
            template_id="contact-message",
            variables={
                "name": data.name.strip(),
                "email": email,
                "subject": data.subject.strip(),
                "message": data.message.strip(),
                "body": body,
            },
        )
    except Exception:
        logger.exception(
            "Contact message stored, but email forwarding to support failed."
        )

    return {"status": "received"}
