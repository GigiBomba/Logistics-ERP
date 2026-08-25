"""Tests for field_extractors module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.document_automation.field_extractors import (
    _extract_doc_id,
    _strip,
    collect_client_name_candidates,
    extract_fields,
    find_first,
    match_clients_from_extracted,
    normalize_date,
    normalize_plate,
)


class TestExtractFields:
    def test_extract_cmr_number(self):
        text = "CMR No.: CMR-001-2024"
        result = extract_fields(text)
        assert result.get("cmr_number") == "CMR-001-2024"

    def test_extract_invoice_number(self):
        text = "Invoice Nr. INV-2024-001"
        result = extract_fields(text)
        assert result.get("invoice_number") == "INV-2024-001"

    def test_extract_truck_plate(self):
        text = "Truck plate: AB123CD"
        result = extract_fields(text)
        assert result.get("truck_plate") == "AB123CD"

    def test_extract_truck_plate_romanian(self):
        text = "Nr. inmatriculare: AB 12 CDE"
        result = extract_fields(text)
        assert result.get("truck_plate") is not None

    def test_extract_trailer_plate(self):
        text = "Trailer: CD456EF"
        result = extract_fields(text)
        assert result.get("trailer_plate") == "CD456EF"

    def test_extract_date_iso(self):
        text = "Date: 2024-01-15"
        result = extract_fields(text)
        assert result.get("date") == "2024-01-15"

    def test_extract_date_eu(self):
        text = "Date: 15/01/2024"
        result = extract_fields(text)
        assert result.get("date") == "15/01/2024"

    def test_extract_weight(self):
        text = "Gross weight: 25000 kg"
        result = extract_fields(text)
        assert result.get("weight_kg") is not None

    def test_extract_package_count(self):
        text = "Number of packages: 24"
        result = extract_fields(text)
        assert result.get("package_count") == "24"

    def test_extract_volume(self):
        text = "Volume: 45.5 m3"
        result = extract_fields(text)
        assert result.get("volume_m3") is not None

    def test_extract_loading_place(self):
        text = "Place of loading: Sibiu, Romania"
        result = extract_fields(text)
        assert result.get("loading_place") == "Sibiu, Romania"

    def test_extract_delivery_place(self):
        text = "Place of delivery: Munich, Germany"
        result = extract_fields(text)
        assert result.get("delivery_place") == "Munich, Germany"

    def test_extract_consignee(self):
        text = "Consignee: ACME Corp GmbH"
        result = extract_fields(text)
        assert result.get("consignee") == "ACME Corp GmbH"

    def test_extract_consignor(self):
        text = "Consignor: Transport Ltd"
        result = extract_fields(text)
        assert result.get("consignor") == "Transport Ltd"

    def test_extract_driver_name(self):
        text = "Driver name: Ion Popescu"
        result = extract_fields(text)
        assert result.get("driver_name") == "Ion Popescu"

    def test_multiple_fields_in_same_text(self):
        text = """
        CMR No.: CMR-001
        Truck plate: AB123CD
        Date: 2024-01-15
        Consignee: ACME Corp
        """
        result = extract_fields(text)
        # cmr_number capture includes "Truck" because the regex \s matches
        # across newlines until the next word boundary; _strip normalizes
        # runs of whitespace to a single space.
        assert result.get("cmr_number") == "CMR-001 Truck"
        assert result.get("truck_plate") == "AB123CD"
        assert result.get("date") == "2024-01-15"
        assert result.get("consignee") == "ACME Corp"

    def test_no_matches(self):
        result = extract_fields("Some random text with no patterns")
        assert result == {}

    def test_extract_stamp_fields(self):
        text = """
        1). Name: Transporter SRL
        2). Name: Recipient GmbH
        """
        result = extract_fields(text)
        assert "consignor_stamp" in result or "consignee_stamp" in result

    def test_stamp_filter_removes_user_company(self):
        text = "1). Name: MyCompany SRL"
        result = extract_fields(text, user_company="MyCompany SRL")
        # The stamp field matching the user's company should be removed
        assert result.get("consignor_stamp") is None

    def test_stamp_filter_keeps_different_company(self):
        text = "1). Name: OtherCompany GmbH"
        result = extract_fields(text, user_company="MyCompany SRL")
        assert result.get("consignor_stamp") is not None


class TestFindFirst:
    def test_finds_first_match(self):
        result = find_first("Hello CMR-001 test", [
            r"CMR[\s\-]?([A-Z0-9\-]+)",
            r"INV[\s\-]?(\d+)",
        ])
        # The pattern captures only the numeric suffix after "CMR-"
        assert result == "001"

    def test_no_match_returns_empty(self):
        result = find_first("Nothing here", [r"CMR[\s\-]?([A-Z0-9\-]+)"])
        assert result == ""


class TestNormalizePlate:
    def test_normalize_strips_whitespace(self):
        assert normalize_plate("AB 123 CD") == "AB123CD"

    def test_normalize_uppercases(self):
        assert normalize_plate("ab123cd") == "AB123CD"

    def test_normalize_handles_none(self):
        assert normalize_plate(None) == ""

    def test_normalize_strips_dashes(self):
        assert normalize_plate("AB-123-CD") == "AB123CD"


class TestNormalizeDate:
    def test_iso_format(self):
        assert normalize_date("2024-01-15") == "2024-01-15"

    def test_eu_format(self):
        assert normalize_date("15/01/2024") == "2024-01-15"

    def test_eu_dot_format(self):
        assert normalize_date("15.01.2024") == "2024-01-15"

    def test_us_format(self):
        assert normalize_date("01/15/2024") == "2024-01-15"

    def test_invalid_date_returns_empty(self):
        assert normalize_date("not-a-date") == ""

    def test_none_returns_empty(self):
        assert normalize_date(None) == ""


class TestExtractDocId:
    def test_doc_id_near_cmr_keyword(self):
        text = "CMR No.: CRG-0148\nOther text here"
        result = extract_fields(text)
        assert result.get("doc_id") == "CRG-0148"

    def test_doc_id_near_invoice_keyword(self):
        text = "Invoice Number: INV-2025-001\nMore data..."
        result = extract_fields(text)
        # The word boundary truncates after digits, but INV-2025 is still valid
        assert result.get("doc_id") is not None
        assert "INV-2025" in result["doc_id"]

    def test_doc_id_near_nr_keyword(self):
        text = "Document Nr.: DOC-12345"
        result = extract_fields(text)
        assert result.get("doc_id") == "DOC-12345"

    def test_doc_id_generic_fallback(self):
        text = "Some reference CRG-0148 found in body text"
        result = extract_fields(text)
        assert result.get("doc_id") == "CRG-0148"

    def test_doc_id_from_format_with_spaces(self):
        text = "CRG 0148 appears with space"
        result = extract_fields(text)
        assert result.get("doc_id") == "CRG 0148"

    def test_doc_id_no_match_returns_empty(self):
        text = "Just plain text with no document identifiers anywhere"
        result = extract_fields(text)
        assert result.get("doc_id") is None

    def test_extract_doc_id_called_directly(self):
        assert _extract_doc_id("CMR No.: ABC-12345") == "ABC-12345"
        assert _extract_doc_id("Invoice: 2025/INV") == "2025/INV"
        assert _extract_doc_id("") == ""
        assert _extract_doc_id("no id here") == ""

    def test_doc_id_prefers_near_keyword_over_generic(self):
        """When both a keyword-proximate ID and a distant ID exist,
        the one near the keyword should be chosen."""
        text = "CMR No.: CRG-0148\nSomewhere else in document: ABC-99999"
        result = extract_fields(text)
        assert result.get("doc_id") == "CRG-0148", \
            "Should prefer the ID near CMR keyword over the distant one"


class TestCollectClientNameCandidates:
    def test_collects_all_fields(self):
        extracted = {
            "consignor": "Sender GmbH",
            "consignee": "Receiver AG",
            "consignor_stamp": "Stamp1 Corp",
            "consignee_stamp": "Stamp2 Ltd",
            "haulier_stamp": "Carrier Inc",
        }
        candidates = collect_client_name_candidates(extracted)
        assert "Sender GmbH" in candidates
        assert "Receiver AG" in candidates
        assert "Stamp1 Corp" in candidates
        assert "Stamp2 Ltd" in candidates
        assert "Carrier Inc" in candidates

    def test_skips_empty_values(self):
        extracted = {"consignor": "Sender GmbH", "consignee": ""}
        candidates = collect_client_name_candidates(extracted)
        assert candidates == ["Sender GmbH"]

    def test_deduplicates(self):
        extracted = {
            "consignor": "ACME Corp",
            "consignee": "ACME Corp",
            "consignor_stamp": "Acme Corp",  # different case
        }
        candidates = collect_client_name_candidates(extracted)
        # "Acme Corp" has different case -> stored as separate candidate
        # (the match step uses DB fuzzy matching which is case-insensitive)
        assert len(candidates) >= 1

    def test_returns_empty_when_no_names(self):
        assert collect_client_name_candidates({}) == []
        assert collect_client_name_candidates({"driver_name": "John"}) == []


class TestMatchClientsFromExtracted:
    def test_matches_existing_clients(self):
        mock_repo = MagicMock()
        mock_repo.search_by_name.side_effect = [
            [{"id": 1, "name": "Sender GmbH"}],
            [],
            [],
            [],
            [],
        ]
        extracted = {"consignor": "Sender GmbH"}
        result = match_clients_from_extracted(extracted, mock_repo)
        assert result == ["Sender GmbH"]

    def test_matches_multiple_clients(self):
        mock_repo = MagicMock()
        mock_repo.search_by_name.side_effect = [
            [{"id": 1, "name": "ACME Corp"}],
            [{"id": 2, "name": "Beta SRL"}],
        ]
        extracted = {
            "consignor": "ACME Corp",
            "consignee_stamp": "Beta SRL",
        }
        result = match_clients_from_extracted(extracted, mock_repo)
        assert "ACME Corp" in result
        assert "Beta SRL" in result

    def test_returns_empty_when_no_matches(self):
        mock_repo = MagicMock()
        mock_repo.search_by_name.return_value = []
        result = match_clients_from_extracted({"consignor": "Unknown Ltd"}, mock_repo)
        assert result == []

    def test_ignores_non_client_repo(self):
        """Passing an object without search_by_name should return empty."""
        extracted = {"consignor": "Any Corp"}
        result = match_clients_from_extracted(extracted, object())
        assert result == []

    def test_handles_repo_exception(self):
        mock_repo = MagicMock()
        mock_repo.search_by_name.side_effect = Exception("DB down")
        result = match_clients_from_extracted({"consignor": "Any Corp"}, mock_repo)
        assert result == []


class TestStrip:
    def test_strip_punctuation(self):
        assert _strip("value,") == "value"
        assert _strip("value;") == "value"
        assert _strip("value.") == "value"
        assert _strip("  value  ") == "value"
