"""LLM Provider Interface — vendor-agnostic by construction.

No module outside this package is allowed to import a vendor SDK.
The Planner, Reasoning Graph resolver, and every other component
talk to models exclusively through this interface.

Blueprint: §23.2
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class LLMMessage(BaseModel):
    """A single message in a conversation with an LLM."""
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: Optional[str] = None


class ToolSpec(BaseModel):
    """Vendor-agnostic tool-calling spec, translated to each provider's own
    function-calling format inside that provider's adapter — never leaked upward."""
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters_json_schema: dict


class LLMRequest(BaseModel):
    """A standardized request to an LLM provider."""
    model_config = ConfigDict(extra="forbid")

    messages: List[LLMMessage]
    tools: List[ToolSpec] = []
    max_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    response_format: Literal["text", "json"] = "text"


class LLMResponse(BaseModel):
    """A standardized response from an LLM provider."""
    model_config = ConfigDict(extra="ignore")

    content: str
    tool_calls: List[dict] = []
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    provider_id: str = ""
    model_id: str = ""
    finish_reason: Literal["stop", "tool_call", "max_tokens", "error"] = "stop"


class LLMProvider(ABC):
    """Every concrete provider (Anthropic, OpenAI, self-hosted, etc.) implements this.

    The Planner, Reasoning Graph resolver, and every other caller import LLMProvider,
    never a vendor SDK directly — the same discipline as BaseTool keeping tool
    callers off raw service internals.
    """

    provider_id: str          # e.g. "anthropic", "openai", "google", "self_hosted_ollama"
    model_id: str             # e.g. "gemini-2.5-flash", "claude-sonnet-5"
    supports_tool_calling: bool = False
    supports_json_mode: bool = False
    is_self_hosted: bool = False  # drives the data-sensitivity routing decision

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a completion (non-streaming)."""
        ...

    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Generate a completion (streaming). Yields content chunks."""
        ...

    @abstractmethod
    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        """Count the number of tokens in a list of messages."""
        ...

    @abstractmethod
    async def health_check(self) -> Literal["healthy", "degraded", "down"]:
        """Check whether this provider is reachable and functioning."""
        ...
