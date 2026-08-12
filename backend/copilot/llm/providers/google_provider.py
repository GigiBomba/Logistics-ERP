"""Google AI Studio / Gemini provider — first concrete LLMProvider implementation.

Uses the existing google-genai>=1.47.0 dependency from requirements.txt.
This is the ONLY file allowed to import google.genai directly (§23.2).

Blueprint: §23.2
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Dict, List, Literal

from google import genai
from google.genai import types as genai_types

from backend.copilot.llm.base import LLMMessage, LLMProvider, LLMRequest, LLMResponse, ToolSpec
from backend.copilot.llm.registry import register_llm_provider
from services.preferences import get_ai_api_key

logger = logging.getLogger(__name__)


@register_llm_provider
class GoogleProvider(LLMProvider):
    """Gemini provider via Google AI Studio / Vertex AI."""

    provider_id: str = "google"
    supports_tool_calling: bool = True
    supports_json_mode: bool = True
    is_self_hosted: bool = False

    def __init__(self, model_id: str = "gemini-2.5-flash", api_key: str = "") -> None:
        self.model_id = model_id
        self._api_key = api_key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            # Explicit key > OPERION_GEMINI_API_KEY env > SDK default
            # (GOOGLE_API_KEY env var or ADC).
            key = self._api_key or get_ai_api_key("gemini", None) or None
            self._client = genai.Client(api_key=key)
        return self._client

    # ── Message conversion ──────────────────────────────────────────────

    @staticmethod
    def _to_gemini_role(role: str) -> str:
        """Map our generic roles to Gemini's model/user convention."""
        role_map = {
            "system": "user",       # Gemini: system prompts go in system_instruction config
            "user": "user",
            "assistant": "model",
            "tool": "user",         # Gemini: tool results fed back as user messages
        }
        return role_map.get(role, "user")

    def _build_contents(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert LLMMessage list to Gemini contents format."""
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            parts: List[Dict[str, Any]] = [{"text": msg.content}]
            contents.append({
                "role": self._to_gemini_role(msg.role),
                "parts": parts,
            })
        return contents

    def _build_tools(self, tools: List[ToolSpec]) -> List[Dict[str, Any]]:
        """Convert ToolSpec list to Gemini function declarations."""
        declarations: List[Dict[str, Any]] = []
        for tool in tools:
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_json_schema,
            })
        return [{"function_declarations": declarations}] if declarations else []

    # ── LLMProvider interface ────────────────────────────────────────────

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()

        try:
            client = self._get_client()
            contents = self._build_contents(request.messages)
            tools = self._build_tools(request.tools)

            # Extract system message if present
            system_instruction: Any = None
            for msg in request.messages:
                if msg.role == "system":
                    system_instruction = msg.content
                    break

            response = client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=request.temperature,
                    max_output_tokens=request.max_tokens,
                    tools=tools if tools else None,
                    response_mime_type="application/json" if request.response_format == "json" else None,
                ),
            )

            latency_ms = int((time.monotonic() - start) * 1000)

            # Extract text content
            content_parts: List[str] = []
            tool_calls: List[dict] = []

            if response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.text:
                            content_parts.append(part.text)
                        if hasattr(part, "function_call") and part.function_call:
                            tool_calls.append({
                                "id": getattr(part.function_call, "id", ""),
                                "name": part.function_call.name,
                                "arguments": part.function_call.args or {},
                            })

            finish_reason: Literal["stop", "tool_call", "max_tokens", "error"] = "stop"
            if response.candidates and response.candidates[0].finish_reason:
                reason = str(response.candidates[0].finish_reason)
                if "MAX_TOKENS" in reason:
                    finish_reason = "max_tokens"
                elif "TOOL" in reason or tool_calls:
                    finish_reason = "tool_call"

            return LLMResponse(
                content="\n".join(content_parts),
                tool_calls=tool_calls,
                input_tokens=getattr(response, "usage_metadata", None) and response.usage_metadata.prompt_token_count or 0,
                output_tokens=getattr(response, "usage_metadata", None) and response.usage_metadata.candidates_token_count or 0,
                latency_ms=latency_ms,
                provider_id=self.provider_id,
                model_id=self.model_id,
                finish_reason=finish_reason,
            )

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error("GoogleProvider.generate() failed: %s", exc)
            return LLMResponse(
                content="",
                latency_ms=latency_ms,
                provider_id=self.provider_id,
                model_id=self.model_id,
                finish_reason="error",
            )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        try:
            client = self._get_client()
            contents = self._build_contents(request.messages)

            system_instruction: Any = None
            for msg in request.messages:
                if msg.role == "system":
                    system_instruction = msg.content
                    break

            response = client.models.generate_content_stream(
                model=self.model_id,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=request.temperature,
                    max_output_tokens=request.max_tokens,
                ),
            )

            for chunk in response:
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.text:
                            yield part.text

        except Exception as exc:
            logger.error("GoogleProvider.stream() failed: %s", exc)
            return

    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        try:
            client = self._get_client()
            contents = self._build_contents(messages)

            response = client.models.count_tokens(
                model=self.model_id,
                contents=contents,
            )
            return response.total_tokens if response else 0
        except Exception as exc:
            logger.warning("GoogleProvider.count_tokens() failed: %s", exc)
            # Rough estimate: 1 token ≈ 4 characters
            total_chars = sum(len(m.content) for m in messages)
            return total_chars // 4

    async def health_check(self) -> Literal["healthy", "degraded", "down"]:
        try:
            client = self._get_client()
            response = client.models.generate_content(
                model=self.model_id,
                contents="ping",
                config=genai_types.GenerateContentConfig(max_output_tokens=1),
            )
            if response and response.candidates:
                return "healthy"
            return "degraded"
        except Exception:
            return "down"
