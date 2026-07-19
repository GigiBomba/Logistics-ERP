"""Comprehensive unit tests for the Freight Exchange adapter layer.

Tests cover:
- ABC enforcement (FreightProviderAdapter)
- Registry decorator (registration, duplicate, type checking)
- Registry lookup (get_adapter, list_adapters, missing)
- Registry validation (missing methods, abstract methods)
- ProviderCapabilities model fields and defaults
- GeoFilter model required fields and radius validation
- LoadSearchFilters defaults and Optional fields
- ProviderSession Optional health fields
- Multiple adapter coexistence
- Registry isolation (clearing and re-registering)
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from models.freight_exchange_models import (
    GeoFilter,
    LoadSearchFilters,
    ProviderCapabilities,
    ProviderCredentials,
    ProviderHealthCheck,
    ProviderSession,
)
from services.freight_exchange.adapter_base import FreightProviderAdapter
from services.freight_exchange.registry import (
    _registry,
    get_adapter,
    get_all_adapters,
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
    """In-memory database — available for any test that needs persistence."""
    return InMemoryDB()


# ═══════════════════════════════════════════════════════════════════════
# 1. ABC Enforcement
# ═══════════════════════════════════════════════════════════════════════


class TestAbcEnforcement:
    """FreightProviderAdapter cannot be instantiated directly; subclasses
    must implement all six abstract methods."""

    def test_cannot_instantiate_abc_directly(self):
        """Cannot instantiate FreightProviderAdapter directly — it is an ABC."""
        with pytest.raises(TypeError):
            FreightProviderAdapter()

    def test_subclass_missing_all_abstract_raises(self):
        """Subclass that implements no abstract methods cannot be instantiated."""

        class IncompleteAdapter(FreightProviderAdapter):
            provider_id = "incomplete"

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_subclass_missing_one_method_raises(self):
        """Subclass missing even a single abstract method cannot be instantiated."""

        class MissingOne(FreightProviderAdapter):
            provider_id = "missing_one"

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            # capabilities() is intentionally omitted

        with pytest.raises(TypeError):
            MissingOne()

    def test_complete_adapter_can_instantiate(self):
        """Subclass implementing all six abstract methods can be instantiated."""

        class CompleteAdapter(FreightProviderAdapter):
            provider_id = "complete"

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            def capabilities(self): ...

        instance = CompleteAdapter()
        assert instance.provider_id == "complete"


# ═══════════════════════════════════════════════════════════════════════
# 2. Registry Decorator
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryDecorator:
    """@register_freight_provider decorator — registration, rejection, validation."""

    @staticmethod
    def _make_complete_cls(pid: str):
        """Build a complete adapter class for testing."""

        class _(FreightProviderAdapter):
            provider_id = pid

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            def capabilities(self): ...

        return _

    def test_registration_success(self):
        """A complete adapter class is registered and accessible."""
        cls = self._make_complete_cls("test_reg")
        result = register_freight_provider(cls)
        assert result is cls
        adapter = get_adapter("test_reg")
        assert adapter is not None
        assert adapter.provider_id == "test_reg"

    def test_duplicate_registration_raises(self):
        """Registering two adapters with the same provider_id raises ValueError."""
        cls1 = self._make_complete_cls("duplicate")
        register_freight_provider(cls1)
        cls2 = self._make_complete_cls("duplicate")
        with pytest.raises(ValueError, match="already registered"):
            register_freight_provider(cls2)

    def test_non_adapter_class_raises_type_error(self):
        """A class that does not subclass FreightProviderAdapter raises TypeError."""

        class NotAnAdapter:
            provider_id = "not_an_adapter"

        with pytest.raises(TypeError, match="must be a subclass"):
            register_freight_provider(NotAnAdapter)

    def test_empty_provider_id_raises_value_error(self):
        """A class with an empty provider_id string raises ValueError."""
        cls = self._make_complete_cls("")
        with pytest.raises(ValueError, match="non-empty provider_id"):
            register_freight_provider(cls)


# ═══════════════════════════════════════════════════════════════════════
# 3. Registry Lookup
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryLookup:
    """Lookup functions: get_adapter, list_adapters, get_all_adapters."""

    @staticmethod
    def _register(pid: str):
        class _(FreightProviderAdapter):
            provider_id = pid

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            def capabilities(self): ...

        register_freight_provider(_)

    def test_get_adapter_returns_instance(self):
        self._register("prov_a")
        adapter = get_adapter("prov_a")
        assert adapter is not None
        assert adapter.provider_id == "prov_a"

    def test_get_adapter_missing_returns_none(self):
        """Looking up an unregistered provider_id returns None."""
        assert get_adapter("nonexistent") is None

    def test_list_adapters_empty_when_nothing_registered(self):
        assert list_adapters() == []

    def test_list_adapters_returns_all_ids(self):
        self._register("alpha")
        self._register("beta")
        ids = list_adapters()
        assert "alpha" in ids
        assert "beta" in ids
        assert len(ids) == 2

    def test_get_all_adapters_returns_dict_copy(self):
        self._register("gamma")
        all_adapters = get_all_adapters()
        assert isinstance(all_adapters, dict)
        assert "gamma" in all_adapters
        # Verify it is a copy — mutating the result does not affect registry
        all_adapters.clear()
        assert get_adapter("gamma") is not None


# ═══════════════════════════════════════════════════════════════════════
# 4. Registry Validation
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryValidation:
    """validate_registry — detects missing / still-abstract methods."""

    @staticmethod
    def _make_valid(pid: str):
        class _(FreightProviderAdapter):
            provider_id = pid

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            def capabilities(self): ...

        register_freight_provider(_)

    def test_valid_registry_returns_no_errors(self):
        self._make_valid("valid_prov")
        errors = validate_registry()
        assert errors == []

    def test_empty_registry_returns_no_errors(self):
        errors = validate_registry()
        assert errors == []

    def test_missing_method_detected(self):
        self._make_valid("missing_method")
        # Delete the capabilities method from the registered class
        adapter_cls = get_adapter("missing_method").__class__
        del adapter_cls.capabilities
        errors = validate_registry()
        assert any("capabilities" in e for e in errors)

    def test_abstract_method_detected(self):
        self._make_valid("abstract_method")
        adapter_cls = get_adapter("abstract_method").__class__

        # Replace capabilities with a function marked as abstract
        async def abstract_capabilities(self):
            ...

        abstract_capabilities.__isabstractmethod__ = True
        adapter_cls.capabilities = abstract_capabilities

        errors = validate_registry()
        assert any("capabilities" in e for e in errors)
        assert any("still abstract" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════
# 5. ProviderCapabilities Model
# ═══════════════════════════════════════════════════════════════════════


class TestProviderCapabilitiesModel:
    """ProviderCapabilities — all fields, defaults for optional booleans."""

    def test_all_required_fields(self):
        caps = ProviderCapabilities(
            provider_id="test_prov",
            supported_filters=["origin", "destination"],
            supports_saved_search=True,
            supports_offer_publishing=False,
            rate_limit_per_minute=30,
        )
        assert caps.provider_id == "test_prov"
        assert caps.supported_filters == ["origin", "destination"]
        assert caps.supports_saved_search is True
        assert caps.supports_offer_publishing is False
        assert caps.rate_limit_per_minute == 30

    def test_optional_bool_defaults(self):
        """adr_search and trailer_type_search default to False when omitted."""
        caps = ProviderCapabilities(
            provider_id="p",
            supported_filters=[],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=10,
        )
        assert caps.adr_search is False
        assert caps.trailer_type_search is False

    def test_optional_bools_can_be_overridden(self):
        caps = ProviderCapabilities(
            provider_id="p",
            supported_filters=[],
            supports_saved_search=False,
            supports_offer_publishing=False,
            rate_limit_per_minute=10,
            adr_search=True,
            trailer_type_search=True,
        )
        assert caps.adr_search is True
        assert caps.trailer_type_search is True


# ═══════════════════════════════════════════════════════════════════════
# 6. GeoFilter Model
# ═══════════════════════════════════════════════════════════════════════


class TestGeoFilterModel:
    """GeoFilter — required fields, radius_km validation."""

    def test_required_fields(self):
        gf = GeoFilter(location="Berlin", radius_km=50.0)
        assert gf.location == "Berlin"
        assert gf.radius_km == 50.0

    def test_radius_can_be_zero(self):
        gf = GeoFilter(location="Paris", radius_km=0.0)
        assert gf.radius_km == 0.0

    def test_radius_can_be_fractional(self):
        gf = GeoFilter(location="Munich", radius_km=25.5)
        assert gf.radius_km == 25.5

    def test_radius_negative_is_allowed_pydantic(self):
        """Pydantic does not enforce non-negative by default — accept float."""
        gf = GeoFilter(location="Nowhere", radius_km=-10.0)
        assert gf.radius_km == -10.0


# ═══════════════════════════════════════════════════════════════════════
# 7. LoadSearchFilters
# ═══════════════════════════════════════════════════════════════════════


class TestLoadSearchFilters:
    """LoadSearchFilters — Origin/destination are Optional (new behaviour)."""

    def test_origin_destination_optional(self):
        """LoadSearchFilters can be constructed without origin/destination."""
        lsf = LoadSearchFilters(
            pickup_date_from="2026-01-01",
            pickup_date_to="2026-01-05",
        )
        assert lsf.origin is None
        assert lsf.destination is None

    def test_required_date_fields(self):
        """pickup_date_from and pickup_date_to are required."""
        lsf = LoadSearchFilters(
            pickup_date_from=date(2026, 1, 1),
            pickup_date_to=date(2026, 1, 5),
        )
        assert lsf.pickup_date_from == date(2026, 1, 1)
        assert lsf.pickup_date_to == date(2026, 1, 5)

    def test_origin_destination_can_be_set(self):
        """When provided, origin and destination are stored correctly."""
        lsf = LoadSearchFilters(
            pickup_date_from="2026-01-01",
            pickup_date_to="2026-01-05",
            origin=GeoFilter(location="Berlin", radius_km=100.0),
            destination=GeoFilter(location="Munich", radius_km=50.0),
        )
        assert lsf.origin is not None
        assert lsf.origin.location == "Berlin"
        assert lsf.origin.radius_km == 100.0
        assert lsf.destination is not None
        assert lsf.destination.location == "Munich"
        assert lsf.destination.radius_km == 50.0

    def test_extra_filters_defaults_to_empty_dict(self):
        lsf = LoadSearchFilters(
            pickup_date_from="2026-01-01",
            pickup_date_to="2026-01-05",
        )
        assert lsf.extra_filters == {}

    def test_string_dates_parsed_to_date_object(self):
        """ISO-format strings are coerced to date by Pydantic."""
        lsf = LoadSearchFilters(
            pickup_date_from="2026-01-01",
            pickup_date_to="2026-01-05",
        )
        assert isinstance(lsf.pickup_date_from, date)
        assert isinstance(lsf.pickup_date_to, date)


# ═══════════════════════════════════════════════════════════════════════
# 8. ProviderSession — Optional Health Fields
# ═══════════════════════════════════════════════════════════════════════


class TestProviderSessionHealth:
    """ProviderSession — last_health_check_* fields are Optional, default None."""

    def test_health_fields_default_to_none(self):
        """ProviderSession can be constructed without health fields."""
        ps = ProviderSession(
            company_id=1,
            provider_id="t",
            access_token_encrypted="x",
            expires_at=datetime.now(timezone.utc),
        )
        assert ps.last_health_check_at is None
        assert ps.last_health_check_status is None

    def test_health_fields_can_be_set(self):
        now = datetime.now(timezone.utc)
        ps = ProviderSession(
            company_id=1,
            provider_id="t",
            access_token_encrypted="x",
            expires_at=now,
            last_health_check_at=now,
            last_health_check_status="healthy",
        )
        assert ps.last_health_check_at == now
        assert ps.last_health_check_status == "healthy"

    def test_health_status_accepts_all_literals(self):
        now = datetime.now(timezone.utc)
        for status in ("healthy", "degraded", "down"):
            ps = ProviderSession(
                company_id=1,
                provider_id="t",
                access_token_encrypted="x",
                expires_at=now,
                last_health_check_status=status,  # type: ignore[arg-type]
            )
            assert ps.last_health_check_status == status

    def test_refresh_token_defaults_to_none(self):
        ps = ProviderSession(
            company_id=1,
            provider_id="t",
            access_token_encrypted="x",
            expires_at=datetime.now(timezone.utc),
        )
        assert ps.refresh_token_encrypted is None


# ═══════════════════════════════════════════════════════════════════════
# 9. Multiple Adapter Coexistence
# ═══════════════════════════════════════════════════════════════════════


class TestMultipleAdapterCoexistence:
    """Multiple adapters can coexist in the registry simultaneously."""

    @staticmethod
    def _build(pid: str):
        class _(FreightProviderAdapter):
            provider_id = pid

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            def capabilities(self): ...

        return _

    def test_three_adapters_registered(self):
        register_freight_provider(self._build("alpha"))
        register_freight_provider(self._build("beta"))
        register_freight_provider(self._build("gamma"))
        ids = list_adapters()
        assert len(ids) == 3
        for pid in ("alpha", "beta", "gamma"):
            assert pid in ids

    def test_each_adapter_is_distinct_instance(self):
        register_freight_provider(self._build("a"))
        register_freight_provider(self._build("b"))
        assert get_adapter("a") is not get_adapter("b")
        assert get_adapter("a").provider_id == "a"
        assert get_adapter("b").provider_id == "b"

    def test_removing_one_does_not_affect_others(self):
        register_freight_provider(self._build("x"))
        register_freight_provider(self._build("y"))
        del _registry["x"]
        assert get_adapter("x") is None
        assert get_adapter("y") is not None


# ═══════════════════════════════════════════════════════════════════════
# 10. Registry Isolation
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryIsolation:
    """Registry isolation — clearing and re-registering."""

    @staticmethod
    def _build(pid: str):
        class _(FreightProviderAdapter):
            provider_id = pid

            async def authenticate(self, creds): ...
            async def refresh_session(self, session): ...
            async def test_connection(self, session): ...
            async def search_loads(self, session, filters): ...
            async def get_load(self, session, load_id): ...
            def capabilities(self): ...

        return _

    def test_clear_via_direct_access(self):
        register_freight_provider(self._build("isolated"))
        assert len(list_adapters()) == 1
        _registry.clear()
        assert list_adapters() == []

    def test_reregister_after_clear(self):
        register_freight_provider(self._build("rerun"))
        _registry.clear()
        register_freight_provider(self._build("rerun"))
        adapter = get_adapter("rerun")
        assert adapter is not None
        assert adapter.provider_id == "rerun"

    def test_registry_isolation_between_tests(self):
        """The autouse _clear_registry fixture ensures each test starts empty."""
        assert list_adapters() == []
