"""Tests for the LLM-first tool-calling brain (§23.4).

Covers: catalog build (RBAC filter + size-budget truncation), strict JSON
tool-call parsing, catalog validation, the tool loop (direct answer, execute →
synthesize, repair retry, hallucinated tool denial, Level 2 pending plan, mixed
turn split, loop cap), the native-tools channel, and the derived reasoning graph.

Hermetic: a FakeProvider scripts the LLM responses; tool execution either uses
the real executor with a patched fleet service or a mocked ``execute_plan``.
"""
from __future__ import annotations

import json
import logging

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.copilot.llm.base import LLMResponse, ToolSpec
from backend.copilot.llm.tool_calling import (
    CATALOG_MAX_CHARS,
    TOOL_LOOP_MAX_ITERATIONS,
    build_tool_catalog,
    build_tool_context,
    catalog_to_prompt_text,
    derive_reasoning_graph,
    parse_tool_call_json,
    run_tool_loop,
    validate_tool_call,
)
from backend.copilot.planner import _ensure_tools_loaded
from backend.copilot.schemas import GlobalContext, ToolContext

_ensure_tools_loaded()


# ── Helpers ─────────────────────────────────────────────────────────────────


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


def _ctx(**overrides) -> GlobalContext:
    defaults = dict(
        company_id=1, user_id=1, role="dispatcher", language="en",
        timezone="UTC", subscription_tier="business",
    )
    defaults.update(overrides)
    return GlobalContext(**defaults)


def _json_response(payload: dict, **kw) -> LLMResponse:
    """A JSON-channel LLMResponse whose content is a tool-call JSON payload."""
    return LLMResponse(content=json.dumps(payload, ensure_ascii=False), finish_reason="stop", **kw)


def _catalog(*names) -> list[ToolSpec]:
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
    fleet = MagicMock()
    result = MagicMock()
    result.success = True
    result.errors = []
    result.data = [MagicMock(model_dump=lambda: {"id": 5, "plate": "AB-12-FRU", "status": "available"})]
    fleet.find_available.return_value = result
    return patch("backend.services.fleet_service.FleetService", return_value=fleet)


_SERVICES = {"db": MagicMock(), "role": "dispatcher", "user_id": 1, "company_id": 1}


# ── Catalog ─────────────────────────────────────────────────────────────────


class TestBuildToolCatalog:
    def test_catalog_is_rbac_filtered(self):
        """Only the permitted tools appear, with confirmation level attached."""
        catalog = _catalog("vehicle.search", "client.create")
        names = [s.name for s in catalog]
        assert names == ["vehicle.search", "client.create"]  # stable sort by level
        by_name = {s.name: s for s in catalog}
        assert by_name["vehicle.search"].confirmation_level == "SAFE"
        assert by_name["client.create"].confirmation_level == "BUSINESS"
        assert "parameters_json_schema" in by_name["vehicle.search"].model_dump()

    def test_catalog_priority_order_safe_first(self):
        """SAFE/INFO tools sort before BUSINESS/DESTRUCTIVE regardless of name."""
        catalog = _catalog("client.create", "vehicle.search", "route.calculate")
        names = [s.name for s in catalog]
        assert names.index("route.calculate") < names.index("client.create")

    def test_catalog_truncation_appends_note_tool(self):
        """Over-budget catalogs drop lower-priority tools and add help.capabilities."""
        many = [s.name for s in _catalog(
            "vehicle.search", "vehicle.health_score", "driver.check_hours",
            "route.calculate", "analytics.query", "client.create", "trip.create",
        )]
        assert len(many) > 3
        with patch("backend.copilot.llm.tool_calling.CATALOG_MAX_CHARS", 200):
            truncated = build_tool_catalog(build_tool_context(set(many)))
        assert truncated[-1].name == "help.capabilities"
        assert "truncated" in truncated[-1].description.lower()
        # The synthetic note tool is NOT executable.
        tool, err = validate_tool_call({"name": "help.capabilities", "arguments": {}}, truncated)
        assert tool is None and err is not None

    def test_catalog_to_prompt_text_embeds_names(self):
        text = catalog_to_prompt_text(_catalog("vehicle.search"))
        assert "vehicle.search" in text
        assert "level=SAFE" in text


# ── Parsing & validation ────────────────────────────────────────────────────


class TestParseToolCallJson:
    def test_plain_json(self):
        data = parse_tool_call_json('{"answer": null, "tool_calls": [{"name": "a"}]}')
        assert data == {"answer": None, "tool_calls": [{"name": "a"}]}

    def test_markdown_fence_and_trailing_text(self):
        text = 'Sure, here you go:\n```json\n{"answer": "hi", "tool_calls": []}\n```\nHope that helps.'
        data = parse_tool_call_json(text)
        assert data is not None
        assert data["answer"] == "hi"

    def test_nested_braces_in_arguments(self):
        text = '{"answer": null, "tool_calls": [{"name": "a", "arguments": {"nested": {"x": [1, 2]}}}]}'
        data = parse_tool_call_json(text)
        assert data is not None
        assert data["tool_calls"][0]["arguments"]["nested"] == {"x": [1, 2]}

    def test_unparseable_returns_none(self):
        assert parse_tool_call_json("garbage not json at all") is None
        assert parse_tool_call_json("") is None
        assert parse_tool_call_json('{"broken": ') is None


class TestValidateToolCall:
    def _catalog(self):
        return _catalog("vehicle.search")

    def test_valid_call(self):
        tool, err = validate_tool_call({"name": "vehicle.search", "arguments": {"query": "x"}}, self._catalog())
        assert tool is not None and tool.name == "vehicle.search"
        assert err is None

    def test_unknown_tool_rejected(self):
        tool, err = validate_tool_call({"name": "dispatch.nuke", "arguments": {}}, self._catalog())
        assert tool is None
        assert err is not None
        assert "not available to you" in err

    def test_missing_name_rejected(self):
        tool, err = validate_tool_call({"arguments": {}}, self._catalog())
        assert tool is None
        assert err is not None

    def test_invalid_arguments_rejected(self):
        # vehicle.health_score requires int vehicle_id — a string here coerces,
        # but a totally wrong type (list) fails construction.
        catalog = _catalog("vehicle.health_score")
        tool, err = validate_tool_call({"name": "vehicle.health_score", "arguments": {"vehicle_id": []}}, catalog)
        assert tool is None
        assert err is not None
        assert "invalid arguments" in err


# ── Tool loop ───────────────────────────────────────────────────────────────


class TestToolLoop:
    async def _run(self, provider, **kw):
        return await run_tool_loop(
            utterance=kw.pop("utterance", "find available trucks"),
            language=kw.pop("language", "en"),
            history=kw.pop("history", None),
            global_ctx=kw.pop("global_ctx", _ctx()),
            services=kw.pop("services", _SERVICES),
            catalog=kw.pop("catalog", _catalog("vehicle.search", "client.create")),
            provider=provider,
            conversation_id=kw.pop("conversation_id", "test-conv"),
            permitted_tools=kw.pop("permitted_tools", None),
            on_step_update=kw.pop("on_step_update", None),
            **kw,
        )

    @pytest.mark.asyncio
    async def test_direct_answer_no_tools(self):
        """finish_reason stop + no tool_calls → the JSON answer is final."""
        provider = FakeToolProvider([_json_response({"answer": "hello", "tool_calls": []})])
        result = await self._run(provider)
        assert result.final_answer == "hello"
        assert result.tool_calls_executed == 0
        assert result.pending_plan is None
        # JSON channel: request used response_format json, no native tools.
        assert provider.calls[0].response_format == "json"
        assert provider.calls[0].tools == []

    @pytest.mark.asyncio
    async def test_tool_call_executes_and_synthesizes(self):
        """vehicle.search executes through the real executor; data flows back
        into the LLM context and the final synthesized answer."""
        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "vehicle.search", "arguments": {"query": "available"}}]}),
            _json_response({"answer": "I found truck AB-12-FRU which is available.", "tool_calls": []}),
        ])
        with _mock_fleet():
            result = await self._run(provider)
        assert result.final_answer == "I found truck AB-12-FRU which is available."
        assert result.tool_calls_executed == 1
        # The tool result envelope is fed back as a tool message — pure JSON
        # per the adapter contract ({"tool_name", "response"}).
        tool_msgs = [m.content for m in provider.calls[1].messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert "tool_name" in tool_msgs[0]
        assert "vehicle.search" in tool_msgs[0]
        assert "AB-12-FRU" in tool_msgs[0]

    @pytest.mark.asyncio
    async def test_executor_called_with_right_step_and_rbac_intact(self):
        """execute_plan receives the validated single-step plan (RBAC/audit intact)."""
        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "vehicle.search", "arguments": {"query": "x"}}]}),
            _json_response({"answer": "done", "tool_calls": []}),
        ])
        captured = {}

        async def fake_execute(plan, services=None, on_step_update=None):
            captured["plan"] = plan
            return _ok_plan(plan)

        with patch("backend.copilot.executor.execute_plan", new=fake_execute):
            result = await self._run(provider)
        assert result.tool_calls_executed == 1
        plan = captured["plan"]
        assert plan.steps[0].tool_name == "vehicle.search"
        assert plan.steps[0].parameters == {"query": "x"}
        assert plan.steps[0].confirmation_level.name == "SAFE"
        assert plan.intent.raw_utterance == "find available trucks"

    @pytest.mark.asyncio
    async def test_repair_retry_on_unparseable_json(self):
        """One repair retry injects the explicit parse error, then the answer.
        The correction is user-role — OpenAI-compat backends reject non-leading
        system messages (Gate 2 corr. 4)."""
        provider = FakeToolProvider([
            LLMResponse(content="I cannot parse this nonsense", finish_reason="stop"),
            _json_response({"answer": "fixed", "tool_calls": []}),
        ])
        result = await self._run(provider)
        assert result.final_answer == "fixed"
        assert len(provider.calls) == 2
        repair_msgs = provider.calls[1].messages
        assert repair_msgs[0].role == "system"  # only the leading system prompt
        assert all(m.role != "system" for m in repair_msgs[1:])
        assert any(m.role == "user" and "could not be parsed" in m.content for m in repair_msgs)

    @pytest.mark.asyncio
    async def test_final_synthesis_neutralizes_json_output_format(self):
        """Gate 2 corr. 2: the final pass strips the baked-in JSON OUTPUT FORMAT
        clause and injects an explicit plain-text override."""
        provider = FakeToolProvider([
            LLMResponse(content="garbage not json", finish_reason="stop"),
            LLMResponse(content="still not json", finish_reason="stop"),
            LLMResponse(content="plain text answer", finish_reason="stop"),
        ])
        result = await self._run(provider)
        assert result.final_answer == "plain text answer"
        final_msgs = provider.calls[2].messages
        # The system prompt no longer carries the JSON-only output instruction.
        sys_msg = next(m for m in final_msgs if m.role == "system")
        assert "OUTPUT FORMAT: reply with ONLY a single JSON object" not in sys_msg.content
        # An explicit neutralization override is present as a user message.
        assert any(
            m.role == "user" and "IGNORE the earlier JSON output-format instruction" in m.content
            for m in final_msgs
        )

    @pytest.mark.asyncio
    async def test_hallucinated_tool_never_executes_and_is_logged(self, caplog):
        """A tool not in the catalog is NEVER executed, is logged, and the turn
        finishes with an apologetic/plain final answer."""
        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "dispatch.nuke", "arguments": {"id": 1}}]}),
            _json_response({"answer": "I cannot do that — that tool is not available to you.", "tool_calls": []}),
        ])
        with patch("backend.copilot.executor.execute_plan", new_callable=AsyncMock) as mock_exec:
            with caplog.at_level(logging.WARNING, logger="backend.copilot.llm.tool_calling"):
                result = await self._run(provider)
        assert result.tool_calls_executed == 0
        assert result.final_answer is not None
        assert "not available to you" in result.final_answer
        mock_exec.assert_not_awaited()
        assert any("LLM tool call denied" in rec.getMessage() for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_level2_returns_pending_plan_and_ends_turn(self):
        """A BUSINESS call → requires_confirmation plan, turn ends immediately."""
        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [{"name": "client.create", "arguments": {"name": "ACME"}}]}),
            _json_response({"answer": "should never be reached", "tool_calls": []}),
        ])
        result = await self._run(provider, services={})  # no db → not autonomous
        assert result.pending_plan is not None
        assert result.pending_plan.requires_confirmation is True
        assert result.pending_plan.steps[0].tool_name == "client.create"
        assert result.pending_plan.steps[0].status == "pending"
        assert result.final_answer is None
        assert len(provider.calls) == 1, "turn must end without further iterations"

    @pytest.mark.asyncio
    async def test_mixed_turn_splits_safe_and_business(self):
        """SAFE calls execute in-loop; the mutation part becomes the pending plan."""
        provider = FakeToolProvider([
            _json_response({"answer": None, "tool_calls": [
                {"name": "vehicle.search", "arguments": {"query": "available"}},
                {"name": "client.create", "arguments": {"name": "ACME"}},
            ]}),
        ])
        with _mock_fleet():
            result = await self._run(provider, services={})
        assert result.tool_calls_executed == 1
        assert result.pending_plan is not None
        assert result.pending_plan.steps[0].tool_name == "client.create"
        assert result.final_answer is None
        assert len(provider.calls) == 1

    @pytest.mark.asyncio
    async def test_loop_cap_forces_final_synthesis(self):
        """N iterations of tool calls → one forced final synthesis pass."""
        responses = [
            _json_response({"answer": None, "tool_calls": [{"name": "vehicle.search", "arguments": {"query": str(i)}}]})
            for i in range(TOOL_LOOP_MAX_ITERATIONS)
        ]
        # The forced final synthesis pass requests PLAIN TEXT (no tools).
        responses.append(LLMResponse(content="summary answer", finish_reason="stop"))

        async def fake_execute(plan, services=None, on_step_update=None):
            return _ok_plan(plan)

        provider = FakeToolProvider(responses)
        with patch("backend.copilot.executor.execute_plan", new=fake_execute):
            result = await self._run(provider)
        assert result.final_answer == "summary answer"
        assert result.tool_calls_executed == TOOL_LOOP_MAX_ITERATIONS
        assert len(provider.calls) == TOOL_LOOP_MAX_ITERATIONS + 1  # +1 final synthesis

    @pytest.mark.asyncio
    async def test_native_channel_sends_tools_and_reads_tool_calls(self):
        """supports_tool_calling → request.tools = catalog, tool_calls from response."""
        provider = FakeToolProvider(
            [
                LLMResponse(content="", tool_calls=[{"id": "1", "name": "vehicle.search", "arguments": {"query": "x"}}], finish_reason="tool_call"),
                LLMResponse(content="found it", finish_reason="stop"),
            ],
            supports_tool_calling=True,
        )

        async def fake_execute(plan, services=None, on_step_update=None):
            return _ok_plan(plan)

        with patch("backend.copilot.executor.execute_plan", new=fake_execute):
            result = await self._run(provider)
        assert result.final_answer == "found it"
        assert result.tool_calls_executed == 1
        assert provider.calls[0].tools  # native channel carries the catalog
        assert provider.calls[0].response_format == "text"
        # The tool result forwards the originating call id so Gemini pairs the
        # functionResponse with the original function_call (Gate 2 corr. 1).
        tool_msgs = [m for m in provider.calls[1].messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "1"

    @pytest.mark.asyncio
    async def test_ui_context_injected_into_prompt_when_provided(self):
        """Gate 2 corr. 3: sanitized UI/session context is injected as DATA."""
        from backend.copilot.schemas import SessionContext, UIContext

        ui = UIContext(active_screen="fleet_panel", selected_entity_type="vehicle", selected_entity_id=42)
        session = SessionContext(current_vehicle_id=7)
        provider = FakeToolProvider([_json_response({"answer": "ok", "tool_calls": []})])
        await self._run(provider, ui_context=ui, session_ctx=session)
        system = provider.calls[0].messages[0].content
        assert "User's current UI context" in system
        assert "screen=fleet_panel" in system
        assert "selected entity type=vehicle" in system
        assert "id=42" in system
        assert "current vehicle=7" in system

    @pytest.mark.asyncio
    async def test_ui_context_absent_when_not_provided(self):
        """Without ui_context/session_ctx the prompt carries no context line."""
        provider = FakeToolProvider([_json_response({"answer": "ok", "tool_calls": []})])
        await self._run(provider)
        assert "User's current UI context" not in provider.calls[0].messages[0].content

    @pytest.mark.asyncio
    async def test_provider_error_marks_provider_failed(self):
        """A provider error aborts the loop (degradation ladder, not the breaker)."""
        provider = FakeToolProvider([LLMResponse(content="", finish_reason="error")])
        result = await self._run(provider)
        assert result.provider_failed is True
        assert result.final_answer is None

    @pytest.mark.asyncio
    async def test_partial_execution_provider_failure_no_keyword_rerun(self):
        """Gate 2 corr. 5: the LLM executed a tool then the provider failed →
        a partial-result response is returned and the keyword path is NOT
        re-run (re-executing INFORMATIONAL tools would duplicate side effects)."""
        from backend.copilot.llm.tool_calling import ToolLoopResult
        from backend.copilot.planner import process_utterance
        from backend.copilot.schemas import ConfirmationLevel, ExecutionStep

        step = ExecutionStep(
            step_id="vehicle.search-0",
            tool_name="vehicle.search",
            tool_version="1.0.0",
            parameters={"query": "x"},
            depends_on=[],
            confirmation_level=ConfirmationLevel.SAFE,
            status="succeeded",
            result={"status": "success", "data": {"vehicles": [{"id": 5}], "total_results": 1, "truncated": False},
                    "message_key": "copilot.step.vehicle_search_done"},
        )
        partial = ToolLoopResult(
            provider_failed=True,
            attempted=True,
            tool_calls_executed=1,
            executed_steps=[step],
            reasoning_graph=derive_reasoning_graph(
                [{"name": "vehicle.search", "arguments": {"query": "x"}}], None, "pc",
            ),
        )

        with patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock, return_value=partial,
        ) as mock_loop:
            with patch(
                "backend.copilot.planner.extract_intent",
                new_callable=AsyncMock,
                side_effect=AssertionError("keyword path must not re-run after partial LLM execution"),
            ) as mock_intent:
                # "find available trucks" now pre-passes deterministically, so
                # the guard is exercised with an utterance that genuinely
                # reaches the LLM (unknown → gate fails → LLM-first tool loop).
                resp = await process_utterance(
                    "do something completely nonsensical xyzzy", _ctx(), "partial-conv",
                )

        mock_loop.assert_awaited_once()
        mock_intent.assert_not_awaited()
        assert resp.clarification_question_key == "copilot.error.model_unreachable"
        assert resp.plan is None
        # The executed tool outcome is attached to the partial response.
        assert len(resp.timeline) == 1
        assert resp.timeline[0].tool_name == "vehicle.search"
        assert resp.timeline[0].status == "succeeded"


# ── Derived reasoning graph ─────────────────────────────────────────────────


class TestDeriveReasoningGraph:
    def test_shape_matches_reasoning_graph_contract(self):
        calls = [
            {"name": "vehicle.search", "arguments": {"query": "available"}},
            {"name": "client.create", "arguments": {"name": "ACME"}, "denied": True},
        ]
        graph = derive_reasoning_graph(calls, "final answer text", conversation_id="conv-1")
        assert graph["conversation_id"] == "conv-1"
        assert graph["root_node_id"] == "goal-llm-turn"
        nodes = graph["nodes"]
        root = nodes["goal-llm-turn"]
        assert root["type"] == "goal"
        # one QUERY per tool call + a DECISION for the answer
        queries = [n for n in nodes.values() if n["type"] == "query"]
        assert len(queries) == 2
        assert queries[1]["status"] == "failed"  # denied call recorded as failed
        assert queries[0]["tool_name"] == "vehicle.search"
        # REQUIREMENT nodes under each query
        reqs = [n for n in nodes.values() if n["type"] == "requirement"]
        assert len(reqs) == 2
        decisions = [n for n in nodes.values() if n["type"] == "decision"]
        assert len(decisions) == 1
        assert decisions[0]["resolved_value"] == "final answer text"
        assert root["children"]  # root links to its query/decision children

    def test_no_answer_no_decision_node(self):
        graph = derive_reasoning_graph([{"name": "vehicle.search", "arguments": {}}], None)
        assert all(n["type"] != "decision" for n in graph["nodes"].values())