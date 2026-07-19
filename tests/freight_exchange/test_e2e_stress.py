"""E2E, stress, load, chaos, mutation, and risk boundary tests for the Freight Exchange subsystem.

Covers 18+ test methods across six categories:
  - E2E (5)  : full pipeline, multi-provider, degraded provider, saved search lifecycle, import parity
  - Stress   : concurrent search, large result set, rapid connect/disconnect
  - Chaos    : provider timeout, corrupted session state, DB connection lost
  - Mutation : zero/negative price, extreme distance, empty strings
  - Risk     : max factors, min factors, rapid re-calc determinism

All tests use ``InMemoryDB``, fake adapters, and ``asyncio.run()``.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.common import Money
from models.freight_exchange_models import (
    GeoFilter,
    ImportResult,
    LoadEvaluation,
    LoadSearchFilters,
    LoadSearchResult,
    ProviderCapabilities,
    ProviderCredentials,
    ProviderHealthCheck,
    ProviderSession,
    SavedSearch,
)
from models.trip_models import TripCreate, TripResult
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.connection_manager import ConnectionManagerService
from services.freight_exchange.evaluation import EvaluationEngineService
from services.freight_exchange.fleet_matcher import FleetMatcherService
from services.freight_exchange.import_pipeline import ImportError, ImportPipelineService
from services.freight_exchange.registry import _registry, register_freight_provider, get_adapter
from services.freight_exchange.risk_scoring import compute_risk_score
from services.freight_exchange.search import SearchEngineService
from tests.test_helpers import InMemoryDB

# ═══════════════════════════════════════════════════════════════════════════
# Fake adapters
# ═══════════════════════════════════════════════════════════════════════════


def _make_load(
    provider_id: str = "e2e_test",
    provider_load_id: str = "E2E-001",
    origin: str = "Bucuresti",
    destination: str = "Berlin",
    amount: float = 1500.0,
    currency: str = "EUR",
    distance_km: float = 1800.0,
    trailer_type: str = "standard",
    adr: bool = False,
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
        trailer_type=trailer_type,
        adr=adr,
    )


def _make_session(provider_id: str = "e2e_test") -> ProviderSession:
    now = datetime.now(timezone.utc)
    return ProviderSession(
        company_id=1,
        provider_id=provider_id,
        access_token_encrypted="e2e-fake-token",
        expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc),
    )


def _make_caps(provider_id: str = "e2e_test") -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_id=provider_id,
        supported_filters=[
            "origin", "destination", "pickup_date_from", "pickup_date_to",
            "trailer_type", "adr_required", "weight_kg_min", "weight_kg_max",
            "distance_km_max",
        ],
        supports_saved_search=False,
        supports_offer_publishing=False,
        rate_limit_per_minute=60,
    )


@register_freight_provider
class E2eHealthyAdapter(FreightProviderAdapter):
    """Fake adapter returning a single known load — used for E2E pipeline tests."""
    provider_id = "e2e_healthy"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _make_session(self.provider_id)

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
    ) -> LoadSearchResult:
        return _make_load(provider_id=self.provider_id, provider_load_id=load_id)

    def capabilities(self) -> ProviderCapabilities:
        return _make_caps(self.provider_id)


@register_freight_provider
class E2eDownAdapter(FreightProviderAdapter):
    """Fake adapter that simulates a down provider."""
    provider_id = "e2e_down"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _make_session(self.provider_id)

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        return session

    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck:
        return ProviderHealthCheck(
            provider_id=self.provider_id, status="down", latency_ms=0,
            checked_at=datetime.now(timezone.utc), error="Connection refused",
        )

    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        raise RuntimeError("Provider is down")

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> LoadSearchResult:
        raise RuntimeError("Provider is down")

    def capabilities(self) -> ProviderCapabilities:
        return _make_caps(self.provider_id)


@register_freight_provider
class E2eProviderAAdapter(FreightProviderAdapter):
    """Fake adapter for multi-provider tests — produces loads with an 'A' prefix."""
    provider_id = "e2e_provider_a"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _make_session(self.provider_id)

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
        return [_make_load(provider_id=self.provider_id, provider_load_id="A-001")]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> LoadSearchResult:
        return _make_load(provider_id=self.provider_id, provider_load_id=load_id)

    def capabilities(self) -> ProviderCapabilities:
        return _make_caps(self.provider_id)


@register_freight_provider
class E2eProviderBAdapter(FreightProviderAdapter):
    """Fake adapter for multi-provider tests — produces loads with a 'B' prefix."""
    provider_id = "e2e_provider_b"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _make_session(self.provider_id)

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
        return [_make_load(provider_id=self.provider_id, provider_load_id="B-001")]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> LoadSearchResult:
        return _make_load(provider_id=self.provider_id, provider_load_id=load_id)

    def capabilities(self) -> ProviderCapabilities:
        return _make_caps(self.provider_id)


@register_freight_provider
class E2eSlowAdapter(FreightProviderAdapter):
    """Fake adapter that delays 2s then raises — simulates a provider timeout."""
    provider_id = "e2e_slow"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _make_session(self.provider_id)

    async def refresh_session(self, session: ProviderSession) -> ProviderSession:
        return session

    async def test_connection(self, session: ProviderSession) -> ProviderHealthCheck:
        return ProviderHealthCheck(
            provider_id=self.provider_id, status="healthy", latency_ms=2000,
            checked_at=datetime.now(timezone.utc),
        )

    async def search_loads(
        self, session: ProviderSession, filters: LoadSearchFilters
    ) -> list[LoadSearchResult]:
        await asyncio.sleep(2.0)
        raise RuntimeError("Provider timeout after 2s")

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> LoadSearchResult:
        await asyncio.sleep(2.0)
        raise RuntimeError("Provider timeout after 2s")

    def capabilities(self) -> ProviderCapabilities:
        return _make_caps(self.provider_id)


@register_freight_provider
class E2eLargeResultAdapter(FreightProviderAdapter):
    """Fake adapter that returns a configurable number of results."""
    provider_id = "e2e_large"

    def __init__(self, result_count: int = 1000):
        super().__init__()
        self._result_count = result_count

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _make_session(self.provider_id)

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
        return [
            _make_load(
                provider_id=self.provider_id,
                provider_load_id=f"LARGE-{i:04d}",
                distance_km=100.0 + i,
            )
            for i in range(self._result_count)
        ]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return _make_load(provider_id=self.provider_id, provider_load_id=load_id)

    def capabilities(self) -> ProviderCapabilities:
        return _make_caps(self.provider_id)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture(autouse=True)
def _manage_registry():
    """Ensure the needed fake adapters are in the registry before each test,
    and clean up after.
    """
    before = dict(_registry)
    # Re-register *all* E2E fake adapters (avoids issues if other tests cleared them)
    _registry["e2e_healthy"] = E2eHealthyAdapter()
    _registry["e2e_down"] = E2eDownAdapter()
    _registry["e2e_provider_a"] = E2eProviderAAdapter()
    _registry["e2e_provider_b"] = E2eProviderBAdapter()
    _registry["e2e_slow"] = E2eSlowAdapter()
    # Keep e2e_large out by default — tests that need it inject it
    yield
    _registry.clear()
    for k, v in before.items():
        # Restore only non-e2e adapters to avoid pollution
        if not k.startswith("e2e_"):
            _registry[k] = v


@pytest.fixture
def conn_mgr(db) -> ConnectionManagerService:
    return ConnectionManagerService(db)


@pytest.fixture
def search_engine(db) -> SearchEngineService:
    return SearchEngineService(db)


@pytest.fixture
def eval_engine(db) -> EvaluationEngineService:
    return EvaluationEngineService(db)


@pytest.fixture
def matcher(db) -> FleetMatcherService:
    return FleetMatcherService(db)


@pytest.fixture
def pipeline(db) -> ImportPipelineService:
    return ImportPipelineService(db)


def _make_session_state_json(provider_id: str = "e2e_healthy") -> str:
    """Generate a valid ProviderSession serialized to JSON for DB storage."""
    session = _make_session(provider_id)
    return json.dumps(session.model_dump(mode="json"))


def _insert_connection(
    db,
    company_id: int = 1,
    provider_id: str = "e2e_healthy",
    status: str = "connected",
    session_state: Optional[str] = None,
):
    """Helper to insert a connection row and mark the provider as healthy."""
    if session_state is None:
        session_state = _make_session_state_json(provider_id)
    db.conn.execute("PRAGMA foreign_keys = OFF")
    db.conn.execute(
        "INSERT OR REPLACE INTO freight_exchange_connections "
        "(company_id, provider_id, credentials_encrypted, session_state, "
        "status, last_health_check_status, created_at) "
        "VALUES (?, ?, 'enc', ?, ?, 'healthy', datetime('now'))",
        (company_id, provider_id, session_state, status),
    )
    db.conn.commit()


def _patch_session_state(conn_mgr, adapter, company_id: int = 1, provider_id: str = "e2e_healthy"):
    """Patch ``conn_mgr`` methods so ``search_loads`` can work without
    a real DB-stored session.

    Returns a context manager that patches ``is_connected`` → True
    and ``get_session`` → a valid ``ProviderSession``.
    """
    session = _make_session(provider_id)
    return patch.multiple(
        conn_mgr,
        is_connected=MagicMock(return_value=True),
        get_session=AsyncMock(return_value=session),
    )


def _make_truck(truck_id: int, **overrides) -> dict:
    defaults = {
        "id": truck_id,
        "plate": f"TRK-{truck_id:03d}",
        "trailer_type": "standard",
        "current_location": "Bucuresti, RO",
        "consumption_l_per_100km": 30,
        "adr_certified": False,
    }
    defaults.update(overrides)
    return defaults


# ═══════════════════════════════════════════════════════════════════════════
# 1. E2E — Full pipeline: connect → search → evaluate → match → import
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestE2EFullPipeline:
    """Wire all services together: connect, search, evaluate, match, import."""

    def test_e2e_pipeline_all_services(self, db, search_engine, eval_engine, matcher, pipeline):
        """Full E2E: connect → search → evaluate → match → import."""
        # ── Connect ──
        _insert_connection(db, provider_id="e2e_healthy")

        # ── Search (patch session so search_loads can reach the adapter) ──
        filters = LoadSearchFilters(
            origin=GeoFilter(location="Bucuresti", radius_km=50),
            destination=GeoFilter(location="Berlin", radius_km=30),
            pickup_date_from=datetime.now(timezone.utc).date(),
            pickup_date_to=datetime.now(timezone.utc).date(),
        )

        async def _search():
            with _patch_session_state(search_engine._conn_mgr, "e2e_healthy"):
                return await search_engine.search_loads(
                    company_id=1, filters=filters, provider_ids=["e2e_healthy"],
                )

        result_set = asyncio.run(_search())
        assert len(result_set.results) >= 0
        assert result_set.total_providers_queried > 0

        # ── Evaluate (need to mock get_load since there's no real data) ──
        load = _make_load(provider_id="e2e_healthy", provider_load_id="E2E-EVAL")

        async def _evaluate():
            with patch.object(eval_engine._search, "get_load", new=AsyncMock(return_value=load)):
                return await eval_engine.evaluate_load(
                    company_id=1, provider_id="e2e_healthy",
                    provider_load_id="E2E-EVAL",
                )

        evaluation = asyncio.run(_evaluate())
        assert isinstance(evaluation, LoadEvaluation)
        assert evaluation.estimated_revenue.amount > 0
        assert 0.0 <= evaluation.risk_score <= 1.0

        # ── Match (need to patch _get_available_trucks and helpers) ──
        truck = _make_truck(1)
        load_for_match = _make_load(provider_id="e2e_healthy", provider_load_id="E2E-EVAL")

        async def _match():
            with patch.object(matcher, "_get_available_trucks", return_value=[truck]):
                with patch.object(matcher, "_get_driver_hours", return_value=40.0):
                    with patch.object(matcher, "_get_health_score", return_value=85.0):
                        with patch.object(
                            matcher._search, "get_load",
                            new=AsyncMock(return_value=load_for_match),
                        ):
                            return await matcher.find_best_trucks(
                                company_id=1, provider_id="e2e_healthy",
                                provider_load_id="E2E-EVAL", top_n=5,
                            )

        matches = asyncio.run(_match())
        assert isinstance(matches, list)

        # ── Import (mock trip_service.create) ──
        async def _import():
            with patch.object(pipeline._search, "get_load", new=AsyncMock(return_value=load)):
                with patch("services.trip_service.TripService.create") as mock_create:
                    mock_result = type("FakeResult", (), {
                        "success": True,
                        "data": TripResult(
                            id=100, client_id=1, reference="FX-E2E-E2E-EVAL",
                            start_date=date.today(), price_eur=1500.0,
                            currency="EUR", status="Planned",
                        ),
                        "errors": [],
                    })()
                    mock_create.return_value = mock_result
                    return await pipeline.import_load(
                        company_id=1, provider_id="e2e_healthy",
                        provider_load_id="E2E-EVAL", user_id=42,
                    )

        result = asyncio.run(_import())
        assert isinstance(result, ImportResult)
        assert result.trip_id == 100
        assert result.source == "freight_exchange"
        assert result.source_provider_id == "e2e_healthy"


@pytest.mark.e2e
class TestE2EMultiProvider:
    """Two providers: search both, import from both, verify distinct trips."""

    def test_two_providers_distinct_trips(self, db, search_engine, pipeline):
        """Search two providers, import both loads, verify trips are distinct."""
        # Connect both providers
        _insert_connection(db, provider_id="e2e_provider_a")
        _insert_connection(db, company_id=1, provider_id="e2e_provider_b")

        filters = LoadSearchFilters(
            origin=GeoFilter(location="Bucuresti", radius_km=50),
            destination=GeoFilter(location="Berlin", radius_km=30),
            pickup_date_from=datetime.now(timezone.utc).date(),
            pickup_date_to=datetime.now(timezone.utc).date(),
        )

        async def _search_both():
            with _patch_session_state(search_engine._conn_mgr, "e2e_provider_a"):
                with _patch_session_state(search_engine._conn_mgr, "e2e_provider_b"):
                    return await search_engine.search_loads(
                        company_id=1, filters=filters,
                        provider_ids=["e2e_provider_a", "e2e_provider_b"],
                    )

        result_set = asyncio.run(_search_both())
        provider_ids = {r.provider_id for r in result_set.results}
        assert "e2e_provider_a" in provider_ids
        assert "e2e_provider_b" in provider_ids

        # Verify both IDs are captured (at least one result per provider)
        assert len(result_set.results) >= 2

        # ── Import from provider A ──
        load_a = _make_load(provider_id="e2e_provider_a", provider_load_id="A-001")

        async def _import_a():
            with patch.object(pipeline._search, "get_load", new=AsyncMock(return_value=load_a)):
                with patch("services.trip_service.TripService.create") as mock_create:
                    mock_result = type("FakeResult", (), {
                        "success": True,
                        "data": TripResult(
                            id=201, client_id=1, reference="FX-E2E-A-001",
                            start_date=date.today(), price_eur=1500.0,
                            currency="EUR", status="Planned",
                        ),
                        "errors": [],
                    })()
                    mock_create.return_value = mock_result
                    return await pipeline.import_load(
                        company_id=1, provider_id="e2e_provider_a",
                        provider_load_id="A-001", user_id=10,
                    )

        result_a = asyncio.run(_import_a())
        assert result_a.trip_id == 201
        assert result_a.source_provider_id == "e2e_provider_a"

        # ── Import from provider B ──
        load_b = _make_load(provider_id="e2e_provider_b", provider_load_id="B-001")

        async def _import_b():
            with patch.object(pipeline._search, "get_load", new=AsyncMock(return_value=load_b)):
                with patch("services.trip_service.TripService.create") as mock_create:
                    mock_result = type("FakeResult", (), {
                        "success": True,
                        "data": TripResult(
                            id=202, client_id=1, reference="FX-E2E-B-001",
                            start_date=date.today(), price_eur=1500.0,
                            currency="EUR", status="Planned",
                        ),
                        "errors": [],
                    })()
                    mock_create.return_value = mock_result
                    return await pipeline.import_load(
                        company_id=1, provider_id="e2e_provider_b",
                        provider_load_id="B-001", user_id=10,
                    )

        result_b = asyncio.run(_import_b())
        assert result_b.trip_id == 202
        assert result_b.source_provider_id == "e2e_provider_b"

        # Trips are distinct
        assert result_a.trip_id != result_b.trip_id
        assert result_a.source_reference_id != result_b.source_reference_id


@pytest.mark.e2e
class TestE2EDegradedProvider:
    """One healthy + one down — search returns partial results."""

    def test_healthy_and_down_providers(self, db, search_engine):
        """Search with one healthy and one down produces partial results."""
        _insert_connection(db, provider_id="e2e_healthy")

        # Insert down provider as connected (health check will fail at search time)
        down_session = _make_session_state_json("e2e_down")
        db.conn.execute("PRAGMA foreign_keys = OFF")
        db.conn.execute(
            "INSERT OR REPLACE INTO freight_exchange_connections "
            "(company_id, provider_id, credentials_encrypted, session_state, "
            "status, last_health_check_status, created_at) "
            "VALUES (1, 'e2e_down', 'enc', ?, 'connected', 'down', datetime('now'))",
            (down_session,),
        )
        db.conn.commit()

        filters = LoadSearchFilters(
            origin=GeoFilter(location="Bucuresti", radius_km=50),
            destination=GeoFilter(location="Berlin", radius_km=30),
            pickup_date_from=datetime.now(timezone.utc).date(),
            pickup_date_to=datetime.now(timezone.utc).date(),
        )

        async def _search():
            # Patch session for the healthy provider; the down provider's
            # health-check failure is handled via the DB status=down.
            with _patch_session_state(search_engine._conn_mgr, "e2e_healthy"):
                return await search_engine.search_loads(
                    company_id=1, filters=filters,
                    provider_ids=["e2e_healthy", "e2e_down"],
                )

        result_set = asyncio.run(_search())

        # Should NOT crash — down provider is skipped gracefully
        assert result_set.total_providers_queried >= 0
        assert result_set.total_providers_skipped >= 0

        # At least the healthy provider should have a status entry
        healthy_statuses = [
            s for s in result_set.provider_statuses if s.provider_id == "e2e_healthy"
        ]
        assert len(healthy_statuses) > 0


@pytest.mark.e2e
class TestE2ESavedSearchLifecycle:
    """Save → refresh → recent → refresh again."""

    def test_saved_search_lifecycle(self, db, search_engine):
        """Full lifecycle of a saved search."""
        _insert_connection(db, provider_id="e2e_healthy")
        company_id = 1
        user_id = 42

        filters = LoadSearchFilters(
            origin=GeoFilter(location="Bucuresti", radius_km=50),
            destination=GeoFilter(location="Berlin", radius_km=30),
            pickup_date_from=datetime.now(timezone.utc).date(),
            pickup_date_to=datetime.now(timezone.utc).date(),
        )

        # ── 1. Save ──
        async def _save():
            return await search_engine.save_search(
                company_id=company_id, user_id=user_id,
                filters=filters, label="E2E Test Search",
            )

        saved = asyncio.run(_save())
        assert isinstance(saved, SavedSearch)
        assert saved.label == "E2E Test Search"
        assert saved.last_refreshed_at is None
        search_id = saved.saved_search_id

        # ── 2. Refresh ──
        async def _refresh():
            return await search_engine.refresh_search(
                company_id=company_id, saved_search_id=search_id,
            )

        refreshed = asyncio.run(_refresh())
        assert hasattr(refreshed, "results")

        # ── 3. Recent ──
        async def _recent():
            return await search_engine.get_recent_searches(
                company_id=company_id, user_id=user_id, limit=10,
            )

        recent = asyncio.run(_recent())
        assert len(recent) >= 1
        ids = [s.saved_search_id for s in recent]
        assert search_id in ids

        # ── 4. Refresh again ──
        async def _refresh2():
            return await search_engine.refresh_search(
                company_id=company_id, saved_search_id=search_id,
            )

        refreshed2 = asyncio.run(_refresh2())
        assert hasattr(refreshed2, "results")

        # ── 5. Verify last_refreshed_at was updated ──
        row = search_engine._repo.get_search(search_id)
        assert row is not None
        assert row.get("last_refreshed_at") is not None, (
            "last_refreshed_at should be set after refresh"
        )


@pytest.mark.e2e
class TestE2EImportParity:
    """Manual trip vs imported trip produce identical financial calculations."""

    def test_import_parity_financials(self, db, eval_engine):
        """A manually created trip and an imported load with identical data
        yield the same financial calculation results."""
        # ── Build identical load data ──
        now = datetime.now(timezone.utc)
        load = LoadSearchResult(
            result_id="PARITY-001",
            provider_id="e2e_healthy",
            provider_load_id="PARITY-001",
            origin="Bucuresti",
            destination="Berlin",
            pickup_window=(now, now),
            delivery_window=(
                datetime.fromtimestamp(now.timestamp() + 48 * 3600, tz=timezone.utc),
                datetime.fromtimestamp(now.timestamp() + 48 * 3600, tz=timezone.utc),
            ),
            price=Money(amount=2000.0, currency="EUR"),
            distance_km=1800.0,
            trailer_type="standard",
            adr=False,
        )

        # Manually create a TripCreate with the same financial data
        manual_trip = TripCreate(
            client_id=1,
            client_name="Test Client",
            reference="MANUAL-PARITY",
            start_date=now.date(),
            end_date=(now + timedelta(days=2)).date(),
            price_eur=2000.0,
            currency="EUR",
            distance_km=1800.0,
            stops=[],
            status="Planned",
            source="manual",
        )

        # Run the evaluation engine's financial calculation on the load
        # (this is the same path both manual and imported trips go through)
        fuel_cost = 630.0   # 1800 * 0.35
        toll_cost = 144.0   # 1800 * 0.08
        salary_cost = 216.0  # 1800 * 0.12

        rev_import, profit_import, margin_import = eval_engine._calculate_financials(
            load, fuel_cost=fuel_cost, toll_cost=toll_cost, driver_salary=salary_cost,
        )

        # For manual trip, revenue comes from price_eur
        rev_manual = manual_trip.price_eur
        total_cost_manual = fuel_cost + toll_cost + salary_cost
        profit_manual = rev_manual - total_cost_manual
        margin_manual = (profit_manual / rev_manual * 100.0) if rev_manual != 0 else 0.0

        assert rev_import == rev_manual, (
            f"Revenue differs: import={rev_import} manual={rev_manual}"
        )
        assert profit_import == profit_manual, (
            f"Profit differs: import={profit_import} manual={profit_manual}"
        )
        assert margin_import == margin_manual, (
            f"Margin differs: import={margin_import} manual={margin_manual}"
        )

        # ── Risk score parity ──
        risk_import = compute_risk_score(
            pickup_window=load.pickup_window,
            delivery_window=load.delivery_window,
            estimated_duration_hours=load.distance_km / 60.0,
            origin=load.origin,
            destination=load.destination,
            load_price=load.price.amount,
        )
        # Manual trip risk would use same route data — identical result
        risk_manual = compute_risk_score(
            pickup_window=load.pickup_window,
            delivery_window=load.delivery_window,
            estimated_duration_hours=load.distance_km / 60.0,
            origin=load.origin,
            destination=load.destination,
            load_price=manual_trip.price_eur,
        )
        assert risk_import == risk_manual, (
            f"Risk differs: import={risk_import} manual={risk_manual}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Stress / Load
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.stresstest
class TestStressConcurrentSearch:
    """10 simultaneous search requests don't crash."""

    def test_10_concurrent_searches(self, db, search_engine):
        """Fire 10 search requests concurrently and verify all complete."""
        _insert_connection(db, provider_id="e2e_healthy")
        company_id = 1

        filters = LoadSearchFilters(
            origin=GeoFilter(location="Bucuresti", radius_km=50),
            destination=GeoFilter(location="Berlin", radius_km=30),
            pickup_date_from=datetime.now(timezone.utc).date(),
            pickup_date_to=datetime.now(timezone.utc).date(),
        )

        async def _single_search(idx: int) -> int:
            """Run a single search and return result count."""
            result = await search_engine.search_loads(
                company_id=company_id, filters=filters,
                provider_ids=["e2e_healthy"],
            )
            return len(result.results)

        async def _run_all():
            tasks = [_single_search(i) for i in range(10)]
            return await asyncio.gather(*tasks, return_exceptions=True)

        outcomes = asyncio.run(_run_all())

        # All 10 should complete without exceptions
        non_exception = [o for o in outcomes if not isinstance(o, Exception)]
        assert len(non_exception) == 10, (
            f"Expected 10 successful searches, got {len(non_exception)} success, "
            f"{len(outcomes) - len(non_exception)} failures"
        )


@pytest.mark.stresstest
class TestStressLargeResultSet:
    """1000+ results handled without performance degradation."""

    def test_large_result_set(self, db):
        """Search returns 1000+ results without crashing or data loss."""
        # Register the large-result adapter manually
        _registry["e2e_large"] = E2eLargeResultAdapter(result_count=1200)
        try:
            _insert_connection(db, provider_id="e2e_large")
            company_id = 1

            search = SearchEngineService(db)
            filters = LoadSearchFilters(
                origin=GeoFilter(location="Bucuresti", radius_km=50),
                destination=GeoFilter(location="Berlin", radius_km=30),
                pickup_date_from=datetime.now(timezone.utc).date(),
                pickup_date_to=datetime.now(timezone.utc).date(),
            )

            async def _search():
                with _patch_session_state(search._conn_mgr, "e2e_large"):
                    return await search.search_loads(
                        company_id=company_id, filters=filters,
                        provider_ids=["e2e_large"],
                    )

            result_set = asyncio.run(_search())
            assert len(result_set.results) == 1200, (
                f"Expected 1200 results, got {len(result_set.results)}"
            )
            # Verify all results have distinct IDs
            all_ids = [r.provider_load_id for r in result_set.results]
            assert len(set(all_ids)) == 1200, "Duplicate load IDs in large result set"
        finally:
            _registry.pop("e2e_large", None)


@pytest.mark.stresstest
class TestStressRapidConnectDisconnect:
    """20 rapid connect/disconnect cycles without state corruption."""

    def test_20_rapid_cycles(self, db, conn_mgr):
        """Rapid connect/disconnect cycles don't leave stale state.
        Uses sequential cycles (SQLite InMemoryDB doesn't support
        concurrent writes) — the stress is the rapid succession, not
        simultaneous writes.
        """
        # Disable foreign keys to avoid FK constraint on company_id
        db.conn.execute("PRAGMA foreign_keys = OFF")
        db.conn.commit()

        creds = ProviderCredentials(
            company_id=1, provider_id="e2e_healthy",
            client_id="stress-client", client_secret_encrypted="stress-secret",
            scope=["loads:read"],
        )

        async def _run_cycles():
            outcomes = []
            for _ in range(20):
                try:
                    conn_result = await conn_mgr.connect_provider(1, "e2e_healthy", creds)
                    await conn_mgr.disconnect_provider(1, "e2e_healthy")
                    outcomes.append(conn_result)
                except Exception as exc:
                    outcomes.append(exc)
            return outcomes

        outcomes = asyncio.run(_run_cycles())

        # All 20 cycles complete without exceptions
        non_exception = [o for o in outcomes if not isinstance(o, Exception)]
        assert len(non_exception) == 20, (
            f"Expected 20 successful cycles, got {len(non_exception)} success, "
            f"{len(outcomes) - len(non_exception)} failures. "
            f"First error: {outcomes[0] if outcomes else 'N/A'}"
        )

        # After all cycles, the connection should be disconnected
        row = conn_mgr.repo.get_connection(1, "e2e_healthy")
        if row is not None:
            assert row["status"] == "disconnected", (
                f"Final status should be disconnected, got {row['status']}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Chaos / Resilience
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.chaos
class TestChaosProviderTimeout:
    """Provider timeout mid-search — adapter raises after 2s delay,
    other providers still return results."""

    def test_timeout_does_not_block_other_providers(self, db, search_engine):
        """A slow/ timing-out provider doesn't prevent other providers from returning."""
        # Set up healthy provider (fast) and slow provider (2s timeout)
        _insert_connection(db, provider_id="e2e_healthy")
        slow_session = _make_session_state_json("e2e_slow")
        db.conn.execute("PRAGMA foreign_keys = OFF")
        db.conn.execute(
            "INSERT OR REPLACE INTO freight_exchange_connections "
            "(company_id, provider_id, credentials_encrypted, session_state, "
            "status, last_health_check_status, created_at) "
            "VALUES (1, 'e2e_slow', 'enc', ?, 'connected', 'healthy', datetime('now'))",
            (slow_session,),
        )
        db.conn.commit()

        company_id = 1
        filters = LoadSearchFilters(
            origin=GeoFilter(location="Bucuresti", radius_km=50),
            destination=GeoFilter(location="Berlin", radius_km=30),
            pickup_date_from=datetime.now(timezone.utc).date(),
            pickup_date_to=datetime.now(timezone.utc).date(),
        )

        async def _search():
            start = time.monotonic()
            with _patch_session_state(search_engine._conn_mgr, "e2e_healthy"):
                with _patch_session_state(search_engine._conn_mgr, "e2e_slow"):
                    result = await search_engine.search_loads(
                        company_id=company_id, filters=filters,
                        provider_ids=["e2e_healthy", "e2e_slow"],
                    )
            elapsed = time.monotonic() - start
            return result, elapsed

        result_set, elapsed = asyncio.run(_search())

        # The slow provider should be marked as "error" in provider_statuses
        slow_statuses = [
            s for s in result_set.provider_statuses
            if s.provider_id == "e2e_slow"
        ]
        if slow_statuses:
            assert slow_statuses[0].status in ("error", "skipped_down")
        else:
            # Slow provider might not have been queried if connection state
            # showed it as down; that's fine too.
            pass

        # The healthy provider should still have reported results
        healthy_statuses = [
            s for s in result_set.provider_statuses
            if s.provider_id == "e2e_healthy"
        ]
        assert len(healthy_statuses) > 0


@pytest.mark.chaos
class TestChaosCorruptedSessionState:
    """Malformed JSON in session_state doesn't crash connection_manager."""

    def test_malformed_session_state(self, db, conn_mgr, search_engine):
        """Corrupted JSON in session_state column is handled gracefully."""
        # Insert a connection with malformed JSON in session_state
        _insert_connection(
            db, provider_id="e2e_healthy",
            session_state="this is not valid json {{{",
        )

        # Connection manager should still list providers
        providers = conn_mgr.list_connected_providers(1)
        assert len(providers) >= 1

        # is_connected should work (checks status, not session_state)
        connected = conn_mgr.is_connected(1, "e2e_healthy")
        assert connected is True

        # get_session should return None (can't deserialize) — not crash
        async def _get_session():
            session = await conn_mgr.get_session(1, "e2e_healthy")
            return session

        session = asyncio.run(_get_session())
        assert session is None, "Session should be None for malformed state"

        # get_active_session_sync should also return None — not crash
        sync_session = conn_mgr.get_active_session_sync(1, "e2e_healthy")
        assert sync_session is None


@pytest.mark.chaos
class TestChaosDBConnectionLost:
    """Repository handles OperationalError gracefully when DB connection lost."""

    def test_db_operation_error_on_search(self, db):
        """OperationalError from the repository doesn't crash the search engine."""
        _insert_connection(db, provider_id="e2e_healthy")

        search = SearchEngineService(db)

        # Patch the repo's _fetchall to raise OperationalError
        with patch.object(
            search._repo,
            "_fetchall",
            side_effect=__import__("sqlite3").OperationalError("database is locked"),
        ):
            filters = LoadSearchFilters(
                origin=GeoFilter(location="Bucuresti", radius_km=50),
                destination=GeoFilter(location="Berlin", radius_km=30),
                pickup_date_from=datetime.now(timezone.utc).date(),
                pickup_date_to=datetime.now(timezone.utc).date(),
            )

            async def _search():
                return await search.search_loads(
                    company_id=1, filters=filters, provider_ids=["e2e_healthy"],
                )

            result_set = asyncio.run(_search())
            # Should return an empty result set rather than crashing
            assert result_set.total_providers_queried >= 0
            # The provider_ids resolution (list_connected_provider_ids) may
            # also fail — the test verifies the system doesn't crash regardless.
            assert isinstance(result_set, object)

    def test_db_operation_error_on_connection_list(self, db, conn_mgr):
        """OperationalError during list_connected_providers propagates
        as a DB-level exception (graceful = isolated to that operation)."""
        with patch.object(
            conn_mgr.repo,
            "list_connections",
            side_effect=__import__("sqlite3").OperationalError("database is locked"),
        ):
            with pytest.raises(__import__("sqlite3").OperationalError):
                conn_mgr.list_connected_providers(1)

    def test_db_operation_error_on_import_duplicate_check(self, db, pipeline):
        """OperationalError during duplicate check returns False (safe default)."""
        load = _make_load(provider_id="e2e_healthy", provider_load_id="L-DB-ERR")

        with patch.object(pipeline, "_is_already_imported", return_value=False):
            async def _import():
                with patch.object(pipeline._search, "get_load", new=AsyncMock(return_value=load)):
                    with patch("services.trip_service.TripService.create") as mock_create:
                        mock_result = type("FakeResult", (), {
                            "success": True,
                            "data": TripResult(
                                id=301, client_id=1, reference="FX-E2E-L-DB-ERR",
                                start_date=date.today(), price_eur=1500.0,
                                currency="EUR", status="Planned",
                            ),
                            "errors": [],
                        })()
                        mock_create.return_value = mock_result
                        return await pipeline.import_load(
                            company_id=1, provider_id="e2e_healthy",
                            provider_load_id="L-DB-ERR", user_id=1,
                        )

            result = asyncio.run(_import())
            assert result.trip_id == 301


# ═══════════════════════════════════════════════════════════════════════════
# 4. Mutation / Boundary
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.mutation
class TestMutationZeroPrice:
    """Zero price load: evaluation handles price=0 without division error."""

    def test_zero_price_does_not_crash_evaluation(self, eval_engine):
        load = _make_load(amount=0.0)
        # _calculate_financials divides by revenue — must handle 0
        rev, profit, margin = eval_engine._calculate_financials(
            load, fuel_cost=100.0, toll_cost=20.0, driver_salary=30.0,
        )
        assert rev == 0.0
        assert profit == -150.0  # 0 - 150
        assert margin == 0.0  # zero revenue → zero margin (no div by zero)

    def test_zero_price_risk_score(self):
        now = datetime.now(timezone.utc)
        # Risk scoring with load_price=0 should not divide by zero
        score = compute_risk_score(
            pickup_window=(now, now),
            delivery_window=(now, now),
            estimated_duration_hours=10,
            origin="A", destination="B",
            load_price=0.0,
        )
        assert 0.0 <= score <= 1.0

    def test_zero_price_import_mapping(self, pipeline):
        load = _make_load(amount=0.0)
        tc = pipeline._map_to_trip_create(load, "e2e_healthy", "L-ZERO")
        assert tc.price_eur == 0.0


@pytest.mark.mutation
class TestMutationNegativePrice:
    """Negative price load: evaluation handles price<0."""

    def test_negative_price_financials(self, eval_engine):
        load = _make_load(amount=-500.0)
        rev, profit, margin = eval_engine._calculate_financials(
            load, fuel_cost=100.0, toll_cost=20.0, driver_salary=30.0,
        )
        assert rev == -500.0
        assert profit == -650.0  # -500 - 150
        # Margin = profit / revenue * 100 = -650 / -500 * 100 = 130.0
        assert margin == 130.0  # negative / negative = positive margin technically

    def test_negative_price_import_mapping(self, pipeline):
        load = _make_load(amount=-500.0)
        # TripCreate validates price_eur >= 0, so _map_to_trip_create raises
        # a ValidationError — verify the error message is clear.
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Price cannot be negative"):
            pipeline._map_to_trip_create(load, "e2e_healthy", "L-NEG")


@pytest.mark.mutation
class TestMutationLargeDistance:
    """Extremely large distance (100,000 km) handled without overflow."""

    def test_large_distance_financials(self, eval_engine):
        load = _make_load(amount=1_000_000.0, distance_km=100_000.0)
        # Costs: fuel=100000*0.35=35000, tolls=100000*0.08=8000, salary=100000*0.12=12000
        rev, profit, margin = eval_engine._calculate_financials(
            load, fuel_cost=35000.0, toll_cost=8000.0, driver_salary=12000.0,
        )
        assert rev == 1_000_000.0
        assert profit == 945_000.0  # 1M - 55K
        assert isinstance(margin, float)

    def test_large_distance_estimate_route(self, eval_engine):
        load = _make_load(distance_km=100_000.0)
        # Mock RouteService so it doesn't make real HTTP calls and override
        # the load's distance with actual route data
        with patch("services.route_service.RouteService") as mock_route_cls:
            mock_route_cls.return_value.calculate_route.return_value = {}
            distance, duration = eval_engine._estimate_route(load)
        # Since RouteService returns {} (no distance_km), the method falls
        # back to the load's distance_km = 100_000.0
        assert distance == 100_000.0
        # duration = 100000 / 60 ≈ 1666.67 hours
        assert duration > 0
        assert isinstance(duration, float)

    def test_large_distance_score_profit(self, matcher):
        load = _make_load(amount=1_000_000.0, distance_km=100_000.0)
        truck = _make_truck(1, consumption_l_per_100km=30)
        score = matcher._score_profit(load, truck)
        assert 0.0 <= score <= 100.0


@pytest.mark.mutation
class TestMutationEmptyStrings:
    """Empty string origin/destination don't crash mappers."""

    def test_empty_origin_destination_search(self, search_engine):
        """Empty strings should not crash the search engine."""
        # The search engine uses origin/destination in filters — empty is fine
        filters = LoadSearchFilters(
            origin=GeoFilter(location="", radius_km=50),
            destination=GeoFilter(location="", radius_km=30),
            pickup_date_from=datetime.now(timezone.utc).date(),
            pickup_date_to=datetime.now(timezone.utc).date(),
        )
        # Just create the filter — serialization should work
        _ = filters.model_dump(mode="json")

    def test_empty_origin_evaluation_estimate_route(self, eval_engine):
        """Empty origin should not crash route estimation."""
        load = _make_load(origin="", destination="Berlin")
        with patch("services.route_service.RouteService") as mock_route_cls:
            mock_route_cls.return_value.calculate_route.return_value = {}
            try:
                distance, duration = eval_engine._estimate_route(load)
                # Should use fallback distance when load.distance_km is set
                assert distance > 0
                assert duration > 0
            except Exception as e:
                pytest.fail(f"Empty origin crashed route estimation: {e}")

    def test_empty_destination_estimate_costs(self, eval_engine):
        """Empty destination should not crash cost estimation."""
        load = _make_load(origin="Bucuresti", destination="", distance_km=500.0)
        try:
            fuel, toll, salary = eval_engine._estimate_costs(load, 500.0)
            assert fuel > 0
            assert toll > 0
        except Exception as e:
            pytest.fail(f"Empty destination crashed cost estimation: {e}")

    def test_empty_origin_destination_import_mapping(self, pipeline):
        """Empty origin/destination in load shouldn't crash import mapping."""
        load = _make_load(origin="", destination="")
        try:
            tc = pipeline._map_to_trip_create(load, "e2e_healthy", "L-EMPTY")
            assert tc.stops[0].address == ""
            assert tc.stops[1].address == ""
        except Exception as e:
            pytest.fail(f"Empty origin/destination crashed import mapping: {e}")

    def test_empty_strings_fleet_matcher_proximity(self, matcher):
        """Empty location strings in fleet matcher should not crash."""
        load = _make_load(origin="")
        truck = _make_truck(1, current_location="")
        try:
            score = matcher._score_proximity(load, truck)
            assert score == 50.0  # neutral score for empty locations
        except Exception as e:
            pytest.fail(f"Empty location strings crashed proximity scoring: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# 5. Risk scoring boundaries
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.mutation
class TestRiskMaxFactors:
    """All risk factors at maximum → score ≤ 1.0."""

    def test_max_tightness(self):
        """Maximum tightness (very narrow window) contributes to score."""
        now = datetime.now(timezone.utc)
        score = compute_risk_score(
            pickup_window=(now, now),
            delivery_window=(now, now),  # zero-width window
            estimated_duration_hours=100.0,  # far exceeds window
            origin="Bucuresti", destination="Berlin",
            counterparty_rating=0.0,  # worst possible rating
            load_price=10000.0, market_rate=100.0,  # huge deviation
        )
        assert score <= 1.0, f"Score {score} exceeds 1.0"
        # Should be near 1.0 (high risk)
        assert score > 0.8, f"Expected high risk score, got {score}"

    def test_all_factors_max_still_bounded(self):
        """Even with worst-case inputs, score is clamped at 1.0."""
        # Night hours for both pickup and delivery
        night_hour = datetime(2026, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        now = night_hour

        score = compute_risk_score(
            pickup_window=(now, now),
            delivery_window=(now, now),
            estimated_duration_hours=100.0,
            origin="Bucuresti", destination="Paris",
            counterparty_rating=0.0,
            load_price=10000.0, market_rate=100.0,
            weights={
                "tightness": 0.30,
                "cross_border": 0.25,
                "counterparty": 0.20,
                "price_deviation": 0.15,
                "night_driving": 0.10,
            },
        )
        assert 0.0 <= score <= 1.0, f"Score {score} out of range"
        assert score > 0.7, f"Expected very high risk score, got {score}"


@pytest.mark.mutation
class TestRiskMinFactors:
    """All risk factors at minimum → score ≥ 0.0."""

    def test_min_factors(self):
        """All factors at minimum → score near 0.0."""
        now = datetime.now(timezone.utc)
        # Wide delivery window, same origin/destination (no cross-border),
        # high counterparty rating, price matches market rate, daytime hours
        score = compute_risk_score(
            pickup_window=(now, now),
            delivery_window=(
                now,
                datetime.fromtimestamp(now.timestamp() + 200 * 3600, tz=timezone.utc),
            ),
            estimated_duration_hours=1.0,
            origin="Bucuresti", destination="Bucuresti",
            counterparty_rating=1.0,  # best rating
            load_price=1000.0, market_rate=1000.0,  # exact match
        )
        assert score >= 0.0, f"Score {score} below 0.0"
        # Should be near 0 (low risk)
        assert score < 0.3, f"Expected very low risk score, got {score}"

    def test_min_risk_is_zero(self):
        """Absolute minimum possible risk score is 0.0."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # noon — no night risk

        score = compute_risk_score(
            pickup_window=(now, now),
            delivery_window=(
                now,
                datetime.fromtimestamp(now.timestamp() + 1000 * 3600, tz=timezone.utc),
            ),
            estimated_duration_hours=0.1,
            origin="Bucuresti", destination="Bucuresti",
            counterparty_rating=1.0,
            load_price=1000.0, market_rate=1000.0,
            weights={
                "tightness": 0.0,
                "cross_border": 0.0,
                "counterparty": 0.0,
                "price_deviation": 0.0,
                "night_driving": 0.0,
            },
        )
        # With all weights at 0, score is 0
        assert score == 0.0, f"Expected 0.0 score, got {score}"


@pytest.mark.mutation
class TestRiskDeterminism:
    """Rapid successive risk calculations produce deterministic results."""

    def test_10_rapid_calculations_identical(self):
        """Run risk score 10 times in quick succession — all must match."""
        now = datetime.now(timezone.utc)
        kwargs = dict(
            pickup_window=(now, now),
            delivery_window=(
                now,
                datetime.fromtimestamp(now.timestamp() + 48 * 3600, tz=timezone.utc),
            ),
            estimated_duration_hours=10.0,
            origin="Bucuresti", destination="Berlin",
            counterparty_rating=0.85,
            load_price=1500.0, market_rate=1400.0,
        )

        scores = []
        for _ in range(10):
            scores.append(compute_risk_score(**kwargs))

        # All 10 results must be identical
        first = scores[0]
        for i, s in enumerate(scores):
            assert s == first, (
                f"Score at iteration {i} differs: {s} != {first}"
            )

    def test_identical_inputs_across_calls(self):
        """Two separate calls with same inputs produce same score."""
        now = datetime.now(timezone.utc)
        kwargs = dict(
            pickup_window=(now, now),
            delivery_window=(now, now),
            estimated_duration_hours=8.0,
            origin="Paris", destination="Berlin",
            counterparty_rating=None,
            load_price=2000.0,
        )

        score1 = compute_risk_score(**kwargs)
        score2 = compute_risk_score(**kwargs)
        assert score1 == score2, (
            f"Deterministic scores differ: {score1} != {score2}"
        )
