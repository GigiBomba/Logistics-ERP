"""Self-hosted LLM provider — primary AI for ARGO, same endpoint as OCR.

Uses the same self-hosted model (Gemma 3:4B at ``https://ocr.operionerp.xyz``)
that powers OCR's AI Vision fallback.  This is ARGO's primary LLM for
cost efficiency and data sensitivity.  Google Gemini (``GoogleProvider``)
acts as the fallback when this provider is unhealthy.

The endpoint and model are read from the same DB settings as
:mod:`services.document_automation.ai_fallback` (``qwen_endpoint``,
``qwen_model``, ``qwen_api_mode``), so a single settings page controls
both OCR and ARGO AI.

Two API modes are supported:
    - **OpenAI-compatible** (default, preferred for ARGO): ``/v1/chat/completions``
    - **Ollama**: ``/api/generate``

Blueprint: §23.2 — LLM provider implementation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import httpx

from backend.copilot.llm.base import LLMMessage, LLMProvider, LLMRequest, LLMResponse, ToolSpec
from backend.copilot.llm.registry import register_llm_provider

logger = logging.getLogger(__name__)

# ── Defaults (mirror services/document_automation/ai_fallback.py) ─────────

DEFAULT_ENDPOINT = "https://ocr.operionerp.xyz"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_API_MODE = "openai"       # OpenAI-compat preferred for text-only chat
DEFAULT_TIMEOUT_S = 120
_MAX_TOKENS = 4096
_TEMPERATURE = 0.2

# Cap on accumulated streaming text to prevent unbounded memory growth.
_MAX_STREAM_CHARS = 100_000


@register_llm_provider
class OcrAIProvider(LLMProvider):
    """Self-hosted LLM provider using the OCR AI endpoint.

    Connects to the same self-hosted model (Gemma 3:4B via Ollama)
    that OCR uses, but for text-only chat (no vision). The endpoint
    is configured via the same DB settings as OCR's AI fallback.

    Provider ID: ``self_hosted`` — referenced by routing rules as the
    primary provider for all ARGO task types.
    """

    provider_id: str = "self_hosted"
    supports_tool_calling: bool = False     # Gemma 3:4B has limited tool support via Ollama
    supports_json_mode: bool = True         # Prompt-based JSON mode via system instruction
    is_self_hosted: bool = True

    def __init__(self) -> None:
        self.model_id = DEFAULT_MODEL
        self._endpoint = DEFAULT_ENDPOINT
        self._api_mode = DEFAULT_API_MODE
        self._timeout_s = DEFAULT_TIMEOUT_S
        self._api_key: str = ""
        self._client: Optional[httpx.AsyncClient] = None

    # ── HTTP client ───────────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_s))
        return self._client

    def _auth_headers(self) -> dict[str, str]:
        """Return auth headers for the self-hosted endpoint."""
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    async def _close_client(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Settings management ──────────────────────────────────────────

    def reload_settings(self, db) -> None:
        """Reload endpoint, model, and API mode from DB settings.

        Call after DB initialisation and whenever the user updates
        AI Vision settings in the UI. Uses the same DB keys as
        :func:`services.document_automation.ai_fallback.init_from_db`.

        This is safe to call before the settings table exists (e.g. during
        test setup) — it will silently keep the current defaults.
        """
        try:
            from repositories.settings_repository import SettingsRepository

            settings = SettingsRepository(db).get_settings_by_keys(
                ["qwen_endpoint", "qwen_model", "qwen_api_mode", "qwen_timeout_s", "qwen_api_key"],
            )
            if settings.get("qwen_endpoint"):
                self._endpoint = settings["qwen_endpoint"]
            if settings.get("qwen_model"):
                self.model_id = settings["qwen_model"]
            if settings.get("qwen_api_mode"):
                self._api_mode = settings["qwen_api_mode"]
            if settings.get("qwen_api_key") or os.environ.get("OPERION_QWEN_API_KEY"):
                from services.preferences import get_ai_api_key
                resolved_key = get_ai_api_key("qwen", settings.get("qwen_api_key"))
                if resolved_key:
                    self._api_key = resolved_key
            if settings.get("qwen_timeout_s"):
                try:
                    self._timeout_s = int(settings["qwen_timeout_s"])
                except ValueError:
                    pass
            # Recreate client so the new timeout takes effect
            self._client = None
            logger.info(
                "OcrAIProvider settings updated: endpoint=%s model=%s api_mode=%s",
                self._endpoint, self.model_id, self._api_mode,
            )
        except Exception:
            logger.debug("OcrAIProvider.reload_settings() skipped (settings table may not exist yet)")

    # ── Message conversion ───────────────────────────────────────────

    @staticmethod
    def _build_chat_messages(messages: List[LLMMessage]) -> List[Dict[str, str]]:
        """Convert LLMMessage list to OpenAI-compatible chat format.

        Tool-result messages are mapped to ``user`` role because
        self-hosted endpoints typically don't have a native ``tool`` role.
        """
        result: List[Dict[str, str]] = []
        for msg in messages:
            role = msg.role
            if role == "tool":
                role = "user"
            result.append({"role": role, "content": msg.content})
        return result

    @staticmethod
    def _system_prompt(messages: List[LLMMessage]) -> Optional[str]:
        """Return the first system message content, or ``None``."""
        for msg in messages:
            if msg.role == "system":
                return msg.content
        return None

    # ── LLMProvider interface ────────────────────────────────────────

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion (non-streaming).

        Dispatches to the active API mode (OpenAI-compatible or Ollama).
        """
        start = time.monotonic()

        try:
            if self._api_mode == "ollama":
                return await self._generate_ollama(request, start)
            return await self._generate_openai(request, start)
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error("OcrAIProvider.generate() failed: %s", exc)
            return LLMResponse(
                content="",
                latency_ms=latency_ms,
                provider_id=self.provider_id,
                model_id=self.model_id,
                finish_reason="error",
            )

    async def _generate_openai(self, request: LLMRequest, start: float) -> LLMResponse:
        """Generate via OpenAI-compatible ``/v1/chat/completions``."""
        client = self._get_client()
        url = self._endpoint.rstrip("/") + "/v1/chat/completions"

        messages = self._build_chat_messages(request.messages)
        sys_prompt = self._system_prompt(request.messages)
        if sys_prompt:
            messages.insert(0, {"role": "system", "content": sys_prompt})

        headers = self._auth_headers()
        payload: Dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }

        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        response = await client.post(url, json=payload, headers=headers)
        latency_ms = int((time.monotonic() - start) * 1000)

        if response.status_code != 200:
            logger.warning(
                "OcrAIProvider OpenAI-compat returned HTTP %d: %s",
                response.status_code, response.text[:300],
            )
            return LLMResponse(
                content="", latency_ms=latency_ms,
                provider_id=self.provider_id, model_id=self.model_id,
                finish_reason="error",
            )

        data = response.json()
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        finish = choice.get("finish_reason", "stop")

        finish_reason: Literal["stop", "tool_call", "max_tokens", "error"] = "stop"
        if finish == "length":
            finish_reason = "max_tokens"
        elif finish == "tool_calls":
            finish_reason = "tool_call"

        return LLMResponse(
            content=content or "",
            latency_ms=latency_ms,
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
            provider_id=self.provider_id,
            model_id=self.model_id,
            finish_reason=finish_reason,
        )

    async def _generate_ollama(self, request: LLMRequest, start: float) -> LLMResponse:
        """Generate via Ollama ``/api/generate``.

        Converts the chat message list into a flat prompt string since
        Ollama's generate endpoint expects a single prompt rather than a
        structured message list.
        """
        client = self._get_client()
        url = self._endpoint.rstrip("/") + "/api/generate"

        headers = self._auth_headers()
        prompt_parts: List[str] = []
        sys_prompt = self._system_prompt(request.messages)
        if sys_prompt:
            prompt_parts.append(f"System: {sys_prompt}")
        for msg in request.messages:
            if msg.role in ("user", "assistant"):
                prompt_parts.append(f"{msg.role}: {msg.content}")
        prompt = "\n".join(prompt_parts)

        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        response = await client.post(url, json=payload, headers=headers)
        latency_ms = int((time.monotonic() - start) * 1000)

        if response.status_code != 200:
            logger.warning(
                "OcrAIProvider Ollama returned HTTP %d: %s",
                response.status_code, response.text[:300],
            )
            return LLMResponse(
                content="", latency_ms=latency_ms,
                provider_id=self.provider_id, model_id=self.model_id,
                finish_reason="error",
            )

        data = response.json()
        content = data.get("response", "")

        return LLMResponse(
            content=content,
            latency_ms=latency_ms,
            input_tokens=0,
            output_tokens=data.get("eval_count", 0),
            provider_id=self.provider_id,
            model_id=self.model_id,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Generate a completion (streaming). Yields content chunks."""
        try:
            if self._api_mode == "ollama":
                async for chunk in self._stream_ollama(request):
                    yield chunk
            else:
                async for chunk in self._stream_openai(request):
                    yield chunk
        except Exception as exc:
            logger.error("OcrAIProvider.stream() failed: %s", exc)
            return

    async def _stream_openai(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream via OpenAI-compatible ``/v1/chat/completions`` with SSE."""
        client = self._get_client()
        url = self._endpoint.rstrip("/") + "/v1/chat/completions"

        messages = self._build_chat_messages(request.messages)
        sys_prompt = self._system_prompt(request.messages)
        if sys_prompt:
            messages.insert(0, {"role": "system", "content": sys_prompt})

        headers = self._auth_headers()
        payload: Dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }

        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                logger.warning(
                    "OcrAIProvider stream (OpenAI) returned HTTP %d",
                    response.status_code,
                )
                return

            total_chars = 0
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {})
                chunk = delta.get("content", "")
                if chunk:
                    yield chunk
                    total_chars += len(chunk)
                    if total_chars > _MAX_STREAM_CHARS:
                        logger.warning("OcrAIProvider stream capped at %d chars", _MAX_STREAM_CHARS)
                        break

    async def _stream_ollama(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream via Ollama ``/api/generate`` with NDJSON streaming."""
        client = self._get_client()
        url = self._endpoint.rstrip("/") + "/api/generate"

        headers = self._auth_headers()
        prompt_parts: List[str] = []
        sys_prompt = self._system_prompt(request.messages)
        if sys_prompt:
            prompt_parts.append(f"System: {sys_prompt}")
        for msg in request.messages:
            if msg.role in ("user", "assistant"):
                prompt_parts.append(f"{msg.role}: {msg.content}")
        prompt = "\n".join(prompt_parts)

        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                logger.warning(
                    "OcrAIProvider stream (Ollama) returned HTTP %d",
                    response.status_code,
                )
                return

            total_chars = 0
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = obj.get("response", "")
                if chunk:
                    yield chunk
                    total_chars += len(chunk)
                    if total_chars > _MAX_STREAM_CHARS:
                        logger.warning("OcrAIProvider stream capped at %d chars", _MAX_STREAM_CHARS)
                        break
                if obj.get("done"):
                    break

    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        """Approximate token count.

        We don't bundle a Gemma tokenizer locally, so this estimates
        ~1 token per 4 characters (a common heuristic for LLMs).
        """
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4

    async def health_check(self) -> Literal["healthy", "degraded", "down"]:
        """Check whether the self-hosted endpoint is reachable.

        Sends a minimal ping request (single token) to the active API
        endpoint. Returns ``"healthy"`` on HTTP 200, ``"degraded"`` on
        other responses, and ``"down"`` on connection errors.
        """
        try:
            client = self._get_client()
            if self._api_mode == "openai":
                url = self._endpoint.rstrip("/") + "/v1/chat/completions"
                payload: Dict[str, Any] = {
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "stream": False,
                }
            else:
                url = self._endpoint.rstrip("/") + "/api/generate"
                payload = {
                    "model": self.model_id,
                    "prompt": "ping",
                    "stream": False,
                    "options": {"num_predict": 1},
                }

            response = await client.post(url, json=payload, headers=self._auth_headers(), timeout=httpx.Timeout(10.0))

            if response.status_code == 200:
                return "healthy"
            logger.warning("OcrAIProvider health_check returned HTTP %d", response.status_code)
            return "degraded"
        except Exception as exc:
            logger.debug("OcrAIProvider health_check failed: %s", exc)
            return "down"
