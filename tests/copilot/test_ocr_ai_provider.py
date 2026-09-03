"""Unit tests for OcrAIProvider — JSON-mode flag and OpenAI-compatible payload.

Covers:
  - Class attribute flags (supports_json_mode=True, supports_tool_calling=False)
  - _generate_openai payload: never contains "tools" today; contains
    ``response_format: {"type": "json_object"}`` only when the request asks
    for ``response_format="json"``
  - Defensive tools guard: the payload only gains ``tools`` when
    ``supports_tool_calling`` is True AND ``request.tools`` is non-empty
    (future-proofing — the flag is False today).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.copilot.llm.base import LLMMessage, LLMRequest, ToolSpec


@pytest.fixture
def provider():
    from backend.copilot.llm.providers.ocr_ai_provider import OcrAIProvider

    return OcrAIProvider()


@pytest.fixture
def mock_http():
    """Patch httpx.AsyncClient at the provider module level.

    ocr_ai_provider.py does ``import httpx`` and constructs
    ``httpx.AsyncClient(timeout=...)`` per call — we intercept it and expose
    the mock client so tests can capture the outbound POST payload.
    """
    with patch("backend.copilot.llm.providers.ocr_ai_provider.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client_cls.return_value = client
        yield client


def _ok_response(content: str = "ok") -> MagicMock:
    """A mock HTTP 200 JSON response from an OpenAI-compatible endpoint.

    MagicMock (not AsyncMock): the provider calls ``response.json()``
    synchronously, mirroring httpx's synchronous ``Response.json()``.
    """
    resp = MagicMock()
    resp.status_code = 200
    resp.text = content
    resp.json.return_value = {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7},
    }
    return resp


async def _generate(provider, mock_http, **kwargs) -> dict:
    """Run generate() through the OpenAI-compat path and return the payload."""
    mock_http.post.return_value = _ok_response()
    request = LLMRequest(messages=[LLMMessage(role="user", content="hi")], **kwargs)
    await provider.generate(request)
    return mock_http.post.await_args.kwargs["json"]


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  Class attribute flags
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlags:
    """The provider advertises JSON mode but NOT tool calling."""

    def test_supports_json_mode_true(self, provider):
        """Gemma via this endpoint supports JSON mode."""
        assert provider.supports_json_mode is True

    def test_supports_tool_calling_false(self, provider):
        """Gemma 3:4B tool support via this endpoint is unverified → False."""
        assert provider.supports_tool_calling is False

    def test_provider_identity(self, provider):
        """Provider id and self-hosting flag are stable."""
        assert provider.provider_id == "self_hosted"
        assert provider.is_self_hosted is True


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  OpenAI-compatible payload (non-streaming)
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpenAIPayload:
    """The outbound /v1/chat/completions payload shape."""

    @pytest.mark.asyncio
    async def test_default_payload_has_no_tools_or_response_format(self, provider, mock_http):
        """Default text mode sends neither tools nor response_format."""
        payload = await _generate(provider, mock_http)
        assert "tools" not in payload
        assert "response_format" not in payload

    @pytest.mark.asyncio
    async def test_json_mode_sets_response_format(self, provider, mock_http):
        """response_format='json' → payload carries json_object."""
        payload = await _generate(provider, mock_http, response_format="json")
        assert payload["response_format"] == {"type": "json_object"}
        assert "tools" not in payload

    @pytest.mark.asyncio
    async def test_tools_never_sent_today(self, provider, mock_http):
        """Tools requested but supports_tool_calling=False → payload omits 'tools'."""
        tool = ToolSpec(
            name="get_weather",
            description="Get the weather for a location",
            parameters_json_schema={
                "type": "object",
                "properties": {"location": {"type": "string"}},
            },
        )
        payload = await _generate(provider, mock_http, tools=[tool])
        assert "tools" not in payload

    @pytest.mark.asyncio
    async def test_tools_guard_activates_when_flag_enabled(self, provider, mock_http):
        """Defensive guard: tools are sent only when supports_tool_calling is True."""
        provider.supports_tool_calling = True
        tool = ToolSpec(
            name="get_weather",
            description="Get the weather for a location",
            parameters_json_schema={
                "type": "object",
                "properties": {"location": {"type": "string"}},
            },
        )
        payload = await _generate(provider, mock_http, tools=[tool])
        assert payload["tools"] == [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                },
            },
        }]

    @pytest.mark.asyncio
    async def test_tools_guard_skips_empty_list_when_flag_enabled(self, provider, mock_http):
        """Even with the flag enabled, an empty tool list sends no 'tools' key."""
        provider.supports_tool_calling = True
        payload = await _generate(provider, mock_http, tools=[])
        assert "tools" not in payload

    @pytest.mark.asyncio
    async def test_json_mode_with_guard_still_sends_response_format(self, provider, mock_http):
        """JSON mode and the (dormant) tools guard are independent."""
        provider.supports_tool_calling = True
        tool = ToolSpec(name="t", description="d", parameters_json_schema={"type": "object", "properties": {}})
        payload = await _generate(provider, mock_http, tools=[tool], response_format="json")
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["tools"][0]["function"]["name"] == "t"