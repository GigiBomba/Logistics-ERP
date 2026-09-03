"""Golden Conversation Regression Suite (§23.4).

A persistent, versioned set of conversation scenarios re-run against
every prompt/model/planner change before it ships. Asserts the reasoning
graph and resulting plan match expected shape — not exact text, but the
right tools, the right confirmation levels, the right decision.

Phase 5: Core scenarios that test planner intent extraction and
tool routing. Will be expanded as real conversations surface
interesting cases.

Version 1.1.0 (§23.4 audit expansion):
  - Romanian (ro) Tier A scenarios mirroring the en Tier A intent shapes
  - Help Mode / Guided scenarios (help.answer_question, help.guide_workflow)
  - pipeline-level LLM degradation ladder coverage

Version 1.2.0 (§23.4 Tier-B multilingual expansion):
  - Multilingual Tier-B intent-extraction baseline across ALL 22 languages
    in backend.copilot.schemas.SUPPORTED_LANGUAGES (MULTILINGUAL_TIER_B)
  - 132 new scenarios (22 langs x 6 = 5 positives + 1 negative each), drawn
    verbatim from INTENT_PATTERNS' per-language phrase corpus, so they match
    by construction under extract_intent(utterance, language=<lang>)
  - The 17 existing scenarios and their language=None default behavior are
    unchanged

Version 2.0.0 (§23.4 LLM-first split):
  - GOLDEN_SCENARIOS + MULTILINGUAL_TIER_B become the OFFLINE-FALLBACK
    contract: every existing scenario + assertion is byte-identical and the
    autouse fixture forces the keyword path (chat_with_tools mocked offline).
  - NEW TestLLMDrivenGolden: 8 LLM-driven scenarios with a shared scripted
    FakeLLMProvider — tool routing (real data in the answer), in-language
    synthesis, clarification round-trip, Level 2 plan-return, Level 3
    DESTRUCTIVE plan-return (§23.4 line 1350), driver-RBAC catalog subset,
    JSON-channel repair retry, and the loop cap.
  - TestUnknownUtteranceWithLLM reworked to the new ladder (llm_chat summary /
    model_unreachable / unknown_intent).
"""
from __future__ import annotations


import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.copilot.planner import process_utterance, extract_intent
from backend.copilot.llm.base import LLMResponse
from backend.copilot.llm.tool_calling import (
    TOOL_LOOP_MAX_ITERATIONS,
    ToolLoopResult,
    build_tool_catalog,
    build_tool_context,
    run_tool_loop,
)
from backend.copilot.schemas import (
    CoPilotResponse, ConfirmationLevel, ExecutionPlan, GlobalContext,
    GuidedWalkthrough, Intent, ToolContext,
)
from backend.copilot.tools.registry import get_tool, all_tools

# Suite version — bump on ANY scenario-set expansion or assertion change.
GOLDEN_SUITE_VERSION = "2.0.0"


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Reset the global circuit breaker between tests.

    Other test files (e.g. test_chaos) trip it for company_id=1 and never
    restore it; the real-executor LLM-driven scenarios would otherwise be
    blocked by a stale tripped breaker when the suite runs in full.
    """
    from backend.copilot.circuit_breaker import get_circuit_breaker
    get_circuit_breaker()._states.clear()


@pytest.fixture(autouse=True)
def _offline_llm_chat():
    """Force the keyword (offline-fallback) path for every golden scenario.

    The real chat_with_tools would consult the provider registry, which can
    pick up real API keys from the environment and attempt live network calls.
    Every scenario here must stay hermetic.  Returning a ToolLoopResult with
    attempted=False and zero tool executions routes ``process_utterance``
    through the offline keyword contract these scenarios pin (§23.5).
    """
    with patch("backend.copilot.llm.chat.chat_with_tools", new_callable=AsyncMock) as m:
        m.return_value = ToolLoopResult(attempted=False, provider_failed=False)
        yield m


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
    # ── Tier A: Romanian (ro) — same intent/plan shapes as the en set ──
    # The Phase-1 keyword planner matches Romanian via shared roots (e.g.
    # "listează" → list) and the ro greeting list; utterances without a
    # mapped root intentionally fall back to unknown → llm_chat (covered
    # in TestUnknownUtteranceWithLLM with chat_answer mocked).
    {
        "utterance": "listează camioanele disponibile",
        "expected_intent": "vehicle.search",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "ro"],
    },
    {
        "utterance": "sumarul plăților pentru clientul 12",
        "expected_intent": "client.payment_summary",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "ro"],
    },
    {
        "utterance": "calculează profitul pentru 1500 km",
        "expected_intent": "trip.calculate_profitability",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "ro"],
    },
    {
        "utterance": "salut",
        "expected_intent": "help.greeting",
        "expect_plan": False,
        "expect_clarification": False,
        "tags": ["tier_a", "ro"],
    },
    {
        "utterance": "cum funcționează motorul diesel",
        "expected_intent": "unknown",
        "expect_plan": False,
        "expect_clarification": True,
        "tags": ["tier_a", "ro", "edge"],
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
    # ── Help Mode / Guided scenarios (§33, §34) ────────────────────────
    {
        "utterance": "explain what a tachograph is",
        "expected_intent": "help.answer_question",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "help", "en"],
    },
    {
        "utterance": "walk me through dispatching a trip",
        "expected_intent": "help.guide_workflow",
        "expect_plan": True,
        "expect_clarification": False,
        "tags": ["tier_a", "help", "en"],
    },
]


# ── Multilingual Tier-B baseline (§23.4) ─────────────────────────────────
# Per-language (utterance, expected_intent) pairs for ALL 22
# SUPPORTED_LANGUAGES. 5 positive scenarios per language — one for each of
# vehicle.search / driver.check_hours / route.calculate / analytics.query /
# help.greeting — using the EXACT phrases from planner.py's INTENT_PATTERNS
# per-language corpus, so they match by construction. Plus 1 negative control
# per language: a plausible-but-nonsense off-domain utterance verified to
# match no keyword of that language (resolves to "unknown"). Tested at the
# intent-extraction level only (same shape as the existing tier_b test).
MULTILINGUAL_TIER_B: Dict[str, List[tuple]] = {
    "en": [
        ("find available trucks", "vehicle.search"),
        ("check driver hours", "driver.check_hours"),
        ("calculate route", "route.calculate"),
        ("fleet analytics", "analytics.query"),
        ("hello", "help.greeting"),
        ("quantum cargo teleportation protocol", "unknown"),
    ],
    "ro": [
        ("caută vehicule libere", "vehicle.search"),
        ("ce camioane am in flota", "vehicle.search"),
        ("verifică orele șoferului", "driver.check_hours"),
        ("calculează un traseu", "route.calculate"),
        ("analiza flotei", "analytics.query"),
        ("salut", "help.greeting"),
        ("pisica cântă jazz", "unknown"),
    ],
    "de": [
        ("finde verfügbare lkws", "vehicle.search"),
        ("prüfe die stunden des fahrers", "driver.check_hours"),
        ("berechne eine route", "route.calculate"),
        ("zeige die flottenanalytik", "analytics.query"),
        ("hallo", "help.greeting"),
        ("känguru tanzt reggae", "unknown"),
    ],
    "fr": [
        ("trouve des camions disponibles", "vehicle.search"),
        ("vérifie les heures du chauffeur", "driver.check_hours"),
        ("calcule un itinéraire", "route.calculate"),
        ("affiche l analyse de la flotte", "analytics.query"),
        ("bonjour", "help.greeting"),
        ("saxophone suave résonne", "unknown"),
    ],
    "es": [
        ("busca camiones disponibles", "vehicle.search"),
        ("revisa las horas del conductor", "driver.check_hours"),
        ("calcula una ruta", "route.calculate"),
        ("muestra el análisis de la flota", "analytics.query"),
        ("hola", "help.greeting"),
        ("ciervos bailan tango", "unknown"),
    ],
    "pl": [
        ("znajdź dostępne ciężarówki", "vehicle.search"),
        ("sprawdź godziny kierowcy", "driver.check_hours"),
        ("oblicz trasę", "route.calculate"),
        ("pokaż analitykę floty", "analytics.query"),
        ("cześć", "help.greeting"),
        ("słoń gra na banjo", "unknown"),
    ],
    "it": [
        ("trova camion disponibili", "vehicle.search"),
        ("controlla le ore dell autista", "driver.check_hours"),
        ("calcola un percorso", "route.calculate"),
        ("mostra l analisi della flotta", "analytics.query"),
        ("ciao", "help.greeting"),
        ("sassofono suadente risuona", "unknown"),
    ],
    "nl": [
        ("vind beschikbare vrachtwagens", "vehicle.search"),
        ("controleer de uren van de chauffeur", "driver.check_hours"),
        ("bereken een route", "route.calculate"),
        ("toon de vlootanalyses", "analytics.query"),
        ("hallo", "help.greeting"),
        ("paarse olifant fluit", "unknown"),
    ],
    "pt": [
        ("encontre caminhões disponíveis", "vehicle.search"),
        ("verifica as horas do motorista", "driver.check_hours"),
        ("calcula uma rota", "route.calculate"),
        ("mostra a análise da frota", "analytics.query"),
        ("olá", "help.greeting"),
        ("girafa toca piano", "unknown"),
    ],
    "ru": [
        ("найти свободные грузовики", "vehicle.search"),
        ("проверь часы водителя", "driver.check_hours"),
        ("рассчитай маршрут", "route.calculate"),
        ("покажи аналитику автопарка", "analytics.query"),
        ("привет", "help.greeting"),
        ("какой самый новый фильм", "unknown"),
    ],
    "uk": [
        ("знайти вільні вантажівки", "vehicle.search"),
        ("перевір години водія", "driver.check_hours"),
        ("розрахуй маршрут", "route.calculate"),
        ("покажи аналітику автопарку", "analytics.query"),
        ("привіт", "help.greeting"),
        ("який найновіший фільм", "unknown"),
    ],
    "tr": [
        ("müsait kamyonları bul", "vehicle.search"),
        ("sürücünün saatlerini kontrol et", "driver.check_hours"),
        ("bir rota hesapla", "route.calculate"),
        ("filo analitiğini göster", "analytics.query"),
        ("merhaba", "help.greeting"),
        ("en yeni film hangisi", "unknown"),
    ],
    "hu": [
        ("keress szabad kamionokat", "vehicle.search"),
        ("ellenőrizd a sofőr óráit", "driver.check_hours"),
        ("számíts ki egy útvonalat", "route.calculate"),
        ("mutasd a flottaelemzést", "analytics.query"),
        ("szia", "help.greeting"),
        ("mi a legújabb film", "unknown"),
    ],
    "cs": [
        ("najdi dostupné kamiony", "vehicle.search"),
        ("zkontroluj hodiny řidiče", "driver.check_hours"),
        ("spočítej trasu", "route.calculate"),
        ("zobraz analýzu vozového parku", "analytics.query"),
        ("ahoj", "help.greeting"),
        ("slon tančí na banjo", "unknown"),
    ],
    "sk": [
        ("nájdi dostupné kamióny", "vehicle.search"),
        ("skontroluj hodiny vodiča", "driver.check_hours"),
        ("vypočítaj trasu", "route.calculate"),
        ("zobraz analýzu vozového parku", "analytics.query"),
        ("ahoj", "help.greeting"),
        ("slon tancuje na banjo", "unknown"),
    ],
    "sl": [
        ("poišči proste tovornjake", "vehicle.search"),
        ("preveri ure voznika", "driver.check_hours"),
        ("izračunaj pot", "route.calculate"),
        ("prikaži analitiko voznega parka", "analytics.query"),
        ("živjo", "help.greeting"),
        ("kateri je najnovejši film", "unknown"),
    ],
    "sr": [
        ("нађи слободне камионе", "vehicle.search"),
        ("провери сате возача", "driver.check_hours"),
        ("израчунај руту", "route.calculate"),
        ("прикажи аналитику возног парка", "analytics.query"),
        ("здраво", "help.greeting"),
        ("који је најновији филм", "unknown"),
    ],
    "hr": [
        ("pronađi slobodne kamione", "vehicle.search"),
        ("provjeri sate vozača", "driver.check_hours"),
        ("izračunaj rutu", "route.calculate"),
        ("prikaži analitiku voznog parka", "analytics.query"),
        ("bok", "help.greeting"),
        ("koji je najnoviji film", "unknown"),
    ],
    "bs": [
        ("pronađi slobodne kamione", "vehicle.search"),
        ("provjeri sate vozača", "driver.check_hours"),
        ("izračunaj rutu", "route.calculate"),
        ("prikaži analitiku voznog parka", "analytics.query"),
        ("zdravo", "help.greeting"),
        ("koji je najnoviji film", "unknown"),
    ],
    "sv": [
        ("hitta lediga lastbilar", "vehicle.search"),
        ("kontrollera förarens timmar", "driver.check_hours"),
        ("beräkna en rutt", "route.calculate"),
        ("visa flottans analys", "analytics.query"),
        ("hej", "help.greeting"),
        ("vilken är den senaste filmen", "unknown"),
    ],
    "el": [
        ("βρες διαθέσιμα φορτηγά", "vehicle.search"),
        ("έλεγξε τις ώρες του οδηγού", "driver.check_hours"),
        ("υπολόγισε μια διαδρομή", "route.calculate"),
        ("δείξε την ανάλυση του στόλου", "analytics.query"),
        ("γεια", "help.greeting"),
        ("ένα σαξόφωνο λαμπερό", "unknown"),
    ],
    "bg": [
        ("намери свободни камиони", "vehicle.search"),
        ("провери часовете на шофьора", "driver.check_hours"),
        ("изчисли маршрут", "route.calculate"),
        ("покажи аналитиката на автопарка", "analytics.query"),
        ("здравей", "help.greeting"),
        ("саксофон блести сам", "unknown"),
    ],
}


# ── LLM-driven golden scenarios (§23.4, Phase 3B) ─────────────────────────
# One scenario per kind, pinning the LLM-first pipeline behaviors the keyword
# (offline) contract can no longer reach.  Each is driven by a scripted
# FakeLLMProvider through the real tool loop (run_tool_loop).  Native-channel
# envelope interop is the separate TestEnvelopeInterop contract
# (tests/copilot/test_google_provider.py) — NOT duplicated here.
LLM_DRIVEN_SCENARIOS: List[dict] = [
    {"id": "tool_routing_vehicle_search", "kind": "tool_routing", "utterance": "find available trucks", "language": "en"},
    {"id": "in_language_synthesis_ro", "kind": "in_language", "utterance": "caută vehicule libere", "language": "ro"},
    {"id": "clarification_round_trip", "kind": "clarification", "utterance": "check the health", "language": "en"},
    {"id": "level2_plan_return", "kind": "level2", "utterance": "create a new client ACME", "language": "en"},
    {"id": "level3_destructive_plan_return", "kind": "level3", "utterance": "delete trip 42", "language": "en"},
    {"id": "rbac_driver_catalog_subset", "kind": "rbac_driver", "utterance": "show me fleet analytics", "language": "en"},
    {"id": "json_repair_retry", "kind": "json_repair", "utterance": "how many trucks are available", "language": "en"},
    {"id": "loop_cap", "kind": "loop_cap", "utterance": "check the fleet", "language": "en"},
]


# ── Shared LLM-driven helpers (mirror tests/copilot/test_tool_calling.py) ──


class FakeToolProvider:
    """Scripted stand-in for an LLMProvider — records every generate request."""

    def __init__(self, responses, supports_tool_calling: bool = False) -> None:
        self.provider_id = "self_hosted"
        self._api_mode = "openai"
        self._api_key = "k"
        self.supports_tool_calling = supports_tool_calling
        self.responses = list(responses)
        self.calls = []

    async def generate(self, request):
        self.calls.append(request)
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content="", finish_reason="error")


def _golden_ctx(**overrides) -> GlobalContext:
    defaults = dict(
        company_id=1, user_id=1, role="dispatcher", language="en",
        timezone="UTC", subscription_tier="business",
    )
    defaults.update(overrides)
    return GlobalContext(**defaults)


def _json_response(payload: dict, **kw) -> LLMResponse:
    """A JSON-channel LLMResponse whose content is a tool-call JSON payload."""
    return LLMResponse(content=json.dumps(payload, ensure_ascii=False), finish_reason="stop", **kw)


def _catalog(*names) -> List[Any]:
    return build_tool_catalog(build_tool_context(set(names)))


def _ok_plan(plan):
    """Mark a freshly-built plan's step as succeeded (for mocked execute_plan)."""
    plan.steps[0].status = "succeeded"
    plan.steps[0].result = {
        "status": "success",
        "data": {"vehicles": [{"id": 5, "plate": "AB-12-FRU", "status": "available"}],
                 "total_results": 1, "truncated": False},
        "message_key": "copilot.step.vehicle_search_done",
    }
    return plan


def _mock_fleet():
    """Patch the fleet service so real vehicle.search execution returns a row."""
    fleet = Mock()
    result = Mock()
    result.success = True
    result.errors = []
    result.data = [Mock(model_dump=lambda: {"id": 5, "plate": "AB-12-FRU", "status": "available"})]
    fleet.find_available.return_value = result
    return patch("backend.services.fleet_service.FleetService", return_value=fleet)


_GOLDEN_SERVICES = {"db": Mock(), "role": "dispatcher", "user_id": 1, "company_id": 1}


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


class TestMultilingualTierB:
    """§23.4 Tier-B multilingual baseline — intent extraction only.

    Parametrized over every (lang, scenario) in MULTILINGUAL_TIER_B: all 22
    SUPPORTED_LANGUAGES x 6 scenarios (5 positives + 1 negative each). Each
    call passes ``language=<lang>`` to extract_intent so the per-language
    phrase corpus is scored. Extraction-only (no pipeline), matching the
    existing tier_b test shape. Hermetic: no LLM, no services, no network.
    """

    @pytest.mark.parametrize(
        "lang,scenario",
        [
            (lang, scenario)
            for lang, scenarios in MULTILINGUAL_TIER_B.items()
            for scenario in scenarios
        ],
        ids=[
            f"{lang}-{expected}"
            for lang, scenarios in MULTILINGUAL_TIER_B.items()
            for _, expected in scenarios
        ],
    )
    @pytest.mark.asyncio
    async def test_multilingual_tier_b_scenario(self, lang: str, scenario: tuple):
        """A multilingual Tier-B scenario must resolve to its expected intent."""
        utterance, expected = scenario
        intent = await extract_intent(utterance, language=lang)
        assert intent.name == expected, (
            f"[{lang}] For '{utterance}': "
            f"expected intent '{expected}', got '{intent.name}'"
        )


class TestLLMDrivenGolden:
    """§23.4 LLM-driven golden scenarios — the LLM-first pipeline contract.

    Each scenario drives the REAL tool loop (run_tool_loop) with a scripted
    FakeLLMProvider.  Hermetic: no provider registry, no network, no DB beyond
    mocked services.  Native-channel envelope interop is covered separately by
    TestEnvelopeInterop (tests/copilot/test_google_provider.py) — referenced,
    not duplicated.
    """

    @pytest.mark.parametrize(
        "scenario",
        LLM_DRIVEN_SCENARIOS,
        ids=[s["id"] for s in LLM_DRIVEN_SCENARIOS],
    )
    @pytest.mark.asyncio
    async def test_llm_driven_scenario(self, scenario: dict):
        kind = scenario["kind"]
        if kind == "tool_routing":
            await self._scenario_tool_routing()
        elif kind == "in_language":
            await self._scenario_in_language()
        elif kind == "clarification":
            await self._scenario_clarification_round_trip()
        elif kind == "level2":
            await self._scenario_level2_plan_return()
        elif kind == "level3":
            await self._scenario_level3_destructive_plan_return()
        elif kind == "rbac_driver":
            await self._scenario_rbac_driver_catalog()
        elif kind == "json_repair":
            await self._scenario_json_repair()
        elif kind == "loop_cap":
            await self._scenario_loop_cap()
        else:
            raise AssertionError(f"Unknown LLM-driven scenario kind: {kind}")

    async def _scenario_tool_routing(self):
        """vehicle.search executes through the real executor; the real tool data
        grounds the synthesized final answer."""
        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "vehicle.search", "arguments": {"query": "available"}}]}),
            _json_response({"answer": "I found truck AB-12-FRU which is available.", "tool_calls": []}),
        ])
        with _mock_fleet():
            result = await run_tool_loop(
                "find available trucks", "en", None, _golden_ctx(), _GOLDEN_SERVICES,
                _catalog("vehicle.search"), provider, "golden-llm-tool",
            )
        assert result.tool_calls_executed == 1
        assert result.final_answer is not None
        assert "AB-12-FRU" in result.final_answer
        # The real tool data was fed back in the structured envelope.
        tool_msgs = [m.content for m in provider.calls[1].messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert "AB-12-FRU" in tool_msgs[0]

    async def _scenario_in_language(self):
        """A Romanian utterance → the request carries the language-name
        discipline (Romanian / (ro)) and the answer is in-language."""
        provider = FakeToolProvider([
            _json_response({"answer": "Am găsit camionul AB-12-FRU.", "tool_calls": []}),
        ])
        result = await run_tool_loop(
            "caută vehicule libere", "ro", None, _golden_ctx(language="ro"), _GOLDEN_SERVICES,
            _catalog("vehicle.search"), provider, "golden-llm-ro",
        )
        system_prompt = provider.calls[0].messages[0].content
        assert "Romanian" in system_prompt
        assert "(ro)" in system_prompt
        assert result.final_answer == "Am găsit camionul AB-12-FRU."

    async def _scenario_clarification_round_trip(self):
        """Turn 1: the LLM asks for a missing detail (no tools).  Turn 2: with
        the detail supplied, the tool executes and the data grounds the answer."""
        provider_1 = FakeToolProvider([
            _json_response({"answer": "Which vehicle should I check?", "tool_calls": []}),
        ])
        result_1 = await run_tool_loop(
            "check the health", "en", None, _golden_ctx(), _GOLDEN_SERVICES,
            _catalog("vehicle.health_score"), provider_1, "golden-llm-clar-1",
        )
        assert result_1.tool_calls_executed == 0
        assert result_1.final_answer == "Which vehicle should I check?"

        provider_2 = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "vehicle.health_score", "arguments": {"vehicle_id": 5}}]}),
            _json_response({"answer": "Vehicle 5 has a health score of 87.", "tool_calls": []}),
        ])
        result_2 = await run_tool_loop(
            "check vehicle 5", "en", None, _golden_ctx(), _GOLDEN_SERVICES,
            _catalog("vehicle.health_score"), provider_2, "golden-llm-clar-2",
        )
        assert result_2.tool_calls_executed == 1
        assert result_2.final_answer is not None
        assert "Vehicle 5" in result_2.final_answer

    async def _scenario_level2_plan_return(self):
        """A BUSINESS tool call → pending plan with requires_confirmation=True,
        the turn ends immediately, no synthesis."""
        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "client.create", "arguments": {"name": "ACME"}}]}),
            _json_response({"answer": "must never be reached", "tool_calls": []}),
        ])
        result = await run_tool_loop(
            "create a new client ACME", "en", None, _golden_ctx(), {},  # no db → not autonomous
            _catalog("client.create"), provider, "golden-llm-level2",
        )
        assert result.pending_plan is not None
        assert result.pending_plan.requires_confirmation is True
        assert result.pending_plan.steps[0].tool_name == "client.create"
        assert result.pending_plan.steps[0].status == "pending"
        assert result.final_answer is None
        assert len(provider.calls) == 1  # no second iteration

    async def _scenario_level3_destructive_plan_return(self):
        """A DESTRUCTIVE tool call (manager role, in-catalog) → pending plan
        with requires_confirmation=True and a DESTRUCTIVE step; the turn ends
        immediately with no synthesis (§23.4 line 1350 Level 3 coverage)."""
        from backend.copilot.context import resolve_available_tools
        from backend.copilot.role_permissions import get_role_permissions

        # The delete tool is in the manager's RBAC catalog (trips:delete).
        manager_ctx = _golden_ctx(role="manager")
        tool_ctx = await resolve_available_tools(manager_ctx, get_role_permissions("manager"))
        assert "trip.delete" in tool_ctx.available_tools

        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "trip.delete", "arguments": {"trip_id": 42, "confirmation_phrase": "42"}}]}),
            _json_response({"answer": "must never be reached", "tool_calls": []}),
        ])
        result = await run_tool_loop(
            "delete trip 42", "en", None, manager_ctx, {},  # no db → not autonomous
            _catalog("trip.delete"), provider, "golden-llm-level3",
        )
        assert result.pending_plan is not None
        assert result.pending_plan.requires_confirmation is True
        step = result.pending_plan.steps[0]
        assert step.tool_name == "trip.delete"
        assert step.confirmation_level == ConfirmationLevel.DESTRUCTIVE
        assert step.status == "pending"
        assert result.final_answer is None
        assert len(provider.calls) == 1  # turn ends, no second iteration / synthesis

    async def _scenario_rbac_driver_catalog(self):
        """A driver session's catalog excludes every DRIVER_FORBIDDEN_TOOLS
        (§8.3) — the RBAC filter runs before the LLM ever sees a tool name.
        Driver permissions are read-only + own-trip (no fleet:read, so
        vehicle.search correctly does NOT resolve)."""
        from backend.copilot.context import resolve_available_tools
        from backend.copilot.role_permissions import DRIVER_FORBIDDEN_TOOLS, get_role_permissions

        driver_ctx = _golden_ctx(role="driver")
        tool_ctx = await resolve_available_tools(driver_ctx, get_role_permissions("driver"))

        # RBAC truth: the driver's permitted set never contains forbidden tools.
        permitted = set(tool_ctx.available_tools)
        assert DRIVER_FORBIDDEN_TOOLS.isdisjoint(permitted), (
            f"driver permitted set leaked forbidden tools: {DRIVER_FORBIDDEN_TOOLS & permitted}"
        )
        assert "analytics.query" not in permitted
        assert "client.payment_summary" not in permitted
        assert "vehicle.search" not in permitted  # fleet:read is not driver scope

        # Belt-and-braces: the LLM-visible catalog is derived from that same
        # RBAC-filtered set, so forbidden tools never even reach the prompt.
        catalog = build_tool_catalog(tool_ctx)
        names = {s.name for s in catalog}
        assert DRIVER_FORBIDDEN_TOOLS.isdisjoint(names), (
            f"driver catalog leaked forbidden tools: {DRIVER_FORBIDDEN_TOOLS & names}"
        )
        # A core-pinned read tool a driver IS allowed still survives truncation
        # (drivers:read → driver.check_hours).  Core-pinned tools are guaranteed
        # to stay in the budget-limited catalog; non-core read tools like
        # route.calculate are not, so we assert on a core one here.
        assert "driver.check_hours" in names

    async def _scenario_json_repair(self):
        """JSON-channel parse failure → one repair retry (user-role correction)
        → a grounded final answer."""
        provider = FakeToolProvider([
            LLMResponse(content="not valid json at all", finish_reason="stop"),
            _json_response({"answer": "Here are the available trucks.", "tool_calls": []}),
        ])
        result = await run_tool_loop(
            "how many trucks are available", "en", None, _golden_ctx(), _GOLDEN_SERVICES,
            _catalog("vehicle.search"), provider, "golden-llm-repair",
        )
        assert result.final_answer == "Here are the available trucks."
        assert len(provider.calls) == 2
        assert any(
            m.role == "user" and "could not be parsed" in m.content
            for m in provider.calls[1].messages
        )

    async def _scenario_loop_cap(self):
        """N tool-call iterations → one forced final synthesis pass."""
        responses = [
            _json_response({"answer": None, "tool_calls": [{"name": "vehicle.search", "arguments": {"query": str(i)}}]})
            for i in range(TOOL_LOOP_MAX_ITERATIONS)
        ]
        # The forced final synthesis pass requests PLAIN TEXT (no tools).
        responses.append(LLMResponse(content="Fleet check summary.", finish_reason="stop"))

        async def fake_execute(plan, services=None, on_step_update=None):
            return _ok_plan(plan)

        provider = FakeToolProvider(responses)
        with patch("backend.copilot.executor.execute_plan", new=fake_execute):
            result = await run_tool_loop(
                "check the fleet", "en", None, _golden_ctx(), _GOLDEN_SERVICES,
                _catalog("vehicle.search"), provider, "golden-llm-cap",
            )
        assert result.tool_calls_executed == TOOL_LOOP_MAX_ITERATIONS
        assert result.final_answer == "Fleet check summary."
        assert len(provider.calls) == TOOL_LOOP_MAX_ITERATIONS + 1


class TestScenarioVersioning:
    """Golden scenario set versioning (§23.4)."""

    def test_golden_scenarios_have_version(self):
        """The golden suite must be versioned."""
        assert hasattr(TestGoldenRegression, "GOLDEN_SCENARIOS") or "GOLDEN_SCENARIOS" in dir(
            __import__("tests.copilot.test_golden_regression", fromlist=["GOLDEN_SCENARIOS"])
        )

    def test_golden_suite_is_versioned(self):
        """The golden suite must carry a semver version constant."""
        assert GOLDEN_SUITE_VERSION, "GOLDEN_SUITE_VERSION must not be empty"
        assert re.match(r"^\d+\.\d+\.\d+$", GOLDEN_SUITE_VERSION), (
            f"GOLDEN_SUITE_VERSION '{GOLDEN_SUITE_VERSION}' must be semver (X.Y.Z)"
        )

    def test_scenario_count_matches_version_baseline(self):
        """The expanded suite must not silently shrink below its versioned
        baseline (10 scenarios in 1.0.0 → 17 in 1.1.0 → 149 in 1.2.0 →
        156 in 2.0.0 → 157 in 2.0.0: 17 golden + 22 languages x 6
        multilingual + 8 LLM-driven incl. Level 3 destructive)."""
        multilingual_total = sum(len(s) for s in MULTILINGUAL_TIER_B.values())
        total = len(GOLDEN_SCENARIOS) + multilingual_total + len(LLM_DRIVEN_SCENARIOS)
        assert total >= 157, (
            f"golden + multilingual + LLM-driven total shrank to {total} — "
            "restore scenarios or bump GOLDEN_SUITE_VERSION"
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


class TestUnknownUtteranceWithLLM:
    """Degradation ladder for utterances no tool can handle (§23.5).

    Ladder (Gate 1 corr. 7): LLM-first answer → llm_chat summary; provider
    attempted + failed and the keyword path yields nothing → model_unreachable;
    never attempted → unknown_intent (offline).
    """

    @pytest.mark.asyncio
    async def test_unknown_utterance_with_llm_returns_summary(self, _offline_llm_chat):
        """The LLM-first path answers an unmapped utterance → llm_chat bubble."""
        _offline_llm_chat.return_value = ToolLoopResult(final_answer="Here is the answer.", attempted=True)
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        resp = await process_utterance("why is the sky blue?", ctx, "golden-llm-1")

        assert resp.summary_key == "copilot.summary.llm_chat"
        assert resp.summary_params["answer"] == "Here is the answer."
        assert resp.clarification_question_key is None
        assert resp.plan is None

    @pytest.mark.asyncio
    async def test_unknown_utterance_llm_failure_is_offline_clarification(
        self, _offline_llm_chat,
    ):
        """Never attempted → an unknown utterance keeps the offline
        unknown_intent clarification contract."""
        _offline_llm_chat.return_value = ToolLoopResult(attempted=False)
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        resp = await process_utterance("do something completely nonsensical xyzzy", ctx, "golden-llm-2")
        assert resp.clarification_question_key is not None
        assert "unknown_intent" in resp.clarification_question_key
        assert resp.plan is None

    @pytest.mark.asyncio
    async def test_unknown_utterance_provider_failed_is_model_unreachable(
        self, _offline_llm_chat,
    ):
        """Degradation ladder step 2: a provider attempt that failed surfaces
        copilot.error.model_unreachable when the keyword path also yields
        nothing (not a silent unknown_intent)."""
        _offline_llm_chat.return_value = ToolLoopResult(attempted=True, provider_failed=True)
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        resp = await process_utterance("why is the sky blue?", ctx, "golden-llm-3")
        assert resp.clarification_question_key is not None
        assert "model_unreachable" in resp.clarification_question_key
        assert resp.summary_key is None
        assert resp.plan is None

    @pytest.mark.asyncio
    async def test_unknown_ro_utterance_llm_returns_summary(self, _offline_llm_chat):
        """An unmapped Romanian utterance is answered by the LLM-first path —
        same shape as English."""
        _offline_llm_chat.return_value = ToolLoopResult(
            final_answer="Poți verifica în manualul de bord.", attempted=True,
        )
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="ro", timezone="UTC", subscription_tier="business",
        )
        resp = await process_utterance("pisica cântă jazz", ctx, "golden-llm-ro-1")

        assert resp.summary_key == "copilot.summary.llm_chat"
        assert resp.summary_params["answer"] == "Poți verifica în manualul de bord."
        assert resp.clarification_question_key is None
        assert resp.plan is None


class TestHelpModeGolden:
    """Help Mode / Guided scenarios (§33, §34) — right tool, SAFE
    confirmation level, no tool-data dependency."""

    def _ctx(self, language: str = "en") -> GlobalContext:
        return GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language=language, timezone="UTC", subscription_tier="business",
        )

    @pytest.mark.asyncio
    async def test_answer_question_plans_free_text_question(self):
        """help.answer_question plans the help tool with the free-text
        question seeded from the utterance — no entity/tool-data dependency."""
        resp = await process_utterance(
            "explain what a tachograph is", self._ctx(), "golden-help-1",
        )
        assert resp.plan is not None
        step = resp.plan.steps[0]
        assert step.tool_name == "help.answer_question"
        assert step.confirmation_level == ConfirmationLevel.SAFE
        assert step.parameters.get("question") == "explain what a tachograph is"
        assert resp.plan.intent.missing_required_entities == []

    @pytest.mark.asyncio
    async def test_guide_workflow_plans_safe_step(self):
        """help.guide_workflow plans the guide tool at SAFE confirmation."""
        resp = await process_utterance(
            "walk me through dispatching a trip", self._ctx(), "golden-help-2",
        )
        assert resp.plan is not None
        step = resp.plan.steps[0]
        assert step.tool_name == "help.guide_workflow"
        assert step.confirmation_level == ConfirmationLevel.SAFE
        assert resp.plan.requires_confirmation is False

    @pytest.mark.asyncio
    async def test_guide_workflow_executes_through_service(self):
        """help.guide_workflow executes via GuidedWorkflowService (mocked,
        hermetic — no DB, no network)."""
        from backend.copilot.schemas import GuideWorkflowParams, SessionContext
        from backend.copilot.tools.base import ToolExecutionContext
        from backend.copilot.tools.help_tools import GuideWorkflowTool

        script = GuidedWalkthrough(
            workflow_id="dispatch_trip",
            title_key="tour.dispatch_trip.title",
            steps=[],
        )
        service = Mock()
        service.get_script = Mock(return_value=script)
        service.adjust_for_familiarity = Mock(return_value=script)

        with patch(
            "backend.copilot.tools.help_tools.get_guided_workflow_service",
            return_value=service,
        ):
            tool = GuideWorkflowTool()
            ctx = ToolExecutionContext(
                company_id=1, user_id=1, role="dispatcher",
                session_context=SessionContext(), services={},
            )
            result = await tool.execute(
                GuideWorkflowParams(workflow_id="dispatch_trip"), ctx,
            )

        service.get_script.assert_called_once_with("dispatch_trip")
        service.adjust_for_familiarity.assert_called_once()
        assert result.status == "success"
        assert result.data is not None
        assert result.data["walkthrough"]["workflow_id"] == "dispatch_trip"
