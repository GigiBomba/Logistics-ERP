"""WhatsApp provider ABC.

Every concrete WhatsApp backend (WhatsApp Business Cloud API, future BSPs)
inherits from :class:`WhatsAppProvider` and self-registers via
``@register_whatsapp_provider`` (``registry.py``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class WhatsAppProvider(ABC):
    """Interface each WhatsApp provider must implement.

    Blueprint §21 Ph.4 item 3 — the Co-Pilot only orchestrates the
    deterministic methods below; it never understands WhatsApp itself.
    """

    provider_id: str = ""

    # ── Capability flag ─────────────────────────────────────────────────
    # Subclasses override with an attribute or a property (e.g. derived from
    # whether credentials are present).

    available: bool = False

    # ── Messaging ──────────────────────────────────────────────────────

    @abstractmethod
    async def send_text(self, recipient: str, body: str) -> Dict[str, Any]:
        """Send a plain-text WhatsApp message to *recipient*.

        Returns the provider response payload (parsed JSON).  Raises on
        transport/provider failure — the caller maps exceptions to i18n
        ToolResults.
        """
        ...

    @abstractmethod
    async def health(self) -> str:
        """Return ``"healthy"``, ``"degraded"``, or ``"down"``."""
        ...

    # ── Settings refresh ───────────────────────────────────────────────

    def reload_settings(self, db: Any = None) -> None:
        """Re-read credentials from the settings store.

        Called after DB initialisation and whenever the user updates the
        WhatsApp settings.  Safe to call before the settings table exists.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} provider_id={self.provider_id!r} available={self.available}>"