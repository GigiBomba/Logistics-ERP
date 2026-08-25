"""Freight Exchange provider adapter registry.

Adapters self-register via the ``@register_freight_provider`` decorator.
Startup validation fails fast if a company's connection references an
unregistered ``provider_id``, or if a registered adapter is missing a
required method — same discipline as every other registry pattern already
established in this codebase.
"""
from __future__ import annotations

import logging
from typing import Optional

from services.freight_exchange.adapter_base import FreightProviderAdapter

logger = logging.getLogger(__name__)

# Global registry: provider_id → adapter instance
_registry: dict[str, FreightProviderAdapter] = {}


def register_freight_provider(cls: type) -> type:
    """Class decorator that registers a ``FreightProviderAdapter`` subclass.

    Usage::

        @register_freight_provider
        class TimocomAdapter(FreightProviderAdapter):
            provider_id = "timocom"
            ...
    """
    if not issubclass(cls, FreightProviderAdapter):
        raise TypeError(
            f"{cls.__name__} must be a subclass of FreightProviderAdapter"
        )
    instance = cls()
    provider_id = instance.provider_id
    if not provider_id:
        raise ValueError(f"{cls.__name__} must define a non-empty provider_id")
    if provider_id in _registry:
        raise ValueError(
            f"Provider '{provider_id}' is already registered by "
            f"{_registry[provider_id].__class__.__name__}"
        )
    _registry[provider_id] = instance
    logger.info("Registered freight provider: %s → %s", provider_id, cls.__name__)
    return cls


def get_adapter(provider_id: str) -> Optional[FreightProviderAdapter]:
    """Look up a registered adapter by provider ID."""
    return _registry.get(provider_id)


def list_adapters() -> list[str]:
    """Return all registered provider IDs."""
    return list(_registry.keys())


def get_all_adapters() -> dict[str, FreightProviderAdapter]:
    """Return the full registry (for iteration)."""
    return dict(_registry)


def validate_registry() -> list[str]:
    """Validate all registered adapters at startup.

    Checks that every adapter's abstract methods are implemented.
    Returns a list of error messages (empty = all good).
    """
    errors: list[str] = []
    for provider_id, adapter in _registry.items():
        required = [
            "authenticate",
            "refresh_session",
            "test_connection",
            "search_loads",
            "get_load",
            "capabilities",
        ]
        for method_name in required:
            method = getattr(adapter, method_name, None)
            if method is None:
                errors.append(
                    f"{adapter.__class__.__name__}: missing method '{method_name}'"
                )
            elif getattr(method, "__isabstractmethod__", False):
                errors.append(
                    f"{adapter.__class__.__name__}: '{method_name}' is still abstract"
                )
    if errors:
        logger.error("Registry validation failed: %s", errors)
    else:
        logger.info("Registry validation passed — %d provider(s)", len(_registry))
    return errors
