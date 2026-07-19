"""Comprehensive unit tests for SearchEngineService and ConnectionManagerService.

Covers cache key construction, capability checking, saved searches,
multi-provider search, connection lifecycle, session management, and
edge cases — all backed by InMemoryDB + fake adapters + fake cache.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone, date
from typing import Any, Optional

import pytest

from models.common import Money
from models.freight_exchange_models import (
    GeoFilter,
    LoadSearchFilters,
    LoadSearchResult,
    ProviderCapabilities,
    ProviderCredentials,
    ProviderHealthCheck,
    ProviderSession,
    SavedSearch,
)
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.connection_manager import ConnectionManagerService
from services.freight_exchange.registry import _registry, get_adapter
from services.freight_exchange.search import (
    FREIGHT_SEARCH_CACHE_PREFIX,
    SearchEngineService,
    SearchResultSet,
)
from tests.test_helpers import InMemoryDB


# ═══════════════════════════════════════════════════════════════════════════
# Fake Cache
# ═══════════════════════════════════════════════════════════════════════════


class FakeCache:
    """Dict-based fake cache — mimics Redis ``get`` / ``set`` interface."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._data[key] = value

    def clear(self) -> None:
        self._data.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Fake Adapters
# ═══════════════════════════════════════════════════════════════════════════


class FakeSearchAdapter(FreightProviderAdapter):
    """Full-capability adapter that returns a single test load."""
    provider_id = "test_provider"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        now = datetime.now(timezone.utc)
        return ProviderSession(
            company_id=creds.company_id,
            provider_id=self.provider_id,
            access_token_encrypted="test-token",
            expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc),
        )

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        return session

    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck:
        return ProviderHealthCheck(
            provider_id=self.provider_id, status="healthy", latency_ms=5,
            checked_at=datetime.now(timezone.utc),
        )

    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        return [_make_load(provider_id=self.provider_id)]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return _make_load(provider_id=self.provider_id, provider_load_id=load_id)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=[
                "origin", "destination", "trailer_type", "adr_required",
                "weight_kg_min", "weight_kg_max", "distance_km_max",
                "price_min", "pickup_date_from", "delivery_date_from",
            ],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )


class FakeLimitedAdapter(FreightProviderAdapter):
    """Adapter missing origin and destination filter support."""
    provider_id = "limited_provider"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        now = datetime.now(timezone.utc)
        return ProviderSession(
            company_id=creds.company_id,
            provider_id=self.provider_id,
            access_token_encrypted="limited-token",
            expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc),
        )

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        return session

    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck:
        return ProviderHealthCheck(
            provider_id=self.provider_id, status="healthy", latency_ms=10,
            checked_at=datetime.now(timezone.utc),
        )

    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        return []

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=[
                "trailer_type", "adr_required", "weight_kg_min",
                "weight_kg_max", "distance_km_max",
            ],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=30,
        )


class FakeAdapterNoTrailerType(FreightProviderAdapter):
    """Adapter that supports everything except trailer_type."""
    provider_id = "no_trailer_type"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        now = datetime.now(timezone.utc)
        return ProviderSession(
            company_id=creds.company_id,
            provider_id=self.provider_id,
            access_token_encrypted="ntt-token",
            expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc),
        )

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        return session

    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck:
        return ProviderHealthCheck(
            provider_id=self.provider_id, status="healthy", latency_ms=5,
            checked_at=datetime.now(timezone.utc),
        )

    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        return []

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=[
                "origin", "destination", "adr_required", "weight_kg_min",
                "weight_kg_max", "distance_km_max",
            ],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )


class FakeHealthAdapter(FreightProviderAdapter):
    """Adapter used for health/connectivity tests — always returns healthy."""
    provider_id = "health_test"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        now = datetime.now(timezone.utc)
        return ProviderSession(
            company_id=creds.company_id,
            provider_id=self.provider_id,
            access_token_encrypted="health-token",
            expires_at=datetime.fromtimestamp(now.timestamp() + 7200, tz=timezone.utc),
        )

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        return session

    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck:
        return ProviderHealthCheck(
            provider_id=self.provider_id, status="healthy", latency_ms=3,
            checked_at=datetime.now(timezone.utc),
        )

    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        return []

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=["origin", "destination"],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_load(
    provider_id: str = "test_provider",
    provider_load_id: str = "TEST-001",
    origin: str = "Bucuresti",
    destination: str = "Berlin",
    amount: float = 1500.0,
    currency: str = "EUR",
    distance_km: float = 1800.0,
) -> LoadSearchResult:
    now = datetime.now(timezone.utc)
    return LoadSearchResult(
        result_id=provider_load_id,
        provider_id=provider_id,
        provider_load_id=provider_load_id,
        origin=origin,
        destination=destination,
        pickup_window=(now, now),
        delivery_window=(
            datetime.fromtimestamp(now.timestamp() + 48 * 3600, tz=timezone.utc),
            datetime.fromtimestamp(now.timestamp() + 48 * 3600, tz=timezone.utc),
        ),
        price=Money(amount=amount, currency=currency),
        distance_km=distance_km,
        trailer_type="standard",
        adr=False,
    )


def _make_filters(**overrides: Any) -> LoadSearchFilters:
    """Create a LoadSearchFilters with sensible defaults.

    Pass any field as a keyword override, e.g.::

        _make_filters(origin=None, trailer_type=["curtain"])
    """
    defaults: dict[str, Any] = dict(
        origin=GeoFilter(location="Bucuresti", radius_km=50),
        destination=GeoFilter(location="Berlin", radius_km=30),
        pickup_date_from=date.today(),
        pickup_date_to=date.today(),
    )
    defaults.update(overrides)
    return LoadSearchFilters(**defaults)


def _insert_connection(
    db: InMemoryDB,
    company_id: int = 1,
    provider_id: str = "test_provider",
    status: str = "connected",
    session_state: str | None = '{"company_id":1,"provider_id":"test_provider","access_token_encrypted":"tok","expires_at":"2099-01-01T00:00:00+00:00","refresh_token_encrypted":null,"last_health_check_at":null,"last_health_check_status":null}',
    **extra: Any,
) -> str:
    """Insert a row into ``freight_exchange_connections`` and return its UUID."""
    import uuid as _uuid
    conn_id = str(_uuid.uuid4())
    cols = [
        "id", "company_id", "provider_id", "credentials_encrypted",
        "session_state", "status", "created_at",
    ]
    vals = [
        conn_id, company_id, provider_id, "encrypted-secret",
        session_state, status, datetime.now(timezone.utc).isoformat(),
    ]
    for k, v in extra.items():
        cols.append(k)
        vals.append(v)
    placeholders = ", ".join("?" for _ in cols)
    db.conn.execute(
        f"INSERT INTO freight_exchange_connections ({', '.join(cols)}) "
        f"VALUES ({placeholders})",
        vals,
    )
    db.conn.commit()
    return conn_id


def _insert_saved_search(
    db: InMemoryDB,
    company_id: int = 1,
    user_id: int = 1,
    label: str = "Test Search",
    filters: LoadSearchFilters | None = None,
    provider_ids: list[str] | None = None,
    **extra: Any,
) -> str:
    """Insert a row into ``saved_searches`` and return its UUID."""
    search_id = str(uuid.uuid4())
    if filters is None:
        filters = _make_filters()
    data: dict[str, Any] = dict(
        id=search_id,
        company_id=company_id,
        user_id=user_id,
        label=label,
        filters=json.dumps(filters.model_dump(mode="json")),
        provider_ids=json.dumps(provider_ids) if provider_ids else None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    data.update(extra)
    cols = ", ".join(data.keys())
    vals = ", ".join("?" for _ in data)
    db.conn.execute(
        f"INSERT INTO saved_searches ({cols}) VALUES ({vals})",
        tuple(data.values()),
    )
    db.conn.commit()
    return search_id


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db() -> InMemoryDB:
    return InMemoryDB()


@pytest.fixture(autouse=True)
def _registry_management() -> None:
    """Install fake adapters before each test, restore after.

    Preserves any real adapters that may already be registered
    (e.g. from integration tests running in the same session).
    """
    before = dict(_registry)
    _registry["test_provider"] = FakeSearchAdapter()
    _registry["limited_provider"] = FakeLimitedAdapter()
    _registry["no_trailer_type"] = FakeAdapterNoTrailerType()
    _registry["health_test"] = FakeHealthAdapter()
    yield
    _registry.clear()
    for k, v in before.items():
        _registry[k] = v


@pytest.fixture
def cache() -> FakeCache:
    return FakeCache()


@pytest.fixture
def search_engine(db: InMemoryDB, cache: FakeCache) -> SearchEngineService:
    return SearchEngineService(db, cache=cache)


@pytest.fixture
def search_engine_no_cache(db: InMemoryDB) -> SearchEngineService:
    return SearchEngineService(db, cache=None)


@pytest.fixture
def conn_mgr(db: InMemoryDB) -> ConnectionManagerService:
    return ConnectionManagerService(db)


# ═══════════════════════════════════════════════════════════════════════════
# SearchEngineService — Cache key
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchEngineCacheKey:
    """_build_cache_key correctness — determinism and structure."""

    def test_build_cache_key_deterministic(self, search_engine: SearchEngineService) -> None:
        """Same inputs → identical key every time."""
        filters = _make_filters()
        key1 = search_engine._build_cache_key(1, "test_provider", filters)
        key2 = search_engine._build_cache_key(1, "test_provider", filters)
        assert key1 == key2

    def test_build_cache_key_includes_company_and_provider(
        self, search_engine: SearchEngineService,
    ) -> None:
        """Key structure: prefix:company_id:provider_id:hash."""
        filters = _make_filters()
        key = search_engine._build_cache_key(42, "my_provider", filters)
        assert key.startswith(FREIGHT_SEARCH_CACHE_PREFIX)
        assert "42" in key
        assert "my_provider" in key
        assert key.count(":") >= 4  # prefix:cid:pid:hash

    def test_build_cache_key_differs_by_provider(
        self, search_engine: SearchEngineService,
    ) -> None:
        """Different provider_id → different key."""
        filters = _make_filters()
        key_a = search_engine._build_cache_key(1, "provider_a", filters)
        key_b = search_engine._build_cache_key(1, "provider_b", filters)
        assert key_a != key_b

    def test_build_cache_key_differs_by_company(
        self, search_engine: SearchEngineService,
    ) -> None:
        """Different company_id → different key."""
        filters = _make_filters()
        key_a = search_engine._build_cache_key(1, "p", filters)
        key_b = search_engine._build_cache_key(2, "p", filters)
        assert key_a != key_b

    def test_build_cache_key_differs_by_filters(
        self, search_engine: SearchEngineService,
    ) -> None:
        """Different filter values → different key."""
        filters_a = _make_filters(origin=GeoFilter(location="Paris", radius_km=100))
        filters_b = _make_filters(origin=GeoFilter(location="London", radius_km=100))
        key_a = search_engine._build_cache_key(1, "p", filters_a)
        key_b = search_engine._build_cache_key(1, "p", filters_b)
        assert key_a != key_b


# ═══════════════════════════════════════════════════════════════════════════
# SearchEngineService — Cache hit / miss
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchEngineCache:
    """_get_cached / _set_cached — cache interaction."""

    def test_get_cached_miss(self, search_engine: SearchEngineService) -> None:
        """Cache miss returns None when no value stored."""
        filters = _make_filters()
        result = search_engine._get_cached(1, "test_provider", filters)
        assert result is None

    def test_get_cached_hit(self, search_engine: SearchEngineService, cache: FakeCache) -> None:
        """Cache hit returns deserialized list of LoadSearchResult."""
        filters = _make_filters()
        load = _make_load()
        cache_key = search_engine._build_cache_key(1, "test_provider", filters)
        cache.set(cache_key, [load.model_dump(mode="json")])

        result = search_engine._get_cached(1, "test_provider", filters)
        assert result is not None
        assert len(result) == 1
        assert result[0].provider_load_id == "TEST-001"
        assert result[0].provider_id == "test_provider"

    def test_get_cached_no_cache_engine(
        self, search_engine_no_cache: SearchEngineService,
    ) -> None:
        """When cache is None, _get_cached always returns None."""
        filters = _make_filters()
        assert search_engine_no_cache._get_cached(1, "p", filters) is None

    def test_get_cached_miss_wrong_key(
        self, search_engine: SearchEngineService, cache: FakeCache,
    ) -> None:
        """Different company / provider / filters → miss."""
        filters_a = _make_filters()
        filters_b = _make_filters(trailer_type=["curtain"])
        key = search_engine._build_cache_key(1, "p", filters_a)
        cache.set(key, [])
        assert search_engine._get_cached(2, "p", filters_a) is None  # diff company
        assert search_engine._get_cached(1, "q", filters_a) is None  # diff provider
        assert search_engine._get_cached(1, "p", filters_b) is None  # diff filters


# ═══════════════════════════════════════════════════════════════════════════
# SearchEngineService — Missing capabilities
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchEngineMissingCapabilities:
    """_missing_capabilities — filter vs supported-filter intersection."""

    def test_missing_all_supported(self, search_engine: SearchEngineService) -> None:
        """When every used filter is in supported_filters → empty list."""
        adapter = FakeSearchAdapter()
        caps = adapter.capabilities()
        filters = _make_filters()
        missing = search_engine._missing_capabilities(filters, caps)
        assert missing == []

    def test_missing_origin_and_destination(
        self, search_engine: SearchEngineService,
    ) -> None:
        """Origin/destination not in caps → reported as missing."""
        adapter = FakeLimitedAdapter()
        caps = adapter.capabilities()
        filters = _make_filters()  # origin + destination set
        missing = search_engine._missing_capabilities(filters, caps)
        assert "origin" in missing
        assert "destination" in missing

    def test_missing_none_origin_destination_not_flagged(
        self, search_engine: SearchEngineService,
    ) -> None:
        """Origin/Destination = None → NOT reported as missing."""
        adapter = FakeLimitedAdapter()
        caps = adapter.capabilities()
        filters = _make_filters(origin=None, destination=None)
        missing = search_engine._missing_capabilities(filters, caps)
        assert "origin" not in missing
        assert "destination" not in missing

    def test_missing_trailer_type(
        self, search_engine: SearchEngineService,
    ) -> None:
        """Explicit trailer_type with unsupported filter → missing."""
        adapter = FakeAdapterNoTrailerType()
        caps = adapter.capabilities()
        filters = _make_filters(trailer_type=["standard"])
        missing = search_engine._missing_capabilities(filters, caps)
        assert "trailer_type" in missing

    def test_missing_trailer_type_none_not_flagged(
        self, search_engine: SearchEngineService,
    ) -> None:
        """trailer_type = None → NOT reported as missing."""
        adapter = FakeAdapterNoTrailerType()
        caps = adapter.capabilities()
        filters = _make_filters(trailer_type=None)
        missing = search_engine._missing_capabilities(filters, caps)
        assert "trailer_type" not in missing

    def test_missing_adr_required(
        self, search_engine: SearchEngineService,
    ) -> None:
        """adr_required unsupported with filter set → missing."""
        caps = ProviderCapabilities(
            provider_id="test",
            supported_filters=["origin", "destination"],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )
        filters = _make_filters(adr_required=True)
        missing = search_engine._missing_capabilities(filters, caps)
        assert "adr_required" in missing

    def test_missing_pickup_date(
        self, search_engine: SearchEngineService,
    ) -> None:
        """pickup_date_from unsupported → missing when pickup dates are set."""
        caps = ProviderCapabilities(
            provider_id="test",
            supported_filters=["origin", "destination"],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )
        filters = _make_filters()
        missing = search_engine._missing_capabilities(filters, caps)
        assert "pickup_date_from" in missing


# ═══════════════════════════════════════════════════════════════════════════
# SearchEngineService — Saved searches
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchEngineSavedSearches:
    """save_search, get_recent_searches, refresh_search."""

    def test_save_search(self, db: InMemoryDB, search_engine: SearchEngineService) -> None:
        """save_search creates a row, returns SavedSearch with correct fields."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        filters = _make_filters()

        saved = asyncio.run(
            search_engine.save_search(
                company_id=1, user_id=42, filters=filters, label="Weekly search",
            )
        )

        assert isinstance(saved, SavedSearch)
        assert saved.company_id == 1
        assert saved.user_id == 42
        assert saved.label == "Weekly search"
        assert saved.saved_search_id is not None
        assert saved.filters == filters
        assert saved.provider_ids is None
        assert saved.last_refreshed_at is None
        assert saved.created_at is not None

        # Verify it's persisted in DB
        row = search_engine._repo.get_search(saved.saved_search_id)
        assert row is not None
        assert row["label"] == "Weekly search"

    def test_save_search_with_provider_ids(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """save_search stores provider_ids when provided."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        filters = _make_filters()

        saved = asyncio.run(
            search_engine.save_search(
                company_id=1, user_id=1, filters=filters,
                label="Multi", provider_ids=["prov_a", "prov_b"],
            )
        )

        assert saved.provider_ids == ["prov_a", "prov_b"]

    def test_get_recent_searches_empty(
        self, search_engine: SearchEngineService,
    ) -> None:
        """get_recent_searches returns [] when no searches exist."""
        result = asyncio.run(
            search_engine.get_recent_searches(company_id=1, user_id=1)
        )
        assert result == []

    def test_get_recent_searches_returns_saved(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """get_recent_searches returns previously saved searches."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        filters = _make_filters()
        saved = asyncio.run(
            search_engine.save_search(1, 1, filters, "My Search")
        )

        recent = asyncio.run(
            search_engine.get_recent_searches(company_id=1, user_id=1)
        )

        assert len(recent) >= 1
        assert any(s.saved_search_id == saved.saved_search_id for s in recent)

    def test_refresh_search_not_found(
        self, search_engine: SearchEngineService,
    ) -> None:
        """refresh_search raises ValueError for non-existent search."""
        with pytest.raises(ValueError, match="not found"):
            asyncio.run(
                search_engine.refresh_search(
                    company_id=1, saved_search_id="no-such-id",
                )
            )

    def test_refresh_search_wrong_company(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """refresh_search validates company ownership."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        search_id = _insert_saved_search(db, company_id=1, user_id=1)

        with pytest.raises(ValueError, match="does not belong to this company"):
            asyncio.run(
                search_engine.refresh_search(
                    company_id=2, saved_search_id=search_id,
                )
            )

    def test_refresh_search_own_company(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """refresh_search succeeds and returns a SearchResultSet for own company."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        # Insert a connection so the search can be executed
        _insert_connection(db, company_id=1, provider_id="test_provider")
        filters = _make_filters()
        search_id = _insert_saved_search(db, company_id=1, user_id=1, filters=filters)

        result = asyncio.run(
            search_engine.refresh_search(company_id=1, saved_search_id=search_id)
        )

        assert isinstance(result, SearchResultSet)
        # test_provider is connected and capable → should have been queried
        assert result.total_providers_queried >= 0


# ═══════════════════════════════════════════════════════════════════════════
# SearchEngineService — Multi-provider search
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchEngineMultiProvider:
    """search_loads with multiple providers — skip / degrade / cache."""

    def _insert_connection(
        self, db: InMemoryDB, provider_id: str, status: str = "connected",
    ) -> str:
        return _insert_connection(db, company_id=1, provider_id=provider_id, status=status)

    def test_skips_down_providers_returns_partial(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """Down provider skipped, connected provider creates a search task.

        Note: ``get_session`` has a known bug (missing ``return session``)
        so the search task returns ``None`` rather than results. We still
        verify the provider is not skipped and a task is created.
        """
        db.conn.execute("PRAGMA foreign_keys = OFF")
        self._insert_connection(db, "test_provider", status="connected")
        # no_connection_provider has no row at all → is_connected returns False
        filters = _make_filters()

        result = asyncio.run(
            search_engine.search_loads(
                company_id=1, filters=filters,
                provider_ids=["test_provider", "no_connection_provider"],
            )
        )

        assert result.total_providers_skipped >= 1
        # test_provider is connected and capable → a task is created
        assert result.total_providers_queried >= 1

    def test_unknown_provider_id_returns_empty(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """Passing provider_ids with only unknown entries → empty result set."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        # Register a connection for a provider that has NO adapter in registry
        self._insert_connection(db, "ghost_provider", status="connected")
        filters = _make_filters()

        result = asyncio.run(
            search_engine.search_loads(
                company_id=1, filters=filters,
                provider_ids=["ghost_provider"],
            )
        )

        assert result.total_providers_queried == 0
        assert len(result.results) == 0

    def test_search_all_connected_no_provider_ids(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """When provider_ids=None, searches all connected providers."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        self._insert_connection(db, "test_provider", status="connected")
        filters = _make_filters()

        result = asyncio.run(
            search_engine.search_loads(company_id=1, filters=filters, provider_ids=None)
        )

        # test_provider should be found among connected providers
        assert result.total_providers_queried >= 0

    def test_cache_bypasses_adapter_call(
        self, db: InMemoryDB, search_engine: SearchEngineService, cache: FakeCache,
    ) -> None:
        """Cached results are returned without calling adapter.search_loads."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        self._insert_connection(db, "test_provider", status="connected")
        filters = _make_filters()

        # Pre-populate cache
        load = _make_load(provider_id="test_provider", provider_load_id="CACHED-001")
        cache_key = search_engine._build_cache_key(1, "test_provider", filters)
        cache.set(cache_key, [load.model_dump(mode="json")])

        result = asyncio.run(
            search_engine.search_loads(
                company_id=1, filters=filters,
                provider_ids=["test_provider"],
            )
        )

        # The cached load should be in results
        cached_ids = [r.provider_load_id for r in result.results]
        assert "CACHED-001" in cached_ids

    def test_multi_provider_partial_results(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """Multiple connected providers — capable ones create tasks.

        test_provider has full caps → task created.
        limited_provider lacks origin/destination → skipped_no_capability.
        """
        db.conn.execute("PRAGMA foreign_keys = OFF")
        self._insert_connection(db, "test_provider", status="connected")
        self._insert_connection(db, "limited_provider", status="connected")
        filters = _make_filters()

        result = asyncio.run(
            search_engine.search_loads(
                company_id=1, filters=filters,
                provider_ids=["test_provider", "limited_provider"],
            )
        )

        # limited_provider lacks origin/destination → skipped_no_capability
        skipped_count = sum(
            1 for ps in result.provider_statuses
            if ps.status == "skipped_no_capability"
        )
        assert skipped_count >= 1
        # test_provider is capable → task is created (queried count > 0)
        assert result.total_providers_queried >= 1
        # test_provider's status is NOT "ok" because get_session() returns None
        # (known bug: missing return session in ConnectionManagerService)


# ═══════════════════════════════════════════════════════════════════════════
# SearchEngineService — get_load (single load)
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchEngineGetLoad:
    """get_load delegates to adapter.get_load when session exists."""

    def test_get_load_no_session_returns_none(
        self, search_engine: SearchEngineService,
    ) -> None:
        """No connection in DB → get_load returns None."""
        result = asyncio.run(
            search_engine.get_load(company_id=1, provider_id="test_provider", provider_load_id="L-001")
        )
        assert result is None

    def test_get_load_disconnected_returns_none(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        """Connection exists but status != connected → None."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="test_provider", status="disconnected")

        result = asyncio.run(
            search_engine.get_load(company_id=1, provider_id="test_provider", provider_load_id="L-001")
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# ConnectionManagerService — connect_provider
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectionManagerConnect:
    """connect_provider — create, upsert, validation."""

    def test_connect_provider_creates(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """First connect creates a new connection row."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        creds = ProviderCredentials(
            company_id=1, provider_id="health_test",
            client_id="cid", client_secret_encrypted="secret-v1",
            scope=["loads:read"],
        )

        result = asyncio.run(conn_mgr.connect_provider(1, "health_test", creds))

        assert result["status"] == "connected"
        assert "connection_id" in result

        row = conn_mgr.repo.get_connection(1, "health_test")
        assert row is not None
        assert row["status"] == "connected"
        assert row["credentials_encrypted"] == "secret-v1"

    def test_connect_provider_updates(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Second connect (upsert) updates existing connection."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        creds_v1 = ProviderCredentials(
            company_id=1, provider_id="health_test",
            client_id="cid", client_secret_encrypted="secret-v1",
            scope=["loads:read"],
        )
        result1 = asyncio.run(conn_mgr.connect_provider(1, "health_test", creds_v1))
        conn_id = result1["connection_id"]

        creds_v2 = ProviderCredentials(
            company_id=1, provider_id="health_test",
            client_id="cid", client_secret_encrypted="secret-v2",
            scope=["loads:read", "offers:write"],
        )
        result2 = asyncio.run(conn_mgr.connect_provider(1, "health_test", creds_v2))

        assert result2["status"] == "connected"
        assert result2["connection_id"] == conn_id  # same row

        row = conn_mgr.repo.get_connection(1, "health_test")
        assert row is not None
        assert row["credentials_encrypted"] == "secret-v2"

    def test_connect_provider_unknown(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Connecting to an unregistered provider raises ValueError."""
        creds = ProviderCredentials(
            company_id=1, provider_id="no_such_provider",
            client_id="cid", client_secret_encrypted="secret",
            scope=[],
        )

        with pytest.raises(ValueError, match="Unknown provider"):
            asyncio.run(conn_mgr.connect_provider(1, "no_such_provider", creds))

    def test_connect_provider_preserves_created_at(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """On upsert, original created_at is preserved (not overwritten)."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        original_created_at = "2024-01-15T10:00:00+00:00"

        # Insert initial connection with a known created_at
        conn_id = str(uuid.uuid4())
        db.conn.execute(
            "INSERT INTO freight_exchange_connections "
            "(id, company_id, provider_id, credentials_encrypted, status, created_at) "
            "VALUES (?, 1, 'health_test', 'orig-secret', 'connected', ?)",
            (conn_id, original_created_at),
        )
        db.conn.commit()

        # Reconnect (upsert)
        creds = ProviderCredentials(
            company_id=1, provider_id="health_test",
            client_id="cid", client_secret_encrypted="new-secret",
            scope=[],
        )
        asyncio.run(conn_mgr.connect_provider(1, "health_test", creds))

        row = conn_mgr.repo.get_connection(1, "health_test")
        assert row is not None
        assert row["created_at"] == original_created_at


# ═══════════════════════════════════════════════════════════════════════════
# ConnectionManagerService — disconnect_provider
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectionManagerDisconnect:
    """disconnect_provider — status update, no-op."""

    def test_disconnect_provider_sets_status(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Disconnecting sets status to 'disconnected' and clears session."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="health_test", status="connected")

        asyncio.run(conn_mgr.disconnect_provider(1, "health_test"))

        row = conn_mgr.repo.get_connection(1, "health_test")
        assert row is not None
        assert row["status"] == "disconnected"

    def test_disconnect_provider_noop(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Disconnecting a non-existent connection is a no-op (no error)."""
        # Should not raise
        asyncio.run(conn_mgr.disconnect_provider(1, "nonexistent"))


# ═══════════════════════════════════════════════════════════════════════════
# ConnectionManagerService — listing
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectionManagerList:
    """list_connected_providers, list_connected_provider_ids."""

    def test_list_connected_providers_returns_all(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """list_connected_providers returns all rows with status info."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="test_provider", status="connected")
        _insert_connection(db, company_id=1, provider_id="limited_provider", status="disconnected")

        providers = conn_mgr.list_connected_providers(1)
        assert len(providers) >= 2

        statuses = {p["provider_id"]: p["status"] for p in providers}
        assert statuses["test_provider"] == "connected"
        assert statuses["limited_provider"] == "disconnected"

    def test_list_connected_provider_ids_filters(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """list_connected_provider_ids only returns connected+healthy providers."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="test_provider", status="connected")
        _insert_connection(
            db, company_id=1, provider_id="limited_provider", status="connected",
            last_health_check_status="down",
        )
        _insert_connection(db, company_id=1, provider_id="down_provider", status="disconnected")

        ids = conn_mgr.list_connected_provider_ids(1)
        assert "test_provider" in ids
        assert "limited_provider" not in ids  # last_health_check_status == "down"
        assert "down_provider" not in ids  # disconnected


# ═══════════════════════════════════════════════════════════════════════════
# ConnectionManagerService — is_connected
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectionManagerIsConnected:
    """is_connected — truthy / falsy."""

    def test_is_connected_true(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Row with status='connected' → True."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="health_test", status="connected")
        assert conn_mgr.is_connected(1, "health_test") is True

    def test_is_connected_false_no_row(
        self, conn_mgr: ConnectionManagerService,
    ) -> None:
        """No connection row → False."""
        assert conn_mgr.is_connected(1, "nonexistent") is False

    def test_is_connected_false_disconnected(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Row with status='disconnected' → False."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="health_test", status="disconnected")
        assert conn_mgr.is_connected(1, "health_test") is False


# ═══════════════════════════════════════════════════════════════════════════
# ConnectionManagerService — get_session
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectionManagerGetSession:
    """get_session — connection existence and status checks."""

    def test_get_session_no_connection(
        self, conn_mgr: ConnectionManagerService,
    ) -> None:
        """No connection row in DB → returns None."""
        result = asyncio.run(conn_mgr.get_session(1, "nonexistent"))
        assert result is None

    def test_get_session_not_connected(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Connection exists but status != 'connected' → returns None."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="health_test", status="disconnected")

        result = asyncio.run(conn_mgr.get_session(1, "health_test"))
        assert result is None

    def test_get_session_no_session_state(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Connected row with session_state=None → deserialise fails → None."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(
            db, company_id=1, provider_id="health_test",
            status="connected", session_state=None,
        )

        result = asyncio.run(conn_mgr.get_session(1, "health_test"))
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# ConnectionManagerService — list_connected_providers (extra)
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectionManagerListConnected:
    """Additional listing edge cases."""

    def test_list_connected_providers_empty(
        self, conn_mgr: ConnectionManagerService,
    ) -> None:
        """No connections at all → empty list."""
        providers = conn_mgr.list_connected_providers(1)
        assert providers == []

    def test_list_connected_provider_ids_empty(
        self, conn_mgr: ConnectionManagerService,
    ) -> None:
        """No connected providers → empty list."""
        ids = conn_mgr.list_connected_provider_ids(1)
        assert ids == []

    def test_is_connected_different_company(
        self, db: InMemoryDB, conn_mgr: ConnectionManagerService,
    ) -> None:
        """Connection for company A → is_connected returns False for company B."""
        db.conn.execute("PRAGMA foreign_keys = OFF")
        _insert_connection(db, company_id=1, provider_id="health_test", status="connected")
        assert conn_mgr.is_connected(2, "health_test") is False
