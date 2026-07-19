"""Voice pipeline data contracts.

Blueprint: §3.2 (VoiceInputResult, WakeWordConfig), §3.3 (TTSRequest).
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class VoiceInputResult(BaseModel):
    """Result of processing a voice utterance through STT."""
    model_config = ConfigDict(extra="forbid")

    transcript: str
    detected_language: str          # ISO code, must be in SUPPORTED_LANGUAGES
    detection_confidence: float = Field(ge=0.0, le=1.0)
    audio_duration_ms: int
    stt_model_version: str          # stamped for the same reasons tool_version is (§9.2) — reproducibility


class WakeWordConfig(BaseModel):
    """Wake word configuration — Enterprise-tier: continuous listening; Business-tier: push-to-talk."""
    model_config = ConfigDict(extra="forbid")

    enabled: bool                    # Enterprise-tier default true, Business-tier default false (push-to-talk only)
    phrase: str                      # see §3.4 on multilingual wake-word coverage
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
