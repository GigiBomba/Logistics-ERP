"""Test data factory functions — lightweight alternative to Factory Boy.

Each ``make_*`` function creates a model instance (Pydantic v2) with sensible
defaults so tests can focus on what they want to override.

Usage::

    from tests.test_data import make_trip, make_client

    trip = make_trip(client_id=42, status="Delivered")
    client = make_client(name="Acme Corp")
"""
from __future__ import annotations


import copy
from datetime import date, datetime, timedelta
from typing import Any, Optional

from models.client_models import ClientCreate, ClientContact
from models.driver_models import DriverCreate
from models.invoice_models import InvoiceCreate, InvoiceLineItem
from models.trip_models import TripCreate, TripStop
from models.vehicle_models import VehicleCreate
from backend.schemas.user import UserCreateRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = date.today()


def _unique_id() -> int:
    """Return a monotonically-increasing integer for default PK-like fields."""
    _unique_id._counter += 1  # type: ignore[attr-defined]
    return _unique_id._counter  # type: ignore[attr-defined]


_unique_id._counter = 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------


def make_trip(**overrides: Any) -> TripCreate:
    """Build a ``TripCreate`` with sensible defaults.

    Any keyword argument overrides the corresponding field.
    """
    defaults: dict[str, Any] = {
        "client_id": 1,
        "reference": f"TRIP-{_unique_id():04d}",
        "start_date": _TODAY,
        "end_date": _TODAY + timedelta(days=3),
        "price_eur": 2450.0,
        "currency": "EUR",
        "distance_km": 850.0,
        "truck_plate": "AB-123-CD",
        "driver_name": "John Doe",
        "client_name": "Default Client",
        "status": "Planned",
        "fuel_cost": 320.0,
        "toll_cost": 85.0,
        "salary_cost": 600.0,
        "extra_costs": 50.0,
        "net_profit": 1395.0,
        "rate_per_km": 2.88,
        "gross_per_km": 1.64,
        "notes": "",
        "stops": [
            TripStop(address="Berlin, Germany", sequence=1, type="pickup"),
            TripStop(address="Paris, France", sequence=2, type="delivery"),
        ],
        "source": "manual",
    }
    merged = {**defaults, **overrides}
    obj = TripCreate(**merged)
    return obj


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def make_client(**overrides: Any) -> ClientCreate:
    """Build a ``ClientCreate`` with sensible defaults."""
    defaults: dict[str, Any] = {
        "name": f"Client-{_unique_id():04d}",
        "company_code": f"CC{_unique_id():04d}",
        "vat_number": f"RO{_unique_id():06d}",
        "address": "123 Main Street",
        "city": "Bucharest",
        "country": "Romania",
        "email": f"client{_unique_id():04d}@example.com",
        "phone": "+40-700-000-000",
        "notes": "",
        "contacts": [
            ClientContact(
                name="Primary Contact",
                email="contact@example.com",
                phone="+40-700-000-001",
                position="Operations Manager",
            ),
        ],
    }
    merged = {**defaults, **overrides}
    return ClientCreate(**merged)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def make_driver(**overrides: Any) -> DriverCreate:
    """Build a ``DriverCreate`` with sensible defaults."""
    defaults: dict[str, Any] = {
        "name": f"Driver-{_unique_id():04d}",
        "email": f"driver{_unique_id():04d}@example.com",
        "phone": "+40-700-111-111",
        "license_number": f"LIC-{_unique_id():06d}",
        "license_expiry": _TODAY.replace(year=_TODAY.year + 5),
        "hours_worked": 0.0,
        "max_hours_per_day": 9.0,
        "status": "active",
    }
    merged = {**defaults, **overrides}
    return DriverCreate(**merged)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


def make_user(**overrides: Any) -> UserCreateRequest:
    """Build a ``UserCreateRequest`` with sensible defaults."""
    uid = _unique_id()
    defaults: dict[str, Any] = {
        "email": f"user{uid:04d}@example.com",
        "password": "s3cur3P@ss!",
        "role": "dispatcher",
        "display_name": f"User-{uid:04d}",
    }
    merged = {**defaults, **overrides}
    return UserCreateRequest(**merged)


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------


def make_vehicle(**overrides: Any) -> VehicleCreate:
    """Build a ``VehicleCreate`` with sensible defaults."""
    uid = _unique_id()
    defaults: dict[str, Any] = {
        "plate": f"B-{uid:03d}-XYZ",
        "brand": "Volvo",
        "model": "FH 460",
        "year": 2022,
        "vin": f"YV2RTW{uid:07d}",
        "max_weight_kg": 19000,
        "fuel_type": "diesel",
        "consumption_l_per_100km": 28.5,
        "insurance_expiry": _TODAY.replace(year=_TODAY.year + 1),
        "technical_inspection_expiry": _TODAY.replace(year=_TODAY.year + 1),
        "tachograph_calibration_expiry": _TODAY.replace(year=_TODAY.year + 2),
        "status": "active",
    }
    merged = {**defaults, **overrides}
    return VehicleCreate(**merged)


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------


def make_invoice(**overrides: Any) -> InvoiceCreate:
    """Build an ``InvoiceCreate`` with sensible defaults."""
    uid = _unique_id()
    defaults: dict[str, Any] = {
        "client_id": 1,
        "trip_id": uid,
        "invoice_date": _TODAY,
        "due_date": _TODAY + timedelta(days=30),
        "currency": "EUR",
        "line_items": [
            InvoiceLineItem(
                description="Transport services",
                quantity=1.0,
                unit_price=2450.0,
                vat_rate=19.0,
            ),
        ],
        "notes": "",
    }
    merged = {**defaults, **overrides}
    return InvoiceCreate(**merged)
