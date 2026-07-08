"""Tests for services.invoicing.cmr_efti — eFTI-compliant eCMR XML generator."""

from __future__ import annotations

import json
from datetime import datetime
from textwrap import dedent
from xml.etree.ElementTree import Element, fromstring, tostring

import pytest

from services.invoicing.cmr_efti import (
    NS_ECMR,
    NS_RAM,
    NS_RSM,
    NS_UDT,
    NS_XSI,
    XSI_SCHEMA_LOCATION,
    _build_location,
    _build_trade_party,
    _date_string,
    _date_time_element,
    _party_postal_address,
    _party_tax_registrations,
    _sub,
    generate_efti_xml,
)


# ==============================================================================
# Helpers: Element creation
# ==============================================================================


class TestSub:
    """Tests for the _sub helper that creates XML SubElements."""

    def test_creates_sub_element(self):
        parent = Element("parent")
        child = _sub(parent, "child")
        assert child.tag == "child"
        assert child.tail is None

    def test_sets_text_content(self):
        parent = Element("parent")
        child = _sub(parent, "child", "hello")
        assert child.text == "hello"

    def test_empty_text_omits_text(self):
        """Empty string or None text should not set .text."""
        parent = Element("parent")
        child = _sub(parent, "child", "")
        assert child.text is None

    def test_none_text_omits_text(self):
        parent = Element("parent")
        child = _sub(parent, "child", None)
        assert child.text is None

    def test_whitespace_only_text_set(self):
        """Whitespace text is *not* empty-string — keep it."""
        parent = Element("parent")
        child = _sub(parent, "child", "   ")
        assert child.text == "   "

    def test_with_attributes(self):
        parent = Element("parent")
        child = _sub(parent, "child", "val", {"attr1": "a", "attr2": "b"})
        assert child.get("attr1") == "a"
        assert child.get("attr2") == "b"
        assert child.text == "val"

    def test_ns_tag(self):
        parent = Element("parent")
        child = _sub(parent, f"{{{NS_RAM}}}TestTag", "data")
        assert child.tag == f"{{{NS_RAM}}}TestTag"
        assert child.text == "data"


# ==============================================================================
# Helpers: _date_string
# ==============================================================================


class TestDateString:
    """Tests for date string normalisation (UDT format=102 → YYYYMMDD)."""

    def test_empty_string(self):
        assert _date_string("") == ""

    def test_none_coerced(self):
        """None is falsy but the guard uses 'if not raw' so returns ''."""
        assert _date_string(None) == ""  # type: ignore[arg-type]

    def test_iso_format(self):
        assert _date_string("2026-06-07") == "20260607"

    def test_compact_format(self):
        assert _date_string("20260607") == "20260607"

    def test_dmy_slash_format(self):
        assert _date_string("07/06/2026") == "20260607"

    def test_dmy_slash_format_takes_precedence(self):
        """%d/%m/%Y matches before %m/%d/%Y, so 06/07 is 6 July."""
        assert _date_string("06/07/2026") == "20260706"

    def test_iso_with_time(self):
        assert _date_string("2026-06-07 14:30:00") == "20260607"

    def test_iso_with_time_no_seconds(self):
        assert _date_string("2026-06-07 14:30") == "20260607"

    def test_dot_format(self):
        assert _date_string("07.06.2026") == "20260607"

    def test_ymd_slash_format(self):
        assert _date_string("2026/06/07") == "20260607"

    def test_t_separator(self):
        assert _date_string("2026-06-07T14:30:00") == "20260607"

    def test_z_suffix(self):
        assert _date_string("2026-06-07T14:30:00Z") == "20260607"

    def test_fallback_digits_only(self):
        """When no format matches, fallback strips non-digits."""
        assert _date_string("2026.06.07") == "20260607"

    def test_fallback_short_digits(self):
        """Less than 8 digits returns the original string."""
        result = _date_string("1234567")
        assert result == "1234567"

    def test_already_normalised_returned_as_is(self):
        assert _date_string("20260607") == "20260607"


# ==============================================================================
# Helpers: _date_time_element
# ==============================================================================


class TestDateTimeElement:
    """Tests for creating <tag><udt:DateTimeString format="102">…</…>."""

    def test_creates_nested_structure(self):
        parent = Element("parent")
        _date_time_element(parent, "event", "2026-06-07")
        xml = tostring(parent, encoding="unicode")
        assert "udt:DateTimeString" in xml
        assert 'format="102"' in xml
        assert "20260607" in xml

    def test_empty_date_skips(self):
        parent = Element("parent")
        _date_time_element(parent, "event", "")
        assert len(parent) == 0

    def test_none_date_skips(self):
        parent = Element("parent")
        _date_time_element(parent, "event", None)
        assert len(parent) == 0


# ==============================================================================
# Helpers: _party_postal_address
# ==============================================================================


class TestPartyPostalAddress:
    """Tests for building ram:PostalTradeAddress sub-tree."""

    def test_full_address(self):
        parent = Element("parent")
        _party_postal_address(parent, "Str. Principala 1", "Bucharest", "010101", "RO")
        xml = tostring(parent, encoding="unicode")
        assert "ram:PostalTradeAddress" in xml
        assert "ram:StreetName" in xml
        assert "Str. Principala 1" in xml
        assert "ram:CityName" in xml
        assert "Bucharest" in xml
        assert "ram:PostcodeCode" in xml
        assert "010101" in xml
        assert "ram:CountryID" in xml
        assert 'schemeID="ISO3166Alpha2"' in xml

    def test_only_city_and_country(self):
        parent = Element("parent")
        _party_postal_address(parent, "", "Paris", "", "FR")
        xml = tostring(parent, encoding="unicode")
        assert "ram:PostalTradeAddress" in xml
        assert "ram:CityName" in xml
        assert "Paris" in xml
        assert "ram:CountryID" in xml
        assert "FR" in xml
        assert "ram:StreetName" not in xml
        assert "ram:PostcodeCode" not in xml

    def test_all_empty_creates_empty_address(self):
        parent = Element("parent")
        _party_postal_address(parent, "", "", "", "")
        xml = tostring(parent, encoding="unicode")
        assert "ram:PostalTradeAddress" in xml
        # Self-closing tag or empty element (no child content)
        assert "/>" in xml or xml.count("ram:") == 1

    def test_country_with_scheme(self):
        parent = Element("parent")
        _party_postal_address(parent, "", "", "", "DE")
        xml = tostring(parent, encoding="unicode")
        assert "ram:CountryID" in xml
        assert 'schemeID="ISO3166Alpha2"' in xml
        assert "DE" in xml


# ==============================================================================
# Helpers: _party_tax_registrations
# ==============================================================================


class TestPartyTaxRegistrations:
    """Tests for VAT/EORI registration elements."""

    def test_vat_only(self):
        parent = Element("parent")
        _party_tax_registrations(parent, vat="RO12345678")
        xml = tostring(parent, encoding="unicode")
        # Count opening tags only (exclude closing tags)
        assert xml.count("<ram:SpecifiedTaxRegistration") == 1
        assert "RO12345678" in xml
        assert 'schemeID="VA"' in xml

    def test_eori_only(self):
        parent = Element("parent")
        _party_tax_registrations(parent, eori="DE123456789012345")
        xml = tostring(parent, encoding="unicode")
        assert xml.count("<ram:SpecifiedTaxRegistration") == 1
        assert 'schemeID="EORI"' in xml

    def test_both_vat_and_eori(self):
        parent = Element("parent")
        _party_tax_registrations(parent, vat="RO123", eori="EORI456")
        xml = tostring(parent, encoding="unicode")
        assert xml.count("<ram:SpecifiedTaxRegistration") == 2

    def test_neither_skipped(self):
        parent = Element("parent")
        _party_tax_registrations(parent)
        assert len(parent) == 0


# ==============================================================================
# Helpers: _build_trade_party
# ==============================================================================


class TestBuildTradeParty:
    """Tests for building a full TradeParty element."""

    def test_minimal(self):
        parent = Element("parent")
        _build_trade_party(parent, f"{{{NS_RAM}}}ShipperTradeParty", "Acme Ltd")
        xml = tostring(parent, encoding="unicode")
        assert "ram:ShipperTradeParty" in xml
        assert "ram:Name" in xml
        assert "Acme Ltd" in xml
        assert "ram:PostalTradeAddress" not in xml

    def test_with_party_id(self):
        parent = Element("parent")
        _build_trade_party(parent, f"{{{NS_RAM}}}CarrierTradeParty",
                           "Carrier Ltd", party_id="CARR-001")
        xml = tostring(parent, encoding="unicode")
        assert "ram:CarrierTradeParty" in xml
        assert "ram:ID" in xml
        assert "CARR-001" in xml

    def test_full_details(self):
        parent = Element("parent")
        _build_trade_party(
            parent, f"{{{NS_RAM}}}ShipperTradeParty",
            name="Shipper Ltd",
            street="Main 1",
            city="London",
            postcode="EC1A 1BB",
            country="GB",
            vat="GB123456",
            eori="GBEORI999",
            party_id="SHIP-01",
        )
        xml = tostring(parent, encoding="unicode")
        assert "ram:ShipperTradeParty" in xml
        assert "SHIP-01" in xml
        assert "Shipper Ltd" in xml
        assert "ram:PostalTradeAddress" in xml
        assert "Main 1" in xml
        assert "London" in xml
        assert "EC1A 1BB" in xml
        assert 'schemeID="ISO3166Alpha2"' in xml
        assert xml.count("<ram:SpecifiedTaxRegistration") == 2


# ==============================================================================
# Helpers: _build_location
# ==============================================================================


class TestBuildLocation:
    """Tests for building Location elements."""

    def test_both_country_and_city(self):
        parent = Element("parent")
        _build_location(parent, f"{{{NS_RAM}}}ArrivalLocation", country="FR", city="Paris")
        # The top-level tag uses {uri} format — serialize and re-parse to resolve namespaces
        xml = tostring(parent, encoding="unicode")
        assert "ram:ArrivalLocation" in xml
        assert "ram:CountryID" in xml
        assert 'schemeID="ISO3166Alpha2"' in xml
        assert "FR" in xml
        assert "ram:CityName" in xml
        assert "Paris" in xml

    def test_only_country(self):
        parent = Element("parent")
        _build_location(parent, f"{{{NS_RAM}}}DepartureLocation", country="DE")
        xml = tostring(parent, encoding="unicode")
        assert "ram:DepartureLocation" in xml
        assert "ram:CountryID" in xml
        assert "DE" in xml
        assert "ram:CityName" not in xml

    def test_only_city(self):
        parent = Element("parent")
        _build_location(parent, f"{{{NS_RAM}}}ArrivalLocation", city="Berlin")
        xml = tostring(parent, encoding="unicode")
        assert "ram:ArrivalLocation" in xml
        assert "ram:CityName" in xml
        assert "Berlin" in xml
        assert "ram:CountryID" not in xml

    def test_empty_creates_empty_element(self):
        parent = Element("parent")
        _build_location(parent, f"{{{NS_RAM}}}SomeLocation")
        xml = tostring(parent, encoding="unicode")
        assert "ram:SomeLocation" in xml


# ==============================================================================
# generate_efti_xml — minimal / structural tests
# ==============================================================================


class TestGenerateEftiXmlStructural:
    """Structural verification of the generated XML document."""

    def _minimal_trip(self) -> dict:
        return {
            "consignor_name": "Sender Ltd",
            "consignor_address": "Str. Sender 1",
            "loading_city": "Bucharest",
            "loading_country": "RO",
            "client_name": "Receiver GmbH",
            "client_address": "Str. Empfänger 10",
            "delivery_city": "Berlin",
            "delivery_country": "DE",
            "cargo_description": "Electronics",
            "package_count": 10,
        }

    def _minimal_config(self) -> dict:
        return {
            "company_name": "Test Trans SRL",
            "address": "Str. Firmei 5",
            "cui": "RO999999",
        }

    def test_root_element_and_namespaces(self):
        xml = generate_efti_xml("CMR-001", self._minimal_trip(), self._minimal_config())
        root = fromstring(xml)
        assert root.tag == f"{{{NS_ECMR}}}eCMR"
        # xml namespace declarations are handled by the parser, not preserved as
        # regular attributes; check the raw string instead
        assert 'xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:25"' in xml

    def test_xml_declaration_present(self):
        xml = generate_efti_xml("CMR-001", self._minimal_trip(), self._minimal_config())
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_exchanged_document_context(self):
        xml = generate_efti_xml("CMR-001", self._minimal_trip(), self._minimal_config())
        root = fromstring(xml)
        ctx = root.find(f"{{{NS_RSM}}}ExchangedDocumentContext")
        assert ctx is not None
        param = ctx.find(f"{{{NS_RAM}}}GuidelineSpecifiedDocumentContextParameter")
        assert param is not None
        id_el = param.find(f"{{{NS_RAM}}}ID")
        assert id_el is not None
        assert id_el.text == "urn:un:unece:uncefact:eCMR:1"

    def test_exchanged_document_with_cmr_number(self):
        xml = generate_efti_xml("CMR-001", self._minimal_trip(), self._minimal_config())
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        assert doc is not None
        id_el = doc.find(f"{{{NS_RAM}}}ID")
        assert id_el is not None
        assert id_el.text == "CMR-001"
        type_el = doc.find(f"{{{NS_RAM}}}TypeCode")
        assert type_el is not None
        assert type_el.text == "701"
        assert type_el.get("listID") == "UN/ECE 1001"

    def test_supply_chain_consignment_present(self):
        xml = generate_efti_xml("CMR-001", self._minimal_trip(), self._minimal_config())
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        assert cons is not None
        assert cons.find(f"{{{NS_RAM}}}ID").text == "CMR-001"

    def test_issue_date_defaults_to_today(self):
        """When no issue_date is provided, fallback to current date."""
        xml = generate_efti_xml("CMR-001", self._minimal_trip(), self._minimal_config())
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        dt_str = doc.find(f"{{{NS_RAM}}}IssueDateTime/{{{NS_UDT}}}DateTimeString")
        assert dt_str is not None
        expected = datetime.now().strftime("%Y%m%d")
        assert dt_str.text == expected

    def test_cmr_number_in_both_doc_and_consignment(self):
        xml = generate_efti_xml("CMR-999", self._minimal_trip(), self._minimal_config())
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        assert doc.find(f"{{{NS_RAM}}}ID").text == "CMR-999"
        assert cons.find(f"{{{NS_RAM}}}ID").text == "CMR-999"

    def test_specified_signatures_present_for_all_parties(self):
        """Three SpecifiedSignature elements (sender, carrier, consignee)."""
        xml = generate_efti_xml("CMR-001", self._minimal_trip(), self._minimal_config())
        root = fromstring(xml)
        sigs = root.findall(f"{{{NS_RSM}}}SpecifiedSignature")
        assert len(sigs) == 3
        types = {s.find(f"{{{NS_RAM}}}TypeCode").text for s in sigs}
        assert types == {"sender", "carrier", "consignee"}
        # All unsigned by default
        for s in sigs:
            assert s.find(f"{{{NS_RAM}}}StatusCode").text == "unsigned"


# ==============================================================================
# generate_efti_xml — role mapping
# ==============================================================================


class TestGenerateEftiXmlRoleMapping:
    """Tests for role-based party mapping (consignor vs consignee)."""

    def _config(self) -> dict:
        return {
            "company_name": "My Trans SRL",
            "address": "Str. Mea 10",
            "cui": "RO111",
            "eori_number": "EORI-RO-111",
        }

    def _trip_data(self) -> dict:
        return {
            "consignor_name": "External Shipper",
            "consignor_address": "Shipper Str. 1",
            "loading_city": "Warsaw",
            "loading_country": "PL",
            "client_name": "Client GmbH",
            "client_address": "Client Str. 99",
            "delivery_city": "Vienna",
            "delivery_country": "AT",
            "cargo_description": "Machinery",
            "package_count": 5,
        }

    def test_default_role_consignor_company_is_shipper(self):
        """Default (consignor) — company is ShipperTradeParty."""
        xml = generate_efti_xml("CMR-001", self._trip_data(), self._config())
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        shipper = cons.find(f"{{{NS_RAM}}}ShipperTradeParty")
        assert shipper.find(f"{{{NS_RAM}}}Name").text == "My Trans SRL"

    def test_default_role_client_is_consignee(self):
        """Default (consignor) — client is ConsigneeTradeParty."""
        xml = generate_efti_xml("CMR-001", self._trip_data(), self._config())
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        consignee = cons.find(f"{{{NS_RAM}}}ConsigneeTradeParty")
        assert consignee.find(f"{{{NS_RAM}}}Name").text == "Client GmbH"

    def test_role_consignee_company_is_consignee(self):
        """role='consignee' — company becomes ConsigneeTradeParty."""
        xml = generate_efti_xml("CMR-001", self._trip_data(), self._config(),
                                role="consignee")
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        consignee = cons.find(f"{{{NS_RAM}}}ConsigneeTradeParty")
        assert consignee.find(f"{{{NS_RAM}}}Name").text == "My Trans SRL"

    def test_role_consignee_client_is_shipper(self):
        """role='consignee' — client becomes ShipperTradeParty."""
        xml = generate_efti_xml("CMR-001", self._trip_data(), self._config(),
                                role="consignee")
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        shipper = cons.find(f"{{{NS_RAM}}}ShipperTradeParty")
        assert shipper.find(f"{{{NS_RAM}}}Name").text == "External Shipper"

    def test_carrier_always_from_company_config(self):
        """Carrier is always the company regardless of role."""
        xml = generate_efti_xml("CMR-001", self._trip_data(), self._config(),
                                role="consignee")
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        main_carr = cons.find(f"{{{NS_RAM}}}MainCarriageTransportMovement")
        carrier = main_carr.find(f"{{{NS_RAM}}}CarrierParty")
        assert carrier.find(f"{{{NS_RAM}}}Name").text == "My Trans SRL"


# ==============================================================================
# generate_efti_xml — truck, trailer, driver
# ==============================================================================


class TestGenerateEftiXmlVehicleAndDriver:
    """Tests for Box 16 (vehicle), Box 17 (trailer), and driver info."""

    def _base(self) -> tuple:
        trip = {"cargo_description": "Goods", "package_count": 1,
                "consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_license_plate_from_truck_data(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                truck_data={"plate_number": "B-123-ABC"})
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        used = cons.find(f"{{{NS_RAM}}}UsedTransportMeans")
        means = used.find(f"{{{NS_RAM}}}TransportMeans")
        equip = means.find(f"{{{NS_RAM}}}RoadTransportEquipment")
        assert equip.find(f"{{{NS_RAM}}}LicensePlateID").text == "B-123-ABC"

    def test_license_plate_from_trip_data_fallback(self):
        trip, cfg = self._base()
        trip["truck_plate"] = "TRIP-TRUCK"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        lid = cons.find(f"{{{NS_RAM}}}UsedTransportMeans/"
                        f"{{{NS_RAM}}}TransportMeans/"
                        f"{{{NS_RAM}}}RoadTransportEquipment/"
                        f"{{{NS_RAM}}}LicensePlateID")
        assert lid.text == "TRIP-TRUCK"

    def test_license_plate_from_truck_number(self):
        trip, cfg = self._base()
        trip["truck_number"] = "TRUCK-NR"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        lid = root.find(f".//{{{NS_RAM}}}LicensePlateID")
        assert lid.text == "TRUCK-NR"

    def test_no_plate_omits_vehicle_element(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        used = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment/"
                         f"{{{NS_RAM}}}UsedTransportMeans")
        assert used is None

    def test_trailer_plate_in_xml(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                truck_data={"plate_number": "TRK", "trailer_plate": "TRL-99"})
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        trailer = cons.find(f"{{{NS_RAM}}}AttachedLogisticsTransportEquipment")
        assert trailer.find(f"{{{NS_RAM}}}ID").text == "TRL-99"

    def test_trailer_plate_from_trip_data(self):
        trip, cfg = self._base()
        trip["trailer_plate"] = "TRAILER-TRIP"
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                truck_data={"plate_number": "TRK"})
        root = fromstring(xml)
        trailer = root.find(f".//{{{NS_RAM}}}AttachedLogisticsTransportEquipment")
        assert trailer.find(f"{{{NS_RAM}}}ID").text == "TRAILER-TRIP"

    def test_driver_name_in_xml(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                driver_data={"name": "John Doe", "license_number": "LIC-123"})
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        person = cons.find(f"{{{NS_RAM}}}SpecifiedTransportPerson")
        assert person.find(f"{{{NS_RAM}}}Name").text == "John Doe"
        assert person.find(f"{{{NS_RAM}}}ID").text == "LIC-123"

    def test_driver_name_from_trip_data(self):
        trip, cfg = self._base()
        trip["driver_name"] = "Trip Driver"
        trip["driver_license"] = "TRIP-LIC"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        person = root.find(f".//{{{NS_RAM}}}SpecifiedTransportPerson")
        assert person.find(f"{{{NS_RAM}}}Name").text == "Trip Driver"

    def test_no_driver_omits_person_element(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        persons = root.findall(f".//{{{NS_RAM}}}SpecifiedTransportPerson")
        assert len(persons) == 0


# ==============================================================================
# generate_efti_xml — goods (boxes 9-12)
# ==============================================================================


class TestGenerateEftiXmlGoods:
    """Tests for Boxes 9-12: package, weight, volume, HS code."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "Widgets"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_package_count(self):
        trip, cfg = self._base()
        trip["package_count"] = 42
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        qty = item.find(f"{{{NS_RAM}}}PackageQuantity")
        assert qty.text == "42"
        assert qty.get("unitCode") == "PCE"

    def test_package_type_and_marks(self):
        trip, cfg = self._base()
        trip["package_type"] = "PALLET"
        trip["cargo_marks"] = "FRAGILE"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        pkg = item.find(f"{{{NS_RAM}}}Package")
        assert pkg.find(f"{{{NS_RAM}}}TypeCode").text == "PALLET"
        assert pkg.find(f"{{{NS_RAM}}}Marking").text == "FRAGILE"

    def test_cargo_marks_fallback_to_marks(self):
        trip, cfg = self._base()
        trip["marks"] = "LEGACY-MARK"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        pkg = item.find(f"{{{NS_RAM}}}Package")
        assert pkg.find(f"{{{NS_RAM}}}Marking").text == "LEGACY-MARK"

    def test_cargo_description(self):
        trip, cfg = self._base()
        trip["cargo_description"] = "Electronic Components"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        desc = item.find(f"{{{NS_RAM}}}SummaryDescription")
        assert desc.text == "Electronic Components"

    def test_hs_code(self):
        trip, cfg = self._base()
        trip["hs_code"] = "8471.30"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        cc = item.find(f"{{{NS_RAM}}}CommodityCode")
        assert cc.find(f"{{{NS_RAM}}}ValueCode").text == "8471.30"

    def test_gross_weight(self):
        trip, cfg = self._base()
        trip["gross_weight_kg"] = 1500.5
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        wt = item.find(f"{{{NS_RAM}}}GrossWeightMeasure")
        assert wt.text == "1500.5"
        assert wt.get("unitCode") == "KGM"

    def test_volume(self):
        trip, cfg = self._base()
        trip["volume_m3"] = 25.0
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        vol = item.find(f"{{{NS_RAM}}}GrossVolumeMeasure")
        assert vol.text == "25.0"
        assert vol.get("unitCode") == "MTQ"

    def test_sequence_number(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        seq = item.find(f"{{{NS_RAM}}}SequenceNumeric")
        assert seq.text == "1"


# ==============================================================================
# generate_efti_xml — freight, payment, financial grid
# ==============================================================================


class TestGenerateEftiXmlFinancial:
    """Tests for Box 13 (freight charges), Box 14 (payment terms), Box 20."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_freight_charges_declared_value(self):
        trip, cfg = self._base()
        trip["freight_charges"] = "2500.00"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        amt = cons.find(f"{{{NS_RAM}}}DeclaredValueForCarriageAmount")
        assert amt.text == "2500.00"
        assert amt.get("currencyID") == "EUR"

    def test_cod_amount_fallback(self):
        trip, cfg = self._base()
        trip["cod_amount"] = "1500"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        amt = cons.find(f"{{{NS_RAM}}}DeclaredValueForCarriageAmount")
        assert amt.text == "1500.00"

    def test_freight_charges_takes_precedence_over_cod(self):
        trip, cfg = self._base()
        trip["freight_charges"] = "2000"
        trip["cod_amount"] = "1000"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        amt = cons.find(f"{{{NS_RAM}}}DeclaredValueForCarriageAmount")
        assert amt.text == "2000.00"

    def test_invalid_freight_charges_skipped(self):
        trip, cfg = self._base()
        trip["freight_charges"] = "not-a-number"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        amt = cons.find(f"{{{NS_RAM}}}DeclaredValueForCarriageAmount")
        assert amt is None

    def test_payment_terms_with_payer_and_distance(self):
        trip, cfg = self._base()
        trip["carriage_payer"] = "Consignee"
        trip["distance_km"] = 850
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        code = cons.find(f"{{{NS_RAM}}}PaymentArrangementCode")
        assert "Payer: Consignee" in code.text
        assert "850" in code.text

    def test_payment_terms_default_empty_string(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        code = cons.find(f"{{{NS_RAM}}}PaymentArrangementCode")
        assert code is None

    def test_financial_grid_with_consignee_payer(self):
        trip, cfg = self._base()
        trip["carriage_payer"] = "Consignee"
        trip["financial_grid"] = {"base": 1000, "extra": 200}
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        code = cons.find(f"{{{NS_RAM}}}FreightPaymentTermCode")
        assert code is not None
        assert code.text == "1"

    def test_financial_grid_with_sender_payer(self):
        trip, cfg = self._base()
        trip["carriage_payer"] = "sender"
        trip["financial_grid"] = {"base": 1000}
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        code = cons.find(f"{{{NS_RAM}}}FreightPaymentTermCode")
        assert code.text == "0"

    def test_financial_grid_skipped_when_empty(self):
        trip, cfg = self._base()
        trip["financial_grid"] = {}
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        code = cons.find(f"{{{NS_RAM}}}FreightPaymentTermCode")
        assert code is None


# ==============================================================================
# generate_efti_xml — successive carriers
# ==============================================================================


class TestGenerateEftiXmlSuccessiveCarriers:
    """Tests for Box 7 — Successive / On-carriage carriers."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def _make_carriers(self):
        return [
            {
                "carrier_name": "Carrier 1 LTD",
                "carrier_address": "Addr 1",
                "carrier_country": "HU",
                "carrier_city": "Budapest",
                "vehicle_plate": "H-123-XX",
                "driver_name": "József",
            },
            {
                "carrier_name": "Carrier 2 GmbH",
                "carrier_address": "Addr 2",
                "carrier_country": "AT",
                "carrier_city": "Vienna",
                "vehicle_plate": "A-456-YY",
                "driver_name": "Hans",
            },
        ]

    def test_successive_carriers_as_parameter(self):
        trip, cfg = self._base()
        carriers = self._make_carriers()
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                successive_carriers=carriers)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        movements = cons.findall(f"{{{NS_RAM}}}OnCarriageTransportMovement")
        assert len(movements) == 2
        # Check first carrier name
        party0 = movements[0].find(f"{{{NS_RAM}}}CarrierParty")
        assert party0.find(f"{{{NS_RAM}}}Name").text == "Carrier 1 LTD"

    def test_successive_carriers_from_trip_data(self):
        trip, cfg = self._base()
        trip["successive_carriers"] = self._make_carriers()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        movements = root.findall(f".//{{{NS_RAM}}}OnCarriageTransportMovement")
        assert len(movements) == 2

    def test_successive_carriers_parameter_takes_precedence(self):
        trip, cfg = self._base()
        # The source uses `successive_carriers or trip_data.get("successive_carriers", [])`
        # so an empty list [] is falsy and falls back. To truly test precedence,
        # pass non-empty parameter while trip data also has carriers.
        trip["successive_carriers"] = self._make_carriers()
        # Pass a different carrier as parameter
        alt_carriers = [{"carrier_name": "Alternate Carrier"}]
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                successive_carriers=alt_carriers)
        root = fromstring(xml)
        movements = root.findall(f".//{{{NS_RAM}}}OnCarriageTransportMovement")
        assert len(movements) == 1
        party = movements[0].find(f"{{{NS_RAM}}}CarrierParty")
        assert party.find(f"{{{NS_RAM}}}Name").text == "Alternate Carrier"

    def test_successive_carrier_vehicle_plate(self):
        trip, cfg = self._base()
        carriers = [{"carrier_name": "C1", "vehicle_plate": "PL-01"}]
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                successive_carriers=carriers)
        root = fromstring(xml)
        lid = root.find(f".//{{{NS_RAM}}}OnCarriageTransportMovement/"
                        f"{{{NS_RAM}}}UsedTransportMeans/"
                        f"{{{NS_RAM}}}TransportMeans/"
                        f"{{{NS_RAM}}}RoadTransportEquipment/"
                        f"{{{NS_RAM}}}LicensePlateID")
        assert lid.text == "PL-01"

    def test_successive_carrier_driver_name(self):
        trip, cfg = self._base()
        carriers = [{"carrier_name": "C1", "driver_name": "Pilot"}]
        xml = generate_efti_xml("CMR-001", trip, cfg,
                                successive_carriers=carriers)
        root = fromstring(xml)
        person = root.find(f".//{{{NS_RAM}}}OnCarriageTransportMovement/"
                           f"{{{NS_RAM}}}SpecifiedTransportPerson/"
                           f"{{{NS_RAM}}}Name")
        assert person.text == "Pilot"

    def test_no_successive_carriers_omits_movements(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        movements = root.findall(f".//{{{NS_RAM}}}OnCarriageTransportMovement")
        assert len(movements) == 0


# ==============================================================================
# generate_efti_xml — loading / delivery locations
# ==============================================================================


class TestGenerateEftiXmlLocations:
    """Tests for Box 3 (delivery) and Box 4 (loading)."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_departure_location_with_city_country(self):
        trip, cfg = self._base()
        trip["loading_city"] = "Bucharest"
        trip["loading_country"] = "RO"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dept = root.find(f".//{{{NS_RAM}}}DepartureTransportMovement")
        loc = dept.find(f"{{{NS_RAM}}}DepartureLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Bucharest"
        assert loc.find(f"{{{NS_RAM}}}CountryID").text == "RO"

    def test_departure_location_from_loading_address(self):
        trip, cfg = self._base()
        trip["loading_address"] = "Depot 42"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dept = root.find(f".//{{{NS_RAM}}}DepartureTransportMovement")
        loc = dept.find(f"{{{NS_RAM}}}DepartureLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Depot 42"

    def test_departure_location_from_origin(self):
        trip, cfg = self._base()
        trip["origin"] = "Origin City"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dept = root.find(f".//{{{NS_RAM}}}DepartureTransportMovement")
        loc = dept.find(f"{{{NS_RAM}}}DepartureLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Origin City"

    def test_departure_date(self):
        trip, cfg = self._base()
        trip["loading_city"] = "X"
        trip["place_of_loading_date"] = "2026-07-15"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dept = root.find(f".//{{{NS_RAM}}}DepartureTransportMovement")
        dt_str = dept.find(f"{{{NS_RAM}}}PlannedDepartureDateTime/"
                           f"{{{NS_UDT}}}DateTimeString")
        assert dt_str.text == "20260715"

    def test_arrival_location_with_city_country(self):
        trip, cfg = self._base()
        trip["delivery_city"] = "Berlin"
        trip["delivery_country"] = "DE"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        delv = root.find(f".//{{{NS_RAM}}}DeliveryTransportMovement")
        loc = delv.find(f"{{{NS_RAM}}}ArrivalLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Berlin"
        assert loc.find(f"{{{NS_RAM}}}CountryID").text == "DE"

    def test_arrival_location_from_unloading_address(self):
        trip, cfg = self._base()
        trip["unloading_address"] = "Warehouse 7"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        delv = root.find(f".//{{{NS_RAM}}}DeliveryTransportMovement")
        loc = delv.find(f"{{{NS_RAM}}}ArrivalLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Warehouse 7"

    def test_arrival_location_from_destination(self):
        trip, cfg = self._base()
        trip["destination"] = "Dest City"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        delv = root.find(f".//{{{NS_RAM}}}DeliveryTransportMovement")
        loc = delv.find(f"{{{NS_RAM}}}ArrivalLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Dest City"


# ==============================================================================
# generate_efti_xml — documents, instructions, reservations, agreements
# ==============================================================================


class TestGenerateEftiXmlMiscBoxes:
    """Tests for Box 5 (documents), Box 8 (reservations),
    Box 18 (instructions), Box 19 (agreements)."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_documents_attached(self):
        trip, cfg = self._base()
        trip["documents_attached"] = "INV-001, CMR-COPY, CERT-01"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        docs = cons.findall(f"{{{NS_RAM}}}AttachedTransportDocument")
        assert len(docs) == 3
        assert docs[0].find(f"{{{NS_RAM}}}ID").text == "INV-001"
        assert docs[0].find(f"{{{NS_RAM}}}TypeCode").text == "916"

    def test_documents_attached_empty_string_skipped(self):
        trip, cfg = self._base()
        trip["documents_attached"] = ""
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        docs = root.findall(f".//{{{NS_RAM}}}AttachedTransportDocument")
        assert len(docs) == 0

    def test_carrier_reservations(self):
        trip, cfg = self._base()
        trip["carrier_reservations"] = "Packages damaged on arrival"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        instructions = root.findall(f".//{{{NS_RAM}}}SpecifiedLogisticsInstruction")
        descs = [i.find(f"{{{NS_RAM}}}Description").text for i in instructions
                 if i.find(f"{{{NS_RAM}}}Description") is not None]
        assert "Packages damaged on arrival" in descs

    def test_carrier_instructions(self):
        trip, cfg = self._base()
        trip["carrier_instructions"] = "Keep refrigerated"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        instructions = root.findall(f".//{{{NS_RAM}}}SpecifiedLogisticsInstruction")
        descs = [i.find(f"{{{NS_RAM}}}Description").text for i in instructions
                 if i.find(f"{{{NS_RAM}}}Description") is not None]
        assert "Keep refrigerated" in descs

    def test_special_agreements(self):
        trip, cfg = self._base()
        trip["special_agreements"] = "Delivery between 08:00-17:00"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        item = root.find(f".//{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
        remarks = item.find(f"{{{NS_RAM}}}Remarks")
        assert remarks.text == "Delivery between 08:00-17:00"


# ==============================================================================
# generate_efti_xml — signatures
# ==============================================================================


class TestGenerateEftiXmlSignatures:
    """Tests for signature elements (Boxes 22, 23, 24)."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_sender_signature(self):
        trip, cfg = self._base()
        trip["sig_sender_path"] = "/path/to/sender/sig"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        auths = doc.findall(f"{{{NS_RAM}}}SignatoryDocumentAuthentication")
        # Should have at least one (sender)
        assert len(auths) >= 1
        auth_text = auths[0].find(f"{{{NS_RAM}}}SignatoryAuthentication")
        assert auth_text.text == "presented"
        assert auth_text.get("authenticationTypeCode") == "DigitalSignature"

    def test_sender_signature_sets_status(self):
        trip, cfg = self._base()
        trip["sig_sender_path"] = "/path/sig"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        sigs = root.findall(f"{{{NS_RSM}}}SpecifiedSignature")
        sender_sig = [s for s in sigs
                      if s.find(f"{{{NS_RAM}}}TypeCode").text == "sender"][0]
        assert sender_sig.find(f"{{{NS_RAM}}}StatusCode").text == "signed"

    def test_carrier_signature(self):
        trip, cfg = self._base()
        trip["sig_carrier_path"] = "/path/carrier/sig"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        sigs = root.findall(f"{{{NS_RSM}}}SpecifiedSignature")
        carrier_sig = [s for s in sigs
                       if s.find(f"{{{NS_RAM}}}TypeCode").text == "carrier"][0]
        assert carrier_sig.find(f"{{{NS_RAM}}}StatusCode").text == "signed"

    def test_consignee_signature(self):
        trip, cfg = self._base()
        trip["sig_consignee_path"] = "/path/consignee/sig"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        # Check DeliveryNote element
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        del_note = cons.find(f"{{{NS_RAM}}}DeliveryNote")
        assert del_note is not None
        sig_auth = del_note.find(f"{{{NS_RAM}}}SignatoryAuthentication")
        assert sig_auth.get("authenticationTypeCode") == "DigitalSignature"
        # Check SpecifiedSignature status
        sigs = root.findall(f"{{{NS_RSM}}}SpecifiedSignature")
        c_sig = [s for s in sigs
                 if s.find(f"{{{NS_RAM}}}TypeCode").text == "consignee"][0]
        assert c_sig.find(f"{{{NS_RAM}}}StatusCode").text == "signed"


# ==============================================================================
# generate_efti_xml — dangerous goods (ADR)
# ==============================================================================


class TestGenerateEftiXmlAdr:
    """Tests for Dangerous Goods / ADR data elements."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_adr_json_string(self):
        trip, cfg = self._base()
        trip["adr_info_json"] = json.dumps([
            {"un_no": "1203", "adr_class": "3", "packing_group": "II",
             "tunnel_code": "E", "quantity": 500},
        ])
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dgs = root.findall(f".//{{{NS_RAM}}}IncludedDangerousGoods")
        assert len(dgs) == 1
        dg = dgs[0]
        assert dg.find(f"{{{NS_RAM}}}UNDGIdentifier").text == "1203"
        assert dg.find(f"{{{NS_RAM}}}ClassificationCode").text == "3"
        assert dg.find(f"{{{NS_RAM}}}PackingGroupCode").text == "II"
        assert dg.find(f"{{{NS_RAM}}}TunnelRestrictionCode").text == "E"
        mass = dg.find(f"{{{NS_RAM}}}GrossMassMeasure")
        assert mass.text == "500"
        assert mass.get("unitCode") == "KGM"

    def test_adr_as_dict(self):
        trip, cfg = self._base()
        trip["adr_info_json"] = [{"un_no": "1001", "adr_class": "2"}]
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dgs = root.findall(f".//{{{NS_RAM}}}IncludedDangerousGoods")
        assert len(dgs) == 1
        assert dgs[0].find(f"{{{NS_RAM}}}UNDGIdentifier").text == "1001"

    def test_adr_multiple_items(self):
        trip, cfg = self._base()
        trip["adr_info_json"] = json.dumps([
            {"un_no": "1203"},
            {"un_no": "1300"},
        ])
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dgs = root.findall(f".//{{{NS_RAM}}}IncludedDangerousGoods")
        assert len(dgs) == 2

    def test_adr_json_decode_error_skipped(self):
        """Invalid JSON should not raise but skip ADR generation."""
        trip, cfg = self._base()
        trip["adr_info_json"] = "{invalid json}"
        # Should not raise
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dgs = root.findall(f".//{{{NS_RAM}}}IncludedDangerousGoods")
        assert len(dgs) == 0

    def test_adr_none_skipped(self):
        trip, cfg = self._base()
        trip["adr_info_json"] = None
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        dgs = root.findall(f".//{{{NS_RAM}}}IncludedDangerousGoods")
        assert len(dgs) == 0


# ==============================================================================
# generate_efti_xml — issue place / date
# ==============================================================================


class TestGenerateEftiXmlIssuePlace:
    """Tests for Box 21 — issue place and date."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_issue_place_from_trip_data(self):
        trip, cfg = self._base()
        trip["issue_place"] = "Paris"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        loc = doc.find(f"{{{NS_RAM}}}IssueLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Paris"

    def test_issue_place_fallback_to_place_of_loading(self):
        trip, cfg = self._base()
        trip["place_of_loading"] = "Lyon"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        loc = doc.find(f"{{{NS_RAM}}}IssueLocation")
        assert loc.find(f"{{{NS_RAM}}}CityName").text == "Lyon"

    def test_issue_country(self):
        trip, cfg = self._base()
        trip["issue_country"] = "FR"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        loc = doc.find(f"{{{NS_RAM}}}IssueLocation")
        assert loc.find(f"{{{NS_RAM}}}CountryID").text == "FR"

    def test_issue_country_fallback_to_loading_country(self):
        trip, cfg = self._base()
        trip["loading_country"] = "IT"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        loc = doc.find(f"{{{NS_RAM}}}IssueLocation")
        assert loc.find(f"{{{NS_RAM}}}CountryID").text == "IT"

    def test_issue_date_explicit(self):
        trip, cfg = self._base()
        trip["issue_date"] = "2026-12-01"
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        doc = root.find(f"{{{NS_RSM}}}ExchangedDocument")
        dt_str = doc.find(f"{{{NS_RAM}}}IssueDateTime/"
                          f"{{{NS_UDT}}}DateTimeString")
        assert dt_str.text == "20261201"


# ==============================================================================
# generate_efti_xml — edge cases and error handling
# ==============================================================================


class TestGenerateEftiXmlEdgeCases:
    """Tests for edge cases — minimal data, missing optional info."""

    def test_absolutely_minimal_data(self):
        """Only the truly required fields to avoid crashes."""
        xml = generate_efti_xml(
            "CMR-000",
            {"consignor_name": "S", "client_name": "R",
             "loading_city": "X", "delivery_city": "Y",
             "cargo_description": "G"},
            {"company_name": "C", "address": "A", "cui": "V"},
        )
        root = fromstring(xml)
        assert root.tag == f"{{{NS_ECMR}}}eCMR"

    def test_empty_company_config_defaults(self):
        """Empty config still produces valid XML with empty values."""
        xml = generate_efti_xml(
            "CMR-000",
            {"consignor_name": "S", "client_name": "R",
             "loading_city": "X", "delivery_city": "Y",
             "cargo_description": "G"},
            {},
        )
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        shipper = cons.find(f"{{{NS_RAM}}}ShipperTradeParty")
        # Name should be from trip data since company_name is empty
        assert shipper.find(f"{{{NS_RAM}}}Name").text == "S"

    def test_client_data_none(self):
        """client_data=None should not crash."""
        xml = generate_efti_xml(
            "CMR-000",
            {"consignor_name": "S", "client_name": "R",
             "loading_city": "X", "delivery_city": "Y",
             "cargo_description": "G"},
            {"company_name": "C", "address": "A", "cui": "V"},
            client_data=None,
        )
        root = fromstring(xml)
        assert root.tag == f"{{{NS_ECMR}}}eCMR"

    def test_truck_data_none(self):
        xml = generate_efti_xml(
            "CMR-000",
            {"consignor_name": "S", "client_name": "R",
             "loading_city": "X", "delivery_city": "Y",
             "cargo_description": "G"},
            {"company_name": "C", "address": "A", "cui": "V"},
            truck_data=None,
        )
        root = fromstring(xml)
        assert root.tag == f"{{{NS_ECMR}}}eCMR"

    def test_driver_data_none(self):
        xml = generate_efti_xml(
            "CMR-000",
            {"consignor_name": "S", "client_name": "R",
             "loading_city": "X", "delivery_city": "Y",
             "cargo_description": "G"},
            {"company_name": "C", "address": "A", "cui": "V"},
            driver_data=None,
        )
        root = fromstring(xml)
        assert root.tag == f"{{{NS_ECMR}}}eCMR"

    def test_all_data_provided_maximal(self):
        """Full data set — no part should cause an error."""
        trip = {
            "consignor_name": "Shipper SA", "consignor_address": "Addr 1",
            "consignor_id": "SHP-01", "consignor_vat": "RO111",
            "consignor_eori": "EORI-RO-111",
            "loading_city": "Paris", "loading_country": "FR",
            "place_of_loading": "Port of Paris",
            "place_of_loading_date": "2026-07-15",
            "client_name": "Receiver Ltd", "client_address": "Addr 2",
            "delivery_city": "Berlin", "delivery_country": "DE",
            "place_of_delivery": "Warehouse 7",
            "issue_place": "Paris", "issue_country": "FR",
            "issue_date": "2026-07-15",
            "cargo_description": "Machinery",
            "package_count": 5, "package_type": "CRATE",
            "cargo_marks": "FRAGILE", "hs_code": "8479.89",
            "gross_weight_kg": 2500.0, "volume_m3": 12.5,
            "freight_charges": "5000",
            "carriage_payer": "consignee",
            "distance_km": 1200,
            "financial_grid": {"base": 4000, "fuel": 1000},
            "carrier_country": "RO", "carrier_city": "Bucharest",
            "carrier_instructions": "Notify 2h before arrival",
            "carrier_reservations": "None",
            "special_agreements": "Insurance covers EUR 50k",
            "documents_attached": "INV-001, CMR-COPY",
            "adr_info_json": json.dumps([{"un_no": "1203", "adr_class": "3"}]),
            "sig_sender_path": "/sig/sender",
            "sig_carrier_path": "/sig/carrier",
        }
        cfg = {
            "company_name": "Trans SRL", "address": "Str. X 10",
            "cui": "RO999", "eori_number": "EORI-RO-999",
        }
        truck = {"plate_number": "B-123-ABC",
                 "trailer_plate": "B-TRL-99"}
        driver = {"name": "Ion Popescu", "license_number": "RO12345"}
        carriers = [
            {"carrier_name": "SubCarrier 1", "vehicle_plate": "H-001-XX",
             "driver_name": "János", "carrier_address": "BP str",
             "carrier_country": "HU", "carrier_city": "Budapest"},
        ]
        xml = generate_efti_xml(
            "CMR-FULL-001", trip, cfg,
            client_data=None,
            truck_data=truck,
            driver_data=driver,
            successive_carriers=carriers,
            role="consignor",
        )
        root = fromstring(xml)
        # Root present
        assert root.tag == f"{{{NS_ECMR}}}eCMR"
        # Truck plate — under SpecifiedSupplyChainConsignment/UsedTransportMeans (not
        # under OnCarriageTransportMovement which appears first in document order)
        lid = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment/"
                        f"{{{NS_RAM}}}UsedTransportMeans/"
                        f"{{{NS_RAM}}}TransportMeans/"
                        f"{{{NS_RAM}}}RoadTransportEquipment/"
                        f"{{{NS_RAM}}}LicensePlateID")
        assert lid.text == "B-123-ABC"
        # Trailer
        trailer = root.find(f".//{{{NS_RAM}}}AttachedLogisticsTransportEquipment")
        assert trailer.find(f"{{{NS_RAM}}}ID").text == "B-TRL-99"
        # ADR
        dgs = root.findall(f".//{{{NS_RAM}}}IncludedDangerousGoods")
        assert len(dgs) == 1
        # Signatures
        sigs = root.findall(f"{{{NS_RSM}}}SpecifiedSignature")
        statuses = {s.find(f"{{{NS_RAM}}}TypeCode").text:
                    s.find(f"{{{NS_RAM}}}StatusCode").text for s in sigs}
        assert statuses["sender"] == "signed"
        assert statuses["carrier"] == "signed"
        assert statuses["consignee"] == "unsigned"


# ==============================================================================
# generate_efti_xml — XML well-formedness & content verification
# ==============================================================================


class TestGenerateEftiXmlContentVerification:
    """String-level verification of the generated XML."""

    def _base(self) -> tuple:
        trip = {"consignor_name": "S", "client_name": "R",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}
        cfg = {"company_name": "C", "address": "A", "cui": "V"}
        return trip, cfg

    def test_xml_contains_schema_location(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        assert XSI_SCHEMA_LOCATION in xml

    def test_xml_pretty_printed(self):
        """Output is indented with 2-space steps."""
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        # XML declaration followed by newline and indented root
        assert '<?xml version="1.0" encoding="UTF-8"?>\n<' in xml

    def test_xml_well_formed_elementtree_parse(self):
        """Entire XML string can be parsed by ElementTree."""
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        root = fromstring(xml)
        # Normalise: round-trip and re-parse to catch any structural issues
        roundtrip = tostring(root, encoding="unicode")
        root2 = fromstring(roundtrip)
        assert root2.tag == f"{{{NS_ECMR}}}eCMR"

    def test_output_is_unicode_string(self):
        trip, cfg = self._base()
        xml = generate_efti_xml("CMR-001", trip, cfg)
        assert isinstance(xml, str)


# ==============================================================================
# generate_efti_xml — client_data with full details
# ==============================================================================


class TestGenerateEftiXmlClientData:
    """Tests for client_data parameter overriding trip data."""

    def _config(self) -> dict:
        return {"company_name": "Trans SRL", "address": "A", "cui": "V"}

    def _trip(self) -> dict:
        return {"consignor_name": "Trip Shipper",
                "client_name": "Trip Client",
                "loading_city": "X", "delivery_city": "Y",
                "cargo_description": "G"}

    def test_client_data_name_overrides_trip(self):
        cfg = self._config()
        trip = self._trip()
        client = {"name": "Client SA", "address": "Addr 1", "country": "CH",
                  "city": "Zurich", "vat_number": "CH123", "eori_number": "CH-EORI"}
        xml = generate_efti_xml("CMR-001", trip, cfg, client_data=client)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        consignee = cons.find(f"{{{NS_RAM}}}ConsigneeTradeParty")
        # client_data.name overrides trip.client_name
        assert consignee.find(f"{{{NS_RAM}}}Name").text == "Client SA"
        addr = consignee.find(f"{{{NS_RAM}}}PostalTradeAddress")
        # client_data.address overrides trip.client_address (trip has none)
        assert addr.find(f"{{{NS_RAM}}}StreetName").text == "Addr 1"
        # delivery_city comes from trip_data (precedence over client.city)
        assert addr.find(f"{{{NS_RAM}}}CityName").text == "Y"
        # delivery_country not in trip, falls back to client.country
        assert addr.find(f"{{{NS_RAM}}}CountryID").text == "CH"

    def test_client_data_vat_and_eori(self):
        cfg = self._config()
        trip = self._trip()
        client = {"name": "C", "vat_number": "VAT-001", "eori_number": "EORI-001"}
        xml = generate_efti_xml("CMR-001", trip, cfg, client_data=client)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        consignee = cons.find(f"{{{NS_RAM}}}ConsigneeTradeParty")
        regs = consignee.findall(f"{{{NS_RAM}}}SpecifiedTaxRegistration")
        ids = [r.find(f"{{{NS_RAM}}}ID").text for r in regs]
        assert "VAT-001" in ids
        assert "EORI-001" in ids

    def test_client_id_as_consignee_party_id(self):
        cfg = self._config()
        trip = self._trip()
        client = {"name": "C", "id": "CL-42"}
        xml = generate_efti_xml("CMR-001", trip, cfg, client_data=client)
        root = fromstring(xml)
        cons = root.find(f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
        consignee = cons.find(f"{{{NS_RAM}}}ConsigneeTradeParty")
        assert consignee.find(f"{{{NS_RAM}}}ID").text == "CL-42"


# ==============================================================================
# Module-level constants
# ==============================================================================


class TestModuleConstants:
    """Verify module-level constants are properly defined."""

    def test_namespace_constants(self):
        assert NS_ECMR.startswith("urn:un:unece")
        assert NS_RSM.startswith("urn:un:unece")
        assert NS_RAM.startswith("urn:un:unece")
        assert NS_UDT.startswith("urn:un:unece")
        assert NS_XSI == "http://www.w3.org/2001/XMLSchema-instance"

    def test_schema_location(self):
        assert XSI_SCHEMA_LOCATION.startswith("urn:un:unece")
        assert XSI_SCHEMA_LOCATION.endswith("eCMR_1p0.xsd")
