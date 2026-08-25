"""Tests for client_models.py — ClientContact, ClientCreate, ClientUpdate, ClientResult."""
from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError
from models.client_models import ClientContact, ClientCreate, ClientUpdate, ClientResult


class TestClientContact:
    """Contact sub-model: required name, optional email/phone/position."""

    def test_name_required(self):
        """name is the only required field."""
        cc = ClientContact(name="Alice")
        assert cc.name == "Alice"
        assert cc.email == ""
        assert cc.phone == ""
        assert cc.position == ""

    def test_all_fields(self):
        cc = ClientContact(
            name="Bob",
            email="bob@example.com",
            phone="+123456789",
            position="Manager",
        )
        assert cc.email == "bob@example.com"
        assert cc.phone == "+123456789"
        assert cc.position == "Manager"

    def test_empty_name_allowed(self):
        """ClientContact has no validator — empty name string is allowed."""
        cc = ClientContact(name="")
        assert cc.name == ""

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ClientContact(email="a@b.com")


class TestClientCreate:
    """Client creation: name required and not empty, all others optional."""

    @pytest.mark.parametrize(
        "name, company_code, city, country",
        [
            ("Acme Corp", "", "Berlin", "Germany"),
            ("  Global Logistics  ", "GL-123", "", ""),
            ("A", "C", "City", "Country"),
            ("Test Client with long name", "VAT-001", "Paris", "France"),
        ],
    )
    def test_valid_creation(self, name, company_code, city, country):
        """Various valid creations."""
        cc = ClientCreate(name=name, company_code=company_code, city=city, country=country)
        assert cc.name == name.strip()
        assert cc.company_code == company_code

    def test_name_stripped(self):
        """Whitespace around name is stripped via validator."""
        cc = ClientCreate(name="  My Client  ")
        assert cc.name == "My Client"

    @pytest.mark.parametrize(
        "name",
        ["", "   ", "\t\n"],
    )
    def test_empty_name_raises(self, name):
        """Blank name raises ValidationError."""
        with pytest.raises(ValidationError, match="Client name is required"):
            ClientCreate(name=name)

    def test_default_fields(self):
        """Defaults: company_code, vat_number, address, city, country,
        email, phone, notes all default to ''; contacts defaults to []."""
        cc = ClientCreate(name="Test Client")
        assert cc.company_code == ""
        assert cc.vat_number == ""
        assert cc.address == ""
        assert cc.city == ""
        assert cc.country == ""
        assert cc.email == ""
        assert cc.phone == ""
        assert cc.notes == ""
        assert cc.contacts == []

    def test_with_contacts(self):
        """Client can be created with a list of contacts."""
        contacts = [
            ClientContact(name="Alice", email="alice@acme.com"),
            ClientContact(name="Bob", phone="+111"),
        ]
        cc = ClientCreate(name="Acme", contacts=contacts)
        assert len(cc.contacts) == 2
        assert cc.contacts[0].name == "Alice"
        assert cc.contacts[1].phone == "+111"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ClientCreate()

    def test_email_empty_string_allowed(self):
        """email defaults to '' and is not validated as email format."""
        cc = ClientCreate(name="X", email="not-an-email")
        assert cc.email == "not-an-email"

    def test_vat_number_and_address(self):
        cc = ClientCreate(
            name="Supplier Ltd",
            vat_number="DE123456789",
            address="Industriestr. 10, Hamburg",
        )
        assert cc.vat_number == "DE123456789"
        assert cc.address == "Industriestr. 10, Hamburg"


class TestClientUpdate:
    """All Optional, partial update supported."""

    def test_empty_update(self):
        """Empty body is valid — all fields optional."""
        cu = ClientUpdate()
        assert cu.name is None
        assert cu.company_code is None
        assert cu.vat_number is None
        assert cu.address is None
        assert cu.city is None
        assert cu.country is None
        assert cu.email is None
        assert cu.phone is None
        assert cu.notes is None

    def test_partial_update_name_only(self):
        cu = ClientUpdate(name="New Name")
        assert cu.name == "New Name"
        assert cu.city is None

    def test_partial_update_multiple(self):
        cu = ClientUpdate(
            name="Updated",
            email="new@example.com",
            phone="+49 1234",
        )
        assert cu.name == "Updated"
        assert cu.email == "new@example.com"
        assert cu.phone == "+49 1234"
        assert cu.address is None

    def test_partial_update_address(self):
        cu = ClientUpdate(address="New Address 42")
        assert cu.address == "New Address 42"

    def test_partial_update_country(self):
        cu = ClientUpdate(country="Austria")
        assert cu.country == "Austria"


class TestClientResult:
    """Client output model with all fields."""

    def test_minimal(self):
        cr = ClientResult(
            id=1,
            name="Test Client",
            company_code="",
            vat_number="",
            address="",
            city="",
            country="",
            email="",
            phone="",
            notes="",
        )
        assert cr.id == 1
        assert cr.trip_count == 0
        assert cr.invoice_count == 0
        assert cr.total_revenue == 0.0
        assert cr.contacts == []
        assert cr.created_at is None
        assert cr.updated_at is None

    def test_with_all_fields(self):
        now = datetime.now()
        cr = ClientResult(
            id=42,
            name="Big Client",
            company_code="BC-001",
            vat_number="ATU12345678",
            address="Main St 1",
            city="Vienna",
            country="Austria",
            email="info@bigclient.at",
            phone="+43 1 234567",
            notes="Important client",
            trip_count=15,
            invoice_count=8,
            total_revenue=125000.50,
            contacts=[
                ClientContact(name="Contact1", email="c1@big.at"),
            ],
            created_at=now,
            updated_at=now,
        )
        assert cr.trip_count == 15
        assert cr.total_revenue == 125000.50
        assert len(cr.contacts) == 1
        assert cr.created_at == now

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            ClientResult(
                name="X",
                company_code="",
                vat_number="",
                address="",
                city="",
                country="",
                email="",
                phone="",
                notes="",
            )

    def test_total_revenue_default(self):
        cr = ClientResult(
            id=1,
            name="T",
            company_code="",
            vat_number="",
            address="",
            city="",
            country="",
            email="",
            phone="",
            notes="",
        )
        assert cr.total_revenue == 0.0
