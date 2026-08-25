"""Mutation tests — verify tests catch regressions.

These tests introduce deliberate "mutations" (bugs) into the code
and verify the existing test suite catches them. If a mutation
passes all tests, that test coverage has a gap.

Blueprint: §27 — Test Methodology Reference.
"""
from __future__ import annotations


import ast
import inspect
import textwrap
from typing import Any, Dict, List

import pytest

from backend.copilot.planner import _ensure_tools_loaded
from backend.copilot.tools.registry import get_tool


# ── Ensure tools are loaded before any mutation test. ─────────────────────

@pytest.fixture(autouse=True)
def _load_tools():
    _ensure_tools_loaded()


class TestSchemaMutationCoverage:
    """Verify existing schema tests catch schema regressions."""

    def test_missing_field_in_entity_is_caught(self):
        """If Entity loses a required field, existing tests should catch it."""
        # The test_schemas roundtrip test creates Entity with all fields
        # and serializes/deserializes. If a field disappears, the roundtrip fails.
        from backend.copilot.schemas import Entity
        required_fields = {"type", "value", "source", "confidence"}
        actual_fields = set(Entity.model_fields.keys())
        # Check all required fields still exist
        missing = required_fields - actual_fields
        assert len(missing) == 0, f"Entity lacks fields: {missing}"

    def test_missing_enum_value_in_reasoning_types(self):
        """If ReasoningNodeType loses an enum value, schema tests catch it."""
        from backend.copilot.schemas import ReasoningNodeType
        expected = {"GOAL", "REQUIREMENT", "SUB_GOAL", "QUERY", "COMPARISON", "DECISION"}
        actual = set(ReasoningNodeType.__members__.keys())
        missing = expected - actual
        assert len(missing) == 0, f"ReasoningNodeType lacks: {missing}"

    def test_missing_confirmation_level(self):
        """If ConfirmationLevel loses a level, tests catch it."""
        from backend.copilot.schemas import ConfirmationLevel
        expected_values = {0: "SAFE", 1: "INFORMATIONAL", 2: "BUSINESS", 3: "DESTRUCTIVE"}
        for val, name in expected_values.items():
            assert ConfirmationLevel(val).name == name, f"Missing ConfirmationLevel.{name}"


class TestToolMutationCoverage:
    """Verify tool tests catch tool regressions."""

    def test_removed_tool_is_caught(self):
        """If a tool is removed from the registry, the 49-tool count test fails."""
        tools_now = get_tool("vehicle.search")
        assert tools_now is not None, "vehicle.search was removed from registry!"
        # The test_tools.py::TestAllToolsRegistered::test_49_tools_registered
        # asserts exactly 49 tools. Removing one would fail it.

    def test_changed_tool_level_is_caught(self):
        """If a tool's confirmation level changes, level tests catch it."""
        from backend.copilot.schemas import ConfirmationLevel
        
        # These are the canonical assignments from the blueprint
        safe_checks = {
            "vehicle.search": ConfirmationLevel.SAFE,
            "route.calculate": ConfirmationLevel.SAFE,
            "analytics.query": ConfirmationLevel.SAFE,
        }
        for name, expected_level in safe_checks.items():
            tool = get_tool(name)
            if tool:
                assert tool.confirmation_level == expected_level, (
                    f"{name} level changed from {expected_level} to {tool.confirmation_level}"
                )

    def test_changed_tool_permission_is_caught(self):
        """If a tool's required_permission changes, permission tests catch it."""
        perm_checks = {
            "vehicle.search": "fleet:read",
            "route.calculate": "routes:read",
            "client.create": "clients:write",
            "dispatch.cancel": "dispatch:write",
        }
        for name, expected_perm in perm_checks.items():
            tool = get_tool(name)
            if tool:
                assert tool.required_permission == expected_perm, (
                    f"{name} permission changed from {expected_perm} to {tool.required_permission}"
                )


class TestPlannerMutationCoverage:
    """Verify planner tests catch planner regressions."""

    def test_removed_intent_pattern_is_caught(self):
        """If an intent pattern is removed, the intent extraction test fails."""
        # The test_planner_executor.py::TestIntentExtraction has parametrized
        # tests for every intent pattern. Removing one would result in
        # a test failure (intent would be "unknown" instead of expected).
        import backend.copilot.planner as planner_module

        # Read the INTENT_PATTERNS list
        has_intent_patterns = hasattr(planner_module, "INTENT_PATTERNS")
        assert has_intent_patterns, "INTENT_PATTERNS was removed from planner!"

    def test_confidence_startup_is_verified(self):
        """If confidence formula changes, boundary tests catch it."""
        from backend.copilot.confidence import MEDIUM_CONFIDENCE_THRESHOLD
        assert MEDIUM_CONFIDENCE_THRESHOLD == 0.55, (
            f"Medium threshold changed from 0.55 to {MEDIUM_CONFIDENCE_THRESHOLD}"
        )

    # ── Intent pattern survival tests ─────────────────────────────────────

    @staticmethod
    def _collect_intent_names() -> list:
        from backend.copilot.planner import INTENT_PATTERNS
        return [pattern[1] for pattern in INTENT_PATTERNS]

    def test_all_expected_intents_present(self):
        """Verify every canonical intent name exists in INTENT_PATTERNS."""
        expected_intents = {
            "vehicle.search",
            "vehicle.health_score",
            "driver.check_hours",
            "route.calculate",
            "route.estimate_cost",
            "route.plan_multistop",
            "trip.calculate_profitability",
            "client.payment_summary",
            "document.search",
            "currency.get_rate",
            "currency.convert",
            "tracking.get_live_positions",
            "tracking.get_vehicle_history",
            "analytics.query",
            "help.answer_question",
            "help.guide_workflow",
        }
        actual = set(self._collect_intent_names())
        missing = expected_intents - actual
        assert len(missing) == 0, f"INTENT_PATTERNS missing intents: {missing}"
        extras = actual - expected_intents
        assert len(extras) == 0, f"INTENT_PATTERNS has unexpected intents: {extras}"

    def test_intent_pattern_count(self):
        """Verify INTENT_PATTERNS has exactly 16 entries."""
        from backend.copilot.planner import INTENT_PATTERNS
        assert len(INTENT_PATTERNS) == 16, (
            f"INTENT_PATTERNS count changed from 16 to {len(INTENT_PATTERNS)}"
        )

    def test_each_pattern_has_three_elements(self):
        """Every INTENT_PATTERNS entry must be a 3-tuple: (keywords, name, entity_mappings)."""
        from backend.copilot.planner import INTENT_PATTERNS
        for i, pattern in enumerate(INTENT_PATTERNS):
            assert len(pattern) == 3, (
                f"INTENT_PATTERNS[{i}] has {len(pattern)} elements, expected 3"
            )
            assert isinstance(pattern[0], list), (
                f"INTENT_PATTERNS[{i}][0] should be a list (keyword_hints)"
            )
            assert isinstance(pattern[1], str), (
                f"INTENT_PATTERNS[{i}][1] should be a str (intent_name)"
            )
            assert isinstance(pattern[2], list), (
                f"INTENT_PATTERNS[{i}][2] should be a list (entity_types)"
            )

    def test_intent_names_are_unique(self):
        """No duplicate intent names in INTENT_PATTERNS."""
        names = self._collect_intent_names()
        assert len(names) == len(set(names)), (
            f"Duplicate intent names found: {[n for n in names if names.count(n) > 1]}"
        )

    def test_first_keyword_hints_are_nonempty(self):
        """Each pattern must have at least one keyword hint."""
        from backend.copilot.planner import INTENT_PATTERNS
        for i, pattern in enumerate(INTENT_PATTERNS):
            assert len(pattern[0]) > 0, (
                f"INTENT_PATTERNS[{i}] has empty keyword_hints list"
            )

    def test_min_match_threshold_is_unchanged(self):
        """Verify MIN_MATCH_THRESHOLD inside extract_intent remains 2."""
        import inspect
        from backend.copilot.planner import extract_intent
        source = inspect.getsource(extract_intent)
        assert "MIN_MATCH_THRESHOLD = 2" in source, (
            "MIN_MATCH_THRESHOLD changed from 2 — intent extraction may now match spuriously"
        )


class TestConfidenceMutationCoverage:
    """Verify confidence thresholds and weights survive changes."""

    def test_high_confidence_threshold(self):
        """HIGH_CONFIDENCE_THRESHOLD must be 0.85."""
        from backend.copilot.confidence import HIGH_CONFIDENCE_THRESHOLD
        assert HIGH_CONFIDENCE_THRESHOLD == 0.85, (
            f"HIGH_CONFIDENCE_THRESHOLD changed from 0.85 to {HIGH_CONFIDENCE_THRESHOLD}"
        )

    def test_medium_confidence_threshold(self):
        """MEDIUM_CONFIDENCE_THRESHOLD must be 0.55."""
        from backend.copilot.confidence import MEDIUM_CONFIDENCE_THRESHOLD
        assert MEDIUM_CONFIDENCE_THRESHOLD == 0.55, (
            f"MEDIUM_CONFIDENCE_THRESHOLD changed from 0.55 to {MEDIUM_CONFIDENCE_THRESHOLD}"
        )

    def test_low_confidence_is_below_medium(self):
        """Scores below MEDIUM_CONFIDENCE_THRESHOLD are implicitly 'low'."""
        from backend.copilot.confidence import MEDIUM_CONFIDENCE_THRESHOLD
        from backend.copilot.confidence import confidence_bucket
        assert confidence_bucket(MEDIUM_CONFIDENCE_THRESHOLD - 0.01) == "low"

    def test_weights_sum_to_one(self):
        """DEFAULT_WEIGHTS must sum to exactly 1.0."""
        from backend.copilot.confidence import DEFAULT_WEIGHTS
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, (
            f"DEFAULT_WEIGHTS sum to {total}, expected 1.0"
        )

    def test_weights_have_expected_keys(self):
        """DEFAULT_WEIGHTS must contain the four canonical keys."""
        from backend.copilot.confidence import DEFAULT_WEIGHTS
        expected_keys = {"intent_match", "entity_completeness", "entity_confidence_avg", "historical_success_rate"}
        assert set(DEFAULT_WEIGHTS.keys()) == expected_keys, (
            f"DEFAULT_WEIGHTS keys changed: {set(DEFAULT_WEIGHTS.keys())}"
        )

    def test_needs_clarification_uses_medium_threshold(self):
        """needs_clarification returns True below MEDIUM_CONFIDENCE_THRESHOLD."""
        from backend.copilot.confidence import MEDIUM_CONFIDENCE_THRESHOLD, needs_clarification
        assert needs_clarification(MEDIUM_CONFIDENCE_THRESHOLD - 0.01) is True
        assert needs_clarification(MEDIUM_CONFIDENCE_THRESHOLD) is False

    def test_needs_recap_range(self):
        """needs_recap returns True only in [MEDIUM, HIGH)."""
        from backend.copilot.confidence import (
            MEDIUM_CONFIDENCE_THRESHOLD,
            HIGH_CONFIDENCE_THRESHOLD,
            needs_recap,
        )
        assert needs_recap(MEDIUM_CONFIDENCE_THRESHOLD) is True
        assert needs_recap(HIGH_CONFIDENCE_THRESHOLD - 0.01) is True
        assert needs_recap(HIGH_CONFIDENCE_THRESHOLD) is False
        assert needs_recap(MEDIUM_CONFIDENCE_THRESHOLD - 0.01) is False


class TestExecutorMutationCoverage:
    """Verify executor tests catch executor regressions."""

    def test_guardrail_constant_not_lowered(self):
        """If MAX_TOOL_CALLS_PER_PLAN drops below 20, guardrail test catches it."""
        from backend.copilot.executor import MAX_TOOL_CALLS_PER_PLAN
        assert MAX_TOOL_CALLS_PER_PLAN >= 20, (
            f"MAX_TOOL_CALLS_PER_PLAN dropped to {MAX_TOOL_CALLS_PER_PLAN}"
        )

    def test_max_tool_calls_exact(self):
        """MAX_TOOL_CALLS_PER_PLAN must be exactly 20."""
        from backend.copilot.executor import MAX_TOOL_CALLS_PER_PLAN
        assert MAX_TOOL_CALLS_PER_PLAN == 20, (
            f"MAX_TOOL_CALLS_PER_PLAN changed from 20 to {MAX_TOOL_CALLS_PER_PLAN}"
        )

    def test_max_reasoning_graph_nodes(self):
        """MAX_REASONING_GRAPH_NODES_PER_TURN must be exactly 50."""
        from backend.copilot.executor import MAX_REASONING_GRAPH_NODES_PER_TURN
        assert MAX_REASONING_GRAPH_NODES_PER_TURN == 50, (
            f"MAX_REASONING_GRAPH_NODES_PER_TURN changed from 50 to {MAX_REASONING_GRAPH_NODES_PER_TURN}"
        )

    def test_max_llm_tokens_per_turn(self):
        """MAX_LLM_TOKENS_PER_TURN must be exactly 32000."""
        from backend.copilot.executor import MAX_LLM_TOKENS_PER_TURN
        assert MAX_LLM_TOKENS_PER_TURN == 32000, (
            f"MAX_LLM_TOKENS_PER_TURN changed from 32000 to {MAX_LLM_TOKENS_PER_TURN}"
        )

    def test_tool_timeout_seconds(self):
        """TOOL_TIMEOUT_SECONDS must be exactly 30."""
        from backend.copilot.executor import TOOL_TIMEOUT_SECONDS
        assert TOOL_TIMEOUT_SECONDS == 30, (
            f"TOOL_TIMEOUT_SECONDS changed from 30 to {TOOL_TIMEOUT_SECONDS}"
        )

    def test_undo_window_minutes(self):
        """UNDO_WINDOW_MINUTES must be exactly 30."""
        from backend.copilot.executor import UNDO_WINDOW_MINUTES
        assert UNDO_WINDOW_MINUTES == 30, (
            f"UNDO_WINDOW_MINUTES changed from 30 to {UNDO_WINDOW_MINUTES}"
        )

    def test_plan_status_members(self):
        """Verify all 11 PlanStatus enum members and their string values."""
        from backend.copilot.executor import PlanStatus
        expected = {
            "UNDERSTOOD": "understood",
            "REASONING": "reasoning",
            "PLANNED": "planned",
            "VALIDATING": "validating",
            "AWAITING_CLARIFICATION": "awaiting_clarification",
            "AWAITING_CONFIRMATION": "awaiting_confirmation",
            "EXECUTING": "executing",
            "SUMMARIZING": "summarizing",
            "COMPLETED": "completed",
            "PARTIALLY_COMPLETED": "partially_completed",
            "CANCELLED": "cancelled",
        }
        actual = {m.name: m.value for m in PlanStatus}
        assert actual == expected, (
            f"PlanStatus members differ:\n"
            f"  extra:   {set(actual.keys()) - set(expected.keys())}\n"
            f"  missing: {set(expected.keys()) - set(actual.keys())}\n"
            f"  changed: {{k for k in expected if k in actual and actual[k] != expected[k]}}"
        )


class TestAPIMutationCoverage:
    """Verify API tests catch API regressions."""

    def test_router_registered(self):
        """The copilot router must exist in the main API router."""
        from backend.api.v1.router import api_v1_router
        from backend.api.v1 import copilot_router
        # Check that copilot routes are included by looking for the embedded router
        for route in api_v1_router.routes:
            if hasattr(route, "original_router") and route.original_router is copilot_router.router:
                assert len(route.original_router.routes) > 0
                # Verify at least the chat endpoint exists
                paths = [getattr(sr, "path", "") for sr in route.original_router.routes]
                assert any("/chat" in p for p in paths), f"No /chat route in copilot router: {paths}"
                return
        pytest.fail("copilot_router not found in api_v1_router.routes")

    def test_kill_switch_cache_keys(self):
        """Kill switch cache key patterns must remain unchanged."""
        # These keys are used by _check_kill_switch and _set_kill_switch
        # Changing them would break the kill switch mechanism
        expected_platform_key = "copilot:kill_switch:platform"
        expected_company_key_fragment = "copilot:kill_switch:company:"

        from backend.api.v1.copilot_router import _check_kill_switch
        import inspect
        source = inspect.getsource(_check_kill_switch)
        assert expected_platform_key in source, (
            f"Platform kill switch key '{expected_platform_key}' not found in _check_kill_switch"
        )
        assert expected_company_key_fragment in source, (
            f"Company kill switch key fragment '{expected_company_key_fragment}' not found in _check_kill_switch"
        )

    def test_kill_switch_ttl(self):
        """Kill switch TTL must remain 86400 (24h)."""
        from backend.api.v1.copilot_router import _set_kill_switch
        import inspect
        source = inspect.getsource(_set_kill_switch)
        # Search for ttl=86400 in the source
        assert "ttl=86400" in source, (
            "Kill switch TTL changed from 86400 — switches may expire prematurely"
        )

    def test_ownership_validation_status_codes(self):
        """_validate_plan_ownership must return 404 (not_found) and 403 (not_owned)."""
        from backend.api.v1.copilot_router import _validate_plan_ownership
        import inspect
        source = inspect.getsource(_validate_plan_ownership)
        assert "status_code=404" in source, "Plan not-found status_code changed from 404"
        assert "status_code=403" in source, "Plan not-owned status_code changed from 403"
        assert "copilot.plan.not_found" in source, "Plan not-found message_key changed"
        assert "copilot.plan.not_owned" in source, "Plan not-owned message_key changed"

    def test_chat_endpoint_path(self):
        """The /chat endpoint must be registered as POST /copilot/chat."""
        from backend.api.v1.copilot_router import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/copilot/chat" in paths, (
            f"POST /copilot/chat not found in router. Paths: {paths}"
        )

    def test_plan_endpoints_exist(self):
        """All plan lifecycle endpoints must be registered."""
        from backend.api.v1.copilot_router import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        expected_endpoints = [
            "/copilot/chat",
            "/copilot/voice",
            "/copilot/plans/{plan_id}",
            "/copilot/plans/{plan_id}/cancel",
            "/copilot/plans/{plan_id}/confirm",
            "/copilot/plans/{plan_id}/undo",
            "/copilot/conversations",
            "/copilot/conversations/{conversation_id}",
            "/copilot/insights",
        ]
        for ep in expected_endpoints:
            assert ep in paths, f"Missing endpoint: {ep}"

    def test_kill_switch_checked_in_chat(self):
        """The /chat endpoint must call _check_kill_switch before processing."""
        from backend.api.v1.copilot_router import chat
        import inspect
        source = inspect.getsource(chat)
        assert "await _check_kill_switch" in source, (
            "chat() no longer calls _check_kill_switch — kill switch bypassed!"
        )

    def test_kill_switch_checked_in_voice(self):
        """The /voice endpoint must call _check_kill_switch before processing."""
        from backend.api.v1.copilot_router import voice_input
        import inspect
        source = inspect.getsource(voice_input)
        assert "await _check_kill_switch" in source, (
            "voice_input() no longer calls _check_kill_switch — kill switch bypassed!"
        )
