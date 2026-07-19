"""LLM Routing — task-to-provider mapping with automatic failover.

Blueprint: §23.2 — Routing config, not hardcoded model choice.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class RoutingRule(BaseModel):
    """Maps a task type to a primary (and optional fallback) LLM provider."""
    model_config = ConfigDict(extra="forbid")

    task: Literal["intent_extraction", "reasoning_graph_resolution", "final_summary", "sensitive_extraction"]
    provider_id: str
    fallback_provider_id: Optional[str] = None  # used if primary provider's health_check() reports "down"


class LLMRoutingConfig(BaseModel):
    """Per-company or platform-default routing configuration."""
    model_config = ConfigDict(extra="forbid")

    company_id: Optional[int] = None    # None = platform default; company-specific overrides for Enterprise
    rules: List[RoutingRule] = []
