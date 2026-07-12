"""Tests for backend/schemas/driver.py — DriverBase, DriverCreate, DriverResponse, DriverUpdate."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.driver import DriverBase, DriverCreate, DriverResponse, DriverUpdate


# ── DriverBase ────────────────────────────────────────────────────────────────


class TestDriverBase:
    """All fields have defaults, extra="forbid"."""

    def test_defaults(self):
        inst = DriverBase()
        assert inst.name == ""
        assert inst.phone == ""
        assert inst.email == ""
        assert inst.license_number == ""
        assert inst.license_category == ""
        assert inst.license_expiry is None
        assert inst.medical_expiry is None
        assert inst.hire_date is None
        assert inst.monthly_salary == 0.0
        assert inst.notes == ""
        assert inst.is_active is True

    def test_all_fields(self):
        inst = DriverBase(
            name="John Doe",
            phone="+123456789",
            email="john@example.com",
            license_number="LIC-001",
            license_category="C+E",
            license_expiry="2025-12-31",
            medical_expiry="2025-06-30",
            hire_date="2024-01-15",
            monthly_salary=3500.0,
            notes="Experienced driver",
            is_active=True,
        )
        assert inst.name == "John Doe"
        assert inst.monthly_salary == 3500.0

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DriverBase(name="x", unknown="y")  # type: ignore[call-arg]


# ── DriverCreate ──────────────────────────────────────────────────────────────


class TestDriverCreate:
    """Inherits DriverBase — same behavior."""

    def test_defaults(self):
        inst = DriverCreate()
        assert inst.name == ""
        assert inst.is_active is True

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DriverCreate(name="x", extra="y")  # type: ignore[call-arg]


# ── DriverResponse ────────────────────────────────────────────────────────────


class TestDriverResponse:
    """Extends DriverBase, adds id (required), created_at (default ""), updated_at (default "")."""

    def test_valid(self):
        inst = DriverResponse(id=1)
        assert inst.id == 1
        assert inst.created_at == ""
        assert inst.updated_at == ""
        assert inst.name == ""

    def test_all_fields(self):
        inst = DriverResponse(
            id=1,
            name="John",
            phone="123",
            email="j@j.com",
            license_number="L1",
            license_category="C",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
        )
        assert inst.id == 1
        assert inst.created_at == "2025-01-01T00:00:00Z"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DriverResponse()  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        inst = DriverResponse(id=1, unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── DriverUpdate ──────────────────────────────────────────────────────────────


class TestDriverUpdate:
    """All fields Optional, extra="forbid"."""

    def test_empty(self):
        inst = DriverUpdate()
        assert inst.name is None
        assert inst.phone is None
        assert inst.monthly_salary is None
        assert inst.is_active is None

    def test_partial(self):
        inst = DriverUpdate(name="Updated Name", monthly_salary=4000.0)
        assert inst.name == "Updated Name"
        assert inst.monthly_salary == 4000.0
        assert inst.phone is None

    def test_set_is_active(self):
        inst = DriverUpdate(is_active=False)
        assert inst.is_active is False

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DriverUpdate(name="x", unknown="y")  # type: ignore[call-arg]
