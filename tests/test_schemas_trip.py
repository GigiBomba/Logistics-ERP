"""Tests for backend/schemas/trip.py — TripBase, TripResponse, TripSearchParams."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.trip import TripBase, TripResponse, TripSearchParams


# ── TripBase ──────────────────────────────────────────────────────────────────


class TestTripBase:
    """extra="forbid"."""

    def test_defaults(self):
        inst = TripBase()
        assert inst.client_name == ""
        assert inst.loading_city == ""
        assert inst.loading_country is None
        assert inst.delivery_city == ""
        assert inst.delivery_country is None

    def test_all_fields(self):
        inst = TripBase(
            client_name="Acme Corp",
            loading_city="Paris",
            loading_country="FR",
            delivery_city="Berlin",
            delivery_country="DE",
        )
        assert inst.client_name == "Acme Corp"
        assert inst.delivery_country == "DE"

    def test_partial(self):
        inst = TripBase(client_name="Client", delivery_city="City")
        assert inst.client_name == "Client"
        assert inst.loading_country is None

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            TripBase(client_name="x", extra="y")  # type: ignore[call-arg]


# ── TripResponse ──────────────────────────────────────────────────────────────


class TestTripResponse:
    """Extends TripBase, extra="ignore". Adds id, status, created_at."""

    def test_valid(self):
        inst = TripResponse(
            id=1,
            status="in_progress",
            created_at="2025-01-01T00:00:00Z",
            client_name="Acme",
            loading_city="Paris",
            delivery_city="Berlin",
        )
        assert inst.id == 1
        assert inst.status == "in_progress"
        assert inst.client_name == "Acme"

    def test_defaults_from_base(self):
        inst = TripResponse(id=1, status="pending", created_at="t")
        assert inst.client_name == ""
        assert inst.loading_city == ""

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            TripResponse(status="ok", created_at="t")  # type: ignore[call-arg]

    def test_missing_status_raises(self):
        with pytest.raises(ValidationError):
            TripResponse(id=1, created_at="t")  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        """extra="ignore": unknown fields are silently dropped."""
        inst = TripResponse(id=1, status="s", created_at="t", unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── TripSearchParams ──────────────────────────────────────────────────────────


class TestTripSearchParams:
    """All optional with defaults, extra="forbid"."""

    def test_defaults(self):
        inst = TripSearchParams()
        assert inst.query == ""
        assert inst.status is None
        assert inst.date_from is None
        assert inst.date_to is None
        assert inst.driver_id is None
        assert inst.truck_id is None
        assert inst.page == 0
        assert inst.page_size == 20

    def test_all_fields(self):
        inst = TripSearchParams(
            query="search term",
            status="completed",
            date_from="2025-01-01",
            date_to="2025-12-31",
            driver_id=10,
            truck_id=20,
            page=1,
            page_size=50,
        )
        assert inst.query == "search term"
        assert inst.driver_id == 10
        assert inst.truck_id == 20
        assert inst.page == 1
        assert inst.page_size == 50

    def test_partial_filters(self):
        inst = TripSearchParams(status="pending", driver_id=5)
        assert inst.status == "pending"
        assert inst.driver_id == 5
        assert inst.date_from is None

    @pytest.mark.parametrize("page", [-1, -10, 0, 1, 100])
    def test_any_integer_page_accepted(self, page: int):
        """No ge/gt constraint — any int is accepted."""
        inst = TripSearchParams(page=page)
        assert inst.page == page

    @pytest.mark.parametrize("page_size", [0, -1, 1, 50, 100, 200])
    def test_any_integer_page_size_accepted(self, page_size: int):
        """No ge/gt constraint — any int is accepted."""
        inst = TripSearchParams(page_size=page_size)
        assert inst.page_size == page_size

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            TripSearchParams(query="x", unknown="y")  # type: ignore[call-arg]
