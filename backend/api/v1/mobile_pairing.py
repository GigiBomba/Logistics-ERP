"""Mobile QR pairing-token endpoints (blueprint §5.3).

POST /api/v1/mobile/pairing-token          — issue a short-lived pairing token.
GET  /api/v1/mobile/pairing-token/validate — validate (and consume) a token.

The store mirrors the refresh-token store in ``backend/api/v1/auth.py``:
Redis is used when ``OPERION_REDIS_URL`` is configured, otherwise an
in-memory dict with an ``expires_at`` check provides the fallback.  Tokens
are single-use: a successful validation deletes the record.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.dependencies_security import get_current_user
from backend.errors import ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile/pairing-token", tags=["mobile-pairing"])

_env = os.environ.get("OPERION_ENV", "development")

# Pairing tokens are short-lived: the QR code is scanned within minutes.
PAIRING_TOKEN_TTL_SECONDS = 300

# ── Redis client (lazy, shared) ─────────────────────────────────────────
_redis_client: Optional[object] = None


def _get_redis():
    """Return a shared Redis client, or None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.environ.get("OPERION_REDIS_URL", "")
    redis_password = os.environ.get("OPERION_REDIS_PASSWORD", "")
    if not redis_url:
        return None
    try:
        import redis as _redis
        client = _redis.Redis.from_url(redis_url, socket_timeout=2, password=redis_password or None)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None  # don't retry every request
    return _redis_client


# ── Pairing token store ─────────────────────────────────────────────────
# In-memory dict keyed by SHA-256 hash of the pairing token.
# Falls back to in-memory if Redis is unavailable.
_pairing_store: Dict[str, Dict[str, Any]] = {}


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of *token*."""
    return hashlib.sha256(token.encode()).hexdigest()


def _store_pairing(token_hash: str, payload: Dict[str, Any]) -> None:
    """Store a pairing token (Redis preferred, in-memory fallback)."""
    r = _get_redis()
    if r is not None:
        try:
            r.setex(
                f"pairing:{token_hash}",
                PAIRING_TOKEN_TTL_SECONDS,
                json.dumps(payload),
            )
            return
        except Exception:
            if _env == "production":
                logger.error("Redis write failed in _store_pairing — falling back to in-memory.")
            else:
                logger.debug("Redis unavailable for pairing token store — using in-memory.")
    _pairing_store[token_hash] = payload


def _get_pairing(token_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve a stored pairing token payload."""
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(f"pairing:{token_hash}")
            if raw:
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse pairing token payload from Redis")
                    return None
            return None
        except Exception:
            if _env == "production":
                logger.error("Redis read failed in _get_pairing — falling back to in-memory.")
            else:
                logger.debug("Redis unavailable for pairing token lookup — using in-memory.")
    return _pairing_store.get(token_hash)


def _delete_pairing(token_hash: str) -> None:
    """Remove a pairing token (single-use / expiry cleanup)."""
    r = _get_redis()
    if r is not None:
        try:
            r.delete(f"pairing:{token_hash}")
            return
        except Exception:
            if _env == "production":
                logger.error("Redis delete failed in _delete_pairing — falling back to in-memory.")
    _pairing_store.pop(token_hash, None)


# ══════════════════════════════════════════════════════════════════════
#  Endpoints
# ══════════════════════════════════════════════════════════════════════


@router.post("")
def create_pairing_token(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Issue a short-lived, single-use pairing token for mobile QR login.

    The token is stored server-side with a 300s TTL and is consumed by the
    mobile device calling ``GET /validate``.
    """
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    now = time.time()
    expires_at = now + PAIRING_TOKEN_TTL_SECONDS
    company_id = current_user.get("company_id", 0)

    _store_pairing(token_hash, {
        "user_id": current_user["id"],
        "company_id": company_id,
        "created_at": now,
        "expires_at": expires_at,
    })

    return {
        "pairing_token": token,
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        "qr_data": f"operion://pair?token={token}&company={company_id}",
    }


@router.get("/validate")
def validate_pairing_token(
    token: str = Query(..., description="Pairing token from the scanned QR code"),
) -> Dict[str, Any]:
    """Validate a pairing token and consume it (single-use).

    Returns 404 for unknown or expired tokens — the mobile app cannot
    distinguish the two cases (anti-enumeration).
    """
    invalid = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": ErrorCode.TOKEN_INVALID.value,
            "detail": "Pairing token invalid or expired",
        },
    )

    if not token:
        raise invalid

    token_hash = _hash_token(token)
    payload = _get_pairing(token_hash)
    if payload is None:
        raise invalid

    expires_at: float = payload.get("expires_at", 0)
    if time.time() >= expires_at:
        _delete_pairing(token_hash)
        raise invalid

    # Consume the token — single use.
    _delete_pairing(token_hash)

    return {
        "valid": True,
        "user_id": payload.get("user_id"),
        "company_id": payload.get("company_id"),
        "expires_in": max(0, int(expires_at - time.time())),
    }
