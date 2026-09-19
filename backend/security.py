"""Password hashing (bcrypt) and JWT encoding/decoding (PyJWT).

All functions are synchronous and thread-safe.  CPU-bound operations such as
``verify_password`` should be wrapped in ``loop.run_in_executor()`` when
called from async FastAPI handlers (see ``backend/api/v1/auth.py``).
"""
from __future__ import annotations


import base64
import hashlib
import hmac
import logging
import os
import secrets
import struct
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from jwt.exceptions import PyJWTError

from backend.config import BackendSettings

logger = logging.getLogger(__name__)

# ── Password hashing (bcrypt) ─────────────────────────────────────────────────

# Phase F: single implementation lives in utils/security.py (the packaged
# desktop build ships no ``backend`` package but the local-first Team view
# hashes passwords).  Re-exported here so all server callers stay unchanged.
from utils.security import hash_password  # noqa: E402


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify *plain_password* against a bcrypt *hashed_password*.

    Returns ``True`` if the password matches the hash, ``False`` otherwise.
    This is a CPU-bound operation (~5-15 ms per call on modern hardware).

    Note: bcrypt has a 72-byte input limit.  Newer versions of the ``bcrypt``
    library raise an exception for passwords exceeding this limit instead of
    silently truncating.  We truncate to 72 bytes here to match the behavior
    that was used when the hash was originally created.
    """
    password_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(
            password_bytes,
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
# Used for MFA second-factor codes.  The secret is a 160-bit random value
# base32-encoded (20 bytes → 32 chars, unpadded), matching Google
# Authenticator / Authy conventions.  All comparisons are constant-time
# (``hmac.compare_digest``); the verification window is bounded by
# ``window_steps``.


def generate_totp_secret() -> str:
    """Generate a new random TOTP secret (20 bytes → unpadded base32)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def build_otpauth_uri(email: str, secret: str, issuer: str = "Operion") -> str:
    """Build an ``otpauth://totp/`` provisioning URI for the authenticator app.

    Format: ``otpauth://totp/Operion:<email>?secret=...&issuer=Operion&
    algorithm=SHA1&digits=6&period=30`` (standard RFC 6238 / Google
    Authenticator defaults).  The label is ``issuer:email`` per convention.
    """
    label = urllib.parse.quote(f"{issuer}:{email}", safe=":@")
    params = urllib.parse.urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": 6,
            "period": 30,
        }
    )
    return f"otpauth://totp/{label}?{params}"


def verify_totp(secret: str, code: str, window_steps: int = 1) -> bool:
    """Verify *code* against the current TOTP for *secret* (RFC 6238).

    Checks the current 30-second step plus ``window_steps`` steps of clock
    skew in each direction (a bounded window).  ``hmac.compare_digest``
    makes every comparison constant-time.  Returns ``False`` for malformed
    secrets/codes without raising.
    """
    if not secret or not code:
        return False
    try:
        key = base64.b32decode(secret.upper().encode("ascii"), casefold=True)
    except Exception:
        return False
    expected = code.strip()
    if not expected or len(expected) < 6 or len(expected) > 8:
        return False
    counter = int(time.time() // 30)
    for offset_step in range(-abs(window_steps), abs(window_steps) + 1):
        msg = struct.pack(">Q", counter + offset_step)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        trunc = struct.unpack(">I", digest[offset: offset + 4])[0] & 0x7FFFFFFF
        candidate = f"{trunc % 1_000_000:06d}"
        if hmac.compare_digest(candidate, expected):
            return True
    return False


# ── At-rest encryption (TOTP secrets etc.) — AES-256-GCM ──────────────────
# Scheme: ``AES-256-GCM`` (``cryptography.hazmat`` AESGCM).  The encryption
# key is derived from the caller-provided secret string via HKDF-SHA256
# (32-byte output, ``b"operion-at-rest-v1"`` info).  Every encryption uses a
# fresh random 12-byte nonce; the stored envelope is
# ``base64url(nonce || ciphertext || tag)`` (GCM appends the 16-byte tag to
# the ciphertext).  This is a real authenticated-encryption scheme — NOT a
# static XOR — and decryption fails loudly on tampering.
_AT_REST_INFO = b"operion-at-rest-v1"
_AT_REST_KEY_BYTES = 32
_AT_REST_NONCE_BYTES = 12


def _derive_at_rest_key(key: str) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(
        algorithm=hashes.SHA256(),
        length=_AT_REST_KEY_BYTES,
        salt=None,
        info=_AT_REST_INFO,
    ).derive(key.encode("utf-8"))


def encrypt_at_rest(plaintext: str, key: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM keyed by *key*.

    Returns a base64url envelope ``nonce || ciphertext || tag``.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(_derive_at_rest_key(key))
    nonce = os.urandom(_AT_REST_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_at_rest(ciphertext: str, key: str) -> str:
    """Decrypt an :func:`encrypt_at_rest` envelope.

    Raises ``cryptography.exceptions.InvalidTag`` (or ValueError for
    malformed envelopes) when the data is not authentic.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    nonce, payload = raw[:_AT_REST_NONCE_BYTES], raw[_AT_REST_NONCE_BYTES:]
    aesgcm = AESGCM(_derive_at_rest_key(key))
    return aesgcm.decrypt(nonce, payload, None).decode("utf-8")
