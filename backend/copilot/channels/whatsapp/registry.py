"""WhatsApp provider adapter registry.

Providers self-register via the ``@register_whatsapp_provider`` decorator —
the same discipline as the tool registry and the freight-exchange adapter
registry.  Startup validation fails fast when a registered provider misses a
required method.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend.copilot.channels.whatsapp.base import WhatsAppProvider

logger = logging.getLogger(__name__)

# Global registry: provider_id → provider instance
_registry: dict[str, WhatsAppProvider] = {}

_REQUIRED_METHODS = ("send_text", "health")


def register_whatsapp_provider(cls: type) -> type:
    """Class decorator that registers a ``WhatsAppProvider`` subclass.

    Usage::

        @register_whatsapp_provider
        class WhatsAppCloudApiProvider(WhatsAppProvider):
            provider_id = "whatsapp_cloud_api"
            ...
    """
    if not issubclass(cls, WhatsAppProvider):
        raise TypeError(f"{cls.__name__} must be a subclass of WhatsAppProvider")
    instance = cls()
    provider_id = instance.provider_id
    if not provider_id:
        raise ValueError(f"{cls.__name__} must define a non-empty provider_id")
    if provider_id in _registry:
        raise ValueError(
            f"WhatsApp provider '{provider_id}' is already registered by "
            f"{_registry[provider_id].__class__.__name__}"
        )
    _registry[provider_id] = instance
    logger.info("Registered WhatsApp provider: %s → %s", provider_id, cls.__name__)
    return cls


def get_whatsapp_provider(provider_id: Optional[str] = None) -> Optional[WhatsAppProvider]:
    """Look up a registered provider by ID.

    When *provider_id* is omitted, returns the first AVAILABLE provider
    (preferring configured ones), falling back to the first registered one so
    callers can distinguish "none registered" from "registered but
    unconfigured" via ``.available``.
    """
    if provider_id is not None:
        return _registry.get(provider_id)
    for provider in _registry.values():
        if provider.available:
            return provider
    return next(iter(_registry.values()), None)


def list_whatsapp_providers() -> List[str]:
    """Return all registered provider IDs."""
    return list(_registry.keys())


def get_all_whatsapp_providers() -> dict[str, WhatsAppProvider]:
    """Return the full registry (for iteration)."""
    return dict(_registry)


def reload_whatsapp_settings(db: Any = None) -> None:
    """Re-read credentials for every registered provider (startup / settings UI)."""
    for provider in _registry.values():
        try:
            provider.reload_settings(db)
        except Exception as exc:
            logger.warning("WhatsApp provider %s settings reload failed: %s", provider.provider_id, exc)


def validate_registry() -> List[str]:
    """Validate all registered providers at startup.

    Checks that every provider's abstract methods are implemented.
    Returns a list of error messages (empty = all good).
    """
    errors: List[str] = []
    for provider_id, provider in _registry.items():
        for method_name in _REQUIRED_METHODS:
            method = getattr(provider, method_name, None)
            if method is None:
                errors.append(
                    f"{provider.__class__.__name__}: missing method '{method_name}'"
                )
            elif getattr(method, "__isabstractmethod__", False):
                errors.append(
                    f"{provider.__class__.__name__}: '{method_name}' is still abstract"
                )
    if errors:
        logger.error("WhatsApp registry validation failed: %s", errors)
    else:
        logger.info("WhatsApp registry validation passed — %d provider(s)", len(_registry))
    return errors