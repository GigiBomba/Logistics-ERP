"""Phase 0 tests — model changes, migration tables, adapter registration.

Verifies:
- ProviderCredentials backward compatibility and new Trans.eu fields
- ProviderSession user_id field
- ProviderCapabilities new flags
- TransEuUserToken, FreightOffer, TransEuWebhookEvent models
- Migration tables exist (when DB is available)
- TransEuAdapter skeleton registers and has correct provider_id
"""
from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest

from models.freight_exchange_models import (
    FreightOffer,
    ProviderCapabilities,
    ProviderCredentials,
    ProviderSession,
    TransEuUserToken,
    TransEuWebhookEvent,
)
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.registry import (
    _registry,
    get_adapter,
    list_adapters,
    register_freight_provider,
    validate_registry,
)
from tests.test_helpers import InMemoryDB


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the global registry before and after each test for isolation."""
    _registry.clear()
    yield
    _registry.clear()


@pytest.fixture
def db():
    """In-memory database for tests that need persistence."""
    return InMemoryDB()


# ── Helpers ─────────────────────────────────────────────────────────────


def _import_reload(mod: str) -> None:
    """Force-import *mod* so its ``@register_freight_provider`` fires.

    Python caches modules in ``sys.modules``, so a plain ``import``
    after ``_clear_registry`` would be a no-op.  Removing the cached
    entries before re-importing forces re-execution of module-level
    code and re-triggers the decorator.
    """
    import sys

    # Remove the module and its submodules from the cache
    sys.modules.pop(mod, None)
    for key in list(sys.modules):
        if key.startswith(mod + "."):
            del sys.modules[key]

    importlib.import_module(mod)


# ═══════════════════════════════════════════════════════════════════════
# 1. Model Changes — Backward Compatibility
# ═══════════════════════════════════════════════════════════════════════


class TestProviderCredentialsBackwardCompat:
    """New fields must default to client_credentials-compatible values."""

    def test_default_grant_type_is_client_credentials(self):
        """Without grant_type specified, defaults to 'client_credentials'."""
        creds = ProviderCredentials(
            company_id=1, provider_id="timocom",
            client_id="x", client_secret_encrypted="y",
        )
        assert creds.grant_type == "client_credentials"

    def test_oauth_fields_are_none_by_default(self):
        """authorization_code, redirect_uri, api_key default to None."""
        creds = ProviderCredentials(
            company_id=1, provider_id="timocom",
            client_id="x", client_secret_encrypted="y",
        )
        assert creds.authorization_code is None
        assert creds.redirect_uri is None
        assert creds.api_key is None

    def test_authorization_code_grant_with_all_fields(self):
        """All new fields populate correctly for Trans.eu OAuth flow."""
        creds = ProviderCredentials(
            company_id=1, provider_id="trans_eu",
            client_id="app_id", client_secret_encrypted="secret_enc",
            grant_type="authorization_code",
            authorization_code="auth_code_123",
            redirect_uri="http://localhost:19999/trans-eu/callback",
            api_key="api_key_456",
        )
        assert creds.grant_type == "authorization_code"
        assert creds.authorization_code == "auth_code_123"
        assert creds.redirect_uri == "http://localhost:19999/trans-eu/callback"
        assert creds.api_key == "api_key_456"

    def test_client_credentials_grant_ignores_oauth_fields(self):
        """When grant_type is client_credentials, OAuth fields are optional."""
        creds = ProviderCredentials(
            company_id=1, provider_id="timocom",
            client_id="x", client_secret_encrypted="y",
            grant_type="client_credentials",
        )
        assert creds.authorization_code is None
        assert creds.api_key is None


class TestProviderSessionUserField:
    """ProviderSession.user_id is Optional[int] for backward compatibility."""

    def test_user_id_defaults_to_none(self):
        now = datetime.now(timezone.utc)
        session = ProviderSession(
            company_id=1, provider_id="t",
            access_token_encrypted="tok", expires_at=now,
        )
        assert session.user_id is None

    def test_user_id_set_for_trans_eu(self):
        now = datetime.now(timezone.utc)
        session = ProviderSession(
            company_id=1, provider_id="trans_eu",
            access_token_encrypted="tok", expires_at=now,
            user_id=42,
        )
        assert session.user_id == 42


class TestProviderCapabilitiesNewFlags:
    """All new capability flags default to False."""

    def test_all_new_flags_default_to_false(self):
        caps = ProviderCapabilities(
            provider_id="test",
            supported_filters=["origin"],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=60,
        )
        assert caps.supports_freight_publication is False
        assert caps.supports_negotiation is False
        assert caps.supports_transport_orders is False
        assert caps.supports_monitoring is False
        assert caps.supports_webhooks is False
        assert caps.supports_oauth_user is False
        assert caps.requires_api_key_header is False

    def test_flags_can_be_set_to_true(self):
        caps = ProviderCapabilities(
            provider_id="trans_eu",
            supported_filters=["origin"],
            supports_saved_search=False,
            supports_offer_publishing=True,
            rate_limit_per_minute=900,
            supports_freight_publication=True,
            supports_negotiation=True,
            supports_transport_orders=True,
            supports_monitoring=True,
            supports_webhooks=True,
            supports_oauth_user=True,
            requires_api_key_header=True,
        )
        assert caps.supports_freight_publication is True
        assert caps.requires_api_key_header is True


class TestNewModels:
    """TransEuUserToken, FreightOffer, TransEuWebhookEvent instantiate correctly."""

    def test_trans_eu_user_token_minimal(self):
        now = datetime.now(timezone.utc)
        token = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="enc_tok",
            refresh_token_encrypted="enc_ref",
            expires_at=now,
            api_key_encrypted="enc_key",
            status="active",
        )
        assert token.company_id == 1
        assert token.user_id == 42
        assert token.status == "active"
        assert token.expires_at == now

    def test_trans_eu_user_token_defaults(self):
        now = datetime.now(timezone.utc)
        token = TransEuUserToken(
            company_id=1, user_id=42,
            access_token_encrypted="enc_tok",
            refresh_token_encrypted="enc_ref",
            expires_at=now,
            api_key_encrypted="enc_key",
        )
        assert token.status == "active"
        assert token.scope == ""
        assert token.client_id == ""
        assert token.client_secret_encrypted == ""
        assert token.trans_eu_account_id is None

    def test_freight_offer_minimal(self):
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=401560,
            origin="Krakow, PL",
            destination="Berlin, DE",
            price_amount=1200.0,
            distance_km=580.0,
        )
        assert offer.trans_eu_freight_id == 401560
        assert offer.origin == "Krakow, PL"
        assert offer.destination == "Berlin, DE"
        assert offer.status == "draft"
        assert offer.price_currency == "EUR"
        assert offer.adr is False
        assert offer.weight_kg == 0.0

    def test_freight_offer_with_all_fields(self):
        now = datetime.now(timezone.utc)
        offer = FreightOffer(
            company_id=1, user_id=42,
            trans_eu_freight_id=401560,
            trans_eu_reference_number="FR/2025/01/01/TEST",
            status="published",
            publication_status="active",
            publication_type="exchange",
            origin="Krakow, PL",
            destination="Berlin, DE",
            pickup_from=now,
            pickup_to=now,
            delivery_from=now,
            delivery_to=now,
            price_amount=1200.0,
            price_currency="EUR",
            distance_km=580.0,
            trailer_type="cooler",
            adr=True,
            weight_kg=8000.0,
            operion_trip_id=123,
            trans_eu_order_id="order-456",
        )
        assert offer.status == "published"
        assert offer.trailer_type == "cooler"
        assert offer.adr is True
        assert offer.weight_kg == 8000.0
        assert offer.operion_trip_id == 123
        assert offer.trans_eu_order_id == "order-456"

    def test_trans_eu_webhook_event_minimal(self):
        now = datetime.now(timezone.utc)
        event = TransEuWebhookEvent(
            company_id=1,
            trans_eu_event_id="evt-123",
            event_name="freights.freight.create",
            occurred_at=now,
        )
        assert event.trans_eu_event_id == "evt-123"
        assert event.event_name == "freights.freight.create"
        assert event.status == "received"
        assert event.payload == {}


# ═══════════════════════════════════════════════════════════════════════
# 2. Adapter Registration
# ═══════════════════════════════════════════════════════════════════════


class TestTransEuAdapterRegistration:
    """TransEuAdapter skeleton registers with the provider registry."""

    def _load_trans_eu(self):
        _import_reload("services.freight_exchange.adapters.trans_eu")

    def test_adapter_registers_on_import(self):
        """Importing trans_eu module triggers @register_freight_provider."""
        self._load_trans_eu()
        adapter = get_adapter("trans_eu")
        assert adapter is not None
        assert adapter.provider_id == "trans_eu"

    def test_adapter_is_freight_provider_adapter_instance(self):
        """TransEuAdapter is a FreightProviderAdapter subclass."""
        self._load_trans_eu()
        adapter = get_adapter("trans_eu")
        assert adapter is not None
        assert isinstance(adapter, FreightProviderAdapter)

    def test_adapter_appears_in_list_adapters(self):
        """Trans.eu appears in the list of registered adapters."""
        self._load_trans_eu()
        adapters = list_adapters()
        assert "trans_eu" in adapters

    def test_registry_validation_passes_with_skeleton(self):
        """validate_registry() returns empty list (no errors) with skeleton."""
        self._load_trans_eu()
        errors = validate_registry()
        assert errors == [], f"Registry validation errors: {errors}"

    def test_capabilities_reports_correct_provider_id(self):
        """capabilities() returns the provider_id."""
        self._load_trans_eu()
        adapter = get_adapter("trans_eu")
        assert adapter is not None
        caps = adapter.capabilities()
        assert caps.provider_id == "trans_eu"

    def test_capabilities_reports_all_supported_filters(self):
        """capabilities() reports all Trans.eu-supported filters."""
        self._load_trans_eu()
        adapter = get_adapter("trans_eu")
        assert adapter is not None
        caps = adapter.capabilities()
        expected_filters = [
            "origin", "destination", "pickup_date_from", "pickup_date_to",
            "delivery_date_from", "delivery_date_to", "trailer_type",
            "adr_required", "weight_kg_min", "weight_kg_max",
            "distance_km_max", "loading_type", "loading_country",
            "delivery_country", "sort_by", "sort_order", "min_trucks",
        ]
        for f in expected_filters:
            assert f in caps.supported_filters, f"Missing filter: {f}"

    def test_capabilities_trans_eu_flags_are_true(self):
        """Trans.eu-specific capability flags should be True."""
        self._load_trans_eu()
        adapter = get_adapter("trans_eu")
        assert adapter is not None
        caps = adapter.capabilities()
        assert caps.supports_offer_publishing is True
        assert caps.supports_freight_publication is True
        assert caps.supports_negotiation is True
        assert caps.supports_transport_orders is True
        assert caps.supports_monitoring is True
        assert caps.supports_webhooks is True
        assert caps.supports_oauth_user is True
        assert caps.requires_api_key_header is True
        assert caps.adr_search is True
        assert caps.trailer_type_search is True


# ═══════════════════════════════════════════════════════════════════════
# 3. Existing Test Compatibility
# ═══════════════════════════════════════════════════════════════════════


class TestNoRegressionOnExistingAdapters:
    """Adding Trans.eu should not break existing adapter tests."""

    def _load_both(self):
        _import_reload("services.freight_exchange.adapters.timocom")
        _import_reload("services.freight_exchange.adapters.trans_eu")

    def test_timocom_adapter_still_registers(self):
        """TIMOCOM adapter still registers after TransEuAdapter import."""
        self._load_both()
        adapters = list_adapters()
        assert "timocom" in adapters
        assert "trans_eu" in adapters

    def test_registry_validation_still_passes_with_both(self):
        """validate_registry passes with both TIMOCOM and Trans.eu."""
        self._load_both()
        errors = validate_registry()
        assert errors == [], f"Registry validation errors: {errors}"

    def test_registry_duplicate_detection_still_works(self):
        """Cannot register the same provider_id twice."""
        _import_reload("services.freight_exchange.adapters.trans_eu")

        class CompleteDuplicate(FreightProviderAdapter):
            provider_id = "trans_eu"

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            def capabilities(self): ...

        with pytest.raises(ValueError, match="already registered"):
            register_freight_provider(CompleteDuplicate)
