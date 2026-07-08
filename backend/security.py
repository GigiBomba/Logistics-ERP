"""Password hashing (bcrypt) and JWT encoding/decoding (PyJWT).

All functions are synchronous and thread-safe.  CPU-bound operations such as
``verify_password`` should be wrapped in ``loop.run_in_executor()`` when
called from async FastAPI handlers (see ``backend/api/v1/auth.py``).
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from jwt.exceptions import PyJWTError

from backend.config import BackendSettings

logger = logging.getLogger(__name__)

# ── Password hashing (bcrypt) ─────────────────────────────────────────────────


def hash_password(password: str, rounds: Optional[int] = None) -> str:
    """Return a salted bcrypt hash of *password*.

    This function is used by the **one-time** ``hash_admin_password.py``
    script and should not be called at runtime from API handlers.
    """
    if rounds is None:
        rounds = BackendSettings().bcrypt_rounds
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=rounds),
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify *plain_password* against a bcrypt *hashed_password*.

    Returns ``True`` if the password matches the hash, ``False`` otherwise.
    This is a CPU-bound operation (~5-15 ms per call on modern hardware).
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as exc:
        logger.error("Password verification error: %s", exc)
        return False


# ── JWT token creation / decoding (PyJWT) ────────────────────────────────────


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Claims to encode (must include ``"sub"`` and ``"role"``).
        expires_delta: Token lifetime.  Defaults to the configured
                       ``access_token_expire_minutes``.

    Returns:
        The encoded JWT string.
    """
    settings = BackendSettings()
    to_encode: Dict[str, Any] = data.copy()

    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes,
        )

    to_encode.update({"exp": expire})
    encoded_jwt: bytes = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt.decode("utf-8")


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT string to decode.

    Returns:
        The decoded payload as a dictionary.

    Raises:
        PyJWTError: If the token is expired, malformed, or signature is invalid.
    """
    settings = BackendSettings()
    payload: Dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    return payload


# ── Refresh token ────────────────────────────────────────────────────────────


def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token.

    Returns a 128-character hex string (64 bytes of random data).
    This token is **not a JWT** — it is an opaque string stored on the
    server (in-memory dict or Redis) for later verification.
    """
    return secrets.token_hex(64)
