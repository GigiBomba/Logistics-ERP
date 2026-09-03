"""Google AI Studio / Gemini provider — first concrete LLMProvider implementation.

Uses the existing google-genai>=1.47.0 dependency from requirements.txt.
This is the ONLY file allowed to import google.genai directly (§23.2).

Blueprint: §23.2
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Literal

from google import genai
from google.genai import types as genai_types

from backend.copilot.llm.base import LLMMessage, LLMProvider, LLMRequest, LLMResponse, ToolSpec
from backend.copilot.llm.registry import register_llm_provider
from services.preferences import get_ai_api_key

logger = logging.getLogger(__name__)

# ── Gemini parameter-schema sanitizer ──────────────────────────────────────
# Pydantic's ``model_json_schema()`` output carries keys the google-genai SDK
# ``Schema`` model rejects ("Extra inputs are not permitted" / a downstream
# "callable" union error) — observed in production on the native tool channel.
# The keys are renamed into the SDK's field names or dropped; optional-field
# ``anyOf`` unions are flattened to ``nullable``.  ``additionalProperties`` is
# DROPPED outright — Gemini's OpenAPI-3.0-subset function-declaration schema
# rejects it in any form (400 INVALID_ARGUMENT: Unknown name
# "additional_properties").  The whitelist is derived from the installed SDK
# so it tracks the SDK version.

_GEMINI_SCHEMA_RENAME = {
    "anyOf": "any_of",
    "minLength": "min_length",
    "maxLength": "max_length",
    "minItems": "min_items",
    "maxItems": "max_items",
    "minProperties": "min_properties",
    "maxProperties": "max_properties",
    "$ref": "ref",
    "$defs": "defs",
}
# Keys that must be dropped entirely rather than renamed: Gemini's
# function-declaration schema does not accept ``additionalProperties`` in any
# form (renaming it to ``additional_properties`` still gets a 400 from the
# REST API).  Both the original and renamed spellings are listed so any path
# is covered.
_GEMINI_SCHEMA_DROP = frozenset({"additionalProperties", "additional_properties"})
_GEMINI_SCHEMA_FIELDS = frozenset(genai_types.Schema.model_fields.keys())
# Name->Schema maps: the *keys* are arbitrary names, only the *values* are
# schemas and must be sanitized recursively.
_GEMINI_NAME_MAP_KEYS = frozenset({"properties", "$defs", "defs"})


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

    @staticmethod
    def _parse_tool_content(content: str) -> Dict[str, Any]:
        """Parse a ``role="tool"`` message body into ``{name, response}``.

        Gemini requires tool results to come back as ``functionResponse``
        parts (not plain text), otherwise the native tool loop breaks on the
        second iteration.  The tool *name* and *response payload* travel in
        the message content as a JSON envelope::

            {"tool_name": "get_weather", "response": {"temperature": 21}}

        ``name`` is accepted as an alias for ``tool_name``.  When the content
        is not an envelope (plain text or JSON without those keys), the raw
        content is used as the response payload with an empty name — the
        caller may still recover the name from ``tool_call_id``.
        """
        name = ""
        response: Any = content
        try:
            parsed = json.loads(content)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            name = str(parsed.get("tool_name") or parsed.get("name") or "")
            response = parsed.get("response", parsed)
        return {"name": name, "response": response}

    def _build_contents(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert LLMMessage list to Gemini contents format.

        Messages with ``role="tool"`` are emitted as ``functionResponse``
        parts (Gemini's required shape for tool results) rather than being
        flattened into text — without this the tool loop cannot continue
        after the first tool call.  The originating call id travels in
        ``LLMMessage.tool_call_id`` (base.py:24) and is forwarded to the
        part's ``id`` field so Gemini pairs the result with the correct
        ``function_call``; the tool name + response payload are reconstructed
        from the content envelope (see :meth:`_parse_tool_content`).
        """
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool":
                parsed = self._parse_tool_content(msg.content)
                fr: Dict[str, Any] = {
                    "name": parsed["name"],
                    "response": parsed["response"],
                }
                if msg.tool_call_id:
                    fr["id"] = msg.tool_call_id
                contents.append({
                    "role": "user",      # Gemini: functionResponse goes in a user message
                    "parts": [{"functionResponse": fr}],
                })
                continue
            parts: List[Dict[str, Any]] = [{"text": msg.content}]
            contents.append({
                "role": self._to_gemini_role(msg.role),
                "parts": parts,
            })
        return contents

    @staticmethod
    def _sanitize_gemini_schema(node: Any) -> Any:
        """Recursively rewrite a Pydantic ``model_json_schema()`` dict into the
        shape the google-genai SDK's ``Schema`` model accepts.

        Pydantic emits several keys the SDK validator rejects:
        ``exclusiveMinimum``/``exclusiveMaximum`` (unsupported),
        ``anyOf`` (SDK name is ``any_of``), ``additionalProperties``
        (DROPPED — Gemini's function-declaration schema does not accept it,
        even renamed), ``minLength``/``maxLength`` (SDK names
        ``min_length``/``max_length``), and any other key not on the SDK
        ``Schema`` model (e.g. a stray ``callable``, ``oneOf``, ``allOf``).
        Optional fields Pydantic encodes as ``anyOf: [<type>, {"type": "null"}]``
        are flattened into the single type branch with ``nullable: true``.
        Types and ``required`` lists are preserved throughout.
        """
        if isinstance(node, list):
            return [GoogleProvider._sanitize_gemini_schema(x) for x in node]
        if not isinstance(node, dict):
            return node

        any_of = node.get("anyOf")
        if isinstance(any_of, list):
            branches = [GoogleProvider._sanitize_gemini_schema(b) for b in any_of]
            non_null = [b for b in branches if b.get("type") != "null"]
            has_null = len(non_null) != len(branches)
            if len(non_null) == 1 and has_null:
                merged: Dict[str, Any] = dict(non_null[0])
                merged["nullable"] = True
                for k, v in node.items():
                    if k not in ("anyOf", "type"):
                        merged[k] = GoogleProvider._sanitize_gemini_schema(v)
                if non_null[0].get("type"):
                    merged["type"] = non_null[0]["type"]
                node = merged
            else:
                out: Dict[str, Any] = {}
                for k, v in node.items():
                    if k == "anyOf":
                        out["any_of"] = non_null
                    else:
                        out[k] = GoogleProvider._sanitize_gemini_schema(v)
                node = out

        out = {}
        for k, v in node.items():
            nk = _GEMINI_SCHEMA_RENAME.get(k, k)
            if nk in ("exclusiveMinimum", "exclusiveMaximum"):
                # Gemini has no exclusive bounds.  Integer bounds map exactly:
                # exclusiveMinimum N → minimum N+1 (values > N), exclusiveMaximum
                # N → maximum N-1 (values < N).  Number bounds map to the raw
                # value (closest supported approximation).
                if node.get("type") == "integer" and isinstance(v, int):
                    bound = "minimum" if nk == "exclusiveMinimum" else "maximum"
                    if bound not in node:
                        out[bound] = v + 1 if nk == "exclusiveMinimum" else v - 1
                elif node.get("type") == "number":
                    bound = "minimum" if nk == "exclusiveMinimum" else "maximum"
                    if bound not in node:
                        out[bound] = v
                continue
            if nk in _GEMINI_NAME_MAP_KEYS and isinstance(v, dict):
                out[nk] = {
                    name: GoogleProvider._sanitize_gemini_schema(schema)
                    for name, schema in v.items()
                }
                continue
            if nk in _GEMINI_SCHEMA_DROP:
                continue
            if nk not in _GEMINI_SCHEMA_FIELDS:
                continue
            out[nk] = GoogleProvider._sanitize_gemini_schema(v)
        return out

    def _build_tools(self, tools: List[ToolSpec]) -> List[Dict[str, Any]]:
        """Convert ToolSpec list to Gemini function declarations.

        Parameter schemas come from Pydantic ``model_json_schema()`` and carry
        keys the google-genai SDK validator rejects (``exclusiveMinimum``,
        ``anyOf``, ``additionalProperties``, ...) — every schema is rewritten
        into the SDK-accepted shape by :meth:`_sanitize_gemini_schema` before
        the declarations are built (locked by the hermetic real-SDK test in
        ``tests/copilot/test_google_provider.py``).
        """
        declarations: List[Dict[str, Any]] = []
        for tool in tools:
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": self._sanitize_gemini_schema(tool.parameters_json_schema or {}),
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
                    # Gemini rejects `tools` combined with `response_mime_type`
                    # — JSON mode is dropped whenever tools are present.
                    response_mime_type=(
                        "application/json"
                        if request.response_format == "json" and not tools
                        else None
                    ),
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
