"""Signed short-lived download tokens for the Local Download manifest.

Implements blueprint §5.3: the manifest never returns raw file bytes — it
returns ``download_url`` values carrying an HMAC-signed token over
``{record_id, company_id, kind, expiry}``.  The companion fetch endpoint
re-validates the signature, the expiry, and (critically) that the JWT's
``company_id`` equals the token's embedded ``company_id`` **at fetch time** —
a signed URL is still tenant-checked, never trusted on its own.

Key material follows the repo's existing pydantic-settings pattern
(``BackendSettings``); ``local_download_token_secret`` defaults to the
JWT secret so single-secret deployments keep working out of the box.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.config import BackendSettings

# Record kinds that can be embedded in a download token.
KIND_DOCUMENT = "document"
KIND_TRIP = "trip"
KIND_EXPORT_FILE = "export_file"


def _signing_secret() -> bytes:
    """Return the HMAC key material (explicit secret or JWT fallback)."""
    settings = BackendSettings()
    secret = settings.local_download_token_secret or settings.jwt_secret_key
    return secret.encode("utf-8")


def download_token_ttl_seconds() -> int:
    """Return the configured token lifetime (default 15 minutes)."""
    return BackendSettings().local_download_token_ttl_seconds


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_download_token(
    record_id: Any,
    company_id: Any,
    kind: str,
    expires_at: Optional[datetime] = None,
) -> str:
    """Build a signed token ``base64url(payload).signature``.

    Payload claims: ``record_id`` (str), ``company_id`` (int),
    ``kind`` (document|trip), ``exp`` (ISO-8601 UTC).
    """
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=download_token_ttl_seconds(),
        )
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    payload: Dict[str, Any] = {
        "record_id": str(record_id),
        "company_id": int(company_id),
        "kind": kind,
        "exp": expires_at.isoformat(),
    }
    encoded = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_signing_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_download_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a download token's signature and return its payload.

    Returns ``None`` for any invalid/malformed/tampered token.  Expiry is
    checked by the caller (it needs to distinguish "expired" for a 403 vs.
    a malformed token).
    """
    try:
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(
            _signing_secret(), encoded.encode("ascii"), hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
        if not all(k in payload for k in ("record_id", "company_id", "kind", "exp")):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def is_token_expired(payload: Dict[str, Any]) -> bool:
    """Return ``True`` when the token's ``exp`` claim is in the past."""
    try:
        exp = datetime.fromisoformat(payload["exp"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp
    except (ValueError, TypeError, KeyError):
        # Malformed expiry → fail closed (treat as expired).
        return True
