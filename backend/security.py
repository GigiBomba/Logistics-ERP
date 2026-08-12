"""Password hashing (bcrypt) and JWT encoding/decoding (PyJWT).

All functions are synchronous and thread-safe.  CPU-bound operations such as
``verify_password`` should be wrapped in ``loop.run_in_executor()`` when
called from async FastAPI handlers (see ``backend/api/v1/auth.py``).
"""

import base64
import hashlib
import hmac
import logging
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

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

    # A unique jti ensures every issued token differs even when issued in
    # the same second (also future-proofs revocation/blacklisting).
    to_encode.update({"exp": expire, "jti": secrets.token_hex(16)})
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


# ── TOTP (RFC 6238) — stdlib only ──────────────────────────────────────────

TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6


def generate_totp_secret(bits: int = 160) -> str:
    """Return a random base32 TOTP secret (padding stripped).

    160 bits = 32 base32 chars, the RFC 4226 recommended key size.
    """
    return base64.b32encode(secrets.token_bytes(bits // 8)).decode("ascii").rstrip("=")


def _b32decode(secret_b32: str) -> bytes:
    """Decode a (possibly unpadded) base32 string to raw bytes."""
    s = secret_b32.strip().upper().replace(" ", "")
    pad = "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s + pad)


def _hotp(secret_b32: str, counter: int, digits: int = TOTP_DIGITS) -> str:
    """RFC 4226 HOTP counter value — the building block of TOTP."""
    key = _b32decode(secret_b32)
    msg = struct.pack(">Q", counter & 0xFFFFFFFFFFFFFFFF)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def totp_code(secret_b32: str, at_time: Optional[float] = None) -> str:
    """Generate the current TOTP code (RFC 6238, 30s step, 6 digits)."""
    now = at_time if at_time is not None else time.time()
    return _hotp(secret_b32, int(now // TOTP_STEP_SECONDS))


def verify_totp(
    secret_b32: str,
    code: str,
    window_steps: int = 1,
    at_time: Optional[float] = None,
) -> bool:
    """Verify a TOTP *code* allowing ±*window_steps* 30-second steps.

    A window of 1 accepts codes valid for the current step plus the
    previous/next step (30s before / after), tolerating clock drift.
    """
    candidate = str(code).strip()
    if not candidate.isdigit():
        return False
    now = at_time if at_time is not None else time.time()
    step = int(now // TOTP_STEP_SECONDS)
    for delta in range(-window_steps, window_steps + 1):
        if hmac.compare_digest(_hotp(secret_b32, step + delta), candidate):
            return True
    return False


def build_otpauth_uri(email: str, secret_b32: str, issuer: str = "Operion") -> str:
    """Build an ``otpauth://`` provisioning URI for authenticator apps."""
    label = quote(f"{issuer}:{email}", safe="")
    return f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer, safe='')}"


# ── Field-level XOR encryption (MFA secrets at rest) ───────────────────────
# Simple, dependency-free obfuscation so TOTP secrets are never stored as
# plaintext in the DB. Not a replacement for real KMS encryption — the key
# comes from config (OPERION_MFA_SECRET_ENCRYPTION_KEY or the JWT secret).


def _xor_stream(plain: bytes, key: str) -> bytes:
    key_bytes = key.encode("utf-8")
    if not key_bytes:
        return plain
    stream = (key_bytes * (len(plain) // len(key_bytes) + 1))[:len(plain)]
    return bytes(a ^ b for a, b in zip(plain, stream))


def encrypt_at_rest(plaintext: str, key: str) -> str:
    """XOR-encrypt *plaintext* with *key*, base64-encoded for storage."""
    if not key:
        return plaintext
    return base64.b64encode(_xor_stream(plaintext.encode("utf-8"), key)).decode("ascii")


def decrypt_at_rest(ciphertext: Optional[str], key: str) -> str:
    """Decrypt a value produced by :func:`encrypt_at_rest`.

    Falls back to returning the raw value when no key is configured or the
    value is not base64 (e.g. legacy plaintext storage).
    """
    if not ciphertext:
        return ""
    if not key:
        return ciphertext
    try:
        raw = base64.b64decode(ciphertext.encode("ascii"), validate=True)
    except Exception:
        return ciphertext
    return _xor_stream(raw, key).decode("utf-8")
