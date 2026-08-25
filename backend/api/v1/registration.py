"""Public registration endpoint — no authentication required.

POST /api/v1/registration/register — Create a new company + manager account.
"""
from __future__ import annotations


import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.dependencies import get_db
from backend.schemas.registration import RegistrationRequest
from backend.security import hash_password
from backend.api.v1.auth import _issue_tokens
from backend.db import DatabaseManager
from repositories.user_repository import UserRepository
from repositories.company_repository import CompanyRepository

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
    existing = UserRepository(db).get_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # ── Create company ────────────────────────────────────────────────
    try:
        company_id = CompanyRepository(db).create({
            "company_name": data.company_name,
            "subscription_tier": "starter",
            "is_active": 1,
        })

        # ── Hash password ─────────────────────────────────────────────
        hashed_pw = hash_password(data.password)

        # ── Create manager user ───────────────────────────────────────
        user_id = UserRepository(db).create_user(
            email=email,
            password_hash=hashed_pw,
            role="manager",
            display_name=data.display_name,
            company_id=company_id,
        )

        logger.info(
            "Registration: company='%s' (id=%d), manager='%s'",
            data.company_name, company_id, email,
        )

        # ── Issue tokens ──────────────────────────────────────────────
        tokens = _issue_tokens(email, "manager", response)
        tokens["user"] = {
            "id": user_id,
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
