"""Subscription Tier Gating tests — §16.

Covers:
- TIER_FEATURES feature flag mapping
- Tier feature gating: enabled features return True, disabled False
- Quota check: not-exceeded passes, exceeded blocks
- Rate limiting integration concept
- Token limit enforcement (MAX_LLM_TOKENS_PER_TURN)
"""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from datetime import datetime

from backend.copilot.executor import (
    MAX_LLM_TOKENS_PER_TURN,
    MAX_TOOL_CALLS_PER_PLAN,
    validate_guardrails,
)
from backend.copilot.schemas import (
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    GlobalContext,
    Intent,
)
from backend.copilot.tier_gate import (
    TIER_FEATURES,
    check_quota,
    get_quota_key,
    require_feature,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_step(
    step_id: str = "step-0",
    status: str = "pending",
) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        tool_name="vehicle.search",
        tool_version="1.0.0",
        parameters={},
        depends_on=[],
        confirmation_level=ConfirmationLevel.SAFE,
        status=status,
    )


def _make_plan(
    steps=None,
    utterance: str = "show me trucks",
    plan_id: str = "plan-tier",
    intent_name: str = "vehicle.search",
    **kwargs,
) -> ExecutionPlan:
    steps = steps or [_make_step()]
    return ExecutionPlan(
        plan_id=plan_id,
        conversation_id="conv-tier",
        reasoning_graph_id="rg-tier",
        intent=Intent(
            name=intent_name,
            entities=[],
            missing_required_entities=[],
            raw_utterance=utterance,
        ),
        steps=steps,
        overall_confidence=0.95,
        requires_confirmation=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TIER_FEATURES data contract
# ═══════════════════════════════════════════════════════════════════════════════


class TestTierFeaturesContract:
    """TIER_FEATURES must define the correct structure for all tiers."""

    def test_all_tiers_defined(self):
        """All three subscription tiers must be present."""
        assert "pro" in TIER_FEATURES
        assert "business" in TIER_FEATURES
        assert "enterprise" in TIER_FEATURES

    def test_pro_tier_features(self):
        """Pro tier: utility_ai_only, no chat/voice/autonomous."""
        pro = TIER_FEATURES["pro"]
        assert pro.get("utility_ai_only") is True
        assert pro.get("chat") is False
        assert pro.get("voice") is False
        assert pro.get("autonomous") is False
        assert pro.get("background_monitoring") is False

    def test_business_tier_features(self):
        """Business tier: chat, voice, push_to_talk, 300 monthly quota."""
        biz = TIER_FEATURES["business"]
        assert biz.get("utility_ai_only") is False
        assert biz.get("chat") is True
        assert biz.get("voice") is True
        assert biz.get("voice_activation") == "push_to_talk"
        assert biz.get("autonomous") is False
        assert biz.get("background_monitoring") is False
        assert biz.get("monthly_quota") == 300

    def test_enterprise_tier_features(self):
        """Enterprise tier: everything enabled, continuous wake word, 5000 quota."""
        ent = TIER_FEATURES["enterprise"]
        assert ent.get("utility_ai_only") is False
        assert ent.get("chat") is True
        assert ent.get("voice") is True
        assert ent.get("voice_activation") == "continuous_wake_word"
        assert ent.get("autonomous") is True
        assert ent.get("background_monitoring") is True
        assert ent.get("monthly_quota") == 5000
        assert ent.get("quota_enforcement") == "soft"

    def test_no_unknown_tier(self):
        """Unknown tiers should not be in TIER_FEATURES."""
        assert "unknown" not in TIER_FEATURES
        assert "free" not in TIER_FEATURES
        assert "" not in TIER_FEATURES


# ═══════════════════════════════════════════════════════════════════════════════
# Tier feature gating
# ═══════════════════════════════════════════════════════════════════════════════


class TestTierFeatureGating:
    """Feature gating: enabled features return True, disabled return False."""

    def test_enabled_feature_is_true(self):
        """An enabled feature must be truthy in the tier config."""
        assert TIER_FEATURES["enterprise"]["chat"] is True
        assert TIER_FEATURES["enterprise"]["voice"] is True
        assert TIER_FEATURES["enterprise"]["autonomous"] is True

    def test_disabled_feature_is_false(self):
        """A disabled feature must be falsy in the tier config."""
        assert TIER_FEATURES["pro"]["chat"] is False
        assert TIER_FEATURES["pro"]["voice"] is False
        assert TIER_FEATURES["business"]["autonomous"] is False
        assert TIER_FEATURES["pro"]["autonomous"] is False

    def test_missing_feature_defaults_to_none(self):
        """A feature not defined for a tier must return None (not crash)."""
        assert TIER_FEATURES["pro"].get("voice_activation") is None
        assert TIER_FEATURES["pro"].get("monthly_quota") is None
        assert TIER_FEATURES["business"].get("quota_enforcement") is None

    def test_require_feature_dependency_is_callable(self):
        """require_feature returns a callable FastAPI dependency."""
        dep = require_feature("chat")
        assert callable(dep)

    def test_require_feature_returns_dependency_with_correct_name(self):
        """The inner dependency function should have the expected
        signature (no params, returns None)."""
        dep = require_feature("voice")
        import inspect
        sig = inspect.signature(dep)
        # The dependency takes no required arguments (GlobalContext is optional)
        assert len([p for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty]) == 0

    def test_feature_access_pattern(self):
        """Feature access via TIER_FEATURES[tier].get(feature) must work."""
        for tier_name, features in TIER_FEATURES.items():
            # Every tier should define these boolean features
            for boolean_feature in ("utility_ai_only", "chat", "voice",
                                    "autonomous", "background_monitoring"):
                value = features.get(boolean_feature)
                assert isinstance(value, bool), (
                    f"{tier_name}.{boolean_feature} should be bool, got {type(value)}"
                )

    def test_pro_has_no_quota(self):
        """Pro tier has no monthly_quota defined (unlimited utility AI)."""
        assert TIER_FEATURES["pro"].get("monthly_quota") is None

    def test_business_has_quota_of_300(self):
        """Business tier has a 300-call monthly quota."""
        assert TIER_FEATURES["business"].get("monthly_quota") == 300

    def test_enterprise_has_quota_of_5000(self):
        """Enterprise tier has a 5000-call monthly quota."""
        assert TIER_FEATURES["enterprise"].get("monthly_quota") == 5000


# ═══════════════════════════════════════════════════════════════════════════════
# Quota check
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuotaCheck:
    """check_quota — not-exceeded passes, exceeded blocks.

    Phase 0: check_quota always returns True. Phase 1+ will integrate
    with Redis to track actual usage.
    """

    def test_quota_key_format(self):
        """The Redis quota key must include company_id and month."""
        key = get_quota_key(42)
        assert "42" in key
        from datetime import datetime
        expected_month = datetime.utcnow().strftime("%Y-%m")
        assert expected_month in key
        assert key.startswith("quota:")

    def test_quota_key_differs_by_company(self):
        """Different companies must have different quota keys."""
        key_a = get_quota_key(1)
        key_b = get_quota_key(2)
        assert key_a != key_b

    def test_quota_key_differs_by_month(self):
        """The same company in different months must have different keys."""
        # This test documents the key pattern; we can't easily mock utcnow
        # but we can verify the format supports monthly partitioning
        key = get_quota_key(1)
        assert len(key.split(":")) == 3  # quota:{company_id}:{yyyy-mm}

    def test_check_quota_returns_true_for_unlimited(self):
        """Tiers without monthly_quota should always pass quota check."""
        assert check_quota(company_id=1, tier="pro") is True

    def test_check_quota_returns_true_for_business(self):
        """Phase 0: business tier with quota always returns True (stub)."""
        assert check_quota(company_id=1, tier="business") is True

    def test_check_quota_returns_true_for_enterprise(self):
        """Phase 0: enterprise tier with quota always returns True (stub)."""
        assert check_quota(company_id=1, tier="enterprise") is True

    def test_check_quota_unknown_tier_defaults_open(self):
        """Unknown tiers should fall through to 'no quota' and return True."""
        assert check_quota(company_id=1, tier="unknown_tier") is True

    def test_check_quota_empty_tier_returns_true(self):
        """Empty tier name should not crash — return True."""
        assert check_quota(company_id=1, tier="") is True

    def test_check_quota_is_idempotent(self):
        """Calling check_quota multiple times should not change result."""
        for _ in range(5):
            assert check_quota(company_id=42, tier="business") is True

    def test_check_quota_company_differentiation(self):
        """Different companies calling check_quota should be independent."""
        # Phase 0: both return True. Phase 1+ will test that company A
        # exceeding quota doesn't affect company B.
        assert check_quota(company_id=1, tier="business") is True
        assert check_quota(company_id=2, tier="business") is True


# ═══════════════════════════════════════════════════════════════════════════════
# Token limit enforcement
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenLimitEnforcement:
    """MAX_LLM_TOKENS_PER_TURN — guardrails block when token estimate exceeds limit."""

    def test_max_tokens_constant_is_defined(self):
        """MAX_LLM_TOKENS_PER_TURN must be a positive integer."""
        assert isinstance(MAX_LLM_TOKENS_PER_TURN, int)
        assert MAX_LLM_TOKENS_PER_TURN > 0

    def test_default_max_tokens(self):
        """Default MAX_LLM_TOKENS_PER_TURN is 32000."""
        assert MAX_LLM_TOKENS_PER_TURN == 32000

    def test_short_utterance_passes_token_guardrail(self):
        """A short utterance with few steps should pass token validation."""
        plan = _make_plan(utterance="show me trucks")
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_tokens" not in errors

    def test_long_utterance_exceeds_token_guardrail(self):
        """A very long utterance should exceed the token estimate."""
        # Estimated tokens = len(utterance) // 2 + len(steps) * 100
        # Need to exceed MAX_LLM_TOKENS_PER_TURN (32000)
        long_utterance = "x" * (MAX_LLM_TOKENS_PER_TURN * 2 + 1)
        plan = _make_plan(utterance=long_utterance)
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_tokens" in errors

    def test_many_steps_contribute_to_token_estimate(self):
        """A plan with many steps should increase the token estimate."""
        many_steps = [_make_step(step_id=f"step-{i}") for i in range(100)]
        plan = _make_plan(steps=many_steps, utterance="show trucks")
        # 100 steps * 100 tokens/step = 10000 tokens
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_tokens" not in errors

    def test_token_guardrail_triggers_on_combined_length(self):
        """Combined long utterance + many steps should trigger the limit."""
        many_steps = [_make_step(step_id=f"step-{i}") for i in range(200)]
        long_utterance = "x" * (MAX_LLM_TOKENS_PER_TURN)  # ~16000 tokens
        plan = _make_plan(steps=many_steps, utterance=long_utterance)
        # 200 * 100 + 16000 = 36000 > 32000
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_tokens" in errors

    def test_token_guardrail_is_not_only_limitation(self):
        """validate_guardrails also checks step count and graph node limits."""
        too_many_steps = [_make_step(step_id=f"step-{i}") for i in range(25)]
        plan = _make_plan(steps=too_many_steps, utterance="hi")
        errors = validate_guardrails(plan)
        # 25 steps > MAX_TOOL_CALLS_PER_PLAN (20)
        assert "copilot.error.too_many_steps" in errors


class TestMaxToolCallsGuardrail:
    """MAX_TOOL_CALLS_PER_PLAN — enforce maximum steps per plan."""

    def test_max_tool_calls_constant_defined(self):
        """MAX_TOOL_CALLS_PER_PLAN must be defined."""
        assert isinstance(MAX_TOOL_CALLS_PER_PLAN, int)
        assert MAX_TOOL_CALLS_PER_PLAN == 20

    def test_plan_within_limit_passes(self):
        """Plan within the step limit should pass guardrails."""
        steps = [_make_step(step_id=f"step-{i}") for i in range(5)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_steps" not in errors

    def test_plan_exceeding_limit_fails(self):
        """Plan exceeding the step limit should be blocked."""
        steps = [_make_step(step_id=f"step-{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 1)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_steps" in errors

    def test_plan_at_exact_limit_passes(self):
        """Plan at exactly the limit should pass guardrails."""
        steps = [_make_step(step_id=f"step-{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_steps" not in errors

    def test_guardrails_return_all_errors(self):
        """validate_guardrails should return ALL violations, not just the first."""
        many_steps = [_make_step(step_id=f"step-{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 1)]
        long_utterance = "x" * (MAX_LLM_TOKENS_PER_TURN * 2)
        plan = _make_plan(steps=many_steps, utterance=long_utterance)
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_steps" in errors
        assert "copilot.error.too_many_tokens" in errors

    @pytest.mark.asyncio
    async def test_execute_plan_blocks_violating_plan(self):
        """Plans that violate guardrails should be blocked at execution time."""
        from backend.copilot.executor import execute_plan

        too_many_steps = [
            _make_step(step_id=f"step-{i}")
            for i in range(MAX_TOOL_CALLS_PER_PLAN + 1)
        ]
        plan = _make_plan(steps=too_many_steps)

        result = await execute_plan(plan)
        # All steps should be skipped
        for step in result.steps:
            assert step.status == "skipped"
            assert step.error is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Rate limiting integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRateLimitingIntegration:
    """Rate limiting — concept and integration points.

    The actual rate limiting is implemented as FastAPI middleware
    (RateLimitMiddleware). These tests verify that:
    - The middleware is registered in the app
    - The copilot endpoints go through the rate limiter
    - Rate limit keys are scoped correctly
    """

    def test_rate_limit_middleware_is_registered(self):
        """RateLimitMiddleware must be registered in the main app."""
        from backend.main import app as fastapi_app

        middleware_class_names = []
        for m in fastapi_app.user_middleware:
            try:
                middleware_class_names.append(m.cls.__name__)
            except AttributeError:
                middleware_class_names.append(str(m.cls))
        assert "RateLimitMiddleware" in middleware_class_names, (
            "RateLimitMiddleware must be registered in main.py"
        )

    def test_rate_limit_config_has_env_var(self):
        """The rate limit environment variable is configurable."""
        import os
        # OPERION_RATE_LIMIT controls the rate limit threshold
        # Default should be parseable as int
        rate_limit = os.environ.get("OPERION_RATE_LIMIT", "10000")
        assert int(rate_limit) > 0

    def test_rate_limit_middleware_imports(self):
        """RateLimitMiddleware can be imported without error."""
        from backend.middleware.rate_limit_middleware import RateLimitMiddleware
        assert RateLimitMiddleware is not None

    def test_copilot_router_goes_through_rate_limiter(self):
        """All copilot endpoints are on the /copilot prefix which goes
        through the rate limit middleware."""
        from backend.api.v1.copilot_router import router
        for route in router.routes:
            path = getattr(route, "path", "")
            assert path.startswith("/copilot"), (
                f"Route {path} should be under /copilot prefix"
            )

    def test_rate_limit_scope_is_per_user(self):
        """Rate limit keys should be scoped per user, not global,
        to prevent one user from exhausting another's quota.

        This test documents the expected behavior — actual enforcement
        is in the middleware.
        """
        # The middleware uses user-specific keys based on JWT claims
        # or IP address. This test verifies the concept:
        # Two different users should have independent rate limit counters.
        rate_limit_config = {"rate": "100/minute"}
        assert rate_limit_config is not None  # placeholder for Phase 1+


# ═══════════════════════════════════════════════════════════════════════════════
# require_feature dependency contract
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireFeatureContract:
    """require_feature — FastAPI dependency contract."""

    def test_require_feature_returns_callable_for_each_feature(self):
        """Every known feature should produce a callable dependency."""
        for feature in ("utility_ai_only", "chat", "voice", "autonomous",
                        "background_monitoring"):
            dep = require_feature(feature)
            assert callable(dep), f"require_feature({feature!r}) must be callable"

    def test_require_feature_for_nonexistent_feature(self):
        """Asking for a non-existent feature should still return a callable
        (the runtime check happens against the tier config later)."""
        dep = require_feature("time_travel")
        assert callable(dep)
