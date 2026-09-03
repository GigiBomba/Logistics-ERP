"""Comprehensive unit tests for GoogleProvider (Gemini via google-genai SDK).

Covers:
  - Construction & attributes
  - Role mapping (system→user, assistant→model, tool→user)
  - Content building (single, multi, empty)
  - Tool building (single, multi, empty)
  - generate() with mocked client (text, finish_reason extraction, tool call parsing,
    token counting, JSON mode, system instruction, empty responses)
  - Streaming (chunk iteration, API call verification, error propagation)
  - Error propagation (generic, auth, rate-limit, timeout)
  - Health check (healthy, degraded, down)
  - Config building (parameter passthrough)
  - Token counting (success, fallback, empty, None response)
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest

from backend.copilot.llm.base import LLMMessage, LLMRequest, LLMResponse, ToolSpec


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_part(text: str = "", function_call: Any = None) -> MagicMock:
    """Build a mock content part with optional text and function_call."""
    part = MagicMock(spec_set=["text", "function_call"])
    part.text = text
    part.function_call = function_call  # None → falsy; a mock → truthy
    return part


def _mock_function_call(name: str, args: dict, call_id: str = "") -> MagicMock:
    """Build a mock function_call part."""
    fc = MagicMock(spec=["name", "args", "id"])
    fc.name = name
    fc.args = args
    fc.id = call_id
    return fc


def _mock_candidate(
    parts: List[MagicMock],
    finish_reason: Any = None,
) -> MagicMock:
    """Build a mock Candidate."""
    candidate = MagicMock(spec=["content", "finish_reason"])
    candidate.content = MagicMock(spec=["parts"])
    candidate.content.parts = parts
    candidate.finish_reason = finish_reason
    return candidate


def _mock_response(
    candidates: List[MagicMock] | None = None,
    prompt_tokens: int = 10,
    output_tokens: int = 20,
) -> MagicMock:
    """Build a mock generate_content response."""
    response = MagicMock(spec=["candidates", "usage_metadata"])
    if candidates is not None:
        response.candidates = candidates
    else:
        response.candidates = None
    response.usage_metadata = MagicMock(spec=["prompt_token_count", "candidates_token_count"])
    response.usage_metadata.prompt_token_count = prompt_tokens
    response.usage_metadata.candidates_token_count = output_tokens
    return response


def _mock_finish_reason(label: str) -> MagicMock:
    """Build a mock finish_reason whose str() returns *label*."""
    fr = MagicMock()
    fr.__str__ = MagicMock(return_value=label)
    return fr


def _stream_chunk(text: str) -> MagicMock:
    """Build a single streaming chunk that yields *text*."""
    chunk = MagicMock(spec=["candidates"])
    candidate = MagicMock(spec=["content"])
    candidate.content = MagicMock(spec=["parts"])
    candidate.content.parts = [_mock_part(text=text)]
    chunk.candidates = [candidate]
    return chunk


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def provider():
    """Return a GoogleProvider with a dummy API key (client is mocked per test)."""
    from backend.copilot.llm.providers.google_provider import GoogleProvider

    return GoogleProvider(model_id="gemini-test", api_key="fake-api-key")


@pytest.fixture
def mock_genai():
    """Patch *both* genai and genai_types at the provider module level.

    google_provider.py does::

        from google import genai
        from google.genai import types as genai_types

    We replace both names so that every SDK call inside the provider is
    intercepted by MagicMock objects.
    """
    with (
        patch("backend.copilot.llm.providers.google_provider.genai") as mock_genai_mod,
        patch("backend.copilot.llm.providers.google_provider.genai_types") as mock_types,
    ):
        client = MagicMock()
        client.models = MagicMock()
        mock_genai_mod.Client.return_value = client

        # Make GenerateContentConfig preserve keyword arguments as attributes
        def _config_factory(**kwargs: Any) -> MagicMock:
            return MagicMock(**kwargs)

        mock_types.GenerateContentConfig.side_effect = _config_factory

        yield {
            "client": client,
            "genai": mock_genai_mod,
            "types": mock_types,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  Construction & Attributes
# ═══════════════════════════════════════════════════════════════════════════════


class TestConstruction:
    """Provider initialisation and basic attribute assertions."""

    def test_construction_with_explicit_model(self):
        """Provider can be built with a model_id and api_key."""
        from backend.copilot.llm.providers.google_provider import GoogleProvider

        p = GoogleProvider(model_id="gemini-2.5-flash", api_key="test-key")
        assert p.provider_id == "google"
        assert p.model_id == "gemini-2.5-flash"
        assert p.supports_tool_calling is True
        assert p.supports_json_mode is True
        assert p.is_self_hosted is False

    def test_default_model(self):
        """Default model_id is gemini-2.5-flash."""
        from backend.copilot.llm.providers.google_provider import GoogleProvider

        p = GoogleProvider(api_key="test")
        assert p.model_id == "gemini-2.5-flash"

    def test_client_is_lazily_initialised(self, provider, mock_genai):
        """_get_client() creates the SDK client on first call and reuses it."""
        # First call → creates client
        c1 = provider._get_client()
        assert c1 is not None
        mock_genai["genai"].Client.assert_called_once_with(api_key="fake-api-key")

        # Second call → same instance, no extra construction
        c2 = provider._get_client()
        assert c2 is c1
        mock_genai["genai"].Client.assert_called_once()

    def test_client_only_created_once(self, provider, mock_genai):
        """Multiple calls to _get_client() return the cached client."""
        client_refs = [provider._get_client() for _ in range(5)]
        assert all(c is client_refs[0] for c in client_refs)
        mock_genai["genai"].Client.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  Role Mapping (_to_gemini_role)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoleMapping:
    """_to_gemini_role maps our generic roles to Gemini's model/user convention."""

    def test_system_maps_to_user(self, provider):
        """system → user (system_instruction config handles it separately)."""
        assert provider._to_gemini_role("system") == "user"

    def test_user_maps_to_user(self, provider):
        assert provider._to_gemini_role("user") == "user"

    def test_assistant_maps_to_model(self, provider):
        assert provider._to_gemini_role("assistant") == "model"

    def test_tool_maps_to_user(self, provider):
        """tool → user (tool results are fed back as user messages)."""
        assert provider._to_gemini_role("tool") == "user"

    def test_unknown_role_defaults_to_user(self, provider):
        """Any unrecognised role falls back to 'user'."""
        assert provider._to_gemini_role("unknown") == "user"
        assert provider._to_gemini_role("") == "user"
        assert provider._to_gemini_role("function") == "user"


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  Content Building (_build_contents)
# ═══════════════════════════════════════════════════════════════════════════════


class TestContentBuilding:
    """_build_contents converts LLMMessage list → Gemini contents format."""

    def test_single_user_message(self, provider):
        """A single user message produces one content entry."""
        contents = provider._build_contents([
            LLMMessage(role="user", content="Hello"),
        ])
        assert contents == [{"role": "user", "parts": [{"text": "Hello"}]}]

    def test_multiple_messages_all_roles(self, provider):
        """All four roles are mapped correctly.

        ``role="tool"`` messages become ``functionResponse`` parts (Gemini's
        required shape for tool results) rather than plain text.
        """
        contents = provider._build_contents([
            LLMMessage(role="system", content="Be helpful"),
            LLMMessage(role="user", content="Hi"),
            LLMMessage(role="assistant", content="Hello!"),
            LLMMessage(
                role="tool",
                content='{"tool_name": "search", "response": {"hit": 1}}',
                tool_call_id="tc_1",
            ),
        ])
        assert contents == [
            {"role": "user", "parts": [{"text": "Be helpful"}]},
            {"role": "user", "parts": [{"text": "Hi"}]},
            {"role": "model", "parts": [{"text": "Hello!"}]},
            {
                "role": "user",
                "parts": [{"functionResponse": {
                    "name": "search",
                    "response": {"hit": 1},
                    "id": "tc_1",
                }}],
            },
        ]

    def test_empty_message_list(self, provider):
        """An empty list produces an empty contents list."""
        assert provider._build_contents([]) == []

    def test_preserves_message_order(self, provider):
        """The output order mirrors the input order."""
        messages = [
            LLMMessage(role="user", content="1"),
            LLMMessage(role="assistant", content="2"),
            LLMMessage(role="user", content="3"),
        ]
        contents = provider._build_contents(messages)
        assert [c["role"] for c in contents] == ["user", "model", "user"]
        assert [c["parts"][0]["text"] for c in contents] == ["1", "2", "3"]


# ═══════════════════════════════════════════════════════════════════════════════
# 3b.  Tool messages → functionResponse parts (native tool-loop plumbing)
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolFunctionResponse:
    """role='tool' messages become functionResponse parts, not flattened text.

    Gemini refuses to continue a tool loop when tool results come back as
    plain text — they must be functionResponse parts tied to the originating
    function_call.id (forwarded from LLMMessage.tool_call_id).
    """

    def test_envelope_with_tool_call_id(self, provider):
        """Envelope content + tool_call_id → name, response, and id."""
        contents = provider._build_contents([
            LLMMessage(
                role="tool",
                content='{"tool_name": "get_weather", "response": {"temperature": 21}}',
                tool_call_id="call_abc",
            ),
        ])
        assert contents == [{
            "role": "user",
            "parts": [{"functionResponse": {
                "name": "get_weather",
                "response": {"temperature": 21},
                "id": "call_abc",
            }}],
        }]

    def test_name_alias_key(self, provider):
        """``name`` is accepted as an alias for ``tool_name``."""
        contents = provider._build_contents([
            LLMMessage(role="tool", content='{"name": "calc", "response": {"sum": 3}}'),
        ])
        part = contents[0]["parts"][0]["functionResponse"]
        assert part["name"] == "calc"
        assert part["response"] == {"sum": 3}
        assert "id" not in part

    def test_no_tool_call_id_parses_envelope(self, provider):
        """Without tool_call_id, name + response are still recovered from the content."""
        contents = provider._build_contents([
            LLMMessage(role="tool", content='{"tool_name": "calc", "response": {"sum": 3}}'),
        ])
        assert contents == [{
            "role": "user",
            "parts": [{"functionResponse": {
                "name": "calc",
                "response": {"sum": 3},
            }}],
        }]

    def test_plain_text_content_used_as_response(self, provider):
        """Non-JSON content falls back to the raw string as the response payload."""
        contents = provider._build_contents([
            LLMMessage(role="tool", content="42 degrees", tool_call_id="tc_9"),
        ])
        part = contents[0]["parts"][0]["functionResponse"]
        assert part["name"] == ""
        assert part["response"] == "42 degrees"
        assert part["id"] == "tc_9"

    def test_json_without_envelope_keys(self, provider):
        """JSON content without envelope keys is passed through as the response."""
        contents = provider._build_contents([
            LLMMessage(role="tool", content='{"temp": 21, "unit": "C"}'),
        ])
        part = contents[0]["parts"][0]["functionResponse"]
        assert part["name"] == ""
        assert part["response"] == {"temp": 21, "unit": "C"}

    def test_string_response_value(self, provider):
        """A string response payload survives round-tripping via json.loads."""
        contents = provider._build_contents([
            LLMMessage(
                role="tool",
                content='{"tool_name": "lookup", "response": "not found"}',
                tool_call_id="c1",
            ),
        ])
        part = contents[0]["parts"][0]["functionResponse"]
        assert part["name"] == "lookup"
        assert part["response"] == "not found"
        assert part["id"] == "c1"

    def test_tool_message_role_is_user(self, provider):
        """functionResponse parts are emitted in a user-role content (Gemini requirement)."""
        contents = provider._build_contents([
            LLMMessage(role="tool", content='{"tool_name": "x", "response": {}}'),
        ])
        assert contents[0]["role"] == "user"


class TestNativeToolLoop:
    """Two-iteration native Gemini tool loop: function_call → functionResponse.

    Iteration 1: the model responds with a function_call part, which generate()
    parses into LLMResponse.tool_calls.  Iteration 2: the tool result is fed
    back as a role='tool' message and must appear as a functionResponse part in
    the outbound request — without this the loop breaks on iteration 2.
    """

    @pytest.mark.asyncio
    async def test_two_iteration_tool_loop(self, provider, mock_genai):
        tool = ToolSpec(
            name="get_weather",
            description="Get the weather for a location",
            parameters_json_schema={
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        )

        # ── Iteration 1: model asks for a tool ─────────────────────────────
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(function_call=_mock_function_call(
                    "get_weather", {"location": "Berlin"}, call_id="call_abc",
                ))],
                finish_reason=_mock_finish_reason("FinishReason.FUNCTION_CALL"),
            )],
        )
        resp_1 = await provider.generate(LLMRequest(
            messages=[LLMMessage(role="user", content="Weather in Berlin?")],
            tools=[tool],
        ))
        assert len(resp_1.tool_calls) == 1
        assert resp_1.tool_calls[0]["id"] == "call_abc"
        assert resp_1.tool_calls[0]["name"] == "get_weather"
        assert resp_1.finish_reason == "tool_call"

        # ── Iteration 2: feed the tool result back ─────────────────────────
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="It's 21C in Berlin.")])],
        )
        resp_2 = await provider.generate(LLMRequest(
            messages=[
                LLMMessage(role="user", content="Weather in Berlin?"),
                LLMMessage(role="assistant", content=""),
                LLMMessage(
                    role="tool",
                    content='{"tool_name": "get_weather", "response": {"temperature": 21, "condition": "sunny"}}',
                    tool_call_id="call_abc",
                ),
            ],
            tools=[tool],
            # Even with JSON mode requested, tools + response_mime_type must
            # never coexist — response_mime_type is dropped.
            response_format="json",
        ))
        assert resp_2.content == "It's 21C in Berlin."
        assert resp_2.finish_reason == "stop"

        # The outbound request on iteration 2 carries a functionResponse part
        # tied to the originating call id.
        _, kwargs = mock_genai["client"].models.generate_content.call_args
        contents = kwargs["contents"]
        fr_contents = [
            c for c in contents
            if any("functionResponse" in p for p in c["parts"])
        ]
        assert len(fr_contents) == 1
        fr = fr_contents[0]["parts"][0]["functionResponse"]
        assert fr == {
            "name": "get_weather",
            "response": {"temperature": 21, "condition": "sunny"},
            "id": "call_abc",
        }

        # tools + response_mime_type never coexist.
        config = kwargs["config"]
        assert config.tools is not None
        assert config.response_mime_type is None

    @pytest.mark.asyncio
    async def test_tools_with_json_mode_drops_response_mime_type(self, provider, mock_genai):
        """response_format='json' + tools → tools sent, response_mime_type omitted."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="ok")])],
        )
        tool = ToolSpec(name="t", description="desc", parameters_json_schema={"type": "object", "properties": {}})

        await provider.generate(LLMRequest(
            messages=[LLMMessage(role="user", content="Use tool")],
            tools=[tool],
            response_format="json",
        ))

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.tools is not None
        assert config.response_mime_type is None

    @pytest.mark.asyncio
    async def test_json_mode_without_tools_still_sets_mime_type(self, provider, mock_genai):
        """response_format='json' without tools → response_mime_type is set."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text='{"k": "v"}')])],
        )

        await provider.generate(LLMRequest(
            messages=[LLMMessage(role="user", content="JSON")],
            response_format="json",
        ))

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.tools is None
        assert config.response_mime_type == "application/json"


class TestEnvelopeInterop:
    """Gate 2 BLOCK fix: real producer output through the real Gemini adapter.

    run_tool_loop (native channel) builds the tool-result message from the REAL
    ``_result_envelope`` and forwards the originating call id in tool_call_id;
    GoogleProvider._build_contents must reconstruct a functionResponse with a
    NON-EMPTY name + id — never the empty-name fallback path.  No envelope here
    is hand-written: both sides are the real production code.
    """

    @pytest.mark.asyncio
    async def test_real_producer_output_through_real_adapter(self, provider):
        from backend.copilot.llm.base import LLMResponse
        from backend.copilot.llm.tool_calling import (
            build_tool_catalog,
            build_tool_context,
            run_tool_loop,
        )
        from backend.copilot.schemas import GlobalContext

        class RecordingProvider:
            """Native-channel stand-in that records every request it receives."""
            provider_id = "google"
            _api_key = "k"
            supports_tool_calling = True

            def __init__(self) -> None:
                self.calls = []
                self.responses = [
                    LLMResponse(
                        content="",
                        tool_calls=[{"id": "call_abc", "name": "vehicle.search", "arguments": {"query": "x"}}],
                        finish_reason="tool_call",
                    ),
                    LLMResponse(content="done", finish_reason="stop"),
                ]

            async def generate(self, request):
                self.calls.append(request)
                if self.responses:
                    return self.responses.pop(0)
                return LLMResponse(content="", finish_reason="error")

        async def fake_execute(plan, services=None, on_step_update=None):
            plan.steps[0].status = "succeeded"
            plan.steps[0].result = {
                "status": "success",
                "data": {"vehicles": [{"id": 5, "plate": "AB-12-FRU"}], "total_results": 1, "truncated": False},
                "message_key": "copilot.step.vehicle_search_done",
            }
            return plan

        ctx = GlobalContext(company_id=1, user_id=1, role="dispatcher", language="en", timezone="UTC", subscription_tier="business")
        rp = RecordingProvider()
        catalog = build_tool_catalog(build_tool_context({"vehicle.search"}))

        with patch("backend.copilot.executor.execute_plan", new=fake_execute):
            result = await run_tool_loop(
                "find trucks", "en", None, ctx,
                {"role": "dispatcher", "user_id": 1, "company_id": 1},
                catalog, rp, conversation_id="interop",
            )
        assert result.final_answer == "done"

        # The iteration-2 request carries the REAL producer envelope + call id.
        it2_messages = rp.calls[1].messages
        tool_msgs = [m for m in it2_messages if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "call_abc"
        assert "tool_name" in tool_msgs[0].content

        # Pipe the REAL producer output through the REAL Gemini adapter.
        contents = provider._build_contents(it2_messages)
        fr_parts = [
            p["functionResponse"]
            for c in contents
            for p in c["parts"]
            if "functionResponse" in p
        ]
        assert len(fr_parts) == 1
        fr = fr_parts[0]
        assert fr["name"] == "vehicle.search"  # recovered from the envelope (non-empty)
        assert fr["id"] == "call_abc"           # forwarded from the originating call
        assert fr["response"]["status"] == "success"
        assert fr["response"]["data"]["vehicles"][0]["plate"] == "AB-12-FRU"


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  Tool Building (_build_tools)
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolBuilding:
    """_build_tools converts ToolSpec list → Gemini function_declarations."""

    def test_single_tool(self, provider):
        """A single ToolSpec produces one function_declaration."""
        gemini_tools = provider._build_tools([
            ToolSpec(
                name="get_weather",
                description="Get the weather for a location",
                parameters_json_schema={
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            ),
        ])
        assert len(gemini_tools) == 1
        decls = gemini_tools[0]["function_declarations"]
        assert len(decls) == 1
        assert decls[0]["name"] == "get_weather"
        assert decls[0]["description"] == "Get the weather for a location"
        assert decls[0]["parameters"] == {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        }

    def test_multiple_tools(self, provider):
        """Multiple ToolSpec entries produce multiple function_declarations."""
        gemini_tools = provider._build_tools([
            ToolSpec(name="a", description="Tool A", parameters_json_schema={"type": "object", "properties": {}}),
            ToolSpec(name="b", description="Tool B", parameters_json_schema={"type": "object", "properties": {}}),
        ])
        assert len(gemini_tools) == 1
        assert [d["name"] for d in gemini_tools[0]["function_declarations"]] == ["a", "b"]

    def test_empty_tool_list(self, provider):
        """An empty tool list produces an empty list (no function_declarations)."""
        assert provider._build_tools([]) == []

    def test_tool_with_complex_schema(self, provider):
        """Complex JSON schemas are passed through unchanged."""
        schema = {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Start city"},
                "destination": {"type": "string"},
                "cargo": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["origin", "destination"],
        }
        gemini_tools = provider._build_tools([
            ToolSpec(name="plan_route", description="Plan a route", parameters_json_schema=schema),
        ])
        assert gemini_tools[0]["function_declarations"][0]["parameters"] == schema


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  generate() — text, finish-reason, tool calls, token counts, errors
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerate:
    """generate() with a mocked genai client — happy path and options."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _run(provider, messages, tools=None, **kwargs) -> LLMResponse:
        request = LLMRequest(messages=messages, tools=tools or [], **kwargs)
        return await provider.generate(request)

    # ------------------------------------------------------------------
    # Basic text generation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_basic_text(self, provider, mock_genai):
        """Generate returns text content from the model response."""
        response = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="Hello world")])],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Say hello")])

        assert result.content == "Hello world"
        assert result.finish_reason == "stop"
        assert result.input_tokens == 10
        assert result.output_tokens == 20
        assert result.provider_id == "google"
        assert result.model_id == "gemini-test"
        assert result.tool_calls == []
        assert isinstance(result.latency_ms, int)

    @pytest.mark.asyncio
    async def test_correct_api_call(self, provider, mock_genai):
        """Verifies the exact arguments passed to generate_content."""
        response = _mock_response(candidates=[_mock_candidate(parts=[_mock_part(text="ok")])])
        mock_genai["client"].models.generate_content.return_value = response

        await self._run(provider, [LLMMessage(role="user", content="Hi")])

        mock_genai["client"].models.generate_content.assert_called_once()
        _, kwargs = mock_genai["client"].models.generate_content.call_args
        assert kwargs["model"] == "gemini-test"
        assert kwargs["contents"] == [{"role": "user", "parts": [{"text": "Hi"}]}]
        assert kwargs["config"] is not None

    @pytest.mark.asyncio
    async def test_with_system_message(self, provider, mock_genai):
        """System message is extracted as system_instruction in config."""
        response = _mock_response(candidates=[_mock_candidate(parts=[_mock_part(text="OK")])])
        mock_genai["client"].models.generate_content.return_value = response

        await self._run(provider, [
            LLMMessage(role="system", content="You are helpful."),
            LLMMessage(role="user", content="Help"),
        ])

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.system_instruction == "You are helpful."

    @pytest.mark.asyncio
    async def test_with_tools(self, provider, mock_genai):
        """Tools are passed in config when provided."""
        response = _mock_response(candidates=[_mock_candidate(parts=[_mock_part(text="ok")])])
        mock_genai["client"].models.generate_content.return_value = response

        tool = ToolSpec(name="t", description="desc", parameters_json_schema={"type": "object", "properties": {}})
        await self._run(provider, [LLMMessage(role="user", content="Use tool")], tools=[tool])

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.tools is not None

    @pytest.mark.asyncio
    async def test_json_mode(self, provider, mock_genai):
        """JSON response_format sets response_mime_type."""
        response = _mock_response(candidates=[_mock_candidate(parts=[_mock_part(text='{"k": "v"}')])])
        mock_genai["client"].models.generate_content.return_value = response

        await self._run(provider, [LLMMessage(role="user", content="JSON")], response_format="json")

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.response_mime_type == "application/json"

    @pytest.mark.asyncio
    async def test_text_mode_default(self, provider, mock_genai):
        """Default text response_format leaves response_mime_type as None."""
        response = _mock_response(candidates=[_mock_candidate(parts=[_mock_part(text="text")])])
        mock_genai["client"].models.generate_content.return_value = response

        await self._run(provider, [LLMMessage(role="user", content="Text")])

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.response_mime_type is None

    @pytest.mark.asyncio
    async def test_multiple_text_parts_joined(self, provider, mock_genai):
        """Multiple text parts in the response are joined with newlines."""
        response = _mock_response(
            candidates=[_mock_candidate(parts=[
                _mock_part(text="First"),
                _mock_part(text="Second"),
            ])],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Two words")])
        assert result.content == "First\nSecond"

    @pytest.mark.asyncio
    async def test_empty_response_no_candidates(self, provider, mock_genai):
        """Response with no candidates and no usage_metadata returns empty content and zero tokens."""
        response = MagicMock(spec=["candidates", "usage_metadata"])
        response.candidates = None
        response.usage_metadata = None

        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Empty")])

        assert result.content == ""
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_empty_response_empty_candidates_list(self, provider, mock_genai):
        """Response with empty candidates list returns empty content."""
        response = _mock_response(candidates=[])
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Empty")])

        assert result.content == ""
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_candidate_without_content(self, provider, mock_genai):
        """Candidate with content=None is handled without error."""
        candidate = MagicMock(spec=["content", "finish_reason"])
        candidate.content = None
        candidate.finish_reason = None

        response = _mock_response(candidates=[candidate])
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="No content")])
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_candidate_with_empty_parts_list(self, provider, mock_genai):
        """Candidate with empty parts list returns empty content."""
        response = _mock_response(
            candidates=[_mock_candidate(parts=[])],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="No parts")])
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_temperature_and_max_tokens_forwarded(self, provider, mock_genai):
        """Request temperature and max_tokens appear in the config."""
        response = _mock_response(candidates=[_mock_candidate(parts=[_mock_part(text="ok")])])
        mock_genai["client"].models.generate_content.return_value = response

        await self._run(
            provider,
            [LLMMessage(role="user", content="Hi")],
            temperature=0.7,
            max_tokens=2048,
        )

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.temperature == 0.7
        assert config.max_output_tokens == 2048

    @pytest.mark.asyncio
    async def test_latency_measured(self, provider, mock_genai):
        """latency_ms is a positive integer."""
        response = _mock_response(candidates=[_mock_candidate(parts=[_mock_part(text="ok")])])
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Latency")])
        assert result.latency_ms >= 0

    # ------------------------------------------------------------------
    # Finish reason extraction
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_finish_reason_stop(self, provider, mock_genai):
        """FinishReason STOP → finish_reason 'stop'."""
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(text="done")],
                finish_reason=_mock_finish_reason("FinishReason.STOP"),
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Finish")])
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_finish_reason_max_tokens(self, provider, mock_genai):
        """FinishReason MAX_TOKENS → finish_reason 'max_tokens'."""
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(text="partial")],
                finish_reason=_mock_finish_reason("FinishReason.MAX_TOKENS"),
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Long")])
        assert result.finish_reason == "max_tokens"

    @pytest.mark.asyncio
    async def test_finish_reason_tool_call_via_string(self, provider, mock_genai):
        """FinishReason containing 'TOOL' → finish_reason 'tool_call'."""
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(function_call=_mock_function_call("x", {}))],
                finish_reason=_mock_finish_reason("FinishReason.FUNCTION_CALL"),
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Call")])
        # "FUNCTION_CALL" does NOT contain "TOOL" → the code falls through
        # to the `or tool_calls` branch because tool_calls is non-empty.
        assert result.finish_reason == "tool_call"

    @pytest.mark.asyncio
    async def test_finish_reason_tool_call_via_tool_calls_list(self, provider, mock_genai):
        """tool_calls non-empty → finish_reason 'tool_call' even when reason string is STOP."""
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(function_call=_mock_function_call("search", {"q": "test"}))],
                finish_reason=_mock_finish_reason("FinishReason.STOP"),
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Search")])
        # STOP reason, but tool_calls list is non-empty → tool_call
        assert result.finish_reason == "tool_call"

    @pytest.mark.asyncio
    async def test_finish_reason_safety_defaults_to_stop(self, provider, mock_genai):
        """SAFETY finish_reason is not specifically handled → defaults to 'stop'.

        This documents current behaviour; the provider may later add explicit
        safety/blocked handling.
        """
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(text="")],
                finish_reason=_mock_finish_reason("FinishReason.SAFETY"),
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Risky")])
        # SAFETY doesn't contain MAX_TOKENS or TOOL, and tool_calls is empty
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_finish_reason_none_stays_stop(self, provider, mock_genai):
        """When finish_reason is None/falsy, finish_reason stays 'stop'."""
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(text="done")],
                finish_reason=None,
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Done")])
        assert result.finish_reason == "stop"

    # ------------------------------------------------------------------
    # Tool call parsing
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_tool_call_parsing(self, provider, mock_genai):
        """function_call.args is extracted as a dict in tool_calls."""
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(function_call=_mock_function_call(
                    "get_weather",
                    {"location": "Berlin"},
                    call_id="call_abc",
                ))],
                finish_reason=_mock_finish_reason("FinishReason.FUNCTION_CALL"),
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Weather in Berlin")])

        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc["name"] == "get_weather"
        assert tc["arguments"] == {"location": "Berlin"}
        assert tc["id"] == "call_abc"

    @pytest.mark.asyncio
    async def test_tool_call_empty_args(self, provider, mock_genai):
        """function_call with no args → empty dict."""
        response = _mock_response(
            candidates=[_mock_candidate(
                parts=[_mock_part(function_call=_mock_function_call("ping", {}))],
            )],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Ping")])

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["arguments"] == {}

    @pytest.mark.asyncio
    async def test_tool_call_multiple_tools_in_one_response(self, provider, mock_genai):
        """Multiple function_call parts produce multiple tool_calls."""
        response = _mock_response(
            candidates=[_mock_candidate(parts=[
                _mock_part(function_call=_mock_function_call("tool_a", {"p": 1}, "id_1")),
                _mock_part(function_call=_mock_function_call("tool_b", {"p": 2}, "id_2")),
            ])],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Two tools")])

        assert len(result.tool_calls) == 2
        assert result.tool_calls[0]["name"] == "tool_a"
        assert result.tool_calls[1]["name"] == "tool_b"

    @pytest.mark.asyncio
    async def test_tool_call_mixed_text_and_function(self, provider, mock_genai):
        """Text and function_call parts in the same candidate are both handled."""
        response = _mock_response(
            candidates=[_mock_candidate(parts=[
                _mock_part(text="I'll search for you"),
                _mock_part(function_call=_mock_function_call("search", {"q": "test"})),
            ])],
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Search")])

        assert result.content == "I'll search for you"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search"

    # ------------------------------------------------------------------
    # Token counting in generate response
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_token_counts_from_metadata(self, provider, mock_genai):
        """input_tokens and output_tokens come from usage_metadata."""
        response = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="ok")])],
            prompt_tokens=50,
            output_tokens=100,
        )
        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Count")])

        assert result.input_tokens == 50
        assert result.output_tokens == 100

    @pytest.mark.asyncio
    async def test_token_counts_zero_when_no_metadata(self, provider, mock_genai):
        """When usage_metadata is None, token counts default to 0."""
        response = MagicMock(spec=["candidates", "usage_metadata"])
        response.candidates = [_mock_candidate(parts=[_mock_part(text="ok")])]
        response.usage_metadata = None

        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Count")])

        assert result.input_tokens == 0
        assert result.output_tokens == 0

    @pytest.mark.asyncio
    async def test_token_counts_with_metadata_missing_attributes(self, provider, mock_genai):
        """When usage_metadata exists but token attrs are 0, defaults to 0."""
        response = MagicMock(spec=["candidates", "usage_metadata"])
        response.candidates = [_mock_candidate(parts=[_mock_part(text="ok")])]
        response.usage_metadata = MagicMock(spec=["prompt_token_count", "candidates_token_count"])
        response.usage_metadata.prompt_token_count = 0
        response.usage_metadata.candidates_token_count = 0

        mock_genai["client"].models.generate_content.return_value = response

        result = await self._run(provider, [LLMMessage(role="user", content="Count")])

        assert result.input_tokens == 0
        assert result.output_tokens == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  generate() — Error propagation
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateErrors:
    """Error handling: the provider catches exceptions and returns an error response."""

    @staticmethod
    async def _assert_error_response(provider, mock_genai, side_effect):
        mock_genai["client"].models.generate_content.side_effect = side_effect
        request = LLMRequest(messages=[LLMMessage(role="user", content="Test")])
        result = await provider.generate(request)
        assert result.finish_reason == "error"
        assert result.content == ""
        assert isinstance(result.latency_ms, int)
        return result

    @pytest.mark.asyncio
    async def test_generic_api_exception(self, provider, mock_genai):
        """Any API exception returns finish_reason 'error'."""
        await self._assert_error_response(provider, mock_genai, Exception("API failure"))

    @pytest.mark.asyncio
    async def test_auth_failure(self, provider, mock_genai):
        """Authentication failure returns error response."""
        await self._assert_error_response(
            provider, mock_genai, Exception("PERMISSION_DENIED: API key not valid"),
        )

    @pytest.mark.asyncio
    async def test_rate_limit(self, provider, mock_genai):
        """Rate-limit error returns error response."""
        await self._assert_error_response(
            provider, mock_genai, Exception("RESOURCE_EXHAUSTED: Rate limit exceeded"),
        )

    @pytest.mark.asyncio
    async def test_timeout(self, provider, mock_genai):
        """Timeout error returns error response."""
        await self._assert_error_response(provider, mock_genai, TimeoutError("Request timed out"))

    @pytest.mark.asyncio
    async def test_connection_error(self, provider, mock_genai):
        """Connection-level errors return error response."""
        await self._assert_error_response(
            provider, mock_genai, ConnectionError("Failed to connect"),
        )

    @pytest.mark.asyncio
    async def test_latency_recorded_on_error(self, provider, mock_genai):
        """Even on error, latency_ms is recorded."""
        mock_genai["client"].models.generate_content.side_effect = Exception("fail")
        request = LLMRequest(messages=[LLMMessage(role="user", content="Test")])
        result = await provider.generate(request)
        assert result.latency_ms >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  stream()
# ═══════════════════════════════════════════════════════════════════════════════


class TestStream:
    """Streaming generate_content_stream — chunks, API verification, errors."""

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_yields_text_chunks(self, provider, mock_genai):
        """Stream yields text chunks from generate_content_stream."""
        mock_genai["client"].models.generate_content_stream.return_value = [
            _stream_chunk("Hello"),
            _stream_chunk(" "),
            _stream_chunk("World"),
            _stream_chunk("!"),
        ]

        request = LLMRequest(messages=[LLMMessage(role="user", content="Say hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == ["Hello", " ", "World", "!"]

    @pytest.mark.asyncio
    async def test_stream_correct_api_call(self, provider, mock_genai):
        """API is called with the right model, contents, and config."""
        mock_genai["client"].models.generate_content_stream.return_value = [
            _stream_chunk("resp"),
        ]

        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content="Be brief"),
                LLMMessage(role="user", content="Hi"),
            ],
            max_tokens=100,
            temperature=0.5,
        )
        async for _ in provider.stream(request):
            pass

        mock_genai["client"].models.generate_content_stream.assert_called_once()
        _, kwargs = mock_genai["client"].models.generate_content_stream.call_args
        assert kwargs["model"] == "gemini-test"
        assert len(kwargs["contents"]) == 2
        assert kwargs["config"].system_instruction == "Be brief"
        assert kwargs["config"].max_output_tokens == 100
        assert kwargs["config"].temperature == 0.5

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_skips_empty_text(self, provider, mock_genai):
        """Chunks with empty text are skipped."""
        mock_genai["client"].models.generate_content_stream.return_value = [
            _stream_chunk(""),
            _stream_chunk("real"),
            _stream_chunk(""),
            _stream_chunk("text"),
            _stream_chunk(""),
        ]

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == ["real", "text"]

    @pytest.mark.asyncio
    async def test_stream_handles_no_candidates(self, provider, mock_genai):
        """Chunks with no candidates are skipped."""
        empty_chunk = MagicMock(spec=["candidates"])
        empty_chunk.candidates = None

        mock_genai["client"].models.generate_content_stream.return_value = [
            empty_chunk,
            _stream_chunk("good"),
        ]

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == ["good"]

    @pytest.mark.asyncio
    async def test_stream_handles_empty_candidates(self, provider, mock_genai):
        """Chunks with empty candidates list are skipped."""
        empty_chunk = MagicMock(spec=["candidates"])
        empty_chunk.candidates = []

        mock_genai["client"].models.generate_content_stream.return_value = [
            empty_chunk,
            _stream_chunk("good"),
        ]

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == ["good"]

    @pytest.mark.asyncio
    async def test_stream_handles_no_content(self, provider, mock_genai):
        """Chunks with no content are skipped."""
        chunk = MagicMock(spec=["candidates"])
        chunk.candidates = [MagicMock(spec=["content"])]
        chunk.candidates[0].content = None  # type: ignore[attr-defined]

        mock_genai["client"].models.generate_content_stream.return_value = [
            chunk,
            _stream_chunk("good"),
        ]

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == ["good"]

    @pytest.mark.asyncio
    async def test_stream_handles_no_parts(self, provider, mock_genai):
        """Chunks with no parts are skipped."""
        chunk = MagicMock(spec=["candidates"])
        chunk.candidates = [MagicMock(spec=["content"])]
        chunk.candidates[0].content = MagicMock(spec=["parts"])
        chunk.candidates[0].content.parts = None  # type: ignore[attr-defined]

        mock_genai["client"].models.generate_content_stream.return_value = [
            chunk,
            _stream_chunk("good"),
        ]

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == ["good"]

    @pytest.mark.asyncio
    async def test_stream_empty_chunks_list(self, provider, mock_genai):
        """An empty stream yields nothing."""
        mock_genai["client"].models.generate_content_stream.return_value = []

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == []

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_api_error_stops_iteration(self, provider, mock_genai):
        """When the API raise an exception, the generator stops (no crash)."""
        mock_genai["client"].models.generate_content_stream.side_effect = Exception("Stream failed")

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == []

    @pytest.mark.asyncio
    async def test_stream_auth_error(self, provider, mock_genai):
        """Auth failure during stream setup is caught."""
        mock_genai["client"].models.generate_content_stream.side_effect = Exception(
            "PERMISSION_DENIED: API key invalid",
        )

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == []

    @pytest.mark.asyncio
    async def test_stream_partial_failure_stops(self, provider, mock_genai):
        """A mid-stream exception after some chunks stops further iteration."""
        def _failing_iter():
            yield _stream_chunk("good")
            raise Exception("Mid-stream error")

        mock_genai["client"].models.generate_content_stream.return_value = _failing_iter()

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        # The good chunk is yielded before the error
        assert collected == ["good"]

    @pytest.mark.asyncio
    async def test_stream_timeout_error(self, provider, mock_genai):
        """Timeout during stream setup is caught."""
        mock_genai["client"].models.generate_content_stream.side_effect = TimeoutError("Timed out")

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        collected = [chunk async for chunk in provider.stream(request)]

        assert collected == []


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  count_tokens()
# ═══════════════════════════════════════════════════════════════════════════════


class TestCountTokens:
    """Token counting — API call and fallback behaviour."""

    @pytest.mark.asyncio
    async def test_count_tokens_success(self, provider, mock_genai):
        """count_tokens returns total_tokens from the API response."""
        mock_response = MagicMock(spec=["total_tokens"])
        mock_response.total_tokens = 42

        mock_genai["client"].models.count_tokens.return_value = mock_response

        messages = [LLMMessage(role="user", content="Hello world")]
        count = await provider.count_tokens(messages)

        assert count == 42

    @pytest.mark.asyncio
    async def test_count_tokens_correct_api_call(self, provider, mock_genai):
        """Verifies the API is called with the right arguments."""
        mock_response = MagicMock(spec=["total_tokens"])
        mock_response.total_tokens = 5
        mock_genai["client"].models.count_tokens.return_value = mock_response

        messages = [
            LLMMessage(role="user", content="Hello"),
            LLMMessage(role="assistant", content="World"),
        ]
        await provider.count_tokens(messages)

        mock_genai["client"].models.count_tokens.assert_called_once()
        _, kwargs = mock_genai["client"].models.count_tokens.call_args
        assert kwargs["model"] == "gemini-test"
        assert kwargs["contents"] == [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"text": "World"}]},
        ]

    @pytest.mark.asyncio
    async def test_count_tokens_empty_list(self, provider, mock_genai):
        """Empty message list returns 0."""
        mock_response = MagicMock(spec=["total_tokens"])
        mock_response.total_tokens = 0
        mock_genai["client"].models.count_tokens.return_value = mock_response

        count = await provider.count_tokens([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_tokens_fallback_on_api_error(self, provider, mock_genai):
        """When the API fails, falls back to char-count // 4."""
        mock_genai["client"].models.count_tokens.side_effect = Exception("API error")

        messages = [
            LLMMessage(role="user", content="Hello world"),      # 11 chars
            LLMMessage(role="assistant", content="Hi there!"),    # 9 chars
        ]
        count = await provider.count_tokens(messages)

        # (11 + 9) // 4 = 20 // 4 = 5
        assert count == 5

    @pytest.mark.asyncio
    async def test_count_tokens_fallback_long_message(self, provider, mock_genai):
        """Fallback handles longer messages correctly."""
        mock_genai["client"].models.count_tokens.side_effect = Exception("fail")

        messages = [LLMMessage(role="user", content="a" * 100)]
        count = await provider.count_tokens(messages)

        assert count == 100 // 4  # 25

    @pytest.mark.asyncio
    async def test_count_tokens_response_is_none(self, provider, mock_genai):
        """When the API returns None, count_tokens returns 0."""
        mock_genai["client"].models.count_tokens.return_value = None

        messages = [LLMMessage(role="user", content="Test")]
        count = await provider.count_tokens(messages)

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_tokens_auth_failure_fallback(self, provider, mock_genai):
        """Auth failure also triggers the fallback estimate."""
        mock_genai["client"].models.count_tokens.side_effect = Exception(
            "PERMISSION_DENIED: Invalid key",
        )

        messages = [LLMMessage(role="user", content="Auth test")]
        count = await provider.count_tokens(messages)

        # 9 chars // 4 = 2
        assert count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 9.  health_check()
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthCheck:
    """Health check — healthy / degraded / down states."""

    @pytest.mark.asyncio
    async def test_healthy(self, provider, mock_genai):
        """Returns 'healthy' when API responds with candidates."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="pong")])],
        )

        status = await provider.health_check()
        assert status == "healthy"

    @pytest.mark.asyncio
    async def test_healthy_correct_api_call(self, provider, mock_genai):
        """Health check sends a 'ping' message with max_output_tokens=1."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="pong")])],
        )

        await provider.health_check()

        mock_genai["client"].models.generate_content.assert_called_once()
        _, kwargs = mock_genai["client"].models.generate_content.call_args
        assert kwargs["model"] == "gemini-test"
        assert kwargs["contents"] == "ping"
        assert kwargs["config"].max_output_tokens == 1

    @pytest.mark.asyncio
    async def test_degraded_no_candidates(self, provider, mock_genai):
        """Returns 'degraded' when API responds without candidates (None)."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=None,
        )

        status = await provider.health_check()
        assert status == "degraded"

    @pytest.mark.asyncio
    async def test_degraded_empty_candidates(self, provider, mock_genai):
        """Returns 'degraded' when candidates list is empty."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[],
        )

        status = await provider.health_check()
        assert status == "degraded"

    @pytest.mark.asyncio
    async def test_down(self, provider, mock_genai):
        """Returns 'down' when the API raises an exception."""
        mock_genai["client"].models.generate_content.side_effect = Exception("Service unavailable")

        status = await provider.health_check()
        assert status == "down"

    @pytest.mark.asyncio
    async def test_down_on_auth_failure(self, provider, mock_genai):
        """Auth failure returns 'down'."""
        mock_genai["client"].models.generate_content.side_effect = Exception(
            "PERMISSION_DENIED: Invalid API key",
        )

        status = await provider.health_check()
        assert status == "down"

    @pytest.mark.asyncio
    async def test_down_on_timeout(self, provider, mock_genai):
        """Timeout returns 'down'."""
        mock_genai["client"].models.generate_content.side_effect = TimeoutError("Timed out")

        status = await provider.health_check()
        assert status == "down"


# ═══════════════════════════════════════════════════════════════════════════════
# 10.  Config building (parameter passthrough to GenerateContentConfig)
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigBuilding:
    """Verify that GenerateContentConfig receives the correct parameters."""

    @pytest.mark.asyncio
    async def test_all_parameters_forwarded(self, provider, mock_genai):
        """All request-level parameters appear in the config object."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="ok")])],
        )

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Test")],
            max_tokens=2048,
            temperature=0.7,
            response_format="json",
        )
        await provider.generate(request)

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.max_output_tokens == 2048
        assert config.temperature == 0.7
        assert config.response_mime_type == "application/json"

    @pytest.mark.asyncio
    async def test_no_system_message(self, provider, mock_genai):
        """When no system message exists, system_instruction is None."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="ok")])],
        )

        request = LLMRequest(messages=[LLMMessage(role="user", content="No system")])
        await provider.generate(request)

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert config.system_instruction is None

    @pytest.mark.asyncio
    async def test_tools_none_when_empty(self, provider, mock_genai):
        """When no tools are given, the config's tools should be None."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="ok")])],
        )

        request = LLMRequest(messages=[LLMMessage(role="user", content="No tools")])
        await provider.generate(request)

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        # The code sets tools=tools if tools else None
        assert config.tools is None

    @pytest.mark.asyncio
    async def test_default_values(self, provider, mock_genai):
        """Default max_tokens and temperature from LLMRequest are passed through."""
        mock_genai["client"].models.generate_content.return_value = _mock_response(
            candidates=[_mock_candidate(parts=[_mock_part(text="ok")])],
        )

        # Use the provider's own defaults (max_tokens=4096, temperature=0.2)
        request = LLMRequest(messages=[LLMMessage(role="user", content="Defaults")])
        await provider.generate(request)

        config = mock_genai["client"].models.generate_content.call_args[1]["config"]
        assert isinstance(config.max_output_tokens, int)
        assert isinstance(config.temperature, float)


# ═══════════════════════════════════════════════════════════════════════════════
# 11.  Real-SDK hermetic tool-schema validation (Phase 4 lane 4C)
# ═══════════════════════════════════════════════════════════════════════════════
# The mock-based TestNativeToolLoop never exercises google-genai's pydantic
# validator, which REJECTS Pydantic model_json_schema() output (observed in
# production on the native tool channel):
#
#   tools.0.Tool.function_declarations.6.parameters.properties.vehicle_id.anyOf.0.exclusiveMinimum
#     Extra inputs are not permitted
#   tools.0.callable
#     Input should be callable
#
# These classes construct the REAL ``google.genai.types.GenerateContentConfig``
# (pure pydantic construction, NO network, NO client) from the FULL real tool
# catalog so the SDK validator runs on every test run.


class TestSchemaSanitizer:
    """``_sanitize_gemini_schema`` rewrites Pydantic ``model_json_schema()``
    output into the shape the google-genai SDK ``Schema`` model accepts."""

    def test_exclusive_minimum_integer_maps_to_minimum_plus_one(self, provider):
        """integer exclusiveMinimum→minimum+1; number exclusiveMinimum→minimum;
        integer exclusiveMaximum→maximum−1."""
        schema = {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "exclusiveMinimum": 0},
                "amount": {"type": "number", "exclusiveMinimum": 0},
                "count": {"type": "integer", "exclusiveMaximum": 10},
            },
            "required": ["client_id"],
        }
        out = provider._sanitize_gemini_schema(schema)
        props = out["properties"]
        assert props["client_id"] == {"type": "integer", "minimum": 1}
        assert props["amount"] == {"type": "number", "minimum": 0}
        assert props["count"] == {"type": "integer", "maximum": 9}
        assert "exclusiveMinimum" not in repr(out)
        assert "exclusiveMaximum" not in repr(out)

    def test_optional_union_flattened_to_nullable(self, provider):
        """anyOf=[<type>, {type:'null'}] → single branch + nullable: true."""
        schema = {
            "type": "object",
            "properties": {
                "vehicle_id": {
                    "anyOf": [{"type": "integer", "exclusiveMinimum": 0}, {"type": "null"}],
                    "default": None,
                },
            },
            "required": [],
        }
        out = provider._sanitize_gemini_schema(schema)
        prop = out["properties"]["vehicle_id"]
        assert prop["type"] == "integer"
        assert prop["minimum"] == 1
        assert prop["nullable"] is True
        assert "anyOf" not in prop and "any_of" not in prop

    def test_renames_sdk_field_names(self, provider):
        """minLength/maxLength → min_length/max_length; minItems/maxItems →
        min_items/max_items; additionalProperties is dropped (Gemini's
        function-declaration schema does not accept it)."""
        schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "minLength": 2, "maxLength": 10},
                "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
            },
            "additionalProperties": False,
        }
        out = provider._sanitize_gemini_schema(schema)
        assert "additional_properties" not in out and "additionalProperties" not in out
        assert out["properties"]["code"] == {"type": "string", "min_length": 2, "max_length": 10}
        assert out["properties"]["tags"]["min_items"] == 1
        assert out["properties"]["tags"]["max_items"] == 5

    def test_stray_keys_dropped(self, provider):
        """Unsupported schema keywords (callable/oneOf/allOf/const) are dropped."""
        schema = {
            "type": "object",
            "properties": {
                "cb": {
                    "type": "string",
                    "callable": "x",
                    "oneOf": [{"type": "string"}],
                    "allOf": [{"type": "string"}],
                    "const": "x",
                },
                "ok": {"type": "string"},
            },
            "required": ["ok"],
        }
        out = provider._sanitize_gemini_schema(schema)
        assert out["properties"]["cb"] == {"type": "string"}
        assert out["properties"]["ok"] == {"type": "string"}
        assert out["required"] == ["ok"]

    def test_multi_branch_any_of_kept_as_any_of(self, provider):
        """anyOf with two real branches survives as the SDK's ``any_of``."""
        schema = {
            "type": "object",
            "properties": {"ref": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
        }
        out = provider._sanitize_gemini_schema(schema)
        prop = out["properties"]["ref"]
        assert "any_of" in prop
        assert [b["type"] for b in prop["any_of"]] == ["string", "integer"]
        assert "type" not in prop

    def test_nested_items_recursion(self, provider):
        """Arrays and their item schemas are sanitized recursively."""
        schema = {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"qty": {"type": "integer", "exclusiveMinimum": 0}},
                        "required": ["qty"],
                    },
                },
            },
            "required": ["rows"],
        }
        out = provider._sanitize_gemini_schema(schema)
        item = out["properties"]["rows"]["items"]
        assert item["properties"]["qty"] == {"type": "integer", "minimum": 1}
        assert item["required"] == ["qty"]

    def test_type_title_description_and_required_preserved(self, provider):
        """Semantic metadata (type/required/title/description) is untouched."""
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer", "exclusiveMinimum": 0}},
            "required": ["a", "b"],
            "title": "X",
            "description": "desc",
        }
        out = provider._sanitize_gemini_schema(schema)
        assert out["type"] == "object"
        assert out["required"] == ["a", "b"]
        assert out["title"] == "X"
        assert out["description"] == "desc"


class TestRealSdkToolCatalogValidation:
    """Hermetic real-SDK validation of the native tool channel.

    The FULL real tool catalog (every registered tool, no size budget) is
    converted through the provider and used to construct the REAL
    ``genai_types.GenerateContentConfig(tools=...)`` — pure pydantic
    construction, no network, no client — proving the conversion survives the
    SDK validator on every test run.
    """

    @staticmethod
    def _full_real_catalog() -> List[ToolSpec]:
        from backend.copilot.tools.registry import all_tools

        specs: List[ToolSpec] = []
        for tool in all_tools():
            try:
                schema = tool.parameters_schema.model_json_schema()
            except Exception:
                schema = {}
            specs.append(ToolSpec(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=schema,
            ))
        return specs

    def test_full_real_catalog_validates_against_real_sdk(self, provider):
        """Construct the REAL GenerateContentConfig from the full converted
        catalog — must not raise a ValidationError."""
        from google.genai import types as genai_types

        catalog = self._full_real_catalog()
        assert len(catalog) >= 10, "registry unexpectedly small"

        tools = provider._build_tools(catalog)
        config = genai_types.GenerateContentConfig(tools=tools)

        decls = config.tools[0].function_declarations
        assert len(decls) == len(catalog)
        assert {d.name for d in decls} == {s.name for s in catalog}

    def test_no_rejected_keys_anywhere_in_full_catalog(self, provider):
        """No SDK-rejected key leaks into the converted Gemini tools."""
        from google.genai import types as genai_types

        catalog = self._full_real_catalog()
        tools = provider._build_tools(catalog)
        dumped = repr(tools)
        for banned in ("exclusiveMinimum", "exclusiveMaximum", "anyOf",
                       "additionalProperties", "minLength", "maxLength"):
            assert banned not in dumped, f"rejected key {banned!r} leaked into Gemini tools"

        config = genai_types.GenerateContentConfig(tools=tools)  # must validate
        assert config.tools

    def test_exclusive_minimum_bounds_survive_as_minimum(self, provider):
        """client.payment_summary.client_id: exclusiveMinimum 0 → minimum 1."""
        from google.genai import types as genai_types

        catalog = self._full_real_catalog()
        tools = provider._build_tools(catalog)
        genai_types.GenerateContentConfig(tools=tools)

        decls = {d["name"]: d for d in tools[0]["function_declarations"]}
        client_id = decls["client.payment_summary"]["parameters"]["properties"]["client_id"]
        assert client_id["type"] == "integer"
        assert client_id["minimum"] == 1
        assert "exclusiveMinimum" not in client_id

    def test_optional_numeric_union_flattened_to_nullable(self, provider):
        """freight.evaluate_load.vehicle_id: anyOf+exclusiveMinimum → integer,
        minimum 1, nullable (the exact runtime failure shape)."""
        from google.genai import types as genai_types

        catalog = self._full_real_catalog()
        tools = provider._build_tools(catalog)
        genai_types.GenerateContentConfig(tools=tools)

        decls = {d["name"]: d for d in tools[0]["function_declarations"]}
        vehicle_id = decls["freight.evaluate_load"]["parameters"]["properties"]["vehicle_id"]
        assert vehicle_id["type"] == "integer"
        assert vehicle_id["minimum"] == 1
        assert vehicle_id.get("nullable") is True
        assert "anyOf" not in vehicle_id and "any_of" not in vehicle_id

    def test_required_and_types_intact_for_reference_tools(self, provider):
        """Types and required lists survive for the reference tool shapes."""
        from google.genai import types as genai_types

        catalog = self._full_real_catalog()
        tools = provider._build_tools(catalog)
        genai_types.GenerateContentConfig(tools=tools)

        decls = {d["name"]: d for d in tools[0]["function_declarations"]}

        trip = decls["trip.create"]["parameters"]
        assert trip["type"] == "object"
        assert "client_id" in trip["required"]
        assert trip["properties"]["client_id"]["type"] == "integer"

        dispatch = decls["dispatch.create"]["parameters"]
        assert "trip_id" in dispatch["required"]
        assert dispatch["properties"]["trip_id"]["minimum"] == 1

        search = decls["vehicle.search"]["parameters"]
        assert search["type"] == "object"
        assert "query" in search["properties"]

    def test_raw_pydantic_schema_is_rejected_without_sanitizer(self, provider):
        """Guard: the raw model_json_schema() output MUST fail the real SDK
        validator — proving the sanitizer does real work and this class would
        catch a regression in it."""
        from google.genai import types as genai_types

        from backend.copilot.tools.registry import get_tool

        raw_schema = get_tool("freight.evaluate_load").parameters_schema.model_json_schema()
        raw_tools = [{
            "function_declarations": [{
                "name": "freight.evaluate_load",
                "description": "x",
                "parameters": raw_schema,
            }],
        }]
        with pytest.raises(Exception) as excinfo:
            genai_types.GenerateContentConfig(tools=raw_tools)
        assert "exclusiveMinimum" in str(excinfo.value)
