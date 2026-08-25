"""TIMOCOM freight exchange adapter.

Maps TIMOCOM's REST API into the normalized ``FreightProviderAdapter``
interface.  All TIMOCOM-specific API knowledge lives here — nothing above
this file ever imports a TIMOCOM type or references a TIMOCOM payload shape.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from models.freight_exchange_models import (
    ProviderCredentials,
    ProviderSession,
    ProviderHealthCheck,
    ProviderCapabilities,
    GeoFilter,
    LoadSearchFilters,
    LoadSearchResult,
)
from models.common import Money
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.registry import register_freight_provider

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
TIMOCOM_AUTH_URL = "https://api.timocom.com/oauth2/token"
TIMOCOM_API_BASE = "https://api.timocom.com/v1"
TIMOCOM_LOAD_SEARCH_ENDPOINT = "/loads/search"
TIMOCOM_LOAD_DETAIL_ENDPOINT = "/loads/{load_id}"
TIMOCOM_HEALTH_ENDPOINT = "/health"
DEFAULT_TIMEOUT = 30  # seconds


# ── TIMOCOM Adapter ────────────────────────────────────────────────────────

@register_freight_provider
class TimocomAdapter(FreightProviderAdapter):
    """TIMOCOM freight exchange adapter.

    Authenticates via OAuth2 client credentials, searches loads,
    fetches individual load details, and reports provider capabilities.
    """

    provider_id = "timocom"

    # ── Authentication ──────────────────────────────────────────────────

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        """Authenticate with TIMOCOM OAuth2 and return a session."""
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                TIMOCOM_AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret_encrypted,
                    "scope": " ".join(creds.scope) if creds.scope else "loads:read",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

        now = datetime.now(timezone.utc)
        expires_in = data.get("expires_in", 3600)
        expires_at = datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc)

        return ProviderSession(
            company_id=creds.company_id,
            provider_id=self.provider_id,
            access_token_encrypted=data["access_token"],
            expires_at=expires_at,
            refresh_token_encrypted=data.get("refresh_token"),
        )

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        """Refresh the session if the token is near expiry.

        TIMOCOM tokens are short-lived.  If more than 80% of the TTL has
        elapsed, re-authenticate using the refresh token.
        """
        now = datetime.now(timezone.utc)
        ttl = (session.expires_at - now).total_seconds()
        if ttl > 60:  # more than 1 minute left — still good
            return session

        # Token expired or near expiry — re-authenticate
        logger.info("TIMOCOM token near expiry (%.0fs left), refreshing", ttl)
        # TIMOCOM supports refresh_token grant if a refresh token was provided
        if session.refresh_token_encrypted:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(
                    TIMOCOM_AUTH_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": session.refresh_token_encrypted,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    expires_in = data.get("expires_in", 3600)
                    expires_at = datetime.fromtimestamp(
                        now.timestamp() + expires_in, tz=timezone.utc
                    )
                    return ProviderSession(
                        company_id=session.company_id,
                        provider_id=self.provider_id,
                        access_token_encrypted=data["access_token"],
                        expires_at=expires_at,
                        refresh_token_encrypted=data.get("refresh_token"),
                    )
                logger.warning("TIMOCOM refresh_token grant failed (HTTP %d)", resp.status_code)

        # Fallback: caller must handle re-authentication with full creds
        raise RuntimeError("TIMOCOM session expired and cannot be refreshed")

    # ── Health Check ────────────────────────────────────────────────────

    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck:
        """Ping TIMOCOM's health endpoint."""
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(
                    f"{TIMOCOM_API_BASE}{TIMOCOM_HEALTH_ENDPOINT}",
                    headers={"Authorization": f"Bearer {session.access_token_encrypted}"},
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                if resp.status_code == 200:
                    return ProviderHealthCheck(
                        provider_id=self.provider_id,
                        status="healthy",
                        latency_ms=latency_ms,
                        checked_at=datetime.now(timezone.utc),
                    )
                return ProviderHealthCheck(
                    provider_id=self.provider_id,
                    status="degraded",
                    latency_ms=latency_ms,
                    checked_at=datetime.now(timezone.utc),
                    error=f"HTTP {resp.status_code}",
                )
        except Exception as e:
            latency_ms = int((time.monotonic() - started) * 1000)
            return ProviderHealthCheck(
                provider_id=self.provider_id,
                status="down",
                latency_ms=latency_ms,
                checked_at=datetime.now(timezone.utc),
                error=str(e),
            )

    # ── Search ─────────────────────────────────────────────────────────

    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        """Search TIMOCOM for loads matching the normalized filters.

        Translates ``LoadSearchFilters`` → TIMOCOM query parameters.
        """
        params = self._build_search_params(filters)

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{TIMOCOM_API_BASE}{TIMOCOM_LOAD_SEARCH_ENDPOINT}",
                params=params,
                headers={"Authorization": f"Bearer {session.access_token_encrypted}"},
            )
            resp.raise_for_status()
            raw_results = resp.json()

        return [self._map_result(r) for r in raw_results.get("loads", [])]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        """Fetch a single TIMOCOM load by its native ID.

        Returns ``None`` if the load is not found (HTTP 404).
        """
        url = f"{TIMOCOM_API_BASE}{TIMOCOM_LOAD_DETAIL_ENDPOINT.format(load_id=load_id)}"

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {session.access_token_encrypted}"},
            )
            if resp.status_code == 404:
                logger.info("TIMOCOM load %s not found (404)", load_id)
                return None
            resp.raise_for_status()
            raw = resp.json()

        return self._map_result(raw)

    # ── Capabilities ───────────────────────────────────────────────────

    def capabilities(self) -> ProviderCapabilities:
        """Report what TIMOCOM's API supports."""
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=[
                "origin",
                "destination",
                "pickup_date_from",
                "pickup_date_to",
                "delivery_date_from",
                "delivery_date_to",
                "trailer_type",
                "adr_required",
                "weight_kg_min",
                "weight_kg_max",
                "distance_km_max",
                "loading_type",
                "loading_country",
                "delivery_country",
                "sort_by",
                "sort_order",
                "min_trucks",
            ],
            supports_saved_search=False,  # TIMOCOM doesn't support server-side saved searches
            supports_offer_publishing=False,  # TIMOCOM load search is read-only
            rate_limit_per_minute=60,
            adr_search=True,
            trailer_type_search=True,
            supports_loading_type=True,
            supports_country_filter=True,
            supports_sort=True,
        )

    # ── Private helpers ─────────────────────────────────────────────────

    def _build_search_params(self, filters: LoadSearchFilters) -> dict:
        """Translate normalized filters into TIMOCOM query parameters."""
        params: dict = {}

        # Origin
        if filters.origin:
            params["loadingPlace"] = filters.origin.location
            if filters.origin.radius_km:
                params["loadingRadiusKm"] = int(filters.origin.radius_km)

        # Destination
        if filters.destination:
            params["unloadingPlace"] = filters.destination.location
            if filters.destination.radius_km:
                params["unloadingRadiusKm"] = int(filters.destination.radius_km)

        # Date ranges
        if filters.pickup_date_from:
            params["loadingDateFrom"] = (
                filters.pickup_date_from.isoformat()
                if hasattr(filters.pickup_date_from, "isoformat")
                else str(filters.pickup_date_from)
            )
        if filters.pickup_date_to:
            params["loadingDateTo"] = (
                filters.pickup_date_to.isoformat()
                if hasattr(filters.pickup_date_to, "isoformat")
                else str(filters.pickup_date_to)
            )

        # Trailer type
        if filters.trailer_type:
            params["vehicleType"] = ",".join(filters.trailer_type)

        # ADR
        if filters.adr_required is not None:
            params["adr"] = str(filters.adr_required).lower()

        # Weight
        if filters.weight_kg_min is not None:
            params["weightFromKg"] = int(filters.weight_kg_min)
        if filters.weight_kg_max is not None:
            params["weightToKg"] = int(filters.weight_kg_max)

        # Loading type
        if filters.loading_type is not None:
            params["loadingType"] = filters.loading_type.upper()  # FTL or LTL

        # Country filters
        if filters.loading_country is not None:
            params["loadingCountry"] = filters.loading_country.upper()
        if filters.delivery_country is not None:
            params["unloadingCountry"] = filters.delivery_country.upper()

        # Min trucks
        if filters.min_trucks is not None:
            params["minTrucks"] = filters.min_trucks

        # Sort (only if the provider supports it)
        if filters.sort_by and filters.sort_order:
            params["sortBy"] = filters.sort_by
            params["sortOrder"] = filters.sort_order.upper()

        # Extra filters pass-through
        if filters.extra_filters:
            params.update(filters.extra_filters)

        return params

    def _map_result(self, raw: dict) -> LoadSearchResult:
        """Map a raw TIMOCOM API response into a normalized ``LoadSearchResult``."""
        load_id = str(raw.get("id", raw.get("loadId", "")))

        # Parse pickup/delivery windows
        pickup_from = raw.get("loadingDateFrom") or raw.get("pickupDateFrom")
        pickup_to = raw.get("loadingDateTo") or raw.get("pickupDateTo")
        delivery_from = raw.get("unloadingDateFrom") or raw.get("deliveryDateFrom")
        delivery_to = raw.get("unloadingDateTo") or raw.get("deliveryDateTo")

        now = datetime.now(timezone.utc)
        pickup_window = (
            datetime.fromisoformat(pickup_from) if pickup_from else now,
            datetime.fromisoformat(pickup_to) if pickup_to else now,
        )
        delivery_window = (
            datetime.fromisoformat(delivery_from) if delivery_from else now,
            datetime.fromisoformat(delivery_to) if delivery_to else now,
        )

        # Price
        price_amount = float(raw.get("price", raw.get("freightPrice", 0)))
        price_currency = raw.get("currency", "EUR")

        # Distance
        distance = float(raw.get("distanceKm", raw.get("distance", 0)))

        # Trailer
        trailer = raw.get("vehicleType", raw.get("trailerType", "standard"))

        # ADR
        adr = raw.get("adr", False)
        if isinstance(adr, str):
            adr = adr.lower() in ("true", "yes", "1")

        return LoadSearchResult(
            result_id=load_id,
            provider_id=self.provider_id,
            provider_load_id=load_id,
            origin=raw.get("loadingPlace", raw.get("origin", "")),
            destination=raw.get("unloadingPlace", raw.get("destination", "")),
            pickup_window=pickup_window,
            delivery_window=delivery_window,
            price=Money(amount=price_amount, currency=price_currency),
            distance_km=distance,
            trailer_type=trailer,
            adr=bool(adr),
            loading_type=raw.get("loadingType", "").lower() or "",
            loading_country=raw.get("loadingCountry", "") or "",
            delivery_country=raw.get("unloadingCountry", "") or "",
            weight_kg=float(raw.get("weightKg", raw.get("weight", 0)) or 0),
            loading_date=raw.get("loadingDate") or raw.get("loadingDateFrom"),
            unloading_date=raw.get("unloadingDate") or raw.get("unloadingDateTo"),
            raw_payload=raw,
        )
