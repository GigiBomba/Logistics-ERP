"""Public registration endpoint — no authentication required.

POST /api/v1/registration/register — Create a new company + manager account.
"""

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.dependencies import get_db
from backend.schemas.registration import RegistrationRequest
from backend.security import hash_password
from backend.api.v1.auth import _issue_tokens
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/registration", tags=["registration"])

# Rate limit: max 3 registration attempts per IP per 15 minutes
_register_rate_limit: Dict[str, list] = {}
_REGISTER_RATE_LIMIT = 3
_REGISTER_RATE_WINDOW = 900  # 15 minutes


def _clear_register_rate_limit() -> None:
    """Clear all registration rate-limit tracking (for testing)."""
    _register_rate_limit.clear()


def _check_register_rate_limit(ip: str) -> None:
    now = time.time()
    attempts = _register_rate_limit.get(ip, [])
    attempts = [t for t in attempts if now - t < _REGISTER_RATE_WINDOW]
    if len(attempts) >= _REGISTER_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
        )
    attempts.append(now)
    _register_rate_limit[ip] = attempts


@router.post("/register", status_code=201)
def register(
    data: RegistrationRequest,
    request: Request,
    response: Response,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new company and its first user (manager role).

    This is the self-service sign-up endpoint for the Operion website.
    No authentication is required.
    """
    email = data.email.strip().lower()

    # ── Rate limit check (per IP) ──────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_register_rate_limit(client_ip)

    # ── Check email uniqueness (global — one email = one account) ──────
    existing = db.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # ── Create company ────────────────────────────────────────────────
    try:
        cursor = db.execute(
            "INSERT INTO companies (company_name, subscription_tier, is_active) "
            "VALUES (?, 'starter', 1)",
            (data.company_name,),
        )
        company_id = cursor.lastrowid

        # ── Hash password ─────────────────────────────────────────────
        hashed_pw = hash_password(data.password)

        # ── Create manager user ───────────────────────────────────────
        cursor = db.execute(
            "INSERT INTO users (email, password_hash, role, company_id, "
            "display_name, is_active) "
            "VALUES (?, ?, 'manager', ?, ?, 1)",
            (email, hashed_pw, company_id, data.display_name),
        )
        db.commit()

        logger.info(
            "Registration: company='%s' (id=%d), manager='%s'",
            data.company_name, company_id, email,
        )

        from backend.posthog_client import get_posthog
        _ph = get_posthog()
        if _ph:
            _ph.capture("company_registered", distinct_id=email, properties={
                "$set": {"role": "manager"},
                "company_id": company_id,
                "signup_method": "self_service",
            })

        # ── Issue tokens ──────────────────────────────────────────────
        tokens = _issue_tokens(email, "manager", response)
        tokens["user"] = {
            "id": cursor.lastrowid,
            "email": email,
            "role": "manager",
            "company_id": company_id,
            "display_name": data.display_name,
            "company_name": data.company_name,
        }
        return tokens

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )
