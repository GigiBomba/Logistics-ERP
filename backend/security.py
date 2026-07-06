"""Password hashing (passlib/bcrypt) and JWT encoding/decoding (python-jose).

All functions are synchronous and thread-safe.  CPU-bound operations such as
``verify_password`` should be wrapped in ``loop.run_in_executor()`` when
called from async FastAPI handlers (see ``backend/api/v1/auth.py``).
"""

import logging
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

from backend.config import BackendSettings

logger = logging.getLogger(__name__)

# ── Suppress noisy passlib/bcrypt compatibility warnings ─────────────────────
# Passlib 1.7.4 + bcrypt >= 4.1 emits an AttributeError during backend probe
# but falls back to a working backend.  The warning is harmless.
warnings.filterwarnings("ignore", message="error reading bcrypt version")
warnings.filterwarnings("ignore", category=UserWarning, module="passlib")

# ── Password hashing (bcrypt via passlib) ─────────────────────────────────────

_pctx = CryptContext(schemes=["bcrypt"])


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of *password*.

    This function is used by the **one-time** ``hash_admin_password.py``
    script and should not be called at runtime from API handlers.
    """
    return _pctx.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify *plain_password* against a bcrypt *hashed_password*.

    Returns ``True`` if the password matches the hash, ``False`` otherwise.
    This is a CPU-bound operation (~5-15 ms per call on modern hardware).
    """
    try:
        return _pctx.verify(plain_password, hashed_password)
    except Exception as exc:
        logger.error("Password verification error: %s", exc)
        return False


# ── JWT token creation / decoding (python-jose) ──────────────────────────────


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
    encoded_jwt: str = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT string to decode.

    Returns:
        The decoded payload as a dictionary.

    Raises:
        JWTError: If the token is expired, malformed, or signature is invalid.
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
