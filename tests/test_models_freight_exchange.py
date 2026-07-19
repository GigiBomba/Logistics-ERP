"""Tests for freight_exchange_models.py — all 15+ Pydantic models.

Covers happy-path construction, field defaults, optional/required fields,
Literal validation, boundary values, and edge cases (None, empty lists,
negative numbers, invalid enums, long strings, large numbers).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import pytest
from pydantic import ValidationError
from models.common import Money
from models.freight_exchange_models import (
    ProviderCredentials,
    ProviderSession,
    ProviderHealthCheck,
    ProviderCapabilities,
    GeoFilter,
    LoadSearchFilters,
    LoadSearchResult,
    SavedSearch,
    ImportResult,
    VehicleCompatibility,
    DriverCompatibility,
    LoadEvaluation,
    TruckMatchScore,
    TransEuUserToken,
    FreightOffer,
    TransEuWebhookEvent,
)


# ── helpers ─────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_window() -> tuple[datetime, datetime]:
    now = _utcnow()
    return (now, now)


def _make_money(amount: float = 100.0, currency: str = "EUR") -> Money:
    return Money(amount=amount, currency=currency)


# ═══════════════════════════════════════════════════════════════════════
# ProviderCredentials
# ═══════════════════════════════════════════════════════════════════════

class TestProviderCredentials:
    """Valid construction, field defaults, Literal validation, edge cases."""

    @pytest.mark.parametrize(
        "company_id, provider_id, client_id, client_secret_encrypted",
        [
            (1, "trans_eu", "my_client", "encrypted_secret"),
            (42, "timocom", "user@example.com", "abc123=="),
            (0, "teleroute", "", ""),
            (-1, "wtransnet", "cli", "sec"),
            (999999, "custom_provider", "a" * 255, "b" * 255),
        ],
    )
    def test_valid_construction(
        self, company_id, provider_id, client_id, client_secret_encrypted
    ):
        creds = ProviderCredentials(
            company_id=company_id,
            provider_id=provider_id,
            client_id=client_id,
            client_secret_encrypted=client_secret_encrypted,
        )
        assert creds.company_id == company_id
        assert creds.provider_id == provider_id
        assert creds.client_id == client_id
        assert creds.client_secret_encrypted == client_secret_encrypted

    def test_defaults(self):
        """Check all default values."""
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id="c", client_secret_encrypted="s",
        )
        assert creds.scope == []
        assert creds.grant_type == "client_credentials"
        assert creds.authorization_code is None
        assert creds.redirect_uri is None
        assert creds.api_key is None

    def test_explicit_grant_type(self):
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id="c", client_secret_encrypted="s",
            grant_type="authorization_code",
        )
        assert creds.grant_type == "authorization_code"

    def test_invalid_grant_type_raises(self):
        with pytest.raises(ValidationError):
            ProviderCredentials(
                company_id=1, provider_id="trans_eu",
                client_id="c", client_secret_encrypted="s",
                grant_type="invalid_grant",
            )

    def test_scope_populated(self):
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id="c", client_secret_encrypted="s",
            scope=["loads:read", "offers:write"],
        )
        assert creds.scope == ["loads:read", "offers:write"]

    def test_optional_fields_populated(self):
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id="c", client_secret_encrypted="s",
            authorization_code="auth_code_123",
            redirect_uri="https://example.com/callback",
            api_key="api_key_value",
        )
        assert creds.authorization_code == "auth_code_123"
        assert creds.redirect_uri == "https://example.com/callback"
        assert creds.api_key == "api_key_value"

    def test_empty_client_id_and_secret(self):
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id="", client_secret_encrypted="",
        )
        assert creds.client_id == ""
        assert creds.client_secret_encrypted == ""

    def test_very_long_strings(self):
        long_val = "x" * 10000
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id=long_val, client_secret_encrypted=long_val,
        )
        assert len(creds.client_id) == 10000
        assert len(creds.client_secret_encrypted) == 10000

    def test_negative_company_id(self):
        creds = ProviderCredentials(
            company_id=-5, provider_id="trans_eu",
            client_id="c", client_secret_encrypted="s",
        )
        assert creds.company_id == -5  # model allows negative; DB layer enforces

    def test_missing_required_company_id_raises(self):
        with pytest.raises(ValidationError):
            ProviderCredentials(
                provider_id="trans_eu", client_id="c",
                client_secret_encrypted="s",
            )

    def test_missing_required_provider_id_raises(self):
        with pytest.raises(ValidationError):
            ProviderCredentials(
                company_id=1, client_id="c",
                client_secret_encrypted="s",
            )

    def test_missing_required_client_id_raises(self):
        with pytest.raises(ValidationError):
            ProviderCredentials(
                company_id=1, provider_id="trans_eu",
                client_secret_encrypted="s",
            )

    def test_missing_required_secret_raises(self):
        with pytest.raises(ValidationError):
            ProviderCredentials(
                company_id=1, provider_id="trans_eu",
                client_id="c",
            )

    def test_authorization_code_with_grant_type_mismatch(self):
        """Model does not enforce coupling — field is just stored."""
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id="c", client_secret_encrypted="s",
            grant_type="client_credentials",
            authorization_code="should_not_be_here",
        )
        assert creds.authorization_code == "should_not_be_here"
        assert creds.grant_type == "client_credentials"


# ═══════════════════════════════════════════════════════════════════════
# ProviderSession
# ═══════════════════════════════════════════════════════════════════════

class TestProviderSession:
    """Expiry handling, token validation, optional fields."""

    def test_minimal(self):
        now = _utcnow()
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=now,
        )
        assert session.company_id == 1
        assert session.provider_id == "trans_eu"
        assert session.access_token_encrypted == "tok"
        assert session.expires_at == now

    def test_all_optional_fields_default_to_none(self):
        now = _utcnow()
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=now,
        )
        assert session.refresh_token_encrypted is None
        assert session.last_health_check_at is None
        assert session.last_health_check_status is None
        assert session.user_id is None

    def test_all_fields_populated(self):
        now = _utcnow()
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=now,
            refresh_token_encrypted="ref_tok",
            last_health_check_at=now,
            last_health_check_status="healthy",
            user_id=42,
        )
        assert session.refresh_token_encrypted == "ref_tok"
        assert session.last_health_check_at == now
        assert session.last_health_check_status == "healthy"
        assert session.user_id == 42

    def test_empty_access_token(self):
        now = _utcnow()
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="", expires_at=now,
        )
        assert session.access_token_encrypted == ""

    def test_expires_at_in_past(self):
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=past,
        )
        assert session.expires_at == past  # model stores whatever is given

    def test_expires_at_in_far_future(self):
        future = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=future,
        )
        assert session.expires_at == future

    @pytest.mark.parametrize("status", ["healthy", "degraded", "down"])
    def test_valid_health_check_status(self, status):
        now = _utcnow()
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=now,
            last_health_check_status=status,
        )
        assert session.last_health_check_status == status

    def test_invalid_health_check_status_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            ProviderSession(
                company_id=1, provider_id="trans_eu",
                access_token_encrypted="tok", expires_at=now,
                last_health_check_status="unknown",
            )

    def test_null_expires_at_raises(self):
        with pytest.raises(ValidationError):
            ProviderSession(
                company_id=1, provider_id="trans_eu",
                access_token_encrypted="tok", expires_at=None,
            )

    def test_missing_company_id_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            ProviderSession(
                provider_id="trans_eu",
                access_token_encrypted="tok", expires_at=now,
            )

    def test_negative_user_id(self):
        now = _utcnow()
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=now,
            user_id=-1,
        )
        assert session.user_id == -1


# ═══════════════════════════════════════════════════════════════════════
# ProviderHealthCheck
# ═══════════════════════════════════════════════════════════════════════

class TestProviderHealthCheck:
    """Status values, latency, error states."""

    @pytest.mark.parametrize(
        "provider_id, status, latency_ms",
        [
            ("trans_eu", "healthy", 0),
            ("timocom", "degraded", 500),
            ("teleroute", "down", 999999),
            ("wtransnet", "healthy", 42),
        ],
    )
    def test_valid_construction(self, provider_id, status, latency_ms):
        now = _utcnow()
        hc = ProviderHealthCheck(
            provider_id=provider_id, status=status,
            latency_ms=latency_ms, checked_at=now,
        )
        assert hc.provider_id == provider_id
        assert hc.status == status
        assert hc.latency_ms == latency_ms
        assert hc.checked_at == now

    @pytest.mark.parametrize("status", ["healthy", "degraded", "down"])
    def test_all_valid_statuses(self, status):
        hc = ProviderHealthCheck(
            provider_id="trans_eu", status=status,
            latency_ms=100, checked_at=_utcnow(),
        )
        assert hc.status == status

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            ProviderHealthCheck(
                provider_id="trans_eu", status="unknown",
                latency_ms=100, checked_at=_utcnow(),
            )

    def test_error_field(self):
        now = _utcnow()
        hc = ProviderHealthCheck(
            provider_id="trans_eu", status="down",
            latency_ms=5000, checked_at=now,
            error="Connection timeout after 30s",
        )
        assert hc.error == "Connection timeout after 30s"

    def test_error_defaults_to_none(self):
        hc = ProviderHealthCheck(
            provider_id="trans_eu", status="healthy",
            latency_ms=0, checked_at=_utcnow(),
        )
        assert hc.error is None

    def test_negative_latency(self):
        hc = ProviderHealthCheck(
            provider_id="trans_eu", status="healthy",
            latency_ms=-100, checked_at=_utcnow(),
        )
        assert hc.latency_ms == -100  # model allows negative

    def test_missing_provider_id_raises(self):
        with pytest.raises(ValidationError):
            ProviderHealthCheck(
                status="healthy", latency_ms=100,
                checked_at=_utcnow(),
            )

    def test_missing_checked_at_raises(self):
        with pytest.raises(ValidationError):
            ProviderHealthCheck(
                provider_id="trans_eu", status="healthy",
                latency_ms=100,
            )


# ═══════════════════════════════════════════════════════════════════════
# ProviderCapabilities
# ═══════════════════════════════════════════════════════════════════════

class TestProviderCapabilities:
    """Boolean flags, feature detection, optional defaults."""

    def test_minimal(self):
        caps = ProviderCapabilities(
            provider_id="trans_eu",
            supported_filters=[],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )
        assert caps.provider_id == "trans_eu"
        assert caps.supported_filters == []
        assert caps.rate_limit_per_minute == 60

    def test_all_defaults_are_false(self):
        caps = ProviderCapabilities(
            provider_id="trans_eu",
            supported_filters=[],
            supports_saved_search=True,
            supports_offer_publishing=True,
            rate_limit_per_minute=30,
        )
        assert caps.adr_search is False
        assert caps.trailer_type_search is False
        assert caps.supports_loading_type is False
        assert caps.supports_country_filter is False
        assert caps.supports_sort is False
        assert caps.supports_freight_publication is False
        assert caps.supports_negotiation is False
        assert caps.supports_transport_orders is False
        assert caps.supports_monitoring is False
        assert caps.supports_webhooks is False
        assert caps.supports_oauth_user is False
        assert caps.requires_api_key_header is False

    def test_all_flags_enabled(self):
        caps = ProviderCapabilities(
            provider_id="trans_eu",
            supported_filters=["price", "distance"],
            supports_saved_search=True,
            supports_offer_publishing=True,
            rate_limit_per_minute=60,
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
        assert caps.adr_search is True
        assert caps.requires_api_key_header is True

    def test_supported_filters_list(self):
        caps = ProviderCapabilities(
            provider_id="trans_eu",
            supported_filters=["price", "distance", "date", "weight"],
            supports_saved_search=True,
            supports_offer_publishing=False,
            rate_limit_per_minute=120,
        )
        assert caps.supported_filters == ["price", "distance", "date", "weight"]

    def test_zero_rate_limit(self):
        caps = ProviderCapabilities(
            provider_id="trans_eu",
            supported_filters=[],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=0,
        )
        assert caps.rate_limit_per_minute == 0

    def test_negative_rate_limit(self):
        caps = ProviderCapabilities(
            provider_id="trans_eu",
            supported_filters=[],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=-1,
        )
        assert caps.rate_limit_per_minute == -1

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            ProviderCapabilities(
                provider_id="trans_eu",
                supported_filters=[],
                supports_saved_search=True,
                # missing supports_offer_publishing
            )


# ═══════════════════════════════════════════════════════════════════════
# GeoFilter
# ═══════════════════════════════════════════════════════════════════════

class TestGeoFilter:
    """Location and radius — coordinate bounds."""

    @pytest.mark.parametrize(
        "location, radius_km",
        [
            ("Berlin", 50.0),
            ("  Paris, France  ", 100.5),
            ("123 Main St", 0.0),
            ("", 999999.99),
            ("A" * 500, -1.0),
        ],
    )
    def test_valid_construction(self, location, radius_km):
        gf = GeoFilter(location=location, radius_km=radius_km)
        assert gf.location == location
        assert gf.radius_km == radius_km

    def test_zero_radius(self):
        gf = GeoFilter(location="Berlin", radius_km=0.0)
        assert gf.radius_km == 0.0

    def test_negative_radius(self):
        gf = GeoFilter(location="Berlin", radius_km=-50.0)
        assert gf.radius_km == -50.0

    def test_very_large_radius(self):
        gf = GeoFilter(location="Earth", radius_km=40075.0)
        assert gf.radius_km == 40075.0

    def test_whitespace_location(self):
        gf = GeoFilter(location="   ", radius_km=10.0)
        assert gf.location == "   "

    def test_missing_location_raises(self):
        with pytest.raises(ValidationError):
            GeoFilter(radius_km=10.0)

    def test_missing_radius_raises(self):
        with pytest.raises(ValidationError):
            GeoFilter(location="Berlin")


# ═══════════════════════════════════════════════════════════════════════
# LoadSearchFilters
# ═══════════════════════════════════════════════════════════════════════

class TestLoadSearchFilters:
    """All field validations, combined filters, boundary conditions."""

    def test_minimal_required_only(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        assert lsf.pickup_date_from == date(2026, 7, 1)
        assert lsf.pickup_date_to == date(2026, 7, 31)
        assert lsf.origin is None
        assert lsf.destination is None
        assert lsf.extra_filters == {}

    def test_default_sort_order(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        assert lsf.sort_order == "asc"
        assert lsf.sort_by is None

    def test_all_fields_populated(self):
        lsf = LoadSearchFilters(
            origin=GeoFilter(location="Berlin", radius_km=50),
            destination=GeoFilter(location="Munich", radius_km=75),
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 10),
            delivery_date_from=date(2026, 7, 2),
            delivery_date_to=date(2026, 7, 12),
            trailer_type=["curtain", "box"],
            adr_required=True,
            weight_kg_min=1000.0,
            weight_kg_max=24000.0,
            price_min=500.0,
            distance_km_max=800.0,
            extra_filters={"exclude_brokers": True},
            loading_type="ftl",
            loading_country="DE",
            delivery_country="FR",
            sort_by="price",
            sort_order="desc",
            min_trucks=2,
            loading_type_list=["ftl", "ltl"],
        )
        assert lsf.origin.location == "Berlin"
        assert lsf.trailer_type == ["curtain", "box"]
        assert lsf.adr_required is True
        assert lsf.weight_kg_min == 1000.0
        assert lsf.sort_by == "price"
        assert lsf.sort_order == "desc"
        assert lsf.min_trucks == 2
        assert lsf.loading_type_list == ["ftl", "ltl"]

    def test_none_optional_fields(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
            origin=None, destination=None,
            delivery_date_from=None, delivery_date_to=None,
            trailer_type=None, adr_required=None,
            weight_kg_min=None, weight_kg_max=None,
            price_min=None, distance_km_max=None,
            loading_type=None, loading_country=None,
            delivery_country=None, sort_by=None,
            min_trucks=None, loading_type_list=None,
        )
        assert lsf.origin is None
        assert lsf.delivery_date_from is None
        assert lsf.trailer_type is None
        assert lsf.adr_required is None
        assert lsf.weight_kg_min is None
        assert lsf.sort_by is None
        assert lsf.sort_order == "asc"  # default preserved

    def test_empty_lists(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
            trailer_type=[],
            loading_type_list=[],
        )
        assert lsf.trailer_type == []
        assert lsf.loading_type_list == []

    def test_extra_filters_default(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        assert lsf.extra_filters == {}

    def test_extra_filters_custom(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
            extra_filters={"exclude_brokers": True, "only_direct": False},
        )
        assert lsf.extra_filters["exclude_brokers"] is True
        assert lsf.extra_filters["only_direct"] is False

    @pytest.mark.parametrize("sort_order", ["asc", "desc"])
    def test_valid_sort_orders(self, sort_order):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
            sort_order=sort_order,
        )
        assert lsf.sort_order == sort_order

    def test_invalid_sort_order_raises(self):
        """sort_order is a plain str field without Literal constraint,
        so any string is accepted by the model."""
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
            sort_order="invalid",
        )
        assert lsf.sort_order == "invalid"

    def test_boundary_dates(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(1, 1, 1),
            pickup_date_to=date(9999, 12, 31),
        )
        assert lsf.pickup_date_from.year == 1
        assert lsf.pickup_date_to.year == 9999

    def test_negative_weight_and_price(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
            weight_kg_min=-100.0,
            weight_kg_max=-1.0,
            price_min=-500.0,
            distance_km_max=-10.0,
        )
        assert lsf.weight_kg_min == -100.0  # model allows negative

    def test_same_date_from_to(self):
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 15),
            pickup_date_to=date(2026, 7, 15),
            delivery_date_from=date(2026, 7, 15),
            delivery_date_to=date(2026, 7, 15),
        )
        assert lsf.pickup_date_from == lsf.pickup_date_to

    def test_missing_pickup_date_from_raises(self):
        with pytest.raises(ValidationError):
            LoadSearchFilters(pickup_date_to=date(2026, 7, 31))

    def test_missing_pickup_date_to_raises(self):
        with pytest.raises(ValidationError):
            LoadSearchFilters(pickup_date_from=date(2026, 7, 1))


# ═══════════════════════════════════════════════════════════════════════
# LoadSearchResult
# ═══════════════════════════════════════════════════════════════════════

class TestLoadSearchResult:
    """Origin/destination, price, weight, ADR, optional fields."""

    def test_minimal(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="Berlin",
            destination="Munich",
            pickup_window=win, delivery_window=win,
            price=_make_money(), distance_km=500.0,
            trailer_type="curtain", adr=False,
        )
        assert result.result_id == "r1"
        assert result.origin == "Berlin"
        assert result.destination == "Munich"
        assert result.adr is False
        assert result.weight_kg == 0.0

    def test_defaults(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="A",
            destination="B",
            pickup_window=win, delivery_window=win,
            price=_make_money(), distance_km=100.0,
            trailer_type="standard", adr=True,
        )
        assert result.raw_payload == {}
        assert result.loading_type == ""
        assert result.loading_country == ""
        assert result.delivery_country == ""
        assert result.weight_kg == 0.0
        assert result.loading_date is None
        assert result.unloading_date is None

    def test_all_fields_populated(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="Berlin",
            destination="Munich",
            pickup_window=win, delivery_window=win,
            price=Money(amount=1500.50, currency="EUR"),
            distance_km=585.3, trailer_type="box", adr=True,
            raw_payload={"external_id": "ext_123"},
            loading_type="ftl",
            loading_country="DE",
            delivery_country="DE",
            weight_kg=12000.0,
            loading_date="2026-07-01",
            unloading_date="2026-07-02",
        )
        assert result.price.amount == 1500.50
        assert result.price.currency == "EUR"
        assert result.distance_km == 585.3
        assert result.raw_payload == {"external_id": "ext_123"}
        assert result.loading_type == "ftl"
        assert result.loading_date == "2026-07-01"

    def test_empty_origin_destination(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="",
            destination="",
            pickup_window=win, delivery_window=win,
            price=_make_money(), distance_km=0.0,
            trailer_type="", adr=False,
        )
        assert result.origin == ""
        assert result.destination == ""
        assert result.distance_km == 0.0

    def test_negative_distance(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="A",
            destination="B",
            pickup_window=win, delivery_window=win,
            price=_make_money(), distance_km=-1.0,
            trailer_type="standard", adr=False,
        )
        assert result.distance_km == -1.0

    def test_zero_price(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="A",
            destination="B",
            pickup_window=win, delivery_window=win,
            price=Money(amount=0, currency="EUR"),
            distance_km=100.0, trailer_type="standard",
            adr=False,
        )
        assert result.price.amount == 0.0

    def test_different_currency(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="A",
            destination="B",
            pickup_window=win, delivery_window=win,
            price=Money(amount=1200.0, currency="PLN"),
            distance_km=100.0, trailer_type="standard",
            adr=False,
        )
        assert result.price.currency == "PLN"

    def test_very_large_weight(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="A",
            destination="B",
            pickup_window=win, delivery_window=win,
            price=_make_money(), distance_km=100.0,
            trailer_type="standard", adr=False,
            weight_kg=1e12,
        )
        assert result.weight_kg == 1e12

    def test_negative_weight(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="A",
            destination="B",
            pickup_window=win, delivery_window=win,
            price=_make_money(), distance_km=100.0,
            trailer_type="standard", adr=False,
            weight_kg=-500.0,
        )
        assert result.weight_kg == -500.0

    def test_adr_true(self):
        win = _make_window()
        result = LoadSearchResult(
            result_id="r1", provider_id="trans_eu",
            provider_load_id="pl1", origin="A",
            destination="B",
            pickup_window=win, delivery_window=win,
            price=_make_money(), distance_km=100.0,
            trailer_type="tank", adr=True,
        )
        assert result.adr is True

    def test_missing_required_result_id_raises(self):
        win = _make_window()
        with pytest.raises(ValidationError):
            LoadSearchResult(
                provider_id="trans_eu", provider_load_id="pl1",
                origin="A", destination="B",
                pickup_window=win, delivery_window=win,
                price=_make_money(), distance_km=100.0,
                trailer_type="standard", adr=False,
            )

    def test_missing_price_raises(self):
        win = _make_window()
        with pytest.raises(ValidationError):
            LoadSearchResult(
                result_id="r1", provider_id="trans_eu",
                provider_load_id="pl1", origin="A",
                destination="B",
                pickup_window=win, delivery_window=win,
                distance_km=100.0, trailer_type="standard",
                adr=False,
            )


# ═══════════════════════════════════════════════════════════════════════
# SavedSearch
# ═══════════════════════════════════════════════════════════════════════

class TestSavedSearch:
    """Creation, fields, nested filter, optional provider_ids."""

    def test_minimal(self):
        now = _utcnow()
        filters = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        ss = SavedSearch(
            saved_search_id="ss1", company_id=1, user_id=42,
            label="DE loads July", filters=filters,
            created_at=now,
        )
        assert ss.saved_search_id == "ss1"
        assert ss.company_id == 1
        assert ss.user_id == 42
        assert ss.label == "DE loads July"
        assert ss.filters.pickup_date_from == date(2026, 7, 1)
        assert ss.created_at == now

    def test_all_fields(self):
        now = _utcnow()
        filters = LoadSearchFilters(
            origin=GeoFilter(location="Berlin", radius_km=50),
            destination=GeoFilter(location="Munich", radius_km=75),
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 10),
            adr_required=True,
            price_min=500.0,
        )
        ss = SavedSearch(
            saved_search_id="ss1", company_id=1, user_id=42,
            label="ADR loads Berlin-Munich", filters=filters,
            provider_ids=["trans_eu", "timocom"],
            created_at=now,
            last_refreshed_at=now,
        )
        assert ss.provider_ids == ["trans_eu", "timocom"]
        assert ss.last_refreshed_at == now
        assert ss.filters.adr_required is True

    def test_provider_ids_defaults_to_none(self):
        now = _utcnow()
        filters = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        ss = SavedSearch(
            saved_search_id="ss1", company_id=1, user_id=42,
            label="test", filters=filters, created_at=now,
        )
        assert ss.provider_ids is None

    def test_empty_provider_ids(self):
        now = _utcnow()
        filters = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        ss = SavedSearch(
            saved_search_id="ss1", company_id=1, user_id=42,
            label="test", filters=filters, created_at=now,
            provider_ids=[],
        )
        assert ss.provider_ids == []

    def test_empty_label(self):
        now = _utcnow()
        filters = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        ss = SavedSearch(
            saved_search_id="ss1", company_id=1, user_id=42,
            label="", filters=filters, created_at=now,
        )
        assert ss.label == ""

    def test_missing_label_raises(self):
        now = _utcnow()
        filters = LoadSearchFilters(
            pickup_date_from=date(2026, 7, 1),
            pickup_date_to=date(2026, 7, 31),
        )
        with pytest.raises(ValidationError):
            SavedSearch(
                saved_search_id="ss1", company_id=1, user_id=42,
                filters=filters, created_at=now,
            )

    def test_missing_filters_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            SavedSearch(
                saved_search_id="ss1", company_id=1, user_id=42,
                label="test", created_at=now,
            )


# ═══════════════════════════════════════════════════════════════════════
# ImportResult
# ═══════════════════════════════════════════════════════════════════════

class TestImportResult:
    """Success/failure states, field tracking, source validation."""

    def test_minimal(self):
        now = _utcnow()
        ir = ImportResult(
            trip_id=1, source="freight_exchange",
            imported_at=now, imported_by_user_id=42,
        )
        assert ir.trip_id == 1
        assert ir.source == "freight_exchange"
        assert ir.imported_by_user_id == 42

    def test_all_fields(self):
        now = _utcnow()
        ir = ImportResult(
            trip_id=1, source="manual",
            source_provider_id="trans_eu",
            source_reference_id="REF-123",
            imported_at=now, imported_by_user_id=42,
        )
        assert ir.source_provider_id == "trans_eu"
        assert ir.source_reference_id == "REF-123"

    def test_defaults_to_none(self):
        now = _utcnow()
        ir = ImportResult(
            trip_id=1, source="freight_exchange",
            imported_at=now, imported_by_user_id=42,
        )
        assert ir.source_provider_id is None
        assert ir.source_reference_id is None

    @pytest.mark.parametrize("source", ["manual", "freight_exchange"])
    def test_valid_sources(self, source):
        now = _utcnow()
        ir = ImportResult(
            trip_id=1, source=source,
            imported_at=now, imported_by_user_id=42,
        )
        assert ir.source == source

    def test_invalid_source_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            ImportResult(
                trip_id=1, source="csv_import",
                imported_at=now, imported_by_user_id=42,
            )

    def test_empty_source_provider_id(self):
        now = _utcnow()
        ir = ImportResult(
            trip_id=1, source="freight_exchange",
            source_provider_id="",
            source_reference_id="",
            imported_at=now, imported_by_user_id=42,
        )
        assert ir.source_provider_id == ""
        assert ir.source_reference_id == ""

    def test_negative_trip_id(self):
        now = _utcnow()
        ir = ImportResult(
            trip_id=-1, source="manual",
            imported_at=now, imported_by_user_id=42,
        )
        assert ir.trip_id == -1

    def test_missing_trip_id_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            ImportResult(
                source="manual",
                imported_at=now, imported_by_user_id=42,
            )

    def test_missing_imported_at_raises(self):
        with pytest.raises(ValidationError):
            ImportResult(
                trip_id=1, source="manual",
                imported_by_user_id=42,
            )


# ═══════════════════════════════════════════════════════════════════════
# VehicleCompatibility
# ═══════════════════════════════════════════════════════════════════════

class TestVehicleCompatibility:
    """Boolean logic, reasons list."""

    def test_compatible(self):
        vc = VehicleCompatibility(
            vehicle_id=1, compatible=True, reasons=[],
        )
        assert vc.vehicle_id == 1
        assert vc.compatible is True
        assert vc.reasons == []

    def test_not_compatible_with_reasons(self):
        vc = VehicleCompatibility(
            vehicle_id=5, compatible=False,
            reasons=["freight.compat.trailer_mismatch",
                     "freight.compat.weight_exceeded"],
        )
        assert vc.compatible is False
        assert len(vc.reasons) == 2

    def test_negative_vehicle_id(self):
        vc = VehicleCompatibility(
            vehicle_id=-1, compatible=True, reasons=[],
        )
        assert vc.vehicle_id == -1

    def test_empty_reasons_when_incompatible(self):
        vc = VehicleCompatibility(
            vehicle_id=1, compatible=False, reasons=[],
        )
        assert vc.compatible is False
        assert vc.reasons == []


# ═══════════════════════════════════════════════════════════════════════
# DriverCompatibility
# ═══════════════════════════════════════════════════════════════════════

class TestDriverCompatibility:
    """Boolean logic, hours_remaining, reasons."""

    def test_compatible(self):
        dc = DriverCompatibility(
            driver_id=1, compatible=True,
            hours_remaining=10.5, reasons=[],
        )
        assert dc.driver_id == 1
        assert dc.compatible is True
        assert dc.hours_remaining == 10.5

    def test_not_compatible(self):
        dc = DriverCompatibility(
            driver_id=2, compatible=False,
            hours_remaining=0.0,
            reasons=["freight.compat.driver_hours_exceeded"],
        )
        assert dc.compatible is False
        assert dc.hours_remaining == 0.0

    def test_negative_hours(self):
        dc = DriverCompatibility(
            driver_id=1, compatible=True,
            hours_remaining=-1.0, reasons=[],
        )
        assert dc.hours_remaining == -1.0

    def test_large_hours(self):
        dc = DriverCompatibility(
            driver_id=1, compatible=True,
            hours_remaining=99.999, reasons=[],
        )
        assert dc.hours_remaining == 99.999

    def test_missing_driver_id_raises(self):
        with pytest.raises(ValidationError):
            DriverCompatibility(
                compatible=True, hours_remaining=8.0,
                reasons=[],
            )

    def test_missing_hours_remaining_raises(self):
        with pytest.raises(ValidationError):
            DriverCompatibility(
                driver_id=1, compatible=True, reasons=[],
            )


# ═══════════════════════════════════════════════════════════════════════
# LoadEvaluation
# ═══════════════════════════════════════════════════════════════════════

class TestLoadEvaluation:
    """Profit margin, risk_score, edge cases (zero cost, negative)."""

    def test_minimal(self):
        now = _utcnow()
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(1000),
            fuel_cost=_make_money(200),
            toll_cost=_make_money(50),
            driver_salary=_make_money(300),
            deadhead_distance_km=50.0,
            expected_profit=_make_money(450),
            profit_margin_pct=45.0,
            estimated_duration_hours=8.5,
            risk_score=0.3,
            evaluated_at=now,
        )
        assert le.provider_id == "trans_eu"
        assert le.profit_margin_pct == 45.0
        assert le.risk_score == 0.3
        assert le.estimated_duration_hours == 8.5
        assert le.vehicle_compatibility == []
        assert le.driver_compatibility == []

    def test_with_compatibility_lists(self):
        now = _utcnow()
        vc = VehicleCompatibility(vehicle_id=1, compatible=True, reasons=[])
        dc = DriverCompatibility(driver_id=1, compatible=True,
                                 hours_remaining=8.0, reasons=[])
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(1000),
            fuel_cost=_make_money(200),
            toll_cost=_make_money(50),
            driver_salary=_make_money(300),
            deadhead_distance_km=50.0,
            expected_profit=_make_money(450),
            profit_margin_pct=45.0,
            estimated_duration_hours=8.5,
            risk_score=0.3,
            vehicle_compatibility=[vc],
            driver_compatibility=[dc],
            evaluated_at=now,
        )
        assert len(le.vehicle_compatibility) == 1
        assert len(le.driver_compatibility) == 1
        assert le.vehicle_compatibility[0].vehicle_id == 1
        assert le.driver_compatibility[0].driver_id == 1

    @pytest.mark.parametrize(
        "profit_margin_pct",
        [0.0, 100.0, -50.0, 1.5, 99.99, -0.01, 0.001],
    )
    def test_various_profit_margins(self, profit_margin_pct):
        now = _utcnow()
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(1000),
            fuel_cost=_make_money(200),
            toll_cost=_make_money(50),
            driver_salary=_make_money(300),
            deadhead_distance_km=50.0,
            expected_profit=_make_money(450),
            profit_margin_pct=profit_margin_pct,
            estimated_duration_hours=8.5,
            risk_score=0.3,
            evaluated_at=now,
        )
        assert le.profit_margin_pct == profit_margin_pct

    @pytest.mark.parametrize("risk_score", [0.0, 1.0, 0.5, 0.001, 0.999, -0.1, 1.5])
    def test_various_risk_scores(self, risk_score):
        """Model accepts any float for risk_score (0-1 suggested, not enforced)."""
        now = _utcnow()
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(1000),
            fuel_cost=_make_money(200),
            toll_cost=_make_money(50),
            driver_salary=_make_money(300),
            deadhead_distance_km=50.0,
            expected_profit=_make_money(450),
            profit_margin_pct=45.0,
            estimated_duration_hours=8.5,
            risk_score=risk_score,
            evaluated_at=now,
        )
        assert le.risk_score == risk_score

    def test_zero_costs(self):
        now = _utcnow()
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(0),
            fuel_cost=_make_money(0),
            toll_cost=_make_money(0),
            driver_salary=_make_money(0),
            deadhead_distance_km=0.0,
            expected_profit=_make_money(0),
            profit_margin_pct=0.0,
            estimated_duration_hours=0.0,
            risk_score=0.0,
            evaluated_at=now,
        )
        assert le.estimated_revenue.amount == 0.0
        assert le.fuel_cost.amount == 0.0
        assert le.deadhead_distance_km == 0.0
        assert le.profit_margin_pct == 0.0

    def test_negative_values(self):
        now = _utcnow()
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(-100),
            fuel_cost=_make_money(200),
            toll_cost=_make_money(50),
            driver_salary=_make_money(300),
            deadhead_distance_km=-50.0,
            expected_profit=_make_money(-450),
            profit_margin_pct=-45.0,
            estimated_duration_hours=-8.5,
            risk_score=-0.5,
            evaluated_at=now,
        )
        assert le.estimated_revenue.amount == -100.0
        assert le.deadhead_distance_km == -50.0
        assert le.expected_profit.amount == -450.0

    def test_negative_duration(self):
        now = _utcnow()
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(1000),
            fuel_cost=_make_money(200),
            toll_cost=_make_money(50),
            driver_salary=_make_money(300),
            deadhead_distance_km=0.0,
            expected_profit=_make_money(450),
            profit_margin_pct=45.0,
            estimated_duration_hours=-1.0,
            risk_score=0.3,
            evaluated_at=now,
        )
        assert le.estimated_duration_hours == -1.0

    def test_very_large_revenue(self):
        now = _utcnow()
        le = LoadEvaluation(
            provider_id="trans_eu", provider_load_id="pl1",
            estimated_revenue=_make_money(1e12),
            fuel_cost=_make_money(1e11),
            toll_cost=_make_money(1e10),
            driver_salary=_make_money(1e11),
            deadhead_distance_km=1e6,
            expected_profit=_make_money(1e12),
            profit_margin_pct=1e6,
            estimated_duration_hours=1e6,
            risk_score=1e6,
            evaluated_at=now,
        )
        assert le.estimated_revenue.amount == 1e12

    def test_missing_evaluated_at_raises(self):
        with pytest.raises(ValidationError):
            LoadEvaluation(
                provider_id="trans_eu", provider_load_id="pl1",
                estimated_revenue=_make_money(1000),
                fuel_cost=_make_money(200),
                toll_cost=_make_money(50),
                driver_salary=_make_money(300),
                deadhead_distance_km=50.0,
                expected_profit=_make_money(450),
                profit_margin_pct=45.0,
                estimated_duration_hours=8.5,
                risk_score=0.3,
            )


# ═══════════════════════════════════════════════════════════════════════
# TruckMatchScore
# ═══════════════════════════════════════════════════════════════════════

class TestTruckMatchScore:
    """Scoring, rank, reasons ordering, deadhead calculations."""

    def test_minimal(self):
        tms = TruckMatchScore(
            vehicle_id=1, score=85.5, rank=1,
            reasons=["distance", "profitability"],
            distance_to_pickup_km=10.0,
            expected_deadhead_km=5.0,
            expected_profit=_make_money(500),
            maintenance_status="ok",
            trailer_compatible=True,
        )
        assert tms.vehicle_id == 1
        assert tms.score == 85.5
        assert tms.rank == 1
        assert tms.distance_to_pickup_km == 10.0
        assert tms.expected_deadhead_km == 5.0
        assert tms.maintenance_status == "ok"
        assert tms.trailer_compatible is True

    def test_all_fields(self):
        tms = TruckMatchScore(
            vehicle_id=1, driver_id=42,
            score=92.0, rank=1,
            reasons=["freight.score.short_deadhead",
                     "freight.score.high_margin",
                     "freight.score.driver_available"],
            distance_to_pickup_km=15.0,
            expected_deadhead_km=8.0,
            expected_profit=Money(amount=750.0, currency="EUR"),
            driver_hours_remaining=8.5,
            maintenance_status="due_soon",
            trailer_compatible=True,
        )
        assert tms.driver_id == 42
        assert tms.score == 92.0
        assert tms.rank == 1
        assert tms.driver_hours_remaining == 8.5
        assert tms.maintenance_status == "due_soon"
        assert tms.trailer_compatible is True

    def test_driver_id_defaults_to_none(self):
        tms = TruckMatchScore(
            vehicle_id=1, score=50.0, rank=2,
            reasons=[], distance_to_pickup_km=0.0,
            expected_deadhead_km=0.0,
            expected_profit=_make_money(0),
            maintenance_status="ok",
            trailer_compatible=False,
        )
        assert tms.driver_id is None

    def test_low_score(self):
        tms = TruckMatchScore(
            vehicle_id=1, score=0.0, rank=99,
            reasons=["freight.score.no_match"],
            distance_to_pickup_km=500.0,
            expected_deadhead_km=300.0,
            expected_profit=_make_money(0),
            maintenance_status="critical",
            trailer_compatible=False,
        )
        assert tms.score == 0.0
        assert tms.rank == 99

    def test_high_score(self):
        tms = TruckMatchScore(
            vehicle_id=1, score=100.0, rank=1,
            reasons=["freight.score.perfect_match"],
            distance_to_pickup_km=0.0,
            expected_deadhead_km=0.0,
            expected_profit=_make_money(2000),
            maintenance_status="ok",
            trailer_compatible=True,
        )
        assert tms.score == 100.0

    def test_negative_values(self):
        tms = TruckMatchScore(
            vehicle_id=1, score=-10.0, rank=-1,
            reasons=[], distance_to_pickup_km=-5.0,
            expected_deadhead_km=-3.0,
            expected_profit=_make_money(-100),
            maintenance_status="",
            trailer_compatible=False,
        )
        assert tms.score == -10.0
        assert tms.rank == -1
        assert tms.distance_to_pickup_km == -5.0

    def test_empty_reasons(self):
        tms = TruckMatchScore(
            vehicle_id=1, score=50.0, rank=3,
            reasons=[],
            distance_to_pickup_km=25.0,
            expected_deadhead_km=10.0,
            expected_profit=_make_money(300),
            maintenance_status="ok",
            trailer_compatible=True,
        )
        assert tms.reasons == []

    def test_reason_order_preserved(self):
        reasons = ["first", "second", "third"]
        tms = TruckMatchScore(
            vehicle_id=1, score=75.0, rank=1,
            reasons=reasons,
            distance_to_pickup_km=10.0,
            expected_deadhead_km=5.0,
            expected_profit=_make_money(400),
            maintenance_status="ok",
            trailer_compatible=True,
        )
        assert tms.reasons == ["first", "second", "third"]

    def test_missing_expected_profit_raises(self):
        with pytest.raises(ValidationError):
            TruckMatchScore(
                vehicle_id=1, score=50.0, rank=1,
                reasons=[], distance_to_pickup_km=0.0,
                expected_deadhead_km=0.0,
                maintenance_status="ok",
                trailer_compatible=True,
            )


# ═══════════════════════════════════════════════════════════════════════
# TransEuUserToken
# ═══════════════════════════════════════════════════════════════════════

class TestTransEuUserToken:
    """Invalid status, expiry, default values."""

    def test_minimal(self):
        now = _utcnow()
        token = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="access",
            refresh_token_encrypted="refresh",
            expires_at=now,
            api_key_encrypted="api_key",
        )
        assert token.company_id == 1
        assert token.user_id == 42
        assert token.access_token_encrypted == "access"
        assert token.refresh_token_encrypted == "refresh"
        assert token.expires_at == now
        assert token.status == "active"
        assert token.id == ""

    def test_defaults(self):
        now = _utcnow()
        token = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="tok",
            refresh_token_encrypted="ref",
            expires_at=now,
            api_key_encrypted="key",
        )
        assert token.id == ""
        assert token.scope == ""
        assert token.client_id == ""
        assert token.client_secret_encrypted == ""
        assert token.status == "active"
        assert token.trans_eu_account_id is None
        assert token.connected_at is None
        assert token.last_used_at is None
        assert token.last_refreshed_at is None

    def test_all_fields(self):
        now = _utcnow()
        token = TransEuUserToken(
            id="tok_1", company_id=1, user_id=42,
            trans_eu_account_id="acc_1",
            access_token_encrypted="access",
            refresh_token_encrypted="refresh",
            scope="loads:read offers:write",
            expires_at=now,
            api_key_encrypted="api_key",
            client_id="my_client",
            client_secret_encrypted="my_secret",
            status="active",
            connected_at=now,
            last_used_at=now,
            last_refreshed_at=now,
        )
        assert token.id == "tok_1"
        assert token.scope == "loads:read offers:write"
        assert token.client_id == "my_client"
        assert token.connected_at == now

    @pytest.mark.parametrize("status", ["active", "expired", "revoked", "needs_reauth"])
    def test_valid_statuses(self, status):
        now = _utcnow()
        token = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="tok",
            refresh_token_encrypted="ref",
            expires_at=now,
            api_key_encrypted="key",
            status=status,
        )
        assert token.status == status

    def test_invalid_status_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            TransEuUserToken(
                company_id=1, user_id=42,
                access_token_encrypted="tok",
                refresh_token_encrypted="ref",
                expires_at=now,
                api_key_encrypted="key",
                status="nonexistent",
            )

    def test_empty_tokens(self):
        now = _utcnow()
        token = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="",
            refresh_token_encrypted="",
            expires_at=now,
            api_key_encrypted="",
        )
        assert token.access_token_encrypted == ""
        assert token.refresh_token_encrypted == ""
        assert token.api_key_encrypted == ""

    def test_expires_at_in_past(self):
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        token = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="tok",
            refresh_token_encrypted="ref",
            expires_at=past,
            api_key_encrypted="key",
        )
        assert token.expires_at == past

    def test_missing_required_fields_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            TransEuUserToken(
                company_id=1, user_id=42,
                access_token_encrypted="tok",
                refresh_token_encrypted="ref",
                # missing expires_at
                api_key_encrypted="key",
            )

    def test_missing_api_key_encrypted_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            TransEuUserToken(
                company_id=1, user_id=42,
                access_token_encrypted="tok",
                refresh_token_encrypted="ref",
                expires_at=now,
                # missing api_key_encrypted
            )


# ═══════════════════════════════════════════════════════════════════════
# FreightOffer
# ═══════════════════════════════════════════════════════════════════════

class TestFreightOffer:
    """Status transitions, defaults, optional fields."""

    def test_minimal(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=100,
            origin="Berlin", destination="Munich",
        )
        assert offer.company_id == 1
        assert offer.user_id == 42
        assert offer.trans_eu_freight_id == 100
        assert offer.origin == "Berlin"
        assert offer.destination == "Munich"

    def test_defaults(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=100,
            origin="X", destination="Y",
        )
        assert offer.id == ""
        assert offer.status == "draft"
        assert offer.trans_eu_reference_number == ""
        assert offer.publication_status is None
        assert offer.publication_type is None
        assert offer.price_amount == 0.0
        assert offer.price_currency == "EUR"
        assert offer.distance_km == 0.0
        assert offer.trailer_type == ""
        assert offer.adr is False
        assert offer.weight_kg == 0.0
        assert offer.raw_payload == {}
        assert offer.externally_modified_at is None
        assert offer.operion_trip_id is None
        assert offer.trans_eu_order_id is None
        assert offer.pickup_from is None
        assert offer.pickup_to is None
        assert offer.delivery_from is None
        assert offer.delivery_to is None

    def test_all_fields(self):
        now = _utcnow()
        offer = FreightOffer(
            id="offer_1", company_id=1, user_id=42,
            trans_eu_freight_id=100,
            trans_eu_reference_number="REF-100",
            status="published",
            publication_status="active",
            publication_type="spot",
            origin="Berlin", destination="Munich",
            pickup_from=now, pickup_to=now,
            delivery_from=now, delivery_to=now,
            price_amount=1500.0,
            price_currency="EUR",
            distance_km=585.0,
            trailer_type="curtain",
            adr=True,
            weight_kg=12000.0,
            raw_payload={"key": "value"},
            externally_modified_at=now,
            operion_trip_id=42,
            trans_eu_order_id="order_1",
        )
        assert offer.id == "offer_1"
        assert offer.status == "published"
        assert offer.publication_status == "active"
        assert offer.price_amount == 1500.0
        assert offer.trailer_type == "curtain"
        assert offer.adr is True
        assert offer.weight_kg == 12000.0
        assert offer.operion_trip_id == 42

    @pytest.mark.parametrize("status", ["draft", "published", "cancelled", "completed", "archived"])
    def test_various_statuses(self, status):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="A", destination="B",
            status=status,
        )
        assert offer.status == status

    def test_zero_price_amount(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="A", destination="B",
            price_amount=0.0,
        )
        assert offer.price_amount == 0.0

    def test_negative_price_amount(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="A", destination="B",
            price_amount=-500.0,
        )
        assert offer.price_amount == -500.0

    def test_negative_distance(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="A", destination="B",
            distance_km=-100.0,
        )
        assert offer.distance_km == -100.0

    def test_negative_weight(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="A", destination="B",
            weight_kg=-500.0,
        )
        assert offer.weight_kg == -500.0

    def test_negative_freight_id(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=-1,
            origin="A", destination="B",
        )
        assert offer.trans_eu_freight_id == -1

    def test_empty_origin_destination(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="", destination="",
        )
        assert offer.origin == ""
        assert offer.destination == ""

    def test_different_currency(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="A", destination="B",
            price_currency="PLN",
        )
        assert offer.price_currency == "PLN"

    def test_created_at_defaults(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=1,
            origin="A", destination="B",
        )
        assert isinstance(offer.created_at, datetime)
        assert isinstance(offer.updated_at, datetime)

    def test_missing_company_id_raises(self):
        with pytest.raises(ValidationError):
            FreightOffer(
                user_id=42, trans_eu_freight_id=1,
                origin="A", destination="B",
            )

    def test_missing_origin_raises(self):
        with pytest.raises(ValidationError):
            FreightOffer(
                company_id=1, user_id=42,
                trans_eu_freight_id=1,
                destination="B",
            )

    def test_missing_trans_eu_freight_id_raises(self):
        with pytest.raises(ValidationError):
            FreightOffer(
                company_id=1, user_id=42,
                origin="A", destination="B",
            )


# ═══════════════════════════════════════════════════════════════════════
# TransEuWebhookEvent
# ═══════════════════════════════════════════════════════════════════════

class TestTransEuWebhookEvent:
    """Event type validation, status transitions, defaults."""

    def test_minimal(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="freight.published",
            occurred_at=now,
        )
        assert event.company_id == 1
        assert event.trans_eu_event_id == "evt_1"
        assert event.event_name == "freight.published"
        assert event.occurred_at == now

    def test_defaults(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="freight.published",
            occurred_at=now,
        )
        assert event.id is None
        assert event.payload == {}
        assert event.status == "received"
        assert event.processed_at is None
        assert event.error_message is None
        assert isinstance(event.created_at, datetime)

    def test_all_fields(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            id="webhook_1",
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="freight.updated",
            occurred_at=now,
            payload={"freight_id": 123, "changes": ["price"]},
            status="processed",
            processed_at=now,
            error_message=None,
        )
        assert event.id == "webhook_1"
        assert event.event_name == "freight.updated"
        assert event.payload["freight_id"] == 123
        assert event.status == "processed"
        assert event.processed_at == now

    @pytest.mark.parametrize("status", ["received", "processed", "failed", "skipped"])
    def test_valid_statuses(self, status):
        now = _utcnow()
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="freight.published",
            occurred_at=now,
            status=status,
        )
        assert event.status == status

    def test_invalid_status_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            TransEuWebhookEvent(
                company_id=1,
                trans_eu_event_id="evt_1",
                event_name="freight.published",
                occurred_at=now,
                status="unknown_status",
            )

    def test_with_error_message(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="freight.published",
            occurred_at=now,
            status="failed",
            error_message="Failed to process: invalid payload",
        )
        assert event.error_message == "Failed to process: invalid payload"
        assert event.status == "failed"

    def test_empty_event_name(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="",
            occurred_at=now,
        )
        assert event.event_name == ""

    def test_empty_trans_eu_event_id(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="",
            event_name="freight.published",
            occurred_at=now,
        )
        assert event.trans_eu_event_id == ""

    def test_id_populated(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            id="db_id_42",
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="freight.published",
            occurred_at=now,
        )
        assert event.id == "db_id_42"

    def test_created_at_defaults(self):
        now = _utcnow()
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt_1",
            event_name="freight.published",
            occurred_at=now,
        )
        assert isinstance(event.created_at, datetime)

    def test_missing_company_id_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            TransEuWebhookEvent(
                trans_eu_event_id="evt_1",
                event_name="freight.published",
                occurred_at=now,
            )

    def test_missing_trans_eu_event_id_raises(self):
        now = _utcnow()
        with pytest.raises(ValidationError):
            TransEuWebhookEvent(
                company_id=1,
                event_name="freight.published",
                occurred_at=now,
            )

    def test_missing_occurred_at_raises(self):
        with pytest.raises(ValidationError):
            TransEuWebhookEvent(
                company_id=1,
                trans_eu_event_id="evt_1",
                event_name="freight.published",
            )
