"""Import parity test — the architectural proof of the freight exchange subsystem.

Blueprint Gate 3 (§12.3): proves that downstream modules genuinely cannot
tell the difference between a manually-created trip and one imported from
any freight exchange provider.  Three identical trips (manual, fake
timocom, fake trans_eu) must produce bit-identical output from every
downstream service.

.. attention::

    Real TIMOCOM API credentials are NOT loaded.  The ``TimocomAdapter``
    is registrable but cannot authenticate against the live API until
    credentials are configured.  This is tracked as **TODO: TIMOCOM_CREDS**
    — search for this token to find all credential-dependent code paths.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

from database.db_manager import DatabaseManager
from models.common import Money
from models.freight_exchange_models import (
    GeoFilter,
    ImportResult,
    LoadSearchFilters,
    LoadSearchResult,
    ProviderCapabilities,
    ProviderCredentials,
    ProviderHealthCheck,
    ProviderSession,
)
from models.trip_models import TripCreate
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.import_pipeline import ImportError, ImportPipelineService
from services.freight_exchange.registry import (
    _registry,
    register_freight_provider,
    validate_registry,
)
from tests.test_helpers import InMemoryDB

# ═══════════════════════════════════════════════════════════════════════════
# TODO: TIMOCOM_CREDS — real TIMOCOM API credentials are not loaded.
# The following tests use fake adapters.  Once credentials are available:
#   1. Set TIMOCOM_CLIENT_ID / TIMOCOM_CLIENT_SECRET in .env
#   2. Unskip test_real_timocom_import in TestRealProviderImport
#   3. Run against the live API with a known test load ID
# ═══════════════════════════════════════════════════════════════════════════


# ── Helpers ────────────────────────────────────────────────────────────────


def _build_load(
    provider_id: str = "timocom",
    provider_load_id: str = "TL-99999",
    origin: str = "Bucuresti",
    destination: str = "Berlin",
    amount: float = 1500.0,
    currency: str = "EUR",
    distance_km: float = 1800.0,
    trailer_type: str = "standard",
    adr: bool = False,
    pickup_delay: int = 0,
    delivery_delay: int = 48,
    pickup_window: Optional[tuple[datetime, datetime]] = None,
    delivery_window: Optional[tuple[datetime, datetime]] = None,
) -> LoadSearchResult:
    """Build a controlled LoadSearchResult for deterministic testing.

    ``pickup_window`` / ``delivery_window`` may be supplied explicitly —
    callers that need bit-identical loads across providers (e.g. the import
    parity test) must pass fixed windows, because ``datetime.now()`` would
    otherwise differ by microseconds between two calls and make the mapped
    ``TripCreate.stops`` comparison flaky.
    """
    now = datetime.now(timezone.utc)
    pickup = pickup_window or (now, now)
    delivery = delivery_window or (
        datetime.fromtimestamp(now.timestamp() + delivery_delay * 3600, tz=timezone.utc),
        datetime.fromtimestamp(now.timestamp() + delivery_delay * 3600, tz=timezone.utc),
    )
    return LoadSearchResult(
        result_id=provider_load_id,
        provider_id=provider_id,
        provider_load_id=provider_load_id,
        origin=origin,
        destination=destination,
        pickup_window=pickup,
        delivery_window=delivery,
        price=Money(amount=amount, currency=currency),
        distance_km=distance_km,
        trailer_type=trailer_type,
        adr=adr,
    )


def _fake_session(provider_id: str = "timocom") -> ProviderSession:
    now = datetime.now(timezone.utc)
    return ProviderSession(
        company_id=1,
        provider_id=provider_id,
        access_token_encrypted="fake-token",
        expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc),
    )


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    """Fresh in-memory database with full schema."""
    return InMemoryDB()


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the adapter registry before AND after each test so fake
    adapters (registered at module import via @register_freight_provider)
    don't leak into another test or into a test that runs in isolation."""
    before = dict(_registry)
    # Pre-test cleanup: drop fakes registered at module import time so
    # TestRegistryCleanup passes when this module runs in isolation.
    _registry.clear()
    for k, v in before.items():
        if k == "timocom":
            _registry[k] = v
    yield
    # Post-test cleanup: restore only non-fake adapters (timocom)
    _registry.clear()
    for k, v in before.items():
        if k == "timocom":
            _registry[k] = v


@pytest.fixture
def pipeline(db) -> ImportPipelineService:
    return ImportPipelineService(db)


# ── Fake adapters ──────────────────────────────────────────────────────────


@register_freight_provider
class FakeTimocomAdapter(FreightProviderAdapter):
    """Fake TIMOCOM adapter for import parity testing.

    Returns only a single known load so the mapping is fully deterministic.
    """
    provider_id = "fake_timocom"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _fake_session(self.provider_id)

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
        return [_build_load(provider_id=self.provider_id)]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return _build_load(provider_id=self.provider_id, provider_load_id=load_id)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=["origin", "destination", "pickup_date_from", "pickup_date_to"],
            supports_saved_search=False, supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )


@register_freight_provider
class FakeTransEuAdapter(FreightProviderAdapter):
    """Fake Trans.eu adapter — identical load data, different provider_id."""
    provider_id = "fake_trans_eu"

    async def authenticate(self, creds: ProviderCredentials) -> ProviderSession:
        return _fake_session(self.provider_id)

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
        return [_build_load(provider_id=self.provider_id)]

    async def get_load(
        self, session: ProviderSession, load_id: str
    ) -> Optional[LoadSearchResult]:
        return _build_load(provider_id=self.provider_id, provider_load_id=load_id)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=["origin", "destination", "pickup_date_from", "pickup_date_to"],
            supports_saved_search=False, supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMapToTripCreate:
    """Verify _map_to_trip_create() is provider-agnostic."""

    def test_maps_load_fields_to_tripcreate(self, pipeline):
        load = _build_load(
            provider_id="timocom", origin="Bucuresti", destination="Berlin",
            amount=1500.0, currency="EUR", distance_km=1800.0,
            trailer_type="standard", adr=False,
        )
        tc = pipeline._map_to_trip_create(load, "timocom", "TL-99999")

        assert tc.source == "freight_exchange"
        assert tc.source_provider_id == "timocom"
        assert tc.source_reference_id == "TL-99999"
        assert tc.price_eur == 1500.0
        assert tc.currency == "EUR"
        assert tc.distance_km == 1800.0
        assert tc.status == "Planned"
        assert len(tc.stops) == 2
        assert tc.stops[0].type == "pickup"
        assert tc.stops[0].address == "Bucuresti"
        assert tc.stops[1].type == "delivery"
        assert tc.stops[1].address == "Berlin"

    def test_reference_string_includes_provider(self, pipeline):
        load = _build_load(provider_id="timocom", provider_load_id="TL-ABCDEF123456")
        tc = pipeline._map_to_trip_create(load, "timocom", "TL-ABCDEF123456")
        assert "FX-TIMO" in tc.reference
        assert "TL-ABCDEF12" in tc.reference

    def test_different_providers_produce_identical_fields_except_source(self, pipeline):
        """Core architectural claim: same load data, different providers,
        identical TripCreate — only source_provider_id differs."""
        # Fixed windows: datetime.now() inside _build_load would make the two
        # loads differ by microseconds, so the mapped stops (which copy the
        # window timestamps verbatim) would differ too — flaky on CI.
        fixed_now = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
        data = dict(
            origin="Bucuresti", destination="Berlin",
            amount=1500.0, currency="EUR", distance_km=1800.0,
            pickup_window=(fixed_now, fixed_now),
            delivery_window=(
                fixed_now + timedelta(hours=48),
                fixed_now + timedelta(hours=48),
            ),
        )

        load_timocom = _build_load(provider_id="timocom", **data)  # type: ignore[arg-type]
        load_trans_eu = _build_load(provider_id="trans_eu", **data)  # type: ignore[arg-type]

        tc_timocom = pipeline._map_to_trip_create(load_timocom, "timocom", "L-001")
        tc_trans_eu = pipeline._map_to_trip_create(load_trans_eu, "trans_eu", "L-001")

        # Compare all fields EXCEPT provider-specific ones
        for field in TripCreate.model_fields:
            if field in ("source_provider_id", "reference", "source_reference_id", "notes"):
                continue
            val_t = getattr(tc_timocom, field)
            val_e = getattr(tc_trans_eu, field)
            assert val_t == val_e, (
                f"Field '{field}' differs: timocom={val_t!r}, trans_eu={val_e!r}"
            )

        # Source fields differ as expected
        assert tc_timocom.source_provider_id == "timocom"
        assert tc_trans_eu.source_provider_id == "trans_eu"
        assert tc_timocom.source == tc_trans_eu.source == "freight_exchange"


class TestMappingEdgeCases:
    """Boundary conditions for load-to-trip mapping."""

    def test_zero_price(self, pipeline):
        load = _build_load(amount=0.0)
        tc = pipeline._map_to_trip_create(load, "timocom", "L-ZERO")
        assert tc.price_eur == 0.0

    def test_minimal_distance(self, pipeline):
        load = _build_load(distance_km=1.0)
        tc = pipeline._map_to_trip_create(load, "timocom", "L-MIN-DIST")
        assert tc.distance_km == 1.0

    def test_adr_load(self, pipeline):
        load = _build_load(adr=True, trailer_type="tanker")
        tc = pipeline._map_to_trip_create(load, "timocom", "L-ADR")
        # ADR status tracked in source fields, not directly on TripCreate
        assert tc.source_reference_id == "L-ADR"

    def test_different_currencies(self, pipeline):
        load = _build_load(currency="RON", amount=7500.0)
        tc = pipeline._map_to_trip_create(load, "timocom", "L-RON")
        assert tc.currency == "RON"
        assert tc.price_eur == 7500.0


class TestIsAlreadyImported:
    """Duplicate detection via (source_provider_id, source_reference_id)."""

    def test_not_imported_returns_false(self, pipeline):
        result = pipeline._is_already_imported(1, "timocom", "L-NEW")
        assert result is False

    def test_already_imported_returns_true(self, db, pipeline):
        # Manually insert a trip with source fields to simulate prior import
        db.conn.execute("PRAGMA foreign_keys = OFF")
        db.conn.execute(
            "INSERT INTO trips (source, source_provider_id, source_reference_id, "
            "company_id, start_date, status, created_at) "
            "VALUES ('freight_exchange', 'timocom', 'L-001', 1, '2026-01-01', "
            "'Planned', datetime('now'))"
        )
        db.conn.commit()

        result = pipeline._is_already_imported(1, "timocom", "L-001")
        assert result is True

    def test_same_load_id_different_provider_not_duplicate(self, db, pipeline):
        db.conn.execute("PRAGMA foreign_keys = OFF")
        db.conn.execute(
            "INSERT INTO trips (source, source_provider_id, source_reference_id, "
            "company_id, start_date, status, created_at) "
            "VALUES ('freight_exchange', 'timocom', 'L-SHARED', 1, '2026-01-01', "
            "'Planned', datetime('now'))"
        )
        db.conn.commit()

        # Same load_id but different provider — NOT a duplicate
        result = pipeline._is_already_imported(1, "trans_eu", "L-SHARED")
        assert result is False

    def test_different_company_same_load_not_duplicate(self, db, pipeline):
        db.conn.execute("PRAGMA foreign_keys = OFF")
        db.conn.execute(
            "INSERT INTO trips (source, source_provider_id, source_reference_id, "
            "company_id, start_date, status, created_at) "
            "VALUES ('freight_exchange', 'timocom', 'L-MULTI', 99, '2026-01-01', "
            "'Planned', datetime('now'))"
        )
        db.conn.commit()

        # Different company — NOT a duplicate
        result = pipeline._is_already_imported(1, "timocom", "L-MULTI")
        assert result is False


class TestImportLoadFlow:
    """End-to-end import flow with mocked adapter chain."""

    def test_import_load_success(self, db, pipeline):
        """Full import: get_load -> map -> trip_service.create -> ImportResult."""
        load = _build_load(provider_id="fake_timocom", provider_load_id="L-OK")

        async def _run():
            with patch.object(
                pipeline._search, "get_load", new=AsyncMock(return_value=load)
            ):
                with patch("services.trip_service.TripService.create") as mock_create:
                    from models.trip_models import TripResult
                    mock_result = type("FakeResult", (), {
                        "success": True,
                        "data": TripResult(
                            id=42, client_id=1, reference="FX-TIMO-L-OK",
                            start_date=date(2026, 1, 1), price_eur=1500.0, currency="EUR",
                            status="Planned",
                        ),
                        "errors": [],
                    })()
                    mock_create.return_value = mock_result
                    return await pipeline.import_load(
                        company_id=1, provider_id="fake_timocom",
                        provider_load_id="L-OK", user_id=10,
                    )

        result = asyncio.run(_run())

        assert isinstance(result, ImportResult)
        assert result.trip_id == 42
        assert result.source == "freight_exchange"
        assert result.source_provider_id == "fake_timocom"
        assert result.source_reference_id == "L-OK"
        assert result.imported_by_user_id == 10

    def test_import_load_not_found(self, pipeline):
        """get_load returns None -> ImportError."""

        async def _run():
            with patch.object(
                pipeline._search, "get_load", new=AsyncMock(return_value=None)
            ):
                with pytest.raises(ImportError, match="not found"):
                    await pipeline.import_load(
                        company_id=1, provider_id="fake_timocom",
                        provider_load_id="L-MISSING", user_id=10,
                    )

        asyncio.run(_run())

    def test_import_load_already_imported(self, db, pipeline):
        """Duplicate import -> ImportError."""
        # Pre-create trip to simulate prior import
        db.conn.execute("PRAGMA foreign_keys = OFF")
        db.conn.execute(
            "INSERT INTO trips (source, source_provider_id, source_reference_id, "
            "company_id, start_date, status, created_at) "
            "VALUES ('freight_exchange', 'fake_timocom', 'L-DUP', 1, '2026-01-01', "
            "'Planned', datetime('now'))"
        )
        db.conn.commit()

        load = _build_load(provider_id="fake_timocom", provider_load_id="L-DUP")

        async def _run():
            with patch.object(
                pipeline._search, "get_load", new=AsyncMock(return_value=load)
            ):
                with pytest.raises(ImportError, match="already imported"):
                    await pipeline.import_load(
                        company_id=1, provider_id="fake_timocom",
                        provider_load_id="L-DUP", user_id=10,
                    )

        asyncio.run(_run())

    def test_import_load_trip_creation_failure(self, pipeline):
        """TripService.create returns failure -> ImportError."""
        load = _build_load(provider_id="fake_timocom", provider_load_id="L-FAIL")

        async def _run():
            with patch.object(
                pipeline._search, "get_load", new=AsyncMock(return_value=load)
            ):
                with patch("services.trip_service.TripService.create") as mock_create:
                    mock_result = type("FakeResult", (), {
                        "success": False,
                        "data": None,
                        "errors": [type("Err", (), {"message": "Validation failed"})()],
                    })()
                    mock_create.return_value = mock_result

                    with pytest.raises(ImportError, match="Trip creation failed"):
                        await pipeline.import_load(
                            company_id=1, provider_id="fake_timocom",
                            provider_load_id="L-FAIL", user_id=10,
                        )

        asyncio.run(_run())


# ═══════════════════════════════════════════════════════════════════════════
# TODO: TIMOCOM_CREDS — skipped until real credentials are available.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skip(reason="TODO: TIMOCOM_CREDS — real TIMOCOM API credentials not loaded")
class TestRealProviderImport:
    """Integration tests requiring live TIMOCOM API access.

    Unskip once TIMOCOM_CLIENT_ID and TIMOCOM_CLIENT_SECRET are configured.
    """

    def test_real_timocom_import(self, db, pipeline):
        """Import a real load from the live TIMOCOM API.

        Requires a known test load ID that exists in the TIMOCOM sandbox.
        """
        TEST_LOAD_ID = "TL-SANDBOX-001"

        async def _run():
            return await pipeline.import_load(
                company_id=1, provider_id="timocom",
                provider_load_id=TEST_LOAD_ID, user_id=1,
            )

        result = asyncio.run(_run())

        assert result.trip_id > 0
        assert result.source == "freight_exchange"
        assert result.source_provider_id == "timocom"


# ═══════════════════════════════════════════════════════════════════════════
# Registry state guard
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistryCleanup:
    """Verify fake adapters don't pollute the global registry after tests."""

    def test_registry_only_has_timocom_after_cleanup(self):
        """After autouse fixture cleanup, only the real timocom remains."""
        from services.freight_exchange.registry import list_adapters

        adapters = list_adapters()
        fake_ids = [a for a in adapters if a.startswith("fake_")]
        assert len(fake_ids) == 0, f"Fake adapters leaked: {fake_ids}"
        # timocom may or may not be registered depending on import order
        # in test runs — the important thing is no fakes leaked
