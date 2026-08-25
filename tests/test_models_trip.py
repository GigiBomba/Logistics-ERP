"""Tests for trip_models.py — TripStop, TripCreate, TripUpdate, TripResult."""
from __future__ import annotations

import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.trip_models import TripStop, TripCreate, TripUpdate, TripResult


class TestTripStop:
    """Valid construction, optional fields, sequence validation."""

    @pytest.mark.parametrize(
        "address, sequence",
        [
            ("Main St 123, Berlin", 1),
            ("  Airport, Frankfurt  ", 2),
            ("Harbor #45, Rotterdam", 0),
            ("Rest Area A3", -1),
        ],
    )
    def test_valid_trip_stop(self, address, sequence):
        """Basic construction with required fields."""
        ts = TripStop(address=address, sequence=sequence)
        assert ts.address == address
        assert ts.sequence == sequence
        assert ts.type == "pickup"

    def test_optional_fields_default_to_none(self):
        """lat, lon, arrival, departure default to None."""
        ts = TripStop(address="Depot", sequence=1)
        assert ts.lat is None
        assert ts.lon is None
        assert ts.arrival is None
        assert ts.departure is None

    def test_type_defaults_to_pickup(self):
        ts = TripStop(address="Warehouse", sequence=1)
        assert ts.type == "pickup"

    def test_type_explicit(self):
        ts = TripStop(address="Customer", sequence=2, type="delivery")
        assert ts.type == "delivery"

    def test_with_all_fields(self):
        """All fields provided explicitly."""
        now = datetime.now()
        ts = TripStop(
            address="123 Main St",
            lat=52.52,
            lon=13.405,
            sequence=1,
            arrival=now,
            departure=now,
            type="rest",
        )
        assert ts.lat == 52.52
        assert ts.lon == 13.405
        assert ts.arrival == now
        assert ts.departure == now
        assert ts.type == "rest"

    def test_missing_address_raises(self):
        with pytest.raises(ValidationError):
            TripStop(sequence=1)

    def test_missing_sequence_raises(self):
        with pytest.raises(ValidationError):
            TripStop(address="Somewhere")


class TestTripCreate:
    """Valid creation, price_eur>=0, distance_km>0, missing required fields."""

    @pytest.mark.parametrize(
        "client_id, start_date, price_eur, distance_km",
        [
            (1, date(2026, 7, 1), 0.0, None),
            (2, date(2026, 8, 15), 1500.0, 500.0),
            (3, date(2026, 6, 1), 100.50, 0.001),
            (4, date(2026, 12, 31), 9999.99, 9999.0),
        ],
    )
    def test_valid_creation(self, client_id, start_date, price_eur, distance_km):
        """Various valid parameter combinations."""
        tc = TripCreate(
            client_id=client_id,
            start_date=start_date,
            price_eur=price_eur,
            distance_km=distance_km,
        )
        assert tc.client_id == client_id
        assert tc.start_date == start_date
        assert tc.price_eur == price_eur
        assert tc.distance_km == distance_km

    def test_default_values(self):
        """Defaults: reference='', currency='EUR', stops=[], notes='',
        status='Planned', and financial fields are None/''."""
        tc = TripCreate(client_id=1, start_date=date(2026, 7, 1))
        assert tc.reference == ""
        assert tc.currency == "EUR"
        assert tc.stops == []
        assert tc.notes == ""
        assert tc.status == "Planned"
        assert tc.price_eur == 0.0
        assert tc.distance_km is None
        assert tc.truck_plate == ""
        assert tc.driver_name == ""
        assert tc.client_name == ""
        assert tc.payment_date is None
        assert tc.net_profit is None
        assert tc.fuel_cost is None

    def test_route_id_and_truck_id_default_to_none(self):
        tc = TripCreate(client_id=1, start_date=date(2026, 7, 1))
        assert tc.route_id is None
        assert tc.truck_id is None
        assert tc.driver_id is None

    @pytest.mark.parametrize("price_eur", [-0.001, -1.0, -100.0])
    def test_price_must_be_non_negative(self, price_eur):
        """Negative price_eur raises ValidationError."""
        with pytest.raises(ValidationError, match="Price"):
            TripCreate(
                client_id=1,
                start_date=date(2026, 7, 1),
                price_eur=price_eur,
            )

    def test_price_zero_is_valid(self):
        """price_eur=0.0 is explicitly allowed."""
        tc = TripCreate(
            client_id=1,
            start_date=date(2026, 7, 1),
            price_eur=0.0,
        )
        assert tc.price_eur == 0.0

    @pytest.mark.parametrize("distance_km", [0.0, -0.001, -1.0])
    def test_distance_must_be_positive_if_provided(self, distance_km):
        """distance_km <= 0 when provided raises ValidationError."""
        with pytest.raises(ValidationError, match="Distance"):
            TripCreate(
                client_id=1,
                start_date=date(2026, 7, 1),
                distance_km=distance_km,
            )

    def test_distance_none_is_valid(self):
        """distance_km=None is allowed."""
        tc = TripCreate(
            client_id=1,
            start_date=date(2026, 7, 1),
            distance_km=None,
        )
        assert tc.distance_km is None

    def test_missing_client_id_raises(self):
        with pytest.raises(ValidationError):
            TripCreate(start_date=date(2026, 7, 1))

    def test_missing_start_date_raises(self):
        with pytest.raises(ValidationError):
            TripCreate(client_id=1)

    def test_with_stops(self):
        """Providing a list of TripStop items."""
        stops = [
            TripStop(address="Origin", sequence=1),
            TripStop(address="Dest", sequence=2, type="delivery"),
        ]
        tc = TripCreate(
            client_id=1,
            start_date=date(2026, 7, 1),
            stops=stops,
        )
        assert len(tc.stops) == 2
        assert tc.stops[0].address == "Origin"
        assert tc.stops[1].type == "delivery"

    def test_end_date_optional(self):
        tc = TripCreate(
            client_id=1,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )
        assert tc.end_date == date(2026, 7, 5)


class TestTripUpdate:
    """All Optional, partial update, empty body allowed."""

    def test_empty_update(self):
        """All fields optional — empty body is valid."""
        tu = TripUpdate()
        assert tu.client_id is None
        assert tu.truck_id is None
        assert tu.driver_id is None
        assert tu.reference is None
        assert tu.start_date is None
        assert tu.end_date is None
        assert tu.price_eur is None
        assert tu.currency is None
        assert tu.distance_km is None
        assert tu.stops is None
        assert tu.notes is None
        assert tu.status is None

    def test_partial_update_single_field(self):
        """Update only one field at a time."""
        tu = TripUpdate(status="In Progress")
        assert tu.status == "In Progress"
        assert tu.price_eur is None
        assert tu.distance_km is None

    def test_partial_update_multiple_fields(self):
        """Update a subset of fields."""
        tu = TripUpdate(
            price_eur=2500.0,
            distance_km=1200.0,
            notes="Updated route",
        )
        assert tu.price_eur == 2500.0
        assert tu.distance_km == 1200.0
        assert tu.notes == "Updated route"
        assert tu.client_id is None
        assert tu.status is None

    def test_update_stops(self):
        """Replacing stops via update."""
        stops = [TripStop(address="New Stop", sequence=1)]
        tu = TripUpdate(stops=stops)
        assert len(tu.stops) == 1
        assert tu.stops[0].address == "New Stop"

    def test_update_client_id(self):
        tu = TripUpdate(client_id=42)
        assert tu.client_id == 42

    def test_update_currency(self):
        tu = TripUpdate(currency="USD")
        assert tu.currency == "USD"

    def test_update_start_date(self):
        d = date(2026, 9, 1)
        tu = TripUpdate(start_date=d)
        assert tu.start_date == d


class TestTripResult:
    """Construction of the output/result model."""

    def test_minimal(self):
        """Minimal required fields."""
        tr = TripResult(
            id=1,
            client_id=1,
            reference="REF001",
            start_date=date(2026, 7, 1),
            price_eur=1000.0,
            currency="EUR",
            status="Planned",
        )
        assert tr.id == 1
        assert tr.client_name == ""
        assert tr.notes == ""
        assert tr.distance_km is None

    def test_with_all_optional_fields(self):
        """All optional fields populated."""
        tr = TripResult(
            id=1,
            client_id=1,
            client_name="Acme Corp",
            route_id=10,
            truck_id=5,
            truck_plate="AB123CD",
            driver_id=3,
            driver_name="John Doe",
            reference="REF001",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
            price_eur=2000.0,
            currency="EUR",
            distance_km=1000.0,
            status="Completed",
            profit=500.0,
            cost=1500.0,
            margin_pct=25.0,
            notes="Delivered on time",
            created_at=datetime(2026, 7, 1, 8, 0),
            updated_at=datetime(2026, 7, 5, 18, 0),
        )
        assert tr.profit == 500.0
        assert tr.margin_pct == 25.0
        assert tr.created_at is not None

    def test_missing_required_id_raises(self):
        with pytest.raises(ValidationError):
            TripResult(
                client_id=1,
                reference="R1",
                start_date=date(2026, 1, 1),
                price_eur=0.0,
                currency="EUR",
                status="Planned",
            )
