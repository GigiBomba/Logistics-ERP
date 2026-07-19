"""Tests for backend/schemas/waitlist.py — WaitlistJoinRequest,
WaitlistEntryUpdate, WaitlistEntryResponse, WaitlistPageResponse,
WaitlistStatsResponse, and module-level constants."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.waitlist import (
    COMPANY_SIZE_VALUES,
    FLEET_SIZE_VALUES,
    VALID_TRANSITIONS,
    WAITLIST_STATUS_VALUES,
    WaitlistEntryResponse,
    WaitlistEntryUpdate,
    WaitlistJoinRequest,
    WaitlistJoinResponse,
    WaitlistPageResponse,
    WaitlistStatsResponse,
)


# ── Module-level constants ─────────────────────────────────────────────────────


class TestConstants:
    """Verify the module-level constant sets."""

    def test_fleet_size_values(self):
        assert FLEET_SIZE_VALUES == {"1-5", "6-20", "21-50", "51-200", "200+"}

    def test_company_size_values(self):
        assert COMPANY_SIZE_VALUES == {"solo", "2-10", "11-50", "51-200", "200+"}

    def test_waitlist_status_values(self):
        expected = {"joined", "invited", "activated", "converted", "churned", "unsubscribed"}
        assert WAITLIST_STATUS_VALUES == expected

    def test_valid_transitions_joined(self):
        assert VALID_TRANSITIONS["joined"] == {"invited", "churned", "unsubscribed"}

    def test_valid_transitions_invited(self):
        assert VALID_TRANSITIONS["invited"] == {"activated", "churned", "unsubscribed"}

    def test_valid_transitions_activated(self):
        assert VALID_TRANSITIONS["activated"] == {"converted", "churned", "unsubscribed"}

    def test_valid_transitions_converted(self):
        assert VALID_TRANSITIONS["converted"] == {"churned", "unsubscribed"}

    def test_valid_transitions_churned(self):
        assert VALID_TRANSITIONS["churned"] == set()

    def test_valid_transitions_unsubscribed(self):
        assert VALID_TRANSITIONS["unsubscribed"] == set()

    def test_no_unknown_keys_in_transitions(self):
        known = {"joined", "invited", "activated", "converted", "churned", "unsubscribed"}
        assert set(VALID_TRANSITIONS.keys()) == known


# ── WaitlistJoinRequest ────────────────────────────────────────────────────────


class TestWaitlistJoinRequest:
    """company_name (min_length=1), email (required), country (max_length=2),
    hp_field (optional honeypot), source (default)."""

    VALID_PAYLOAD: Dict[str, Any] = {
        "company_name": "Acme Transport",
        "email": "user@acme.com",
    }

    def test_minimal_valid(self):
        inst = WaitlistJoinRequest(**self.VALID_PAYLOAD)
        assert inst.company_name == "Acme Transport"
        assert inst.email == "user@acme.com"
        assert inst.source == "landing_page"
        assert inst.contact_name is None
        assert inst.fleet_size is None
        assert inst.company_size is None
        assert inst.country is None
        assert inst.hp_field is None

    def test_all_fields(self):
        inst = WaitlistJoinRequest(
            company_name="Big Fleet Ltd",
            contact_name="John",
            email="john@bigfleet.com",
            fleet_size="51-200",
            company_size="200+",
            country="DE",
            source="facebook_ad",
            hp_field="",
        )
        assert inst.company_name == "Big Fleet Ltd"
        assert inst.contact_name == "John"
        assert inst.country == "DE"
        assert inst.source == "facebook_ad"
        assert inst.hp_field == ""

    def test_company_name_empty_raises(self):
        with pytest.raises(ValidationError):
            WaitlistJoinRequest(company_name="", email="x@y.com")

    def test_company_name_missing_raises(self):
        with pytest.raises(ValidationError):
            WaitlistJoinRequest(email="x@y.com")  # type: ignore[call-arg]

    # ── email validation ──

    def test_email_missing_raises(self):
        with pytest.raises(ValidationError):
            WaitlistJoinRequest(company_name="Acme")  # type: ignore[call-arg]

    def test_email_none_raises(self):
        with pytest.raises(ValidationError):
            WaitlistJoinRequest(company_name="Acme", email=None)  # type: ignore[arg-type]

    def test_email_empty_is_valid(self):
        """No min_length on email — empty string is accepted."""
        inst = WaitlistJoinRequest(company_name="Acme", email="")
        assert inst.email == ""

    def test_email_invalid_format_is_accepted_by_pydantic(self):
        """Pydantic BaseModel doesn't validate email format by default — string is fine."""
        inst = WaitlistJoinRequest(company_name="Acme", email="not-an-email")
        assert inst.email == "not-an-email"

    # ── country max_length ──

    def test_country_valid_two_letters(self):
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com", country="RO")
        assert inst.country == "RO"

    def test_country_max_length_exact(self):
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com", country="AB")
        assert inst.country == "AB"

    def test_country_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            WaitlistJoinRequest(company_name="Acme", email="x@y.com", country="USA")

    def test_country_single_character_is_valid(self):
        """max_length=2 means 1 char is fine."""
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com", country="U")
        assert inst.country == "U"

    def test_country_none_is_valid(self):
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com", country=None)
        assert inst.country is None

    # ── hp_field (honeypot) ──

    def test_hp_field_set_to_empty_string(self):
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com", hp_field="")
        assert inst.hp_field == ""

    def test_hp_field_set_to_non_empty(self):
        """Honeypot should be left empty, but the schema only stores it — validation is external."""
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com", hp_field="bot_value")
        assert inst.hp_field == "bot_value"

    def test_hp_field_default_none(self):
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com")
        assert inst.hp_field is None

    # ── source default ──

    def test_source_defaults_to_landing_page(self):
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com")
        assert inst.source == "landing_page"

    def test_source_custom(self):
        inst = WaitlistJoinRequest(company_name="Acme", email="x@y.com", source="referral")
        assert inst.source == "referral"


# ── WaitlistJoinResponse ───────────────────────────────────────────────────────


class TestWaitlistJoinResponse:
    """status (default joined), referral_code (required)."""

    def test_minimal_valid(self):
        inst = WaitlistJoinResponse(referral_code="CODE123")
        assert inst.referral_code == "CODE123"
        assert inst.status == "joined"

    def test_custom_status(self):
        inst = WaitlistJoinResponse(referral_code="CODE123", status="invited")
        assert inst.status == "invited"

    def test_missing_referral_code_raises(self):
        with pytest.raises(ValidationError):
            WaitlistJoinResponse()  # type: ignore[call-arg]


# ── WaitlistEntryUpdate ────────────────────────────────────────────────────────


class TestWaitlistEntryUpdate:
    """status (optional), notes (optional), admin_override (default False)."""

    def test_defaults(self):
        inst = WaitlistEntryUpdate()
        assert inst.status is None
        assert inst.notes is None
        assert inst.admin_override is False

    def test_all_fields(self):
        inst = WaitlistEntryUpdate(status="activated", notes="Done", admin_override=True)
        assert inst.status == "activated"
        assert inst.notes == "Done"
        assert inst.admin_override is True

    def test_status_optional_none(self):
        inst = WaitlistEntryUpdate(status=None)
        assert inst.status is None

    def test_admin_override_false(self):
        inst = WaitlistEntryUpdate(admin_override=True)
        assert inst.admin_override is True

    def test_notes_empty_string(self):
        inst = WaitlistEntryUpdate(notes="")
        assert inst.notes == ""

    def test_admin_override_non_bool_raises(self):
        """Pydantic coerces some strings to bool, but list/object types raise."""
        with pytest.raises(ValidationError):
            WaitlistEntryUpdate(admin_override=[1, 2, 3])  # type: ignore[arg-type]


# ── WaitlistEntryResponse ──────────────────────────────────────────────────────


class TestWaitlistEntryResponse:
    """All fields present in the response model."""

    MINIMAL: Dict[str, Any] = {
        "id": 1,
        "company_name": "Acme",
        "email": "a@b.com",
        "source": "web",
        "referral_code": "R1",
        "status": "joined",
        "joined_at": "2025-01-01T00:00:00Z",
    }

    def test_minimal_valid(self):
        inst = WaitlistEntryResponse(**self.MINIMAL)
        assert inst.id == 1
        assert inst.company_name == "Acme"
        assert inst.contact_name is None
        assert inst.referral_code == "R1"

    def test_all_fields(self):
        data: Dict[str, Any] = {
            **self.MINIMAL,
            "contact_name": "John",
            "fleet_size": "21-50",
            "company_size": "11-50",
            "country": "RO",
            "referred_by": "REF1",
            "invited_at": "2025-02-01T00:00:00Z",
            "activated_at": "2025-03-01T00:00:00Z",
            "converted_at": "2025-04-01T00:00:00Z",
            "notes": "Some notes",
            "user_agent": "Mozilla/5.0",
            "unsubscribed_at": None,
        }
        inst = WaitlistEntryResponse(**data)
        assert inst.contact_name == "John"
        assert inst.fleet_size == "21-50"
        assert inst.country == "RO"
        assert inst.referred_by == "REF1"
        assert inst.invited_at == "2025-02-01T00:00:00Z"
        assert inst.notes == "Some notes"
        assert inst.user_agent == "Mozilla/5.0"
        assert inst.unsubscribed_at is None

    def test_missing_id_raises(self):
        data = {k: v for k, v in self.MINIMAL.items() if k != "id"}
        with pytest.raises(ValidationError):
            WaitlistEntryResponse(**data)

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            WaitlistEntryResponse()  # type: ignore[call-arg]

    def test_type_mismatch_id(self):
        with pytest.raises(ValidationError):
            WaitlistEntryResponse(**{**self.MINIMAL, "id": "not-an-int"})  # type: ignore[arg-type]


# ── WaitlistPageResponse ───────────────────────────────────────────────────────


class TestWaitlistPageResponse:
    """entries (list[WaitlistEntryResponse]), total, page, page_size, by_status."""

    ENTRY = {
        "id": 1,
        "company_name": "Acme",
        "email": "a@b.com",
        "source": "web",
        "referral_code": "R1",
        "status": "joined",
        "joined_at": "2025-01-01T00:00:00Z",
    }

    VALID_PAGE: Dict[str, Any] = {
        "entries": [ENTRY],
        "total": 1,
        "page": 1,
        "page_size": 50,
        "by_status": {"joined": 1},
    }

    def test_minimal_valid(self):
        inst = WaitlistPageResponse(**self.VALID_PAGE)
        assert len(inst.entries) == 1
        assert inst.total == 1
        assert inst.page == 1
        assert inst.page_size == 50
        assert inst.by_status == {"joined": 1}

    def test_multiple_entries(self):
        entry2 = {**self.ENTRY, "id": 2, "company_name": "Beta"}
        data = {**self.VALID_PAGE, "entries": [self.ENTRY, entry2], "total": 2}
        inst = WaitlistPageResponse(**data)
        assert len(inst.entries) == 2
        assert inst.total == 2

    def test_empty_entries(self):
        data = {**self.VALID_PAGE, "entries": [], "total": 0, "by_status": {}}
        inst = WaitlistPageResponse(**data)
        assert inst.entries == []

    def test_missing_total_raises(self):
        data = {k: v for k, v in self.VALID_PAGE.items() if k != "total"}
        with pytest.raises(ValidationError):
            WaitlistPageResponse(**data)

    def test_missing_entries_raises(self):
        data = {k: v for k, v in self.VALID_PAGE.items() if k != "entries"}
        with pytest.raises(ValidationError):
            WaitlistPageResponse(**data)

    def test_invalid_entry_type_raises(self):
        with pytest.raises(ValidationError):
            WaitlistPageResponse(**{**self.VALID_PAGE, "entries": ["not-a-dict"]})  # type: ignore[arg-type]

    def test_page_zero(self):
        """Page can be 0 — no gt/ge constraint."""
        data = {**self.VALID_PAGE, "page": 0}
        inst = WaitlistPageResponse(**data)
        assert inst.page == 0

    def test_page_negative(self):
        """Negative page — no constraint, so it's accepted."""
        data = {**self.VALID_PAGE, "page": -1}
        inst = WaitlistPageResponse(**data)
        assert inst.page == -1


# ── WaitlistStatsResponse ──────────────────────────────────────────────────────


class TestWaitlistStatsResponse:
    """total, by_status, by_country, by_company_size, by_fleet_size,
    by_source, growth_daily, conversion_rate."""

    MINIMAL: Dict[str, Any] = {
        "total": 100,
        "by_status": {"joined": 80, "invited": 20},
        "by_country": {"RO": 50, "DE": 50},
        "by_company_size": {"solo": 30, "2-10": 70},
        "by_fleet_size": {"1-5": 40, "6-20": 60},
        "by_source": {"landing_page": 90, "referral": 10},
        "growth_daily": [{"date": "2025-01-01", "count": 5}],
        "conversion_rate": 0.25,
    }

    def test_minimal_valid(self):
        inst = WaitlistStatsResponse(**self.MINIMAL)
        assert inst.total == 100
        assert inst.by_status["joined"] == 80
        assert inst.conversion_rate == 0.25
        assert len(inst.growth_daily) == 1

    def test_empty_dicts(self):
        data = {**self.MINIMAL, "by_status": {}, "by_country": {}}
        inst = WaitlistStatsResponse(**data)
        assert inst.by_status == {}
        assert inst.by_country == {}

    def test_empty_growth_daily(self):
        data = {**self.MINIMAL, "growth_daily": []}
        inst = WaitlistStatsResponse(**data)
        assert inst.growth_daily == []

    def test_conversion_rate_zero(self):
        data = {**self.MINIMAL, "conversion_rate": 0.0}
        inst = WaitlistStatsResponse(**data)
        assert inst.conversion_rate == 0.0

    def test_conversion_rate_negative(self):
        """No constraint on conversion_rate — negative accepted."""
        data = {**self.MINIMAL, "conversion_rate": -1.5}
        inst = WaitlistStatsResponse(**data)
        assert inst.conversion_rate == -1.5

    def test_total_negative(self):
        """No gt constraint — negative accepted."""
        data = {**self.MINIMAL, "total": -5}
        inst = WaitlistStatsResponse(**data)
        assert inst.total == -5

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            WaitlistStatsResponse()  # type: ignore[call-arg]

    def test_type_mismatch_total(self):
        with pytest.raises(ValidationError):
            WaitlistStatsResponse(**{**self.MINIMAL, "total": "one-hundred"})  # type: ignore[arg-type]
