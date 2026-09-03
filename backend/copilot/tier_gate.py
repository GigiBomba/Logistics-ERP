"""Subscription Tier Gating — FastAPI dependency, not scattered if-checks.

Blueprint: §16
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from fastapi import Depends, HTTPException

logger = logging.getLogger(__name__)


# ── Canonical tier features (single source of truth) ────────────────────────

TIER_FEATURES: Dict[str, Dict[str, Any]] = {
    "pro": {
        "utility_ai_only": True,
        "chat": False,
        "help_mode": True,       # §33.4/§34.10 — Help Mode (docs + how-to) on every tier
        "voice": False,
        "autonomous": False,
        "background_monitoring": False,
    },
    "business": {
        "utility_ai_only": False,
        "chat": True,
        "help_mode": True,
        "voice": True,
        "voice_activation": "push_to_talk",
        "voice_activation_mobile": "push_to_talk",  # §16 — mobile push-to-talk
        "autonomous": False,
        "background_monitoring": False,
        "monthly_quota": 300,
    },
    "enterprise": {
        "utility_ai_only": False,
        "chat": True,
        "help_mode": True,
        "voice": True,
        "voice_activation": "continuous_wake_word",
        "voice_activation_mobile": "foreground_wake_word",  # §16 — mobile foreground wake word (enterprise-only)
        "autonomous": True,
        "background_monitoring": True,
        "monthly_quota": 5000,
        "quota_enforcement": "soft",  # soft cap: exceeding alerts the team, does not 403 the customer
    },
}

# Canonical DB tiers are 'starter' | 'professional' | 'enterprise' (see the
# companies CHECK constraints); the legacy 'pro' / 'business' values are
# accepted too.  Normalise onto the TIER_FEATURES keys.
_TIER_NORMALIZATION = {
    "starter": "pro",
    "pro": "pro",
    "professional": "business",
    "business": "business",
    "enterprise": "enterprise",
}


def _normalize_tier(tier: str) -> str:
    """Map a DB tier value onto the canonical TIER_FEATURES keys."""
    return _TIER_NORMALIZATION.get(tier, tier)


def has_feature(tier: str, feature: str) -> bool:
    """Pure check whether a subscription *tier* enables *feature*.

    The FastAPI dependency (:func:`require_feature`) is the authoritative gate
    for endpoints; this helper is for checks that happen inside the pipeline
    (e.g. the planner deciding whether autonomous execution is allowed for the
    caller's tier).  Admins bypass tier gating everywhere, so no admin special
    case is needed here — the endpoint-level dependency already handled it.
    """
    tier = _normalize_tier(str(tier or ""))
    tier_config = TIER_FEATURES.get(tier, {})
    return bool(tier_config.get(feature))


def require_feature(feature: str):
    """FastAPI dependency: gate an endpoint behind a subscription tier feature flag.

    Usage:
        @router.post("/chat", dependencies=[Depends(require_feature("chat"))])
        async def chat(...): ...

    Resolves the authenticated user (JWT → subscription_tier), normalises the
    tier, and rejects the request with 403 when the tier lacks *feature*.
    Admins bypass tier gating (operational access).  Quota is enforced for
    non-soft tiers via the Redis monthly counter.

    Blueprint: §16
    """
    from backend.dependencies_security import get_current_user

    async def dependency(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> None:
        # Admins bypass subscription-tier gating (operational access).
        if current_user.get("is_admin") or current_user.get("role") == "admin":
            return

        tier = _normalize_tier(str(current_user.get("subscription_tier", "") or ""))
        tier_config = TIER_FEATURES.get(tier, {})
        if not tier_config.get(feature):
            raise HTTPException(
                status_code=403,
                detail={"message_key": "copilot.error.feature_not_in_tier"},
            )
        if not await asyncio.to_thread(check_quota, current_user.get("company_id", 0), tier):
            raise HTTPException(
                status_code=429,
                detail={"message_key": "copilot.error.quota_exceeded"},
            )

    return dependency


def require_any_feature(*features: str):
    """FastAPI dependency: allow when the tier enables ANY of *features*.

    Used for endpoints that are reachable through more than one feature —
    e.g. /chat is gated on ``chat`` OR ``help_mode`` (§16, §33.4): Pro tiers
    lack ``chat`` but get Help Mode access.  Quota is still enforced for
    non-soft tiers when the company has a ``monthly_quota``.
    """
    from backend.dependencies_security import get_current_user

    async def dependency(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> None:
        if current_user.get("is_admin") or current_user.get("role") == "admin":
            return
        tier = _normalize_tier(str(current_user.get("subscription_tier", "") or ""))
        tier_config = TIER_FEATURES.get(tier, {})
        if not any(tier_config.get(f) for f in features):
            raise HTTPException(
                status_code=403,
                detail={"message_key": "copilot.error.feature_not_in_tier"},
            )
        if not await asyncio.to_thread(check_quota, current_user.get("company_id", 0), tier):
            raise HTTPException(
                status_code=429,
                detail={"message_key": "copilot.error.quota_exceeded"},
            )

    return dependency


def get_quota_key(company_id: int) -> str:
    """Redis key for monthly quota tracking."""
    from datetime import datetime
    month = datetime.utcnow().strftime("%Y-%m")
    return f"quota:{company_id}:{month}"


def check_quota(company_id: int, tier: str) -> bool:
    """Check whether a company has remaining monthly quota.

    Reads the Redis counter (``quota:{company_id}:{yyyy-mm}``); when no
    counter exists the company has used nothing.  Tiers without a
    ``monthly_quota`` (unlimited) or with ``quota_enforcement == "soft"``
    (enterprise) are never blocked.  Fallback: if the cache is unreachable,
    the check is open (fail-open so a Redis blip never 403s paying users).
    """
    tier_config = TIER_FEATURES.get(tier, {})
    quota = tier_config.get("monthly_quota")
    if quota is None:
        return True
    if tier_config.get("quota_enforcement") == "soft":
        return True

    try:
        from backend.cache import get_cache
        used = get_cache().get(get_quota_key(company_id))
        try:
            used_int = int(used or 0)
        except (TypeError, ValueError):
            used_int = 0
        return used_int < int(quota)
    except Exception:
        logger.debug("Quota check failed open (cache unavailable)", exc_info=True)
        return True


def record_usage(company_id: int, amount: int = 1) -> None:
    """Increment the monthly usage counter for a company (best-effort).

    Called after a chat/voice turn so the monthly quota counter reflects real
    consumption.  A long TTL (31 days) keeps the counter alive for the month.
    """
    try:
        from backend.cache import get_cache
        key = get_quota_key(company_id)
        cache = get_cache()
        used = cache.get(key)
        try:
            used_int = int(used or 0)
        except (TypeError, ValueError):
            used_int = 0
        cache.set(key, used_int + amount, ttl=31 * 86400)
    except Exception:
        logger.debug("Quota usage increment skipped", exc_info=True)