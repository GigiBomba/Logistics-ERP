"""Freight Exchange Search Engine — provider-agnostic, multi-provider search.

Searches across one, several, or all connected providers in parallel and
returns one normalized, merged result set.  A provider that is down or
lacks a required filter capability is skipped with a logged reason — never
silently, and never causing a total failure of the search.
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from models.freight_exchange_models import (
    LoadSearchFilters,
    LoadSearchResult,
    SavedSearch,
)
from repositories.freight_exchange_repository import FreightExchangeRepository
from services.freight_exchange.circuit_breaker import (
    CircuitBreakerOpenError,
    FreightCircuitBreaker,
)
from services.freight_exchange.connection_manager import ConnectionManagerService
from services.freight_exchange.rate_limiter import FreightRateLimiter, RateLimitExceededError
from services.freight_exchange.registry import get_adapter

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
FREIGHT_SEARCH_CACHE_TTL = 180  # 3 minutes — freight loads expire fast
FREIGHT_SEARCH_CACHE_PREFIX = "freight:search"


class ProviderSearchStatus:
    """Per-provider status returned alongside search results."""
    def __init__(self, provider_id: str, status: str, error: str = ""):
        self.provider_id = provider_id
        self.status = status  # "ok", "skipped_down", "skipped_no_capability", "error"
        self.error = error


class SearchResultSet:
    """Complete multi-provider search result, including per-provider status."""
    def __init__(self):
        self.results: list[LoadSearchResult] = []
        self.provider_statuses: list[ProviderSearchStatus] = []
        self.total_providers_queried: int = 0
        self.total_providers_skipped: int = 0


class SearchEngineService:
    """Provider-agnostic search across all connected freight exchanges.

    Usage::

        service = SearchEngineService(db, cache=redis_cache)
        results = await service.search_loads(
            company_id=1,
            filters=filters,
            provider_ids=None,  # search all connected
        )
    """

    def __init__(self, db, cache: Any = None, rate_limiter: Any = None):
        self._repo = FreightExchangeRepository(db)
        self._conn_mgr = ConnectionManagerService(db)
        self._cache = cache  # RedisCache or None (caching skipped if None)
        # Freight resilience guard rails (F5): per-(company, provider) Redis
        # token bucket + per-provider circuit breaker.  Both degrade to
        # "allow" when Redis is unavailable (see _guard_* helpers) so a down
        # Redis can never block legitimate searches.
        self._rate_limiter = rate_limiter if rate_limiter is not None else FreightRateLimiter()
        self._breakers: dict[str, FreightCircuitBreaker] = {}

    # ── Search ─────────────────────────────────────────────────────────

    async def search_loads(
        self,
        company_id: int,
        filters: LoadSearchFilters,
        provider_ids: Optional[list[str]] = None,
    ) -> SearchResultSet:
        """Search loads across specified providers (or all connected if None).

        Searches providers in parallel via ``asyncio.gather``.  Each provider
        is independently checked for health and capability compatibility
        before the search fires.  A down/incompatible provider is skipped
        with a logged reason — the caller gets partial results, not a crash.

        Caching: results are cached **per provider** (not as a merged set),
        keyed by ``{provider_id}:{sha256(filters)}``.  TTL = 3 minutes.
        """
        result_set = SearchResultSet()

        # Resolve which providers to query
        if provider_ids is None:
            provider_ids = self._conn_mgr.list_connected_provider_ids(company_id)

        if not provider_ids:
            logger.info("No connected providers for company %d", company_id)
            return result_set

        # Build per-provider search tasks
        tasks = []
        task_provider_map: dict[int, str] = {}

        task_idx = 0
        for i, pid in enumerate(provider_ids):
            # Check cache first (per provider)
            cached = self._get_cached(company_id, pid, filters)
            if cached is not None:
                logger.debug("Cache hit for provider '%s'", pid)
                result_set.results.extend(cached)
                result_set.provider_statuses.append(
                    ProviderSearchStatus(pid, "ok")
                )
                continue

            # Check health
            if not self._conn_mgr.is_connected(company_id, pid):
                logger.info("Provider '%s' is down — skipping", pid)
                result_set.provider_statuses.append(
                    ProviderSearchStatus(pid, "skipped_down", "Provider disconnected")
                )
                result_set.total_providers_skipped += 1
                continue

            # Check capabilities compatibility
            adapter = get_adapter(pid)
            if adapter is None:
                result_set.provider_statuses.append(
                    ProviderSearchStatus(pid, "skipped_no_capability", "Unknown provider")
                )
                result_set.total_providers_skipped += 1
                continue

            caps = adapter.capabilities()
            missing = self._missing_capabilities(filters, caps)
            if missing:
                logger.info(
                    "Provider '%s' lacks filters %s — skipping", pid, missing
                )
                result_set.provider_statuses.append(
                    ProviderSearchStatus(
                        pid, "skipped_no_capability",
                        f"Missing filters: {', '.join(missing)}",
                    )
                )
                result_set.total_providers_skipped += 1
                continue

            # Create search task
            tasks.append(self._search_one_provider(company_id, pid, filters))
            task_provider_map[task_idx] = pid
            task_idx += 1

        result_set.total_providers_queried = len(tasks)

        if not tasks:
            return result_set

        # Fire all searches in parallel
        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        for idx, outcome in enumerate(gathered):
            pid = task_provider_map.get(idx, f"unknown-{idx}")
            if isinstance(outcome, Exception):
                logger.error("Search failed for provider '%s': %s", pid, outcome)
                result_set.provider_statuses.append(
                    ProviderSearchStatus(pid, "error", str(outcome))
                )
            elif outcome is not None:
                result_set.results.extend(outcome)
                result_set.provider_statuses.append(
                    ProviderSearchStatus(pid, "ok")
                )
                # Cache the per-provider results
                self._set_cached(company_id, pid, filters, outcome)

        # Sort merged results if requested
        if filters.sort_by:
            reverse = filters.sort_order == "desc"
            key_map = {
                "price": lambda r: r.price.amount,
                "distance": lambda r: r.distance_km,
                "date": lambda r: r.pickup_window[0] if r.pickup_window else datetime.min.replace(tzinfo=timezone.utc),
            }
            sort_key = key_map.get(filters.sort_by)
            if sort_key:
                result_set.results.sort(key=sort_key, reverse=reverse)

        logger.info(
            "Search complete: %d results from %d providers (%d skipped)",
            len(result_set.results),
            result_set.total_providers_queried,
            result_set.total_providers_skipped,
        )
        return result_set

    async def get_load(
        self,
        company_id: int,
        provider_id: str,
        provider_load_id: str,
    ) -> Optional[LoadSearchResult]:
        """Fetch a single load by its provider-specific ID."""
        adapter = get_adapter(provider_id)
        if adapter is None:
            return None

        session = await self._conn_mgr.get_session(company_id, provider_id)
        if session is None:
            return None

        return await adapter.get_load(session, provider_load_id)

    # ── Saved Searches ─────────────────────────────────────────────────

    async def save_search(
        self,
        company_id: int,
        user_id: int,
        filters: LoadSearchFilters,
        label: str,
        provider_ids: Optional[list[str]] = None,
    ) -> SavedSearch:
        """Save a search for later recall."""
        import uuid
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        search_id = str(uuid.uuid4())

        data = {
            "company_id": company_id,
            "user_id": user_id,
            "label": label,
            "filters": json.dumps(filters.model_dump(mode="json")),
            "provider_ids": json.dumps(provider_ids) if provider_ids else None,
            "created_at": now.isoformat(),
        }
        # Use the repository (the id is generated by Python for SQLite,
        # or by the DB for PostgreSQL)
        data["id"] = search_id
        actual_id = self._repo.create_search(data)
        search_id = actual_id if actual_id else search_id

        return SavedSearch(
            saved_search_id=search_id,
            company_id=company_id,
            user_id=user_id,
            label=label,
            filters=filters,
            provider_ids=provider_ids,
            created_at=now,
            last_refreshed_at=None,
        )

    async def refresh_search(
        self,
        company_id: int,
        saved_search_id: str,
    ) -> SearchResultSet:
        """Re-run a saved search and update its last_refreshed_at."""
        row = self._repo.get_search(saved_search_id)
        if not row:
            raise ValueError(f"Saved search not found: {saved_search_id}")
        if row.get("company_id") != company_id:
            raise ValueError("Saved search does not belong to this company")

        # Deserialize filters
        filters_data = json.loads(row["filters"]) if isinstance(row["filters"], str) else row["filters"]
        filters = LoadSearchFilters(**filters_data)

        provider_ids = None
        if row.get("provider_ids"):
            pid_raw = row["provider_ids"]
            if isinstance(pid_raw, str):
                provider_ids = json.loads(pid_raw)
            elif isinstance(pid_raw, list):
                provider_ids = pid_raw

        # Run the search
        result_set = await self.search_loads(company_id, filters, provider_ids)

        # Update last_refreshed_at
        self._repo.update_search(
            saved_search_id,
            {"last_refreshed_at": datetime.now(timezone.utc).isoformat()},
        )

        return result_set

    async def get_recent_searches(
        self,
        company_id: int,
        user_id: int,
        limit: int = 20,
    ) -> list[SavedSearch]:
        """Return the user's most recent saved searches."""
        rows = self._repo.list_searches(company_id, user_id, limit)
        result = []
        for row in rows:
            filters_data = json.loads(row["filters"]) if isinstance(row["filters"], str) else row["filters"]
            provider_ids = None
            if row.get("provider_ids"):
                pid_raw = row["provider_ids"]
                if isinstance(pid_raw, str):
                    provider_ids = json.loads(pid_raw)
                elif isinstance(pid_raw, list):
                    provider_ids = pid_raw

            result.append(
                SavedSearch(
                    saved_search_id=row["id"],
                    company_id=row["company_id"],
                    user_id=row["user_id"],
                    label=row["label"],
                    filters=LoadSearchFilters(**filters_data),
                    provider_ids=provider_ids,
                    created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now(timezone.utc),
                    last_refreshed_at=datetime.fromisoformat(row["last_refreshed_at"]) if row.get("last_refreshed_at") else None,
                )
            )
        return result

    # ── Private helpers ──────────────────────────────────────────────────

    async def _search_one_provider(
        self,
        company_id: int,
        provider_id: str,
        filters: LoadSearchFilters,
    ) -> Optional[list[LoadSearchResult]]:
        """Search a single provider (called via asyncio.gather).

        Guarded by the freight rate limiter (per company/provider token
        bucket) and a per-provider circuit breaker.  Both primitives degrade
        to "allow" when Redis is unavailable (see ``_guard_*`` helpers) so a
        Redis outage can never block legitimate traffic; only an actually
        OPEN circuit or an exhausted token bucket skips a provider.
        """
        adapter = get_adapter(provider_id)
        if adapter is None:
            return None

        # Circuit breaker: skip the provider while its circuit is OPEN.
        if not await self._guard_allowed(company_id, provider_id):
            logger.warning(
                "Provider '%s' circuit is OPEN — skipping search (company %d)",
                provider_id, company_id,
            )
            raise CircuitBreakerOpenError(provider_id, company_id)

        session = await self._conn_mgr.get_session(company_id, provider_id)
        if session is None:
            logger.warning("No session for provider '%s'", provider_id)
            return None

        try:
            # Rate limit: acquire an API token before hitting the provider.
            if not await self._guard_rate_limit(company_id, provider_id):
                logger.warning(
                    "Rate limit exceeded for provider '%s' — skipping search (company %d)",
                    provider_id, company_id,
                )
                raise RateLimitExceededError(company_id, provider_id, "api")

            results = await adapter.search_loads(session, filters)
            self._record_breaker_success(company_id, provider_id)
            return results
        except RateLimitExceededError:
            # A rate-limit denial is a self-imposed guard rail, not a
            # provider failure — surface it but do not trip the breaker.
            raise
        except Exception as e:
            self._record_breaker_failure(company_id, provider_id)
            logger.error("Provider '%s' search error: %s", provider_id, e)
            raise  # re-raised, caught by asyncio.gather(return_exceptions=True)

    # ── Resilience guard helpers ──────────────────────────────────────────
    # All four helpers catch Redis/breaker/limiter errors and fall back to
    # permissive behavior so the search path never blocks on infrastructure.

    def _breaker_for(self, provider_id: str) -> FreightCircuitBreaker:
        """Return the per-provider circuit breaker (created on demand)."""
        cb = self._breakers.get(provider_id)
        if cb is None:
            cb = FreightCircuitBreaker()
            self._breakers[provider_id] = cb
        return cb

    async def _guard_allowed(self, company_id: int, provider_id: str) -> bool:
        """Circuit-breaker is_allowed() that bypasses when Redis is down."""
        try:
            return await self._breaker_for(provider_id).is_allowed(
                company_id, provider_id
            )
        except Exception as e:
            logger.warning(
                "Circuit breaker check bypassed for provider '%s': %s",
                provider_id, e,
            )
            return True

    async def _guard_rate_limit(self, company_id: int, provider_id: str) -> bool:
        """Rate-limiter acquire_api() that bypasses when Redis is down."""
        try:
            return await self._rate_limiter.acquire_api(company_id, provider_id)
        except Exception as e:
            logger.warning(
                "Rate limiter bypassed for provider '%s': %s", provider_id, e,
            )
            return True

    def _record_breaker_success(self, company_id: int, provider_id: str) -> None:
        try:
            self._breaker_for(provider_id).record_success(company_id, provider_id)
        except Exception as e:
            logger.debug(
                "Circuit breaker record_success skipped for '%s': %s",
                provider_id, e,
            )

    def _record_breaker_failure(self, company_id: int, provider_id: str) -> None:
        try:
            self._breaker_for(provider_id).record_failure(company_id, provider_id)
        except Exception as e:
            logger.debug(
                "Circuit breaker record_failure skipped for '%s': %s",
                provider_id, e,
            )

    def _get_cached(
        self,
        company_id: int,
        provider_id: str,
        filters: LoadSearchFilters,
    ) -> Optional[list[LoadSearchResult]]:
        """Try to get cached search results for a provider."""
        if self._cache is None:
            return None

        cache_key = self._build_cache_key(company_id, provider_id, filters)
        try:
            raw = self._cache.get(cache_key)
            if raw is None:
                return None
            return [LoadSearchResult(**item) for item in raw]
        except Exception:
            return None

    def _set_cached(
        self,
        company_id: int,
        provider_id: str,
        filters: LoadSearchFilters,
        results: list[LoadSearchResult],
    ) -> None:
        """Cache search results per provider."""
        if self._cache is None or not results:
            return

        cache_key = self._build_cache_key(company_id, provider_id, filters)
        try:
            serialized = [r.model_dump(mode="json") for r in results]
            self._cache.set(cache_key, serialized, FREIGHT_SEARCH_CACHE_TTL)
        except Exception as e:
            logger.debug("Failed to cache results for '%s': %s", provider_id, e)

    def _build_cache_key(
        self,
        company_id: int,
        provider_id: str,
        filters: LoadSearchFilters,
    ) -> str:
        """Build a deterministic cache key: freight:search:{cid}:{pid}:{sha256(filters)}"""
        filters_json = json.dumps(
            filters.model_dump(mode="json"), sort_keys=True
        )
        filters_hash = hashlib.sha256(filters_json.encode()).hexdigest()[:16]
        return f"{FREIGHT_SEARCH_CACHE_PREFIX}:{company_id}:{provider_id}:{filters_hash}"

    def _missing_capabilities(
        self, filters: LoadSearchFilters, caps
    ) -> list[str]:
        """Check which used filters aren't supported by the provider.

        Only checks filters that are explicitly set (non-None, non-default).
        """
        missing = []
        supported = set(caps.supported_filters) if caps else set()

        if filters.origin is not None and filters.origin.location and "origin" not in supported:
            missing.append("origin")
        if filters.destination is not None and filters.destination.location and "destination" not in supported:
            missing.append("destination")
        if filters.trailer_type and "trailer_type" not in supported:
            missing.append("trailer_type")
        if filters.adr_required is not None and "adr_required" not in supported:
            missing.append("adr_required")
        if filters.weight_kg_min is not None and "weight_kg_min" not in supported:
            missing.append("weight_kg_min")
        if filters.weight_kg_max is not None and "weight_kg_max" not in supported:
            missing.append("weight_kg_max")
        if filters.distance_km_max is not None and "distance_km_max" not in supported:
            missing.append("distance_km_max")
        if filters.price_min is not None and "price_min" not in supported:
            missing.append("price_min")
        if (filters.pickup_date_from or filters.pickup_date_to) and "pickup_date_from" not in supported:
            missing.append("pickup_date_from")
        if (filters.delivery_date_from or filters.delivery_date_to) and "delivery_date_from" not in supported:
            missing.append("delivery_date_from")
        if filters.loading_type is not None and "loading_type" not in supported:
            missing.append("loading_type")
        if filters.loading_country is not None and "loading_country" not in supported:
            missing.append("loading_country")
        if filters.delivery_country is not None and "delivery_country" not in supported:
            missing.append("delivery_country")

        return missing
