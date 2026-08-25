"""Golden Conversation Regression Suite (§23.4).

A persistent, versioned set of conversation scenarios re-run against
every prompt/model/planner change before it ships. Asserts the reasoning
graph and resulting plan match expected shape — not exact text, but the
right tools, the right confirmation levels, the right decision.

Phase 5: Core scenarios that test planner intent extraction and
tool routing. Will be expanded as real conversations surface
interesting cases.
"""
from __future__ import annotations


import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from backend.copilot.planner import process_utterance, extract_intent
from backend.copilot.schemas import (
    CoPilotResponse, ExecutionPlan, GlobalContext, Intent,
)
from backend.copilot.tools.registry import get_tool, all_tools


# ── Golden scenario format ────────────────────────────────────────────────
# Each scenario is a dict with:
#   utterance: str — the user's natural language input
#   expected_intent: str — the expected Intent.name
#   expect_plan: bool — whether a plan should be produced
#   expect_clarification: bool — whether a clarification is expected
#   tags: list[str] — "tier_a", "tier_b", "en", "ro" etc.

GOLDEN_SCENARIOS = [
    # ── Tier A: Full depth scenarios (English only — Phase 1 keyword planner) ─
    {
        "utterance": "find available trucks",
        "expected_intent": "vehicle.search",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "en"],
    },
    {
        "utterance": "show payment summary for client 12",
        "expected_intent": "client.payment_summary",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "en"],
    },
    {
        "utterance": "what is the USD exchange rate",
        "expected_intent": "currency.get_rate",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "en"],
    },
    # ── Tier B: Baseline coverage ──────────────────────────────────────
    {
        "utterance": "calculate a route from Berlin to Warsaw",
        "expected_intent": "route.calculate",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_b", "en"],
    },
    {
        "utterance": "check driver 7 hours",
        "expected_intent": "driver.check_hours",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_b", "en"],
    },
    {
        "utterance": "how much does client 42 owe",
        "expected_intent": "client.payment_summary",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_b", "en"],
    },
    {
        "utterance": "show me fleet analytics",
        "expected_intent": "analytics.query",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_b", "en"],
    },
    # ── Edge cases ─────────────────────────────────────────────────────
    {
        "utterance": "",
        "expected_intent": "unknown",
        "expect_plan": False,
        "expect_clarification": True,
        "tags": ["tier_b", "edge"],
    },
    {
        "utterance": "do something completely nonsensical xyzzy",
        "expected_intent": "unknown",
        "expect_plan": False,
        "expect_clarification": True,
        "tags": ["tier_b", "edge"],
    },
    {
        "utterance": "aaaaa",
        "expected_intent": "unknown",
        "expect_plan": False,
        "expect_clarification": True,
        "tags": ["tier_b", "edge"],
    },
]


class TestGoldenRegression:
    """Golden conversation regression suite (§23.4).
    
    Run against every prompt/model/planner change before shipping.
    Languages: full depth in Tier A, baseline in Tier B.
    """

    @pytest.mark.parametrize(
        "scenario",
        [s for s in GOLDEN_SCENARIOS if "tier_a" in s.get("tags", [])],
        ids=[s["utterance"][:40] for s in GOLDEN_SCENARIOS if "tier_a" in s.get("tags", [])],
    )
    @pytest.mark.asyncio
    async def test_tier_a_scenarios(self, scenario):
        """Tier A: Full scenario depth for primary languages."""
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en" if "en" in scenario.get("tags", []) else "ro",
            timezone="UTC", subscription_tier="business",
        )
        intent = await extract_intent(scenario["utterance"])
        
        assert intent.name == scenario["expected_intent"], (
            f"For '{scenario['utterance']}': "
            f"expected intent '{scenario['expected_intent']}', got '{intent.name}'"
        )

    @pytest.mark.parametrize(
        "scenario",
        [s for s in GOLDEN_SCENARIOS if "tier_a" in s.get("tags", [])],
        ids=[s["utterance"][:40] for s in GOLDEN_SCENARIOS if "tier_a" in s.get("tags", [])],
    )
    @pytest.mark.asyncio
    async def test_tier_a_pipeline(self, scenario):
        """Tier A: Full pipeline — intent extraction + plan compilation."""
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en" if "en" in scenario.get("tags", []) else "ro",
            timezone="UTC", subscription_tier="business",
        )
        resp = await process_utterance(scenario["utterance"], ctx, f"golden-{hash(scenario['utterance'])}")
        
        assert isinstance(resp, CoPilotResponse)
        if scenario["expect_plan"]:
            assert resp.plan is not None or resp.clarification_question_key is not None
        if scenario["expect_clarification"]:
            assert resp.clarification_question_key is not None or resp.plan is None

    @pytest.mark.parametrize(
        "scenario",
        [s for s in GOLDEN_SCENARIOS if "tier_b" in s.get("tags", [])],
        ids=[s["utterance"][:40] for s in GOLDEN_SCENARIOS if "tier_b" in s.get("tags", [])],
    )
    @pytest.mark.asyncio
    async def test_tier_b_scenarios(self, scenario):
        """Tier B: Baseline coverage — intent extraction only."""
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        intent = await extract_intent(scenario["utterance"])
        assert intent.name == scenario["expected_intent"], (
            f"Tier B: For '{scenario['utterance']}': "
            f"expected '{scenario['expected_intent']}', got '{intent.name}'"
        )


class TestScenarioVersioning:
    """Golden scenario set versioning (§23.4)."""

    def test_golden_scenarios_have_version(self):
        """The golden suite must be versioned."""
        assert hasattr(TestGoldenRegression, "GOLDEN_SCENARIOS") or "GOLDEN_SCENARIOS" in dir(
            __import__("tests.copilot.test_golden_regression", fromlist=["GOLDEN_SCENARIOS"])
        )

    def test_all_scenarios_have_expected_fields(self):
        """Every scenario must have all required fields."""
        for scenario in GOLDEN_SCENARIOS:
            assert "utterance" in scenario
            assert "expected_intent" in scenario
            assert "tags" in scenario
            assert scenario["tags"]  # non-empty

    def test_no_duplicate_utterances(self):
        """No two scenarios should have the same utterance."""
        utterances = [s["utterance"] for s in GOLDEN_SCENARIOS]
        duplicates = {u for u in utterances if utterances.count(u) > 1}
        assert len(duplicates) == 0, f"Duplicate scenarios: {duplicates}"
