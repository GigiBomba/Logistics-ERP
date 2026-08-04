"""Tests for the F5 rate-limiter + circuit-breaker wiring in SearchEngineService.

Covers the production wiring (previously the resilience primitives were never
used by the search path):

  - ``is_allowed()`` is checked before the provider search fires
  - ``acquire_api()`` is acquired before the provider search fires
  - an OPEN circuit skips the provider (error status, adapter never called)
  - a rate-limit denial skips the provider without tripping the breaker
  - ``record_success`` / ``record_failure`` are recorded after each call
  - Redis-down degradation: a limiter/breaker that raises is bypassed and
    the search still proceeds (guard rails never block legitimate traffic)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone, date
from typing import Iterator, Optional
from unittest.mock import AsyncMock, MagicMock

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
)
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.registry import _registry
from services.freight_exchange.search import SearchEngineService
from tests.test_helpers import InMemoryDB


# ── Fake adapter ────────────────────────────────────────────────────────


class ProbeAdapter(FreightProviderAdapter):
    """Full-capability adapter returning a single test load."""
    provider_id = "resilience_probe"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _make_session(self.provider_id, creds.company_id)

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
        return [_make_load(self.provider_id)]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return _make_load(self.provider_id, load_id)

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


def _make_load(
    provider_id: str = "resilience_probe",
    provider_load_id: str = "PROBE-001",
) -> LoadSearchResult:
    now = datetime.now(timezone.utc)
    return LoadSearchResult(
        result_id=provider_load_id,
        provider_id=provider_id,
        provider_load_id=provider_load_id,
        origin="Bucuresti",
        destination="Berlin",
        pickup_window=(now, now),
        delivery_window=(now, now),
        price=Money(amount=1500.0, currency="EUR"),
        distance_km=1800.0,
        trailer_type="standard",
        adr=False,
    )


def _make_session(
    provider_id: str = "resilience_probe", company_id: int = 1,
) -> ProviderSession:
    now = datetime.now(timezone.utc)
    return ProviderSession(
        company_id=company_id,
        provider_id=provider_id,
        access_token_encrypted="test-token",
        expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc),
    )


def _insert_connection(db: InMemoryDB, provider_id: str = "resilience_probe") -> str:
    db.conn.execute("PRAGMA foreign_keys = OFF")
    conn_id = str(uuid.uuid4())
    session = _make_session(provider_id)
    db.conn.execute(
        "INSERT INTO freight_exchange_connections "
        "(id, company_id, provider_id, credentials_encrypted, session_state, "
        "status, last_health_check_status, last_health_check_at, created_at) "
        "VALUES (?, 1, ?, 'encrypted', ?, 'connected', 'healthy', "
        "datetime('now'), datetime('now'))",
        (conn_id, provider_id, json.dumps(session.model_dump(mode="json"))),
    )
    db.conn.commit()
    return conn_id


def _make_filters() -> LoadSearchFilters:
    return LoadSearchFilters(
        origin=GeoFilter(location="Bucuresti", radius_km=50),
        destination=GeoFilter(location="Berlin", radius_km=30),
        pickup_date_from=date.today(),
        pickup_date_to=date.today(),
    )


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def db() -> InMemoryDB:
    return InMemoryDB()


@pytest.fixture(autouse=True)
def _registry_management() -> Iterator[None]:
    before = dict(_registry)
    adapter = ProbeAdapter()
    _registry[adapter.provider_id] = adapter
    yield
    _registry.clear()
    for k, v in before.items():
        _registry[k] = v


@pytest.fixture
def search_engine(db: InMemoryDB) -> SearchEngineService:
    engine = SearchEngineService(db, cache=None)
    # Replace the real Redis-backed primitives with test doubles.
    engine._rate_limiter = AsyncMock()
    engine._rate_limiter.acquire_api = AsyncMock(return_value=True)
    breaker = MagicMock()
    breaker.is_allowed = AsyncMock(return_value=True)
    breaker.record_success = MagicMock()
    breaker.record_failure = MagicMock()
    engine._breakers = {"resilience_probe": breaker}
    return engine


# ── Wiring: primitives are actually called ──────────────────────────────


class TestResilienceWiring:
    def test_breaker_is_allowed_checked_before_search(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        _insert_connection(db)
        result = asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))
        assert len(result.results) == 1
        search_engine._breakers["resilience_probe"].is_allowed.assert_awaited_with(
            1, "resilience_probe"
        )

    def test_rate_limiter_acquired_before_search(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        _insert_connection(db)
        asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))
        search_engine._rate_limiter.acquire_api.assert_awaited_with(
            1, "resilience_probe"
        )

    def test_breaker_success_recorded_on_success(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        _insert_connection(db)
        asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))
        breaker = search_engine._breakers["resilience_probe"]
        breaker.record_success.assert_called_with(1, "resilience_probe")
        breaker.record_failure.assert_not_called()

    def test_breaker_failure_recorded_on_adapter_error(
        self, db: InMemoryDB, search_engine: SearchEngineService,
    ) -> None:
        _insert_connection(db)
        adapter = _registry["resilience_probe"]
        adapter.search_loads = AsyncMock(side_effect=RuntimeError("provider down"))
        result = asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))
        breaker = search_engine._breakers["resilience_probe"]
        breaker.record_failure.assert_called_with(1, "resilience_probe")
        # Failure surfaces as an error status, never a crash.
        assert any(ps.status == "error" for ps in result.provider_statuses)


# ── Guard behavior: OPEN circuit / rate limit ───────────────────────────


class TestResilienceGuards:
    def test_open_circuit_skips_provider(self, db: InMemoryDB, search_engine) -> None:
        _insert_connection(db)
        breaker = search_engine._breakers["resilience_probe"]
        breaker.is_allowed = AsyncMock(return_value=False)
        adapter = _registry["resilience_probe"]
        adapter.search_loads = AsyncMock(return_value=[_make_load()])

        result = asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))

        # Provider reported as an error (blocked) and never actually called.
        assert any(ps.status == "error" for ps in result.provider_statuses)
        adapter.search_loads.assert_not_awaited()
        # The limiter must not have been consulted while the circuit is OPEN.
        search_engine._rate_limiter.acquire_api.assert_not_awaited()

    def test_rate_limit_denial_skips_provider_without_tripping_breaker(
        self, db: InMemoryDB, search_engine,
    ) -> None:
        _insert_connection(db)
        search_engine._rate_limiter.acquire_api = AsyncMock(return_value=False)
        adapter = _registry["resilience_probe"]
        adapter.search_loads = AsyncMock(return_value=[_make_load()])

        result = asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))

        assert any(ps.status == "error" for ps in result.provider_statuses)
        adapter.search_loads.assert_not_awaited()
        breaker = search_engine._breakers["resilience_probe"]
        breaker.record_failure.assert_not_called()  # not a provider failure


# ── Redis-down degradation ──────────────────────────────────────────────


class TestResilienceRedisDown:
    def test_limiter_exception_is_bypassed(self, db: InMemoryDB, search_engine) -> None:
        """Limiter raising (Redis dropped mid-flight) must not block search."""
        _insert_connection(db)
        search_engine._rate_limiter.acquire_api = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )

        result = asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))

        assert len(result.results) == 1  # search proceeded
        assert any(ps.status == "ok" for ps in result.provider_statuses)

    def test_breaker_exception_is_bypassed(self, db: InMemoryDB, search_engine) -> None:
        """Breaker raising (Redis dropped mid-flight) must not block search."""
        _insert_connection(db)
        search_engine._breakers["resilience_probe"].is_allowed = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )

        result = asyncio.run(search_engine.search_loads(
            company_id=1, filters=_make_filters(),
            provider_ids=["resilience_probe"],
        ))

        assert len(result.results) == 1  # search proceeded
        assert any(ps.status == "ok" for ps in result.provider_statuses)
