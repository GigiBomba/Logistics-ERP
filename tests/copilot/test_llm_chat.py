"""Tests for backend.copilot.llm.chat — the free-form LLM chat fallback (§23.5).

Covers the degradation ladder end-to-end at the ``chat_answer`` level and the
planner integration points (known intents never reach the LLM, blank input
stays offline).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.copilot.llm.base import LLMResponse
from backend.copilot.llm.chat import (
    LLM_CHAT_MAX_TOKENS,
    MAX_ANSWER_CHARS,
    SYSTEM_PROMPT,
    _build_messages,
    _provider_usable,
    chat_answer,
)
from backend.copilot.schemas import GlobalContext


# ── Hermetic provider chain ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _offline_llm_chat():
    """Force the keyword (offline-fallback) path for pipeline tests.

    A configured provider (env API keys like GOOGLE_API_KEY must never trigger
    live calls inside the test suite) would otherwise make process_utterance
    attempt real network requests.
    """
    from backend.copilot.llm.tool_calling import ToolLoopResult

    with patch("backend.copilot.llm.chat.chat_with_tools", new_callable=AsyncMock) as m:
        m.return_value = ToolLoopResult(attempted=False, provider_failed=False)
        yield m


# ── Helpers ─────────────────────────────────────────────────────────────────


class FakeProvider:
    """Minimal stand-in for an LLMProvider used by chat_answer."""

    def __init__(
        self,
        provider_id: str = "self_hosted",
        api_mode: str = "openai",
        api_key: str = "",
        result: LLMResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.provider_id = provider_id
        self._api_mode = api_mode
        self._api_key = api_key
        self._result = result
        self._error = error
        self.generate_calls = []

    async def generate(self, request):
        self.generate_calls.append(request)
        if self._error is not None:
            raise self._error
        if self._result is not None:
            return self._result
        return LLMResponse(content="", finish_reason="error")


def _ctx(language: str = "en") -> GlobalContext:
    return GlobalContext(
        company_id=1,
        user_id=1,
        role="dispatcher",
        language=language,
        timezone="UTC",
        subscription_tier="business",
    )


def _ok_result(text: str = "hello there") -> LLMResponse:
    return LLMResponse(content=text, finish_reason="stop")


# ── Provider readiness ─────────────────────────────────────────────────────


class TestProviderUsable:
    def test_self_hosted_ollama_mode_needs_no_key(self):
        p = FakeProvider(provider_id="self_hosted", api_mode="ollama", api_key="")
        assert _provider_usable(p) is True

    def test_self_hosted_openai_mode_requires_key(self):
        assert _provider_usable(FakeProvider(api_mode="openai", api_key="")) is False
        assert _provider_usable(FakeProvider(api_mode="openai", api_key="k")) is True

    def test_google_requires_key_when_no_env(self):
        """Without an explicit key or env fallback, google is not usable."""
        with patch.dict("os.environ", {}, clear=True):
            assert _provider_usable(FakeProvider(provider_id="google", api_key="")) is False
            assert _provider_usable(FakeProvider(provider_id="google", api_key="g")) is True

    def test_google_usable_with_operion_env_key(self):
        """OPERION_GEMINI_API_KEY (read by get_ai_api_key) makes google usable
        even with no instance-level key — env-keyed deployments must not be
        silently skipped."""
        with patch.dict("os.environ", {"OPERION_GEMINI_API_KEY": "env-k"}, clear=True):
            assert _provider_usable(FakeProvider(provider_id="google", api_key="")) is True

    def test_google_usable_with_google_env_key(self):
        """GOOGLE_API_KEY (the genai SDK default) makes google usable too."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "gk"}, clear=True):
            assert _provider_usable(FakeProvider(provider_id="google", api_key="")) is True

    def test_google_explicit_key_wins_over_env(self):
        """An instance-level key is usable regardless of env state."""
        with patch.dict("os.environ", {}, clear=True):
            assert _provider_usable(FakeProvider(provider_id="google", api_key="k")) is True


class TestBuildMessages:
    def test_system_prompt_pinned_first(self):
        msgs = _build_messages("  hey there  ", "en")
        assert msgs[0].role == "system"
        assert msgs[0].content == SYSTEM_PROMPT.format(
            language_name="English", language_code="en"
        )

    def test_system_prompt_uses_language_name(self):
        """The prompt must name the language ('Romanian'), not just the bare
        ISO code — small models follow a full name far more reliably."""
        msgs = _build_messages("salut", "ro")
        assert "Romanian" in msgs[0].content
        assert "(ro)" in msgs[0].content
        assert "in ro" not in msgs[0].content

    def test_system_prompt_unknown_language_falls_back_to_code(self):
        msgs = _build_messages("salut", "xx")
        assert "xx" in msgs[0].content

    def test_single_user_message_sanitized_and_trimmed(self):
        msgs = _build_messages("  hello   world  ", "ro")
        assert len(msgs) == 2
        assert msgs[1].role == "user"
        # whitespace collapsed, leading/trailing stripped
        assert msgs[1].content == "hello world"

    def test_long_utterance_capped(self):
        msgs = _build_messages("x" * 5000, "en")
        assert len(msgs[1].content) <= 2000


# ── chat_answer ladder ─────────────────────────────────────────────────────


class TestChatAnswer:
    @pytest.mark.asyncio
    async def test_arbitrary_utterance_returns_answer(self):
        """A usable provider answers any free-form utterance."""
        p = FakeProvider(api_key="k", result=_ok_result("  hi there  "))
        with patch("backend.copilot.llm.chat.get_provider", return_value=p):
            answer, attempted = await chat_answer("what is the weather?", _ctx(), None)
        assert answer == "hi there"
        assert attempted is True

    @pytest.mark.asyncio
    async def test_provider_empty_content_returns_none(self):
        p = FakeProvider(api_key="k", result=LLMResponse(content="", finish_reason="error"))
        with patch("backend.copilot.llm.chat.get_provider", return_value=p):
            answer, attempted = await chat_answer("hello?", _ctx(), None)
        assert answer is None
        assert attempted is True

    @pytest.mark.asyncio
    async def test_provider_raises_returns_none(self):
        p = FakeProvider(api_key="k", error=RuntimeError("boom"))
        with patch("backend.copilot.llm.chat.get_provider", return_value=p):
            answer, attempted = await chat_answer("hello?", _ctx(), None)
        assert answer is None
        assert attempted is True

    @pytest.mark.asyncio
    async def test_unconfigured_provider_makes_no_generate_call(self):
        """With no configured key AND no env-key fallback, no provider is
        usable and no generate call is made (env cleared for hermeticity —
        GOOGLE_API_KEY on the host must not count as configured here)."""
        sh = FakeProvider(api_mode="openai", api_key="")
        ggl = FakeProvider(provider_id="google", api_key="")
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "backend.copilot.llm.chat.get_provider",
                side_effect=lambda pid: {"self_hosted": sh, "google": ggl}[pid],
            ):
                answer, attempted = await chat_answer("anything", _ctx(), None)
        assert answer is None
        assert attempted is False
        assert sh.generate_calls == []
        assert ggl.generate_calls == []

    @pytest.mark.asyncio
    async def test_self_hosted_fails_google_fallback_attempted(self):
        sh = FakeProvider(api_key="k", result=LLMResponse(content="", finish_reason="error"))
        ggl = FakeProvider(
            provider_id="google", api_key="g", result=_ok_result("google answer"),
        )
        with patch(
            "backend.copilot.llm.chat.get_provider",
            side_effect=lambda pid: {"self_hosted": sh, "google": ggl}[pid],
        ):
            answer, attempted = await chat_answer("anything", _ctx(), None)
        assert answer == "google answer"
        assert attempted is True
        assert len(sh.generate_calls) == 1
        assert len(ggl.generate_calls) == 1

    @pytest.mark.asyncio
    async def test_system_prompt_present_in_request(self):
        captured = {}

        class _CaptureProvider(FakeProvider):
            async def generate(self, request):
                captured["request"] = request
                return _ok_result()

        p = _CaptureProvider(api_key="k")
        with patch("backend.copilot.llm.chat.get_provider", return_value=p):
            await chat_answer("Why is the sky blue?", _ctx(language="en"), None)

        req = captured["request"]
        assert req.messages[0].role == "system"
        assert "You are the AI assistant inside Operion ERP" in req.messages[0].content
        assert req.messages[0].content == SYSTEM_PROMPT.format(language_name="English", language_code="en")
        user_msgs = [m for m in req.messages if m.role == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "Why is the sky blue?"
        # No tools — the model cannot execute anything on this branch.
        assert req.tools == []
        assert req.max_tokens == LLM_CHAT_MAX_TOKENS
        assert req.temperature == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_answer_truncated_at_max_chars(self):
        long_answer = "z" * (MAX_ANSWER_CHARS + 500)
        p = FakeProvider(api_key="k", result=_ok_result(long_answer))
        with patch("backend.copilot.llm.chat.get_provider", return_value=p):
            answer, attempted = await chat_answer("tell me a long story", _ctx(), None)
        assert attempted is True
        assert answer is not None
        assert len(answer) == MAX_ANSWER_CHARS


# ── Planner integration ────────────────────────────────────────────────────


class TestPlannerIntegration:
    """process_utterance routing for the chat branch."""

    @pytest.mark.asyncio
    async def test_known_intent_never_calls_llm(self, _offline_llm_chat):
        """A high-confidence known intent executes deterministically BEFORE
        the LLM — chat_with_tools (the LLM-first tool loop) is never called.
        Covers both the EN canonical phrase and the RO fleet-listing phrase.
        Control: an unknown utterance DOES reach the LLM tool loop."""
        from backend.copilot.planner import process_utterance
        from backend.copilot.llm.tool_calling import ToolLoopResult

        resp = await process_utterance("find available trucks", _ctx(), "test-conv-known")
        _offline_llm_chat.assert_not_awaited()
        assert resp is not None

        resp_ro = await process_utterance(
            "ce camioane am in flota", _ctx("ro"), "test-conv-known-ro",
        )
        _offline_llm_chat.assert_not_awaited()
        assert resp_ro is not None

        _offline_llm_chat.return_value = ToolLoopResult(final_answer="42", attempted=True)
        resp_unknown = await process_utterance(
            "do something completely nonsensical xyzzy", _ctx(), "test-conv-unknown",
        )
        _offline_llm_chat.assert_awaited_once()
        assert resp_unknown.summary_key == "copilot.summary.llm_chat"
        assert resp_unknown.summary_params["answer"] == "42"

    @pytest.mark.asyncio
    async def test_blank_utterance_makes_no_llm_call(self):
        """Blank/whitespace input stays fully offline."""
        from backend.copilot.planner import process_utterance

        with patch(
            "backend.copilot.llm.chat.chat_answer",
            new_callable=AsyncMock,
            side_effect=AssertionError("chat_answer must not be called"),
        ) as mock_chat:
            resp = await process_utterance("   ", _ctx(), "test-conv-blank")
            mock_chat.assert_not_called()
        assert resp.clarification_question_key is not None
        assert "unknown_intent" in resp.clarification_question_key
        assert resp.plan is None

    @pytest.mark.asyncio
    async def test_unknown_utterance_flows_through_tool_loop(self):
        """An unrecognized non-blank utterance goes through the LLM-first tool
        loop (chat_with_tools) and surfaces as a summary bubble."""
        from backend.copilot.planner import process_utterance
        from backend.copilot.llm.tool_calling import ToolLoopResult

        with patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock,
            return_value=ToolLoopResult(final_answer="42", attempted=True),
        ) as mock_loop:
            resp = await process_utterance(
                "do something completely nonsensical xyzzy", _ctx(), "test-conv-42",
            )
            mock_loop.assert_awaited_once()
        assert resp.summary_key == "copilot.summary.llm_chat"
        assert resp.summary_params["answer"] == "42"