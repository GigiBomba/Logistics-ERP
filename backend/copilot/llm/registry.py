"""LLM Provider Registry — decorator-based registration with startup validation.

Same pattern as tool registry (§9): providers self-register at import time,
and startup validation fails fast if a RoutingRule references an unregistered provider.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from backend.copilot.llm.base import LLMProvider

logger = logging.getLogger(__name__)

_registry: Dict[str, LLMProvider] = {}


def register_llm_provider(cls: Type[LLMProvider]) -> Type[LLMProvider]:
    """Class decorator: register an LLMProvider subclass at import time."""
    if not issubclass(cls, LLMProvider):
        raise TypeError(f"@register_llm_provider requires LLMProvider subclass, got {cls.__name__}")

    instance = cls()
    _registry[instance.provider_id] = instance
    logger.debug("Registered LLM provider: %s (%s)", instance.provider_id, instance.model_id)
    return cls


def get_provider(provider_id: str) -> Optional[LLMProvider]:
    """Look up a provider by ID."""
    return _registry.get(provider_id)


def all_providers() -> Dict[str, LLMProvider]:
    """Return all registered providers."""
    return dict(_registry)


def validate_registry() -> List[str]:
    """Run at startup. Returns list of validation errors (empty = all valid)."""
    errors: List[str] = []

    for pid, provider in _registry.items():
        if not provider.provider_id or not provider.provider_id.strip():
            errors.append(f"Provider '{pid}': provider_id is empty")
        if not provider.model_id or not provider.model_id.strip():
            errors.append(f"Provider '{pid}': model_id is empty")

    if errors:
        logger.error("LLM provider registry validation FAILED: %d error(s)", len(errors))
        for err in errors:
            logger.error("  - %s", err)
    else:
        logger.info("LLM provider registry validated: %d provider(s) registered", len(_registry))

    return errors
