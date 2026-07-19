"""Text-to-Speech provider interface — vendor-agnostic, same discipline as LLMProvider (§23.2).

Blueprint: §3.3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TTSRequest(BaseModel):
    """A TTS synthesis request — text is already t()-resolved, never a raw i18n key."""
    model_config = ConfigDict(extra="forbid")

    text: str                        # the already-t()-resolved string — TTS never touches an i18n key directly
    language: str                    # must be in SUPPORTED_LANGUAGES
    voice_profile_id: Optional[str] = None   # per-language voice selection


class TTSProvider(ABC):
    """Every concrete TTS engine implements this interface.

    Self-hosted by default (same reasoning as STT and Gemma 3:4B for handwriting).
    TTS is behind the same abstraction discipline as LLMProvider — TTSProvider
    is its own interface, concrete engines are swappable, and nothing outside
    backend/copilot/voice/ imports a specific TTS SDK directly.
    """

    provider_id: str = ""
    model_id: str = ""

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> bytes:
        """Synthesize text to audio bytes — streamed to the client."""
        ...

    @abstractmethod
    def supported_languages(self) -> List[str]:
        """Return list of language codes this TTS engine supports."""
        ...
