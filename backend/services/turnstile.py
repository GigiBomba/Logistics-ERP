"""Cloudflare Turnstile server-side verification.

Public endpoints (waitlist, registration, contact, newsletter subscribe,
login) accept an optional ``turnstile_token``.  This module validates that
token against Cloudflare's siteverify API and exposes a guard helper.

VERIFICATION POLICY (deliberate decision — audit F15):

* **Token present → always verify.**  A token we cannot prove valid is
  never trusted: invalid tokens are rejected with HTTP 400, and if the
  secret key is unconfigured we *fail closed* (log a warning + reject)
  rather than silently accept.  Failing open on an unverifiable token
  would render Turnstile meaningless.
* **Token absent → pass through by default.**  Existing Operion desktop /
  mobile ERP clients do not render a Turnstile widget and can never send
  a token; rejecting them would break launch.  Set ``REQUIRE_TURNSTILE=1``
  to flip these endpoints to fail-closed for missing tokens.  The audit
  recommends enabling that enforcement post-launch once all web flows
  ship the widget.
"""
from __future__ import annotations


import logging
import os
from typing import Any, Dict, Optional

import requests

from backend.config import BackendSettings

logger = logging.getLogger(__name__)

_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TIMEOUT_SECONDS = 5


def require_turnstile(token: Optional[str], remote_ip: Optional[str] = None) -> None:
    """Guard helper for public endpoints.

    Raises HTTP 400 when the request must be rejected:

    * a token was provided but failed verification (or the secret is
      missing → fail closed), or
    * no token was provided AND ``REQUIRE_TURNSTILE=1`` enforcement is on.

    Returns silently otherwise (backward-compatible pass-through for
    desktop/mobile clients that cannot render a widget).
    """
    # Imported lazily so this module stays importable outside FastAPI
    # contexts (e.g. scripts, Celery tasks).
    from fastapi import HTTPException

    if not token:
        if os.environ.get("REQUIRE_TURNSTILE", "0") == "1":
            logger.warning(
                "Turnstile token missing and REQUIRE_TURNSTILE is set — rejecting request."
            )
            raise HTTPException(
                status_code=400, detail="Turnstile verification failed"
            )
        return

    settings = BackendSettings()
    secret = settings.turnstile_secret_key or ""

    if not secret:
        # Fail closed: a token we cannot verify must never be accepted.
        logger.warning(
            "Turnstile secret key is not configured "
            "(TURNSTILE_SECRET_KEY / OPERION_TURNSTILE_SECRET_KEY) — "
            "refusing to accept a Turnstile token."
        )
        raise HTTPException(status_code=400, detail="Turnstile verification failed")

    form: Dict[str, Any] = {"secret": secret, "response": token}
    if remote_ip:
        form["remoteip"] = remote_ip

    try:
        resp = requests.post(_SITEVERIFY_URL, data=form, timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # network errors, HTTP errors, bad JSON
        logger.warning("Turnstile siteverify request failed: %s", exc)
        raise HTTPException(status_code=400, detail="Turnstile verification failed")

    if not payload.get("success"):
        logger.warning(
            "Turnstile verification failed: %s", payload.get("error-codes")
        )
        raise HTTPException(status_code=400, detail="Turnstile verification failed")
