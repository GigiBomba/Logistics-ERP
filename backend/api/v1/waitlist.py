"""Waitlist API — public join + admin management.

POST /api/waitlist/join          — Public signup (Phase 1)
Admin endpoints come in Phase 2.
"""

import hashlib
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.dependencies import get_db
from backend.schemas.waitlist import WaitlistJoinRequest, WaitlistJoinResponse
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

# ── Rate limiting (waitlist-specific: 5 per IP per 10 min) ────────────
_waitlist_rate_limit: Dict[str, list] = {}
_WAITLIST_MAX = 5
_WAITLIST_WINDOW = 600  # 10 minutes

# Salt for IP hashing (generated once at module load)
_IP_SALT = os.environ.get("OPERION_IP_HASH_SALT", secrets.token_hex(16))


def _generate_referral_code(length: int = 8) -> str:
    """Generate a short unique referral code (alphanumeric, uppercase)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no confusing chars
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    attempts = _waitlist_rate_limit.get(ip, [])
    attempts = [t for t in attempts if now - t < _WAITLIST_WINDOW]
    if len(attempts) >= _WAITLIST_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again in a few minutes.",
            headers={"Retry-After": str(_WAITLIST_WINDOW)},
        )
    attempts.append(now)
    _waitlist_rate_limit[ip] = attempts


def _hash_ip(ip: str) -> str:
    """SHA-256 hash of IP with salt — never store raw IP."""
    return hashlib.sha256(f"{ip}:{_IP_SALT}".encode()).hexdigest()


# ── Phase 1: Public Join ──────────────────────────────────────────────

@router.post("/join", response_model=WaitlistJoinResponse, status_code=201)
def join_waitlist(
    data: WaitlistJoinRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Public waitlist signup — no authentication required."""

    # ── Honeypot check ─────────────────────────────────────────────────
    if data.hp_field:
        # Bot detected — fake success response, don't reveal it was caught
        logger.info("Waitlist honeypot triggered from IP: %s", 
                     request.client.host if request.client else "unknown")
        return {"status": "joined", "referral_code": "WLCM-" + secrets.token_hex(4).upper()}

    # ── Rate limit check ───────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Normalize email ────────────────────────────────────────────────
    email = data.email.strip().lower()

    # ── Check for duplicate email (case-insensitive) ───────────────────
    existing = db.execute(
        "SELECT id FROM waitlist_entries WHERE lower(email) = lower(?)",
        (email,),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You're already on the list — check your inbox for updates.",
        )

    # ── Generate unique referral code ──────────────────────────────────
    # Try up to 10 times to avoid collision (extremely unlikely with 8-char code)
    max_attempts = 10
    referral_code = ""
    for _ in range(max_attempts):
        candidate = _generate_referral_code()
        exists = db.execute(
            "SELECT id FROM waitlist_entries WHERE referral_code = ?",
            (candidate,),
        ).fetchone()
        if not exists:
            referral_code = candidate
            break
    if not referral_code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate referral code. Please try again.",
        )

    # ── Gather abuse-detection metadata ────────────────────────────────
    forwarded = request.headers.get("X-Forwarded-For", "")
    real_ip = forwarded.split(",")[0].strip() or client_ip
    ip_hash = _hash_ip(real_ip)
    user_agent = request.headers.get("User-Agent", "")[:300] or None

    # ── Insert row ─────────────────────────────────────────────────────
    try:
        db.execute(
            """INSERT INTO waitlist_entries 
               (company_name, contact_name, email, fleet_size, company_size,
                country, source, referral_code, ip_hash, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.company_name,
                data.contact_name,
                email,
                data.fleet_size,
                data.company_size,
                data.country.upper() if data.country else None,
                data.source,
                referral_code,
                ip_hash,
                user_agent,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signup failed. Please try again.",
        )

    logger.info(
        "Waitlist join: company='%s' email=%s source=%s code=%s",
        data.company_name, email, data.source, referral_code,
    )

    from backend.posthog_client import get_posthog
    _ph = get_posthog()
    if _ph:
        _ph.capture("waitlist_joined", distinct_id=email, properties={
            "$set": {"fleet_size": data.fleet_size, "company_size": data.company_size},
            "fleet_size": data.fleet_size,
            "company_size": data.company_size,
            "country": data.country,
            "source": data.source,
        })

    # ── TODO Phase 3: Enqueue Welcome email (async, not blocking) ──────
    # Email 1 trigger goes here once EmailProvider is built.

    return {"status": "joined", "referral_code": referral_code}
