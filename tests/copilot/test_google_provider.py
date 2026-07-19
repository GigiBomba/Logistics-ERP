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
        """All four roles are mapped correctly."""
        contents = provider._build_contents([
            LLMMessage(role="system", content="Be helpful"),
            LLMMessage(role="user", content="Hi"),
            LLMMessage(role="assistant", content="Hello!"),
            LLMMessage(role="tool", content="{}", tool_call_id="tc_1"),
        ])
        assert contents == [
            {"role": "user", "parts": [{"text": "Be helpful"}]},
            {"role": "user", "parts": [{"text": "Hi"}]},
            {"role": "model", "parts": [{"text": "Hello!"}]},
            {"role": "user", "parts": [{"text": "{}"}]},
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
