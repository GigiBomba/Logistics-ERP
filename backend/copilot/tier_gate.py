"""Subscription Tier Gating — FastAPI dependency, not scattered if-checks.

Blueprint: §16
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, HTTPException


# ── Canonical tier features (single source of truth) ────────────────────────

TIER_FEATURES: Dict[str, Dict[str, Any]] = {
    "pro": {
        "utility_ai_only": True,
        "chat": False,
        "voice": False,
        "autonomous": False,
        "background_monitoring": False,
    },
    "business": {
        "utility_ai_only": False,
        "chat": True,
        "voice": True,
        "voice_activation": "push_to_talk",
        "autonomous": False,
        "background_monitoring": False,
        "monthly_quota": 300,
    },
    "enterprise": {
        "utility_ai_only": False,
        "chat": True,
        "voice": True,
        "voice_activation": "continuous_wake_word",
        "autonomous": True,
        "background_monitoring": True,
        "monthly_quota": 5000,
        "quota_enforcement": "soft",  # soft cap: exceeding alerts the team, does not 403 the customer
    },
}


def require_feature(feature: str):
    """FastAPI dependency: gate an endpoint behind a subscription tier feature flag.

    Usage:
        @router.post("/chat", dependencies=[Depends(require_feature("chat"))])
        async def chat(...): ...

    Blueprint: §16
    """
    async def dependency(
        # global_ctx: GlobalContext = Depends(get_global_context),
        # PHASE 0: skip actual dependency injection until Phase 1 router is built.
        # For now, this function exists as the contract.
    ) -> None:
        # Placeholder — Phase 1 will extract subscription_tier from GlobalContext
        # and check TIER_FEATURES[tier].get(feature).
        # For now, all features are effectively disabled (Phase 0 has no endpoints).
        pass

    return dependency


def get_quota_key(company_id: int) -> str:
    """Redis key for monthly quota tracking."""
    from datetime import datetime
    month = datetime.utcnow().strftime("%Y-%m")
    return f"quota:{company_id}:{month}"


def check_quota(company_id: int, tier: str) -> bool:
    """Check whether a company has remaining monthly quota.

    PHASE 0 STUB — always returns True. Phase 1 will increment/decrement Redis counter.
    """
    tier_config = TIER_FEATURES.get(tier, {})
    quota = tier_config.get("monthly_quota")
    if quota is None:
        return True

    # Phase 1: check Redis counter quota:{company_id}:{yyyy-mm}
    return True
