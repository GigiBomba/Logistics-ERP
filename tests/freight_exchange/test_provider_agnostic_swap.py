"""Freight provider-swap test — §6.3 provider-agnostic discipline, in-suite.

Deferred as "staging" earlier; now done mechanically in the test suite.

What this proves
----------------
The mobile ``FreightLoad`` model (``freight_load.dart``) consumes EXACTLY the
provider-agnostic keys ``id, origin, destination, cargo_type, price, currency,
pickup_date, deadline_date, weight_kg, distance_km`` (plus the optional
``provider_id`` segment parsed by ``fromJson``).  The backend load-board
contract (``FreightLoadListItem`` in ``backend/api/v1/freight_exchange.py``)
must return the SAME shape regardless of which freight-exchange provider is the
ACTIVE adapter — no TIMOCOM/Trans.eu field name ever leaks into the wire.

The adapter factory mechanism (found in this session)
------------------------------------------------------
- ``services/freight_exchange/registry.py`` is the **factory**: adapters
  self-register via ``@register_freight_provider`` into the module-level
  ``_registry: dict[str, FreightProviderAdapter]`` keyed by ``provider_id``,
  and are looked up through ``get_adapter(provider_id)``.
- The **active provider for a company** is configured in
  ``SearchEngineService.search_loads`` (``services/freight_exchange/search.py``)
  via ``ConnectionManagerService.list_connected_provider_ids(company_id)`` —
  each connected id is then resolved through the registry.
- The registry is a plain dict, so the active adapter **is swappable
  in-process**: this test swaps ``_registry[provider_id]`` to a stub adapter
  (whose ``search_loads`` returns results produced by the REAL provider mappers
  — ``TimocomAdapter._map_result`` / ``TransEuAdapter._map_freight_to_result``
  — so the real mapping discipline is exercised, with zero network).

The endpoint is driven through the repo's standard TestClient +
dependency-override conventions (``tests/freight_exchange/test_api_contract.py``).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.main import create_app
from config import Config
from models.freight_exchange_models import (
    LoadSearchFilters,
    ProviderCapabilities,
    ProviderSession,
)
from services.freight_exchange import registry
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.adapters.timocom import TimocomAdapter
from services.freight_exchange.adapters.trans_eu import TransEuAdapter
from tests.test_helpers import InMemoryDB


# ═══════════════════════════════════════════════════════════════════════════
# Mobile contract keys — sourced from the mobile repo
# (mobile/lib/features/freight_exchange/models/freight_load.dart and
#  mobile/test/features/freight_exchange/test_freight_provider_agnostic.dart)
# ═══════════════════════════════════════════════════════════════════════════

# The fixed provider-agnostic contract field names (Dart _contractFieldNames).
MOBILE_FIXED_CONTRACT_KEYS = {
    "id", "origin", "destination", "cargo_type", "price", "currency",
    "pickup_date", "deadline_date", "weight_kg", "distance_km",
}

# Every key the Dart ``FreightLoad.fromJson`` reads — the superset the model
# can parse (includes the optional provider_id segment).
MOBILE_FROM_JSON_KEYS = MOBILE_FIXED_CONTRACT_KEYS | {"provider_id"}

# Provider-specific field names that must NEVER appear on the wire (§6.3).
FORBIDDEN_KEYS = {
    "provider_id", "provider_load_id", "result_id",
    "trailer_type", "pickup_window", "delivery_window", "raw_payload", "adr",
    "loading", "unloading", "publication", "requirements", "loads",
    "loadingPlace", "unloadingPlace", "loadingDateFrom", "unloadingDateTo",
    "loading_country", "delivery_country", "loading_type", "freight_id",
}


# ═══════════════════════════════════════════════════════════════════════════
# Canned provider payloads — real shapes, produced by the REAL adapter mappers.
# ═══════════════════════════════════════════════════════════════════════════

RAW_TIMOCOM: Dict[str, Any] = {
    "id": "TIM-77",
    "loadingPlace": "Berlin",
    "unloadingPlace": "Paris",
    "loadingDateFrom": "2026-08-01T08:00:00+02:00",
    "loadingDateTo": "2026-08-01T12:00:00+02:00",
    "unloadingDateFrom": "2026-08-02T08:00:00+02:00",
    "unloadingDateTo": "2026-08-02T12:00:00+02:00",
    "price": 1450.00,
    "currency": "EUR",
    "distanceKm": 1200.0,
    "vehicleType": "curtain",
    "adr": False,
    "weightKg": 21000,
    "loadingType": "FTL",
    "loadingCountry": "DE",
    "unloadingCountry": "FR",
}

RAW_TRANS_EU: Dict[str, Any] = {
    "id": 9001,
    "loading": {
        "place": {"country": "DE", "locality": "Berlin", "postal_code": "10115"},
        "timespans": {"begin": "2026-08-01T08:00:00+02:00", "end": "2026-08-01T12:00:00+02:00"},
    },
    "unloading": {
        "place": {"country": "FR", "locality": "Paris", "postal_code": "75001"},
        "timespans": {"begin": "2026-08-02T08:00:00+02:00", "end": "2026-08-02T12:00:00+02:00"},
    },
    "publication": {"price": {"value": 1450.00, "currency": "EUR"}},
    "requirements": {"required_truck_bodies": ["curtain"], "required_adr_classes": []},
    "loads": [{"weight": 21000}],
    "ftl": True,
    "transit_time": 1200,
}

# The canned LoadSearchResult list is built by the REAL adapter mappers, so the
# endpoint swap exercises the real Trans.eu / TIMOCOM normalization — with the
# network call replaced by a stub.
TIMOCOM_MAPPED = TimocomAdapter()._map_result(RAW_TIMOCOM)
TRANS_EU_MAPPED = TransEuAdapter()._map_freight_to_result(RAW_TRANS_EU)


# Shared normalized fields whose values the two providers produce identically.
SHARED_NORMALIZED_FIELDS = {
    "price", "currency", "cargo_type", "weight_kg", "pickup_date", "deadline_date",
}


class _ProviderStub(FreightProviderAdapter):
    """A registry-swapped adapter whose ``search_loads`` returns canned results.

    Only ``search_loads`` is exercised by the endpoint flow; the other abstract
    methods are never called (health/session management is bypassed by the
    ConnectionManager mock), so they raise to prove they are not on the path.
    """

    def __init__(self, provider_id: str, results) -> None:
        self.provider_id = provider_id
        self._results = results

    async def search_loads(self, session, filters) -> list:
        return self._results

    async def authenticate(self, creds):
        raise NotImplementedError("stub adapter — authenticate not on test path")

    async def refresh_session(self, session):
        raise NotImplementedError("stub adapter — refresh_session not on test path")

    async def test_connection(self, session):
        raise NotImplementedError("stub adapter — test_connection not on test path")

    async def get_load(self, session, load_id):
        return None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supported_filters=[
                "origin", "destination", "pickup_date_from", "pickup_date_to",
                "delivery_date_from", "delivery_date_to", "trailer_type",
                "adr_required", "weight_kg_min", "weight_kg_max",
                "distance_km_max", "loading_type", "loading_country",
                "delivery_country", "sort_by", "sort_order", "min_trucks",
            ],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures — test_api_contract.py conventions.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db() -> InMemoryDB:
    return InMemoryDB()


@pytest.fixture
def client(db: InMemoryDB, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with mocked get_db + require_dispatcher (dispatcher role)."""
    # Deterministic regardless of shell/.env state: no API-key gate, non-prod.
    monkeypatch.setattr(Config, "API_KEY", "")
    monkeypatch.setenv("OPERION_ENV", "testing")

    app = create_app()

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    async def _mock_dispatcher() -> Dict[str, Any]:
        return {
            "id": 1,
            "email": "dispatcher@test.com",
            "role": "dispatcher",
            "is_admin": False,
            "company_id": 1,
        }

    app.dependency_overrides[require_dispatcher] = _mock_dispatcher

    return TestClient(app)


def _activate_provider(
    monkeypatch: pytest.MonkeyPatch,
    provider_id: str,
    adapter: FreightProviderAdapter,
    provider_ids: list[str],
) -> None:
    """Swap the ACTIVE provider per the factory mechanism.

    1. Registry (the factory): replace the entry for *provider_id* with the
       stub adapter — ``get_adapter()`` returns it for every lookup.
    2. Selection (the active-provider config): the engine's
       ``ConnectionManagerService`` reports *provider_id* as the connected /
       active provider for the company.
    """
    monkeypatch.setitem(registry._registry, provider_id, adapter)

    conn_mgr = MagicMock()
    conn_mgr.list_connected_provider_ids.return_value = provider_ids
    conn_mgr.is_connected.return_value = True
    conn_mgr.get_session = AsyncMock(
        return_value=ProviderSession(
            company_id=1,
            provider_id=provider_id,
            access_token_encrypted="stub-token",
            expires_at=datetime.now(timezone.utc),
        )
    )
    mock_factory = MagicMock(return_value=conn_mgr)
    monkeypatch.setattr(
        "services.freight_exchange.search.ConnectionManagerService", mock_factory
    )


def _list_loads(client: TestClient) -> list[Dict[str, Any]]:
    resp = client.get("/api/v1/freight/loads")
    assert resp.status_code == 200, f"GET /freight/loads failed: {resp.text}"
    items = resp.json()
    assert isinstance(items, list) and len(items) == 1, items
    return items


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderSwap:
    """The ACTIVE adapter can be swapped to Trans.eu in-process, and the
    endpoint still returns the identical provider-agnostic mobile contract."""

    def test_factory_registry_is_swappable_in_process(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Documentation of the factory mechanism: the registry is a plain dict
        keyed by provider_id, and ``get_adapter`` returns whatever is active."""
        assert registry.list_adapters()  # real adapters self-registered

        stub = _ProviderStub("trans_eu", [TRANS_EU_MAPPED])
        monkeypatch.setitem(registry._registry, "trans_eu", stub)

        assert registry.get_adapter("trans_eu") is stub
        assert stub.provider_id == "trans_eu"
        # And the real TIMOCOM adapter remains registered alongside it.
        assert registry.get_adapter("timocom") is not None

    def test_trans_eu_swap_returns_mobile_contract(
        self, monkeypatch: pytest.MonkeyPatch, client: TestClient,
    ) -> None:
        """Active adapter = Trans.eu stub → GET /freight/loads returns the
        mobile contract: EXACT fixed key set, parseable by the Dart model,
        with no provider-specific field leakage."""
        _activate_provider(monkeypatch, "trans_eu", _ProviderStub("trans_eu", [TRANS_EU_MAPPED]), ["trans_eu"])

        items = _list_loads(client)
        item = items[0]

        # Exact fixed contract (§6.3) — no extras, no omissions.
        assert set(item.keys()) == MOBILE_FIXED_CONTRACT_KEYS, (
            f"Trans.eu-configured response leaked keys: "
            f"{sorted(set(item.keys()) - MOBILE_FIXED_CONTRACT_KEYS)}"
        )
        # Every key is parseable by the Dart model's fromJson (the optional
        # provider_id is simply absent — the mobile model defaults it to null).
        assert set(item.keys()) <= MOBILE_FROM_JSON_KEYS
        # No provider-specific field names (TIMOCOM/Trans.eu/Teleroute/Wtransnet).
        assert FORBIDDEN_KEYS.isdisjoint(item.keys())

        # Normalized value assertions (the mobile contract's semantics).
        assert item["id"] == "9001"
        assert item["origin"].startswith("Berlin")
        assert item["destination"].startswith("Paris")
        assert item["cargo_type"] == "curtain"
        assert item["price"] == 1450.0
        assert item["currency"] == "EUR"
        assert item["weight_kg"] == 21000.0
        assert isinstance(item["distance_km"], str)  # Dart: String? distanceKm
        assert item["pickup_date"] == "2026-08-01T08:00:00+02:00"
        assert item["deadline_date"] == "2026-08-02T12:00:00+02:00"

    def test_timocom_and_trans_eu_responses_have_identical_shape(
        self, monkeypatch: pytest.MonkeyPatch, client: TestClient,
    ) -> None:
        """The §6.3 discipline, mechanically proven: whichever provider is the
        ACTIVE adapter, the wire response is the identical provider-agnostic
        shape — same key set, same normalized field values."""
        _activate_provider(monkeypatch, "timocom", _ProviderStub("timocom", [TIMOCOM_MAPPED]), ["timocom"])
        timocom_item = _list_loads(client)[0]

        # Swap the ACTIVE adapter to Trans.eu on the SAME endpoint.
        monkeypatch.undo()
        _activate_provider(monkeypatch, "trans_eu", _ProviderStub("trans_eu", [TRANS_EU_MAPPED]), ["trans_eu"])
        trans_eu_item = _list_loads(client)[0]

        # Identical key set — the core provider-agnostic guarantee.
        assert set(timocom_item.keys()) == set(trans_eu_item.keys())
        assert set(timocom_item.keys()) == MOBILE_FIXED_CONTRACT_KEYS

        # Identical normalized values for every field both providers carry.
        for field in sorted(SHARED_NORMALIZED_FIELDS):
            assert timocom_item[field] == trans_eu_item[field], (
                f"Provider swap changed the {field!r} value on the wire"
            )
        # Fields that legitimately differ are provider DATA (id / locality /
        # distance), never provider field NAMES.
        assert timocom_item["id"] != trans_eu_item["id"]

    def test_mobile_model_parses_both_provider_responses(
        self, monkeypatch: pytest.MonkeyPatch, client: TestClient,
    ) -> None:
        """Cross-check against the Dart model: every key the backend emits is a
        key ``FreightLoad.fromJson`` reads (from freight_load.dart)."""
        for provider_id, mapped in (
            ("timocom", TIMOCOM_MAPPED),
            ("trans_eu", TRANS_EU_MAPPED),
        ):
            monkeypatch.undo()
            _activate_provider(monkeypatch, provider_id, _ProviderStub(provider_id, [mapped]), [provider_id])
            item = _list_loads(client)[0]
            assert set(item.keys()) <= MOBILE_FROM_JSON_KEYS, (
                f"{provider_id} response not fully parseable by the mobile "
                f"FreightLoad.fromJson: {sorted(set(item.keys()) - MOBILE_FROM_JSON_KEYS)}"
            )

    def test_mapper_level_normalization_of_both_provider_payloads(
        self,
    ) -> None:
        """Unit-level backstop: even without the registry swap, the mapping
        layer (`_to_freight_load_item`-equivalent) normalizes BOTH providers'
        raw payloads to the identical contract — the §6.3 discipline lives in
        the mapper, so no provider-specific field can reach the wire."""
        from backend.api.v1.freight_exchange import _to_freight_load_item

        timocom_item = _to_freight_load_item(TIMOCOM_MAPPED).model_dump()
        trans_eu_item = _to_freight_load_item(TRANS_EU_MAPPED).model_dump()

        assert set(timocom_item.keys()) == set(trans_eu_item.keys())
        assert set(timocom_item.keys()) == MOBILE_FIXED_CONTRACT_KEYS
        assert FORBIDDEN_KEYS.isdisjoint(timocom_item.keys())
        assert FORBIDDEN_KEYS.isdisjoint(trans_eu_item.keys())
        for field in sorted(SHARED_NORMALIZED_FIELDS):
            assert timocom_item[field] == trans_eu_item[field]

        # The normalized item JSON is the mobile contract fixture shape.
        wire = json.loads(json.dumps(timocom_item))
        assert set(wire.keys()) == MOBILE_FIXED_CONTRACT_KEYS
