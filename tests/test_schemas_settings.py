"""Tests for backend/schemas/settings.py — CompanyConfigUpdateRequest,
SettingUpdateRequest."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.settings import CompanyConfigUpdateRequest, SettingUpdateRequest


# ── CompanyConfigUpdateRequest ─────────────────────────────────────────────────


class TestCompanyConfigUpdateRequest:
    """All fields Optional with max_length constraints.
    company_name (max_length=255), cui (max_length=100),
    reg_number (max_length=100), address (max_length=500),
    phone (max_length=100), email (max_length=255),
    logo_path (max_length=500), company_color (max_length=50),
    signature_path (max_length=500), stamp_path (max_length=500),
    extra="forbid"."""

    def test_defaults_all_none(self):
        inst = CompanyConfigUpdateRequest()
        assert inst.company_name is None
        assert inst.cui is None
        assert inst.reg_number is None
        assert inst.address is None
        assert inst.phone is None
        assert inst.email is None
        assert inst.logo_path is None
        assert inst.company_color is None
        assert inst.signature_path is None
        assert inst.stamp_path is None

    def test_all_fields_set(self):
        inst = CompanyConfigUpdateRequest(
            company_name="Acme Transport SRL",
            cui="RO12345678",
            reg_number="J12/345/2020",
            address="Str. Principala 10, Bucuresti",
            phone="+40721234567",
            email="contact@acme.ro",
            logo_path="/logos/acme.png",
            company_color="#FF5733",
            signature_path="/signatures/director.png",
            stamp_path="/stamps/company.png",
        )
        assert inst.company_name == "Acme Transport SRL"
        assert inst.cui == "RO12345678"
        assert inst.email == "contact@acme.ro"
        assert inst.company_color == "#FF5733"

    # ── company_name max_length=255 ──

    def test_company_name_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(company_name="x" * 255)
        assert inst.company_name == "x" * 255

    def test_company_name_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(company_name="x" * 256)

    def test_company_name_empty_string(self):
        """Empty string is valid since field is Optional with no min_length."""
        inst = CompanyConfigUpdateRequest(company_name="")
        assert inst.company_name == ""

    def test_company_name_none(self):
        inst = CompanyConfigUpdateRequest(company_name=None)
        assert inst.company_name is None

    # ── cui max_length=100 ──

    def test_cui_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(cui="x" * 100)
        assert inst.cui == "x" * 100

    def test_cui_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(cui="x" * 101)

    def test_cui_empty_string(self):
        inst = CompanyConfigUpdateRequest(cui="")
        assert inst.cui == ""

    def test_cui_none(self):
        inst = CompanyConfigUpdateRequest(cui=None)
        assert inst.cui is None

    # ── reg_number max_length=100 ──

    def test_reg_number_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(reg_number="x" * 100)
        assert inst.reg_number == "x" * 100

    def test_reg_number_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(reg_number="x" * 101)

    def test_reg_number_none(self):
        inst = CompanyConfigUpdateRequest(reg_number=None)
        assert inst.reg_number is None

    # ── address max_length=500 ──

    def test_address_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(address="x" * 500)
        assert inst.address == "x" * 500

    def test_address_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(address="x" * 501)

    def test_address_none(self):
        inst = CompanyConfigUpdateRequest(address=None)
        assert inst.address is None

    # ── phone max_length=100 ──

    def test_phone_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(phone="x" * 100)
        assert inst.phone == "x" * 100

    def test_phone_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(phone="x" * 101)

    def test_phone_none(self):
        inst = CompanyConfigUpdateRequest(phone=None)
        assert inst.phone is None

    # ── email max_length=255 ──

    def test_email_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(email="x" * 255)
        assert inst.email == "x" * 255

    def test_email_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(email="x" * 256)

    def test_email_none(self):
        inst = CompanyConfigUpdateRequest(email=None)
        assert inst.email is None

    # ── logo_path max_length=500 ──

    def test_logo_path_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(logo_path="x" * 500)
        assert inst.logo_path == "x" * 500

    def test_logo_path_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(logo_path="x" * 501)

    def test_logo_path_none(self):
        inst = CompanyConfigUpdateRequest(logo_path=None)
        assert inst.logo_path is None

    # ── company_color max_length=50 ──

    def test_company_color_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(company_color="x" * 50)
        assert inst.company_color == "x" * 50

    def test_company_color_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(company_color="x" * 51)

    def test_company_color_none(self):
        inst = CompanyConfigUpdateRequest(company_color=None)
        assert inst.company_color is None

    # ── signature_path max_length=500 ──

    def test_signature_path_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(signature_path="x" * 500)
        assert inst.signature_path == "x" * 500

    def test_signature_path_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(signature_path="x" * 501)

    def test_signature_path_none(self):
        inst = CompanyConfigUpdateRequest(signature_path=None)
        assert inst.signature_path is None

    # ── stamp_path max_length=500 ──

    def test_stamp_path_max_length_exact(self):
        inst = CompanyConfigUpdateRequest(stamp_path="x" * 500)
        assert inst.stamp_path == "x" * 500

    def test_stamp_path_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(stamp_path="x" * 501)

    def test_stamp_path_none(self):
        inst = CompanyConfigUpdateRequest(stamp_path=None)
        assert inst.stamp_path is None

    # ── extra=forbid ──

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            CompanyConfigUpdateRequest(unknown="x")  # type: ignore[call-arg]


# ── SettingUpdateRequest ───────────────────────────────────────────────────────


class TestSettingUpdateRequest:
    """value: str (default="", max_length=2000), extra="forbid"."""

    def test_default_value_empty_string(self):
        inst = SettingUpdateRequest()
        assert inst.value == ""

    def test_custom_value(self):
        inst = SettingUpdateRequest(value="dark_mode")
        assert inst.value == "dark_mode"

    def test_value_max_length_exact(self):
        inst = SettingUpdateRequest(value="x" * 2000)
        assert inst.value == "x" * 2000

    def test_value_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            SettingUpdateRequest(value="x" * 2001)

    def test_value_empty_string_explicit(self):
        inst = SettingUpdateRequest(value="")
        assert inst.value == ""

    def test_value_none_raises(self):
        """Pydantic v2 does not coerce None to the default for str."""
        with pytest.raises(ValidationError):
            SettingUpdateRequest(value=None)  # type: ignore[arg-type]

    def test_value_type_mismatch_raises(self):
        with pytest.raises(ValidationError):
            SettingUpdateRequest(value=123)  # type: ignore[arg-type]

    def test_value_boolean_raises(self):
        with pytest.raises(ValidationError):
            SettingUpdateRequest(value=True)  # type: ignore[arg-type]

    # ── extra=forbid ──

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            SettingUpdateRequest(value="x", unknown="y")  # type: ignore[call-arg]
