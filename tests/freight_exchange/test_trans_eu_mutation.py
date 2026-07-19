"""Mutation tests — resilience to malformed data, edge cases, and boundary values.

Tests that Trans.eu integration code handles corrupted/missing/malformed
data gracefully without crashing.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
import pytest
from models.freight_exchange_models import (
    ProviderCredentials, ProviderSession, ProviderCapabilities,
    LoadSearchFilters, LoadSearchResult, TransEuUserToken, FreightOffer,
)
from models.common import Money


class TestProviderCredentialsMutation:
    def test_empty_client_id(self):
        creds = ProviderCredentials(company_id=1, provider_id="trans_eu", client_id="", client_secret_encrypted="sec")
        assert creds.client_id == ""

    def test_empty_grant_type_defaults(self):
        creds = ProviderCredentials(company_id=1, provider_id="trans_eu", client_id="c", client_secret_encrypted="s")
        assert creds.grant_type == "client_credentials"

    def test_invalid_literal_type_fails_on_unknown(self):
        with pytest.raises(ValueError):
            ProviderCredentials(company_id=1, provider_id="trans_eu", client_id="c", client_secret_encrypted="s", grant_type="invalid_grant")

    def test_very_long_fields(self):
        long_val = "x" * 10000
        creds = ProviderCredentials(company_id=1, provider_id="trans_eu", client_id=long_val, client_secret_encrypted=long_val)
        assert len(creds.client_id) == 10000

    def test_negative_company_id(self):
        creds = ProviderCredentials(company_id=-1, provider_id="trans_eu", client_id="c", client_secret_encrypted="s")
        assert creds.company_id == -1  # No validation — will fail at DB level


class TestProviderSessionMutation:
    def test_expires_at_in_past(self):
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        session = ProviderSession(company_id=1, provider_id="trans_eu", access_token_encrypted="tok", expires_at=past)
        assert session.expires_at.year == 2000

    def test_empty_access_token(self):
        now = datetime.now(timezone.utc)
        session = ProviderSession(company_id=1, provider_id="trans_eu", access_token_encrypted="", expires_at=now)
        assert session.access_token_encrypted == ""

    def test_null_expires_at_raises(self):
        with pytest.raises(Exception):
            ProviderSession(company_id=1, provider_id="trans_eu", access_token_encrypted="tok", expires_at=None)


class TestLoadSearchResultEdgeCases:
    def test_zero_distance(self):
        now = datetime.now(timezone.utc)
        r = LoadSearchResult(
            result_id="1", provider_id="trans_eu", provider_load_id="1",
            origin="", destination="",
            pickup_window=(now, now), delivery_window=(now, now),
            price=Money(amount=0, currency="EUR"), distance_km=0.0,
            trailer_type="", adr=False,
        )
        assert r.distance_km == 0.0
        assert r.price.amount == 0

    def test_negative_distance(self):
        now = datetime.now(timezone.utc)
        r = LoadSearchResult(
            result_id="1", provider_id="trans_eu", provider_load_id="1",
            origin="A", destination="B",
            pickup_window=(now, now), delivery_window=(now, now),
            price=Money(amount=100, currency="EUR"), distance_km=-1,
            trailer_type="standard", adr=False,
        )
        assert r.distance_km == -1  # Model allows negative — caller must validate

    def test_very_large_weight(self):
        now = datetime.now(timezone.utc)
        r = LoadSearchResult(
            result_id="1", provider_id="trans_eu", provider_load_id="1",
            origin="A", destination="B",
            pickup_window=(now, now), delivery_window=(now, now),
            price=Money(amount=100, currency="EUR"), distance_km=100,
            trailer_type="standard", adr=False, weight_kg=1e12,
        )
        assert r.weight_kg == 1e12


class TestTransEuUserTokenMutation:
    def test_empty_token(self):
        now = datetime.now(timezone.utc)
        t = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="",
            refresh_token_encrypted="",
            expires_at=now, api_key_encrypted="",
        )
        assert t.access_token_encrypted == ""
        assert t.status == "active"

    def test_invalid_status_fails(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError):
            TransEuUserToken(
                company_id=1, user_id=42,
                access_token_encrypted="tok", refresh_token_encrypted="ref",
                expires_at=now, api_key_encrypted="key",
                status="nonexistent_status",
            )


class TestFreightOfferMutation:
    def test_zero_price(self):
        offer = FreightOffer(
            company_id=1, user_id=42, trans_eu_freight_id=1,
            origin="X", destination="Y", price_amount=0.0,
        )
        assert offer.price_amount == 0.0

    def test_null_publication_status(self):
        offer = FreightOffer(
            company_id=1, user_id=42, trans_eu_freight_id=1,
            origin="X", destination="Y",
        )
        assert offer.publication_status is None
        assert offer.status == "draft"

    def test_negative_freight_id(self):
        offer = FreightOffer(
            company_id=1, user_id=42, trans_eu_freight_id=-1,
            origin="X", destination="Y",
        )
        assert offer.trans_eu_freight_id == -1

    def test_missing_required_raises(self):
        with pytest.raises(ValueError):
            FreightOffer(company_id=1, user_id=42)  # missing trans_eu_freight_id, origin, destination


class TestMappingNullValues:
    """Mutation tests for the adapter's _map_freight_to_result."""
    def test_null_entire_loading_section(self):
        from services.freight_exchange.adapters.trans_eu import TransEuAdapter
        a = TransEuAdapter()
        result = a._map_freight_to_result({"id": 1, "loading": None, "unloading": None})
        assert result.origin == ""
        assert result.destination == ""

    def test_loading_dict_with_null_place(self):
        from services.freight_exchange.adapters.trans_eu import TransEuAdapter
        a = TransEuAdapter()
        result = a._map_freight_to_result({
            "id": 1, "loading": {"place": None}, "unloading": {"place": None},
        })
        assert result.origin == ""
        assert result.destination == ""


class TestCircuitBreakerChaosEdgeCases:
    def test_negative_failure_threshold_not_applicable(self):
        from services.freight_exchange.circuit_breaker import FAILURE_THRESHOLD
        assert FAILURE_THRESHOLD > 0

    def test_zero_company_id(self):
        import asyncio
        from services.freight_exchange.circuit_breaker import FreightCircuitBreaker
        class FakeRedis:
            def __init__(self): self._data = {}
            def get(self, k): return self._data.get(k)
            def set(self, k, v): self._data[k] = v
            def delete(self, *k): [self._data.pop(x, None) for x in k]
            def incr(self, k): v = int(self._data.get(k, 0)) + 1; self._data[k] = str(v); return v
        cb = FreightCircuitBreaker(FakeRedis())
        async def _run():
            return await cb.is_allowed(0, "trans_eu")
        allowed = asyncio.run(_run())
        assert allowed is True
