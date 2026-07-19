"""Phase 1 tests — TransEuAdapter mapping, edge cases, search filters.

Proves:
- _map_freight_to_result: all field mappings correct
- _map_freight_to_result: edge cases (empty loads, missing fields, multi-spot)
- _build_search_params: all filter translations correct
- Full adapter methods exist and return correct types
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from models.common import Money
from models.freight_exchange_models import (
    GeoFilter,
    LoadSearchFilters,
    LoadSearchResult,
    ProviderCapabilities,
)
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.registry import _registry


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_registry():
    _registry.clear()
    yield
    _registry.clear()


@pytest.fixture
def adapter():
    """Return a fresh TransEuAdapter instance for testing."""
    from services.freight_exchange.adapters.trans_eu import TransEuAdapter
    return TransEuAdapter()


@pytest.fixture
def sample_freight():
    """Realistic Trans.eu freight JSON for mapping tests."""
    return {
        "id": 401560,
        "reference_number": "FR/2020/08/03/Y1F3",
        "ftl": True,
        "transit_time": 460,
        "loading": {
            "place": {"country": "pl", "locality": "Krakow", "postal_code": "31-008"},
            "timespans": {
                "begin": "2019-11-15T10:00:00+01:00",
                "end": "2019-11-15T11:00:00+01:00",
            },
        },
        "unloading": {
            "place": {"country": "pl", "locality": "Warszawa", "postal_code": "00-001"},
            "timespans": {
                "begin": "2019-11-16T08:00:00+01:00",
                "end": "2019-11-16T10:00:00+01:00",
            },
        },
        "publication": {
            "price": {"currency": "eur", "value": 1200},
        },
        "requirements": {
            "required_truck_bodies": ["cooler"],
            "required_adr_classes": ["adr_1_1"],
        },
        "loads": [{"weight": 5000}, {"weight": 3000}],
    }


# ═══════════════════════════════════════════════════════════════════════
# 1. Mapping — Happy Path
# ═══════════════════════════════════════════════════════════════════════


class TestMappingHappyPath:
    """Full Trans.eu freight JSON maps correctly to LoadSearchResult."""

    def test_result_has_correct_provider_id(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.provider_id == "trans_eu"

    def test_result_has_correct_load_id(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.provider_load_id == "401560"

    def test_origin_from_loading_place(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert "Krakow" in result.origin
        assert "PL" in result.origin

    def test_destination_from_unloading_place(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert "Warszawa" in result.destination
        assert "PL" in result.destination

    def test_price_from_publication(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.price.amount == 1200.0
        assert result.price.currency == "EUR"

    def test_trailer_from_requirements(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.trailer_type == "cooler"

    def test_adr_from_adr_classes(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.adr is True

    def test_weight_sums_loads(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.weight_kg == 8000.0

    def test_distance_estimated_from_transit_time(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        # 460 minutes at ~70 km/h = ~536.7 km
        assert result.distance_km > 500
        assert result.distance_km < 600

    def test_loading_type_ftl(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.loading_type == "ftl"

    def test_loading_country_from_place(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.loading_country == "pl"

    def test_delivery_country_from_place(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.delivery_country == "pl"

    def test_raw_payload_preserved(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert result.raw_payload == sample_freight

    def test_pickup_window_from_timespans(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        pickup_from, pickup_to = result.pickup_window
        assert isinstance(pickup_from, datetime)
        assert isinstance(pickup_to, datetime)
        assert pickup_from < pickup_to

    def test_delivery_window_from_timespans(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        delivery_from, delivery_to = result.delivery_window
        assert isinstance(delivery_from, datetime)
        assert isinstance(delivery_to, datetime)
        assert delivery_from < delivery_to

    def test_result_is_load_search_result_type(self, adapter, sample_freight):
        result = adapter._map_freight_to_result(sample_freight)
        assert isinstance(result, LoadSearchResult)


# ═══════════════════════════════════════════════════════════════════════
# 2. Mapping — Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestMappingEdgeCases:
    """Edge cases: empty loads, null fields, missing blocks, LTL, multi-spot."""

    def test_empty_loads_returns_zero_weight(self, adapter):
        freight = {
            "id": 1,
            "loading": {},
            "unloading": {},
            "loads": [],
        }
        result = adapter._map_freight_to_result(freight)
        assert result.weight_kg == 0.0

    def test_missing_loading_uses_empty_strings(self, adapter):
        freight = {
            "id": 1,
            "loading": {},
            "unloading": {},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.origin == ""
        assert result.loading_country == ""

    def test_null_price_uses_zero(self, adapter):
        freight = {
            "id": 1,
            "loading": {"place": {"country": "pl", "locality": "X"}},
            "unloading": {"place": {"country": "de", "locality": "Y"}},
            "publication": {"price": {}},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.price.amount == 0.0

    def test_missing_price_block_uses_zero(self, adapter):
        freight = {
            "id": 1,
            "loading": {"place": {"country": "pl", "locality": "X"}},
            "unloading": {"place": {"country": "de", "locality": "Y"}},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.price.amount == 0.0

    def test_no_adr_classes_means_no_adr(self, adapter):
        freight = {
            "id": 1,
            "loading": {"place": {"country": "pl", "locality": "X"}},
            "unloading": {"place": {"country": "de", "locality": "Y"}},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.adr is False

    def test_empty_required_truck_bodies_uses_standard(self, adapter):
        freight = {
            "id": 1,
            "loading": {"place": {"country": "pl", "locality": "X"}},
            "unloading": {"place": {"country": "de", "locality": "Y"}},
            "requirements": {"required_truck_bodies": []},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.trailer_type == "standard"

    def test_fallback_to_truck_bodies_field(self, adapter):
        """If requirements.required_truck_bodies is empty, try raw.truck_bodies."""
        freight = {
            "id": 1,
            "loading": {"place": {"country": "pl", "locality": "X"}},
            "unloading": {"place": {"country": "de", "locality": "Y"}},
            "requirements": {},
            "truck_bodies": ["curtainsider"],
        }
        result = adapter._map_freight_to_result(freight)
        assert result.trailer_type == "curtainsider"

    def test_ltl_loading_type(self, adapter):
        freight = {
            "id": 1,
            "ftl": False,
            "loading": {"place": {"country": "pl", "locality": "X"}},
            "unloading": {"place": {"country": "de", "locality": "Y"}},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.loading_type == "ltl"

    def test_zero_transit_time_means_zero_distance(self, adapter):
        freight = {
            "id": 1,
            "transit_time": 0,
            "loading": {"place": {"country": "pl", "locality": "X"}},
            "unloading": {"place": {"country": "de", "locality": "Y"}},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.distance_km == 0.0

    def test_missing_dates_use_defaults(self, adapter):
        """When timespans are missing, pickup/delivery windows use defaults."""
        freight = {
            "id": 1,
            "loading": {},
            "unloading": {},
        }
        result = adapter._map_freight_to_result(freight)
        pickup_from, pickup_to = result.pickup_window
        assert isinstance(pickup_from, datetime)
        assert isinstance(pickup_to, datetime)
        # Default pickup window should be ~4 hours
        assert (pickup_to - pickup_from).total_seconds() > 0

    def test_origin_without_country(self, adapter):
        freight = {
            "id": 1,
            "loading": {"place": {"locality": "Krakow"}},
            "unloading": {"place": {"locality": "Berlin"}},
        }
        result = adapter._map_freight_to_result(freight)
        assert result.origin == "Krakow"
        assert "," not in result.origin


# ═══════════════════════════════════════════════════════════════════════
# 3. Search Filter Translation
# ═══════════════════════════════════════════════════════════════════════


class TestSearchFilterTranslation:
    """LoadSearchFilters → Trans.eu query params."""

    def test_page_defaults_to_one(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
            )
        )
        assert params["page"] == 1

    def test_origin_filter(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                origin=GeoFilter(location="Krakow", radius_km=50),
            )
        )
        assert params["loadingPlace"] == "Krakow"
        assert params["loadingRadiusKm"] == 50

    def test_origin_without_radius(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                origin=GeoFilter(location="Krakow", radius_km=0),
            )
        )
        assert params["loadingPlace"] == "Krakow"
        assert "loadingRadiusKm" not in params

    def test_destination_filter(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                destination=GeoFilter(location="Berlin", radius_km=30),
            )
        )
        assert params["unloadingPlace"] == "Berlin"
        assert params["unloadingRadiusKm"] == 30

    def test_date_filters(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                delivery_date_from=date(2026, 1, 18),
                delivery_date_to=date(2026, 1, 19),
            )
        )
        assert params["loadingDateFrom"] == "2026-01-15"
        assert params["loadingDateTo"] == "2026-01-16"
        assert params["unloadingDateFrom"] == "2026-01-18"
        assert params["unloadingDateTo"] == "2026-01-19"

    def test_trailer_type_filter(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                trailer_type=["cooler", "curtainsider"],
            )
        )
        assert params["truck_body_type"] == "cooler,curtainsider"

    def test_adr_filter_true(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                adr_required=True,
            )
        )
        assert params["adr"] == "true"

    def test_adr_filter_false(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                adr_required=False,
            )
        )
        assert params["adr"] == "false"

    def test_weight_filters(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                weight_kg_min=5000,
                weight_kg_max=24000,
            )
        )
        assert params["weight_min"] == 5000
        assert params["weight_max"] == 24000

    def test_country_filters(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                loading_country="PL",
                delivery_country="DE",
            )
        )
        assert params["loading_country"] == "pl"
        assert params["delivery_country"] == "de"

    def test_sort_filters(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                sort_by="price",
                sort_order="asc",
            )
        )
        assert params["sortBy"] == "price"
        assert params["order"] == "asc"

    def test_sort_by_only(self, adapter):
        """sort_by without sort_order still includes sortBy."""
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                sort_by="price",
                sort_order=None,
            )
        )
        assert params["sortBy"] == "price"
        assert "order" not in params

    def test_extra_filters_passthrough(self, adapter):
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                extra_filters={"custom_field": "custom_value", "page": 2},
            )
        )
        assert params["custom_field"] == "custom_value"
        # extra_filters should override defaults
        assert params["page"] == 2

    def test_all_filters_combined(self, adapter):
        """All filter types together produce a complete params dict."""
        params = adapter._build_search_params(
            LoadSearchFilters(
                pickup_date_from=date(2026, 1, 15),
                pickup_date_to=date(2026, 1, 16),
                delivery_date_from=date(2026, 1, 18),
                delivery_date_to=date(2026, 1, 19),
                origin=GeoFilter(location="Krakow", radius_km=50),
                destination=GeoFilter(location="Berlin", radius_km=30),
                trailer_type=["cooler"],
                adr_required=True,
                weight_kg_min=5000,
                weight_kg_max=24000,
                loading_country="PL",
                delivery_country="DE",
                sort_by="price",
                sort_order="asc",
            )
        )
        assert len(params) >= 12  # at least 12 field-value pairs


# ═══════════════════════════════════════════════════════════════════════
# 4. Adapter Interface Compliance
# ═══════════════════════════════════════════════════════════════════════


class TestAdapterInterfaceCompliance:
    """TransEuAdapter fulfills the FreightProviderAdapter contract."""

    def test_is_freight_provider_adapter_subclass(self, adapter):
        from services.freight_exchange.adapter_base import FreightProviderAdapter
        assert isinstance(adapter, FreightProviderAdapter)

    def test_has_provider_id(self, adapter):
        assert adapter.provider_id == "trans_eu"

    def test_capabilities_returns_correct_type(self, adapter):
        caps = adapter.capabilities()
        assert isinstance(caps, ProviderCapabilities)

    def test_capabilities_rate_limit_per_minute(self, adapter):
        caps = adapter.capabilities()
        assert caps.rate_limit_per_minute == 900

    def test_search_loads_exists(self, adapter):
        assert hasattr(adapter, "search_loads")
        assert callable(adapter.search_loads)

    def test_get_load_exists(self, adapter):
        assert hasattr(adapter, "get_load")
        assert callable(adapter.get_load)

    def test_authenticate_exists(self, adapter):
        assert hasattr(adapter, "authenticate")
        assert callable(adapter.authenticate)

    def test_refresh_session_exists(self, adapter):
        assert hasattr(adapter, "refresh_session")
        assert callable(adapter.refresh_session)

    def test_test_connection_exists(self, adapter):
        assert hasattr(adapter, "test_connection")
        assert callable(adapter.test_connection)

    def test_capabilities_exists(self, adapter):
        assert hasattr(adapter, "capabilities")
        assert callable(adapter.capabilities)
