"""Trans.eu freight exchange adapter.

Implements FreightProviderAdapter for Trans.eu Platform API.
Maps Trans.eu's REST API into the normalized interface.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from models.freight_exchange_models import (
    ProviderCredentials,
    ProviderSession,
    ProviderHealthCheck,
    ProviderCapabilities,
    LoadSearchFilters,
    LoadSearchResult,
)
from models.common import Money
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.registry import register_freight_provider

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
TRANS_EU_API_BASE = "https://api.platform.trans.eu/ext"
TRANS_EU_TOKEN_ENDPOINT = "/auth-api/accounts/token"
TRANS_EU_FREIGHTS_ENDPOINT = "/freights-api/v1/freights"
TRANS_EU_FREIGHT_DETAIL_ENDPOINT = "/freights-api/v1/freights/{freight_id}"
DEFAULT_TIMEOUT = 30


@register_freight_provider
class TransEuAdapter(FreightProviderAdapter):
    """Trans.eu freight exchange adapter.

    Authenticates via OAuth 2.0 Authorization Code flow (per-user tokens).
    Searches freights from Trans.eu exchange, maps to normalized
    LoadSearchResult objects.
    """

    provider_id = "trans_eu"

    # ── Authentication ──────────────────────────────────────────────────

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        """Exchange OAuth authorization_code for access_token + refresh_token."""
        if creds.grant_type != "authorization_code":
            raise ValueError(
                f"Trans.eu requires authorization_code grant type, got {creds.grant_type}"
            )
        if not creds.authorization_code:
            raise ValueError("authorization_code is required for Trans.eu authentication")
        if not creds.api_key:
            raise ValueError("api_key is required for Trans.eu authentication")

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                f"{TRANS_EU_API_BASE}{TRANS_EU_TOKEN_ENDPOINT}",
                data={
                    "grant_type": "authorization_code",
                    "code": creds.authorization_code,
                    "redirect_uri": creds.redirect_uri or "",
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret_encrypted,
                },
                headers={
                    "Api-key": creds.api_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        now = datetime.now(timezone.utc)
        expires_in = data.get("expires_in", 21599)
        expires_at = datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc)

        return ProviderSession(
            company_id=creds.company_id,
            provider_id=self.provider_id,
            access_token_encrypted=data["access_token"],
            expires_at=expires_at,
            refresh_token_encrypted=data.get("refresh_token"),
        )

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        """Refresh access token using refresh_token.

        Trans.eu tokens expire in ~6 hours. If more than 5 minutes remain,
        skip refresh. If expired and no refresh_token available, raise.
        """
        now = datetime.now(timezone.utc)
        ttl = (session.expires_at - now).total_seconds()
        if ttl > 300:
            return session

        if not session.refresh_token_encrypted:
            raise RuntimeError(
                "Trans.eu session expired and no refresh token available — "
                "re-authentication required"
            )

        logger.info("Trans.eu token near expiry (%.0fs left), refreshing", ttl)
        raise RuntimeError(
            "TransEuAdapter.refresh_session() requires stored client credentials. "
            "Use ConnectionManagerService.get_trans_eu_token() for full refresh."
        )

    # ── Health Check ────────────────────────────────────────────────────

    async def test_connection(
        self, session: ProviderSession
    ) -> ProviderHealthCheck:
        """Test Trans.eu connectivity by calling the freights endpoint."""
        import time

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(
                    f"{TRANS_EU_API_BASE}{TRANS_EU_FREIGHTS_ENDPOINT}",
                    headers={
                        "Authorization": f"Bearer {session.access_token_encrypted}",
                        "Accept": "application/json",
                    },
                    params={"page": 1},
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
        """Search Trans.eu for freights matching normalized filters."""
        params = self._build_search_params(filters)

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{TRANS_EU_API_BASE}{TRANS_EU_FREIGHTS_ENDPOINT}",
                params=params,
                headers={
                    "Authorization": f"Bearer {session.access_token_encrypted}",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data if isinstance(data, list) else data.get("freights", data.get("items", []))
        return [self._map_freight_to_result(r) for r in results]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        """Fetch a single Trans.eu freight by its native ID."""
        url = f"{TRANS_EU_API_BASE}{TRANS_EU_FREIGHT_DETAIL_ENDPOINT.format(freight_id=load_id)}"

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {session.access_token_encrypted}",
                },
            )
            if resp.status_code == 404:
                logger.info("Trans.eu freight %s not found (404)", load_id)
                return None
            resp.raise_for_status()
            raw = resp.json()

        return self._map_freight_to_result(raw)

    # ── Capabilities ───────────────────────────────────────────────────

    def capabilities(self) -> ProviderCapabilities:
        """Return static metadata about Trans.eu API capabilities."""
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
            supports_saved_search=False,
            supports_offer_publishing=True,
            rate_limit_per_minute=900,
            adr_search=True,
            trailer_type_search=True,
            supports_loading_type=True,
            supports_country_filter=True,
            supports_sort=True,
            supports_freight_publication=True,
            supports_negotiation=True,
            supports_transport_orders=True,
            supports_monitoring=True,
            supports_webhooks=True,
            supports_oauth_user=True,
            requires_api_key_header=True,
        )

    # ── Private: Filter mapping ────────────────────────────────────────

    def _build_search_params(self, filters: LoadSearchFilters) -> dict:
        """Translate normalized LoadSearchFilters → Trans.eu query params."""
        params: dict = {"page": 1}

        if filters.origin and filters.origin.location:
            params["loadingPlace"] = filters.origin.location
            if filters.origin.radius_km:
                params["loadingRadiusKm"] = int(filters.origin.radius_km)

        if filters.destination and filters.destination.location:
            params["unloadingPlace"] = filters.destination.location
            if filters.destination.radius_km:
                params["unloadingRadiusKm"] = int(filters.destination.radius_km)

        if filters.pickup_date_from:
            val = filters.pickup_date_from
            params["loadingDateFrom"] = val.isoformat() if hasattr(val, "isoformat") else str(val)
        if filters.pickup_date_to:
            val = filters.pickup_date_to
            params["loadingDateTo"] = val.isoformat() if hasattr(val, "isoformat") else str(val)
        if filters.delivery_date_from:
            val = filters.delivery_date_from
            params["unloadingDateFrom"] = val.isoformat() if hasattr(val, "isoformat") else str(val)
        if filters.delivery_date_to:
            val = filters.delivery_date_to
            params["unloadingDateTo"] = val.isoformat() if hasattr(val, "isoformat") else str(val)

        if filters.trailer_type:
            params["truck_body_type"] = ",".join(filters.trailer_type)

        if filters.adr_required is not None:
            params["adr"] = str(filters.adr_required).lower()

        if filters.weight_kg_min is not None:
            params["weight_min"] = int(filters.weight_kg_min)
        if filters.weight_kg_max is not None:
            params["weight_max"] = int(filters.weight_kg_max)

        if filters.loading_country:
            params["loading_country"] = filters.loading_country.lower()
        if filters.delivery_country:
            params["delivery_country"] = filters.delivery_country.lower()

        if filters.sort_by and filters.sort_order:
            params["sortBy"] = filters.sort_by
            params["order"] = filters.sort_order
        elif filters.sort_by:
            params["sortBy"] = filters.sort_by

        if filters.extra_filters:
            params.update(filters.extra_filters)

        return params

    # ── Private: Result mapping ────────────────────────────────────────

    def _map_freight_to_result(self, raw: dict) -> LoadSearchResult:
        """Map a Trans.eu freight object → normalized LoadSearchResult.

        Trans.eu freight schema:
          - loading: {place: {country, locality, postal_code}, timespans: {begin, end}}
          - unloading: {place: {...}, timespans: {...}}
          - publication: {price: {currency, value}, ...}
          - requirements: {required_truck_bodies: [...], required_adr_classes: [...]}
          - loads: [{weight, height, length, ...}]
          - ftl: bool, transit_time: int (minutes)
        """
        freight_id = str(raw.get("id", ""))

        loading = raw.get("loading") or {}
        unloading = raw.get("unloading") or {}

        # Origin
        origin_place = loading.get("place") or {}
        origin = origin_place.get("locality", "") or ""
        loading_country = origin_place.get("country", "")
        if loading_country:
            origin = f"{origin}, {loading_country.upper()}"

        # Destination
        dest_place = unloading.get("place") or {}
        destination = dest_place.get("locality", "") or ""
        delivery_country = dest_place.get("country", "")
        if delivery_country:
            destination = f"{destination}, {delivery_country.upper()}"

        # Dates
        loading_times = loading.get("timespans", {})
        unloading_times = unloading.get("timespans", {})
        now = datetime.now(timezone.utc)

        pickup_from_str = loading_times.get("begin")
        pickup_to_str = loading_times.get("end")
        delivery_from_str = unloading_times.get("begin")
        delivery_to_str = unloading_times.get("end")

        pickup_from = datetime.fromisoformat(pickup_from_str) if pickup_from_str else now
        pickup_to = datetime.fromisoformat(pickup_to_str) if pickup_to_str else now + timedelta(hours=4)
        delivery_from = datetime.fromisoformat(delivery_from_str) if delivery_from_str else now + timedelta(hours=24)
        delivery_to = datetime.fromisoformat(delivery_to_str) if delivery_to_str else now + timedelta(hours=28)

        # Price from publication
        publication = raw.get("publication", {})
        price_data = publication.get("price", {})
        price_amount = float(price_data.get("value", 0))
        price_currency = price_data.get("currency", "EUR").upper()

        # Distance estimate from transit_time (minutes → km at ~70 km/h)
        transit_time = raw.get("transit_time", 0)
        distance = (transit_time / 60.0) * 70.0 if transit_time > 0 else 0.0

        # Trailer type from requirements
        requirements = raw.get("requirements", {})
        truck_bodies = requirements.get("required_truck_bodies", [])
        trailer_type = truck_bodies[0] if truck_bodies else "standard"
        if trailer_type == "standard" and raw.get("truck_bodies"):
            bt = raw["truck_bodies"]
            if isinstance(bt, list) and bt:
                trailer_type = bt[0]

        # ADR
        adr_classes = requirements.get("required_adr_classes", [])
        adr = len(adr_classes) > 0 if adr_classes else False

        # Weight: sum of loads
        loads = raw.get("loads", [])
        weight_kg = sum(float(ld.get("weight", 0) or 0) for ld in loads)

        # Loading type
        is_ftl = raw.get("ftl", requirements.get("is_ftl", None))
        if is_ftl is True:
            loading_type = "ftl"
        elif is_ftl is False:
            loading_type = "ltl"
        else:
            loading_type = raw.get("transport_type", "") or ""

        return LoadSearchResult(
            result_id=freight_id,
            provider_id=self.provider_id,
            provider_load_id=freight_id,
            origin=origin,
            destination=destination,
            pickup_window=(pickup_from, pickup_to),
            delivery_window=(delivery_from, delivery_to),
            price=Money(amount=price_amount, currency=price_currency),
            distance_km=distance or 0.0,
            trailer_type=trailer_type,
            adr=adr,
            loading_type=loading_type,
            loading_country=loading_country,
            delivery_country=delivery_country,
            weight_kg=weight_kg,
            loading_date=pickup_from_str,
            unloading_date=delivery_from_str,
            raw_payload=raw,
        )
