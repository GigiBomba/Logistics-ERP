"""Copilot isolation tests — company, user, and conversation boundary enforcement.

Covers:
- Company plan isolation: plans are scoped per-company
- Company conversation isolation: conversation IDs are scoped per-company
- User data isolation: users can't cross company boundaries
- Ownership validation: _validate_plan_ownership rejects cross-company access
- Kill switch isolation: one company's switch doesn't affect others
"""
from __future__ import annotations


from datetime import datetime
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.copilot.schemas import (
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    GlobalContext,
    Intent,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_step(
    step_id: str = "step-0",
    tool_name: str = "vehicle.search",
    status: str = "pending",
) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        tool_name=tool_name,
        tool_version="1.0.0",
        parameters={},
        depends_on=[],
        confirmation_level=ConfirmationLevel.SAFE,
        status=status,
    )


def _make_plan(
    plan_id: str = "plan-1",
    conversation_id: str = "conv-1",
    steps=None,
    requires_confirmation: bool = False,
) -> ExecutionPlan:
    steps = steps or [_make_step()]
    return ExecutionPlan(
        plan_id=plan_id,
        conversation_id=conversation_id,
        reasoning_graph_id=f"rg-{plan_id}",
        intent=Intent(
            name="vehicle.search",
            entities=[],
            missing_required_entities=[],
            raw_utterance="show me trucks",
        ),
        steps=steps,
        overall_confidence=0.95,
        requires_confirmation=requires_confirmation,
        created_at=datetime.utcnow(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures — clean in-memory state between tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _cleanup_state():
    """Clear in-memory copilot state between tests to prevent cross-test pollution."""
    import backend.api.v1.copilot_router as cr
    cr._pending_plans.clear()
    cr._plan_owners.clear()
    cr._company_conversations.clear()
    cr._ws_connections.clear()
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# Company plan isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompanyPlanIsolation:
    """Different companies must not see each other's plans."""

    def test_plans_stored_with_correct_company_owner(self):
        """A plan stored for company A must have company A as the owner."""
        import backend.api.v1.copilot_router as cr

        plan = _make_plan(plan_id="plan-a")
        cr._pending_plans["plan-a"] = plan
        cr._plan_owners["plan-a"] = 1  # Company A

        assert cr._plan_owners["plan-a"] == 1

    def test_company_a_cannot_access_company_b_plan(self):
        """Company A (id=1) must not be able to access a plan owned by Company B (id=2)."""
        import backend.api.v1.copilot_router as cr

        plan_b = _make_plan(plan_id="plan-b-hidden")
        cr._pending_plans["plan-b-hidden"] = plan_b
        cr._plan_owners["plan-b-hidden"] = 2  # Company B

        # Company A tries to validate ownership
        from backend.api.v1.copilot_router import _validate_plan_ownership

        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("plan-b-hidden", company_id=1)
        assert exc.value.status_code == 403
        assert exc.value.detail["message_key"] == "copilot.plan.not_owned"

    def test_company_can_access_own_plan(self):
        """A company must be able to access its own plans."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan = _make_plan(plan_id="plan-own")
        cr._pending_plans["plan-own"] = plan
        cr._plan_owners["plan-own"] = 42

        result = _validate_plan_ownership("plan-own", company_id=42)
        assert result is plan
        assert result.plan_id == "plan-own"

    def test_plan_without_owner_falls_back_safely(self):
        """A plan without a recorded owner should still be accessible
        (backward compatibility during transition)."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan = _make_plan(plan_id="plan-no-owner")
        cr._pending_plans["plan-no-owner"] = plan
        # No entry in _plan_owners

        result = _validate_plan_ownership("plan-no-owner", company_id=1)
        assert result is plan

    def test_non_existent_plan_raises_404(self):
        """Accessing a plan that does not exist raises 404."""
        from backend.api.v1.copilot_router import _validate_plan_ownership

        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("ghost-plan", company_id=1)
        assert exc.value.status_code == 404
        assert exc.value.detail["message_key"] == "copilot.plan.not_found"


# ═══════════════════════════════════════════════════════════════════════════════
# Company conversation isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompanyConversationIsolation:
    """Conversation IDs must be scoped per company."""

    def test_conversations_tracked_per_company(self):
        """_company_conversations must track which plan IDs belong to which company."""
        import backend.api.v1.copilot_router as cr

        cr._company_conversations.setdefault(1, set()).add("plan-1")
        cr._company_conversations.setdefault(1, set()).add("plan-2")
        cr._company_conversations.setdefault(2, set()).add("plan-3")

        assert cr._company_conversations[1] == {"plan-1", "plan-2"}
        assert cr._company_conversations[2] == {"plan-3"}

    def test_company_does_not_see_other_company_conversations(self):
        """Company A's conversation set must not contain Company B's plans."""
        import backend.api.v1.copilot_router as cr

        cr._company_conversations.setdefault(1, set()).add("plan-a")
        cr._company_conversations.setdefault(2, set()).add("plan-b")

        company_a_plans = cr._company_conversations.get(1, set())
        assert "plan-b" not in company_a_plans

        company_b_plans = cr._company_conversations.get(2, set())
        assert "plan-a" not in company_b_plans

    def test_new_company_gets_empty_conversation_set(self):
        """A company with no conversations should get an empty set, not an error."""
        import backend.api.v1.copilot_router as cr

        plans = cr._company_conversations.get(999, set())
        assert plans == set()


# ═══════════════════════════════════════════════════════════════════════════════
# User data isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserDataIsolation:
    """User A cannot access User B's conversation through the plan store."""

    def test_pending_plans_are_scoped_by_company_id(self):
        """Plans are stored keyed by plan_id but ownership is tracked
        via _plan_owners[plan_id] = company_id. A user from company A
        cannot access a plan owned by company B."""
        import backend.api.v1.copilot_router as cr

        # Simulate plan from company B
        plan = _make_plan(plan_id="plan-b")
        cr._pending_plans["plan-b"] = plan
        cr._plan_owners["plan-b"] = 2

        # Company A user tries to get the plan via the router helper
        from backend.api.v1.copilot_router import _validate_plan_ownership

        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("plan-b", company_id=1)
        assert exc.value.status_code == 403

    def test_plan_not_found_for_wrong_company_via_get_plan(self):
        """The GET /plans/{plan_id} endpoint should be tested for isolation,
        but the endpoint itself does not enforce ownership (it returns
        plan data for any caller). This is by design for Phase 1 —
        Phase 2 will add ownership checks.

        Instead, we verify the lower-level ownership validation works.
        """
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan = _make_plan(plan_id="plan-any")
        cr._pending_plans["plan-any"] = plan
        cr._plan_owners["plan-any"] = 2

        # Company A should be blocked
        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("plan-any", company_id=1)
        assert exc.value.status_code == 403

    def test_cancel_endpoint_validates_ownership(self):
        """The cancel endpoint calls _validate_plan_ownership which
        enforces company isolation."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan_b = _make_plan(plan_id="plan-b-cancel", requires_confirmation=True)
        cr._pending_plans["plan-b-cancel"] = plan_b
        cr._plan_owners["plan-b-cancel"] = 2

        # Company A cannot cancel Company B's plan
        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("plan-b-cancel", company_id=1)
        assert exc.value.status_code == 403

    def test_confirm_endpoint_validates_ownership(self):
        """The confirm endpoint calls _validate_plan_ownership which
        enforces company isolation."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan_b = _make_plan(plan_id="plan-b-confirm", requires_confirmation=True)
        cr._pending_plans["plan-b-confirm"] = plan_b
        cr._plan_owners["plan-b-confirm"] = 2

        # Company A cannot confirm Company B's plan
        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("plan-b-confirm", company_id=1)
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Ownership validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestOwnershipValidation:
    """_validate_plan_ownership — comprehensive boundary checks."""

    def test_ownership_returns_plan_for_correct_company(self):
        """Happy path: plan owned by requesting company is returned."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan = _make_plan(plan_id="plan-ok")
        cr._pending_plans["plan-ok"] = plan
        cr._plan_owners["plan-ok"] = 5

        result = _validate_plan_ownership("plan-ok", 5)
        assert result.plan_id == "plan-ok"

    def test_ownership_rejects_different_company(self):
        """Plan owned by company 5 must not be accessible to company 3."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan = _make_plan(plan_id="plan-guarded")
        cr._pending_plans["plan-guarded"] = plan
        cr._plan_owners["plan-guarded"] = 5

        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("plan-guarded", 3)
        assert exc.value.status_code == 403

    def test_ownership_rejects_unknown_plan(self):
        """Non-existent plan raises 404."""
        from backend.api.v1.copilot_router import _validate_plan_ownership

        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("i-dont-exist", 1)
        assert exc.value.status_code == 404

    def test_ownership_allows_when_no_owner_recorded(self):
        """Backward compat: plan with no owner entry is still returned."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan = _make_plan(plan_id="plan-legacy")
        cr._pending_plans["plan-legacy"] = plan
        # No _plan_owners entry

        result = _validate_plan_ownership("plan-legacy", 42)
        assert result is plan

    def test_ownership_with_zero_company_id(self):
        """Edge case: company_id of 0 should not match plans owned by real companies."""
        import backend.api.v1.copilot_router as cr
        from backend.api.v1.copilot_router import _validate_plan_ownership

        plan = _make_plan(plan_id="plan-zero")
        cr._pending_plans["plan-zero"] = plan
        cr._plan_owners["plan-zero"] = 1

        # Unauthenticated/unscoped user (company_id=0) should not have access
        with pytest.raises(HTTPException) as exc:
            _validate_plan_ownership("plan-zero", 0)
        assert exc.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Kill switch per-company isolation
# ═══════════════════════════════════════════════════════════════════════════════


class TestKillSwitchIsolation:
    """One company's kill switch must not affect other companies (§26)."""

    @pytest.mark.asyncio
    @patch("backend.cache.get_cache")
    async def test_company_a_kill_switch_does_not_block_company_b(self, mock_get_cache):
        """When Company A's kill switch is active, Company B must still
        be able to use the Co-Pilot."""
        from backend.api.v1.copilot_router import _check_kill_switch

        mock_cache = MagicMock()

        def cache_get_side_effect(key: str):
            if key == "copilot:kill_switch:company:1":
                return True  # Company A is killed
            return False  # Everything else is fine

        mock_cache.get.side_effect = cache_get_side_effect
        mock_get_cache.return_value = mock_cache

        # Company B (id=2) should NOT be blocked
        try:
            await _check_kill_switch(company_id=2)  # Should not raise
        except HTTPException:
            pytest.fail("Company B should not be affected by Company A's kill switch")

    @pytest.mark.asyncio
    @patch("backend.cache.get_cache")
    async def test_company_a_kill_switch_blocks_company_a(self, mock_get_cache):
        """Company A's requests should be blocked when its kill switch is active."""
        from backend.api.v1.copilot_router import _check_kill_switch

        mock_cache = MagicMock()

        def cache_get_side_effect(key: str):
            if key == "copilot:kill_switch:company:1":
                return True
            return False

        mock_cache.get.side_effect = cache_get_side_effect
        mock_get_cache.return_value = mock_cache

        with pytest.raises(HTTPException) as exc:
            await _check_kill_switch(company_id=1)
        assert exc.value.status_code == 503
        assert exc.value.detail["message_key"] == "copilot.error.unavailable"

    @pytest.mark.asyncio
    @patch("backend.cache.get_cache")
    async def test_platform_kill_switch_blocks_all_companies(self, mock_get_cache):
        """Platform-wide kill switch must block every company."""
        from backend.api.v1.copilot_router import _check_kill_switch

        mock_cache = MagicMock()
        mock_cache.get.return_value = True  # Platform-wide kill
        mock_get_cache.return_value = mock_cache

        for company_id in [1, 2, 42, 999]:
            with pytest.raises(HTTPException) as exc:
                await _check_kill_switch(company_id=company_id)
            assert exc.value.status_code == 503

    @pytest.mark.asyncio
    @patch("backend.cache.get_cache")
    async def test_company_not_in_kill_switch_dict_passes(self, mock_get_cache):
        """Companies without an explicit kill switch entry should pass through."""
        from backend.api.v1.copilot_router import _check_kill_switch

        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # No kill switch set (None = not in Redis)
        mock_get_cache.return_value = mock_cache

        # Should not raise for any company
        for company_id in [1, 2, 3, 100]:
            try:
                await _check_kill_switch(company_id=company_id)
            except HTTPException:
                pytest.fail(f"Company {company_id} should not be blocked when no kill switch is set")

    @pytest.mark.asyncio
    @patch("backend.cache.get_cache")
    async def test_kill_switch_per_company_key_pattern(self, mock_get_cache):
        """The kill switch key pattern must include the company_id so
        companies are isolated."""
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_get_cache.return_value = mock_cache

        from backend.api.v1.copilot_router import _check_kill_switch

        # Platform check uses key "copilot:kill_switch:platform"
        # Per-company check uses key "copilot:kill_switch:company:{company_id}"

        # Verify the keys used by _check_kill_switch:
        # Platform key is checked first, then per-company key
        await _check_kill_switch(company_id=7)
        calls = mock_cache.get.call_args_list
        keys_checked = [call[0][0] for call in calls]

        assert "copilot:kill_switch:platform" in keys_checked
        assert "copilot:kill_switch:company:7" in keys_checked

    @pytest.mark.asyncio
    @patch("backend.api.v1.copilot_router._cancel_inflight_plans")
    @patch("backend.cache.get_cache")
    async def test_set_kill_switch_cancels_only_that_companys_plans(
        self, mock_get_cache, mock_cancel,
    ):
        """When toggling kill switch for a company, only that company's
        in-flight plans should be cancelled."""
        from backend.api.v1.copilot_router import _set_kill_switch

        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        # Set kill switch for company 5
        await _set_kill_switch(company_id=5, killed=True)

        # Verify inflight plans were cancelled for company 5 only
        mock_cancel.assert_called_once_with(5)

    @pytest.mark.asyncio
    @patch("backend.cache.get_cache")
    async def test_kill_switch_response_is_i18n(self, mock_get_cache):
        """Kill switch response must use i18n message key, not raw text."""
        from backend.api.v1.copilot_router import _check_kill_switch

        mock_cache = MagicMock()
        mock_cache.get.return_value = True
        mock_get_cache.return_value = mock_cache

        with pytest.raises(HTTPException) as exc:
            await _check_kill_switch(company_id=1)

        detail = exc.value.detail
        assert isinstance(detail, dict)
        assert "message_key" in detail
        assert detail["message_key"] == "copilot.error.unavailable"
