"""Freight Exchange provider adapter ABC.

All provider-specific adapters (Timocom, Trans.eu, Teleroute, Wtransnet, …)
inherit from ``FreightProviderAdapter`` and self-register via the
``@register_freight_provider`` decorator in ``registry.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from models.freight_exchange_models import (
    ProviderCredentials,
    ProviderSession,
    ProviderHealthCheck,
    ProviderCapabilities,
    LoadSearchFilters,
    LoadSearchResult,
)


class FreightProviderAdapter(ABC):
    """Interface each freight-exchange provider must implement."""

    provider_id: str = ""

    # ── Session lifecycle ──────────────────────────────────────────────

    @abstractmethod
    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        """Obtain a new session from raw credentials."""
        ...

    @abstractmethod
    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        """Refresh an expired or about-to-expire session."""
        ...

    @abstractmethod
    async def test_connection(
        self, session: ProviderSession
    ) -> ProviderHealthCheck:
        """Verify the provider endpoint is reachable and the token is valid."""
        ...

    # ── Load search ────────────────────────────────────────────────────

    @abstractmethod
    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        """Search available loads matching *filters*."""
        ...

    @abstractmethod
    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        """Fetch a single load by its provider-specific identifier."""
        ...

    # ── Introspection ──────────────────────────────────────────────────

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return static metadata about what this provider supports."""
        ...
