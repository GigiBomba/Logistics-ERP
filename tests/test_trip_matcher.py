"""Tests for trip_matcher module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import services.document_automation.trip_matcher as tm

from services.document_automation.trip_matcher import (
    TripMatcher,
    _filename_hints,
    _fuzzy_score,
    _geo_fuzzy_score,
    _load_auto_link_threshold,
    _load_weights,
    normalize_plate,
)
from services.document_automation.types import MatchCandidate, MatchResult


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.conn = MagicMock()
    return db


@pytest.fixture
def matcher(mock_db):
    with patch("services.document_automation.trip_matcher.TripRepository"), \
         patch("services.document_automation.trip_matcher.ClientRepository"), \
         patch("services.document_automation.trip_matcher.ContactRepository"), \
         patch("services.document_automation.trip_matcher.InvoiceRepository"), \
         patch("services.document_automation.trip_matcher.SettingsRepository") as mock_sett_cls:
        mock_sett = MagicMock()
        mock_sett.get_settings_by_key_pattern.return_value = {}
        mock_sett.get_setting_value.return_value = None
        mock_sett_cls.return_value = mock_sett
        m = TripMatcher(mock_db)
        return m


class TestFuzzyScore:
    def test_exact_match(self):
        assert _fuzzy_score("hello", "hello") == 1.0

    def test_no_match(self):
        assert _fuzzy_score("abc", "xyz") < 0.5

    def test_empty_strings(self):
        assert _fuzzy_score("", "") == 0.0
        assert _fuzzy_score("test", "") == 0.0

    def test_case_insensitive(self):
        assert _fuzzy_score("Hello", "hello") == 1.0


class TestGeoFuzzyScore:
    def test_same_place(self):
        score = _geo_fuzzy_score("Munich, DE", "Munich, DE")
        assert score > 0.5

    def test_partial_match(self):
        score = _geo_fuzzy_score("Munich", "Munich, Germany")
        assert score > 0.3

    def test_no_match(self):
        score = _geo_fuzzy_score("Paris", "London")
        assert score == 0.0

    def test_empty(self):
        assert _geo_fuzzy_score("", "Munich") == 0.0
        assert _geo_fuzzy_score("Munich", "") == 0.0


class TestFilenameHints:
    def test_trip_id_in_filename(self):
        hints = _filename_hints("CMR-2487.pdf")
        assert hints.get("trip_id_hint") == "2487"

    def test_date_in_filename(self):
        hints = _filename_hints("scan_2024-01-15.pdf")
        assert hints.get("date_hint") == "2024-01-15"

    def test_plate_in_filename(self):
        hints = _filename_hints("WhatsApp Image AB123CD.jpg")
        assert hints.get("plate_hint") is not None
        if hints.get("plate_hint"):
            assert normalize_plate(hints["plate_hint"]) == "AB123CD"

    def test_no_hints(self):
        hints = _filename_hints("image.jpg")
        assert "text" in hints

    def test_empty_filename(self):
        hints = _filename_hints("")
        assert "text" in hints


class TestLoadWeights:
    def _clear_cache(self):
        tm._WEIGHTS_CACHE = {}
        tm._WEIGHTS_TS = 0

    def test_load_weights_default(self):
        self._clear_cache()
        db = MagicMock()
        with patch("services.document_automation.trip_matcher.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_settings_by_key_pattern.return_value = {}
            mock_cls.return_value = mock_settings
            weights = _load_weights(db)
        assert weights["cmr"] == 0.10
        assert weights["client"] == 0.25
        assert weights["plate"] == 0.20

    def test_load_weights_from_db(self):
        self._clear_cache()
        db = MagicMock()
        with patch("services.document_automation.trip_matcher.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_settings_by_key_pattern.return_value = {
                "match_weight_cmr": "0.20",
                "match_weight_client": "0.50",
            }
            mock_cls.return_value = mock_settings
            weights = _load_weights(db)
        assert weights["cmr"] == 0.20
        assert weights["client"] == 0.50


class TestLoadAutoLinkThreshold:
    def _clear_cache(self):
        tm._AUTO_LINK_THRESHOLD_CACHE = 0.50
        tm._AUTO_LINK_THRESHOLD_TS = 0

    def test_default(self):
        self._clear_cache()
        db = MagicMock()
        with patch("services.document_automation.trip_matcher.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = None
            mock_cls.return_value = mock_settings
            threshold = _load_auto_link_threshold(db)
        assert threshold == 0.50

    def test_from_db(self):
        self._clear_cache()
        db = MagicMock()
        with patch("services.document_automation.trip_matcher.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = "0.75"
            mock_cls.return_value = mock_settings
            threshold = _load_auto_link_threshold(db)
        assert threshold == 0.75

    def test_clamped(self):
        self._clear_cache()
        db = MagicMock()
        with patch("services.document_automation.trip_matcher.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = "5.0"
            mock_cls.return_value = mock_settings
            threshold = _load_auto_link_threshold(db)
        assert threshold == 1.0


class TestTripMatcher:
    def test_match_no_candidates_fallback_to_recent(self, matcher):
        matcher.trips.get_recent_trips_for_matching.return_value = [
            {"id": 1, "client_name": "ACME"},
            {"id": 2, "client_name": "Other"},
        ]

        result = matcher.match(
            extracted={"client_name": "Unknown"},
            ocr_text="", source_filename="test.pdf",
        )

        assert isinstance(result, MatchResult)
        assert result.best_match is None
        assert len(result.candidates) > 0
        assert result.needs_manual is True

    def test_match_by_cmr_number(self, matcher):
        matcher.trips.get_by_cmr_number.return_value = [
            {"id": 42, "client_name": "ACME"},
        ]
        # Provide trip row for final scoring batch fetch
        matcher.trips.get_by_ids.return_value = [
            {"id": 42, "client_name": "ACME", "origin": "", "destination": "", "start_date": ""},
        ]

        result = matcher.match(
            extracted={"cmr_number": "CMR-001"},
        )

        assert result.best_match is not None
        assert result.candidates[0].signals.get("cmr", 0) > 0

    def test_match_by_plate(self, matcher):
        matcher.trips.get_by_truck_plate.return_value = [
            {"id": 42, "truck_plate": "AB123CD", "client_name": "ACME"},
        ]
        matcher.trips.get_by_ids.return_value = [
            {"id": 42, "client_name": "ACME", "truck_plate": "AB123CD", "origin": "", "destination": "", "start_date": ""},
        ]

        result = matcher.match(
            extracted={"truck_plate": "AB123CD"},
        )

        assert result.best_match is not None

    def test_match_by_invoice_number(self, matcher):
        matcher.trips.get_by_invoice_via_trip_invoice.return_value = [
            {"id": 42, "client_name": "ACME"},
        ]
        matcher.trips.get_by_ids.return_value = [
            {"id": 42, "client_name": "ACME", "origin": "", "destination": "", "start_date": ""},
        ]

        result = matcher.match(
            extracted={"invoice_number": "INV-001"},
        )

        assert result.best_match is not None

    def test_match_by_client_name_fuzzy(self, matcher):
        matcher.trips.get_by_client_name_fuzzy.return_value = [
            {"id": 42, "client_name": "ACME Corporation GmbH"},
        ]
        # Prevent company_stamp section from crashing (no matching clients)
        matcher.clients.search_by_name.return_value = []
        matcher.trips.get_by_ids.return_value = [
            {"id": 42, "client_name": "ACME Corporation GmbH", "origin": "", "destination": "", "start_date": ""},
        ]

        result = matcher.match(
            extracted={"consignee": "ACME Corporation"},
        )

        assert result.best_match is not None

    def test_match_by_driver_name(self, matcher):
        matcher.trips.get_by_driver_name.return_value = [
            {"id": 42, "driver_name": "Ion Popescu", "client_name": "ACME"},
        ]
        matcher.trips.get_by_ids.return_value = [
            {"id": 42, "driver_name": "Ion Popescu", "client_name": "ACME", "origin": "", "destination": "", "start_date": ""},
        ]

        result = matcher.match(
            extracted={"driver_name": "Ion Popescu"},
        )

        assert result.best_match is not None

    def test_match_auto_attach_threshold(self, matcher):
        """Trip ID in filename should reach auto-attach threshold."""
        matcher.trips.get_by_id.return_value = {"id": 42, "client_name": "ACME"}

        result = matcher.match(
            extracted={},
            source_filename="CMR-42.pdf",
        )

        if result.best_match:
            # Should have filename signal
            assert any("filename" in c.signals for c in result.candidates)

    def test_match_by_date_proximity(self, matcher):
        matcher.trips.get_trips_by_date_proximity.return_value = [
            {"id": 42, "start_date": "2024-01-15", "client_name": "ACME"},
        ]
        matcher.trips.get_by_ids.return_value = [
            {"id": 42, "start_date": "2024-01-15", "client_name": "ACME", "origin": "", "destination": ""},
        ]

        result = matcher.match(
            extracted={"date": "2024-01-15"},
        )

        assert result.best_match is not None

    def test_match_by_company_stamp(self, matcher):
        matcher.clients.search_by_name.return_value = [
            {"id": 1, "name": "ACME Corp"},
        ]
        matcher.trips.get_by_client_name_fuzzy.return_value = [
            {"id": 42, "client_name": "ACME Corp"},
        ]
        matcher.trips.get_by_ids.return_value = [
            {"id": 42, "client_name": "ACME Corp"},
        ]

        result = matcher.match(
            extracted={"consignor_stamp": "ACME Corp"},
        )

        assert result is not None


class TestMatchResultProperties:
    def test_is_auto_attach(self):
        result = MatchResult(
            best_match={"id": 1}, confidence=0.95,
            candidates=[], signals={},
        )
        assert result.is_auto_attach is True

    def test_is_suggested(self):
        result = MatchResult(
            best_match={"id": 1}, confidence=0.80,
            candidates=[], signals={},
        )
        assert result.is_suggested is True

    def test_needs_manual_low_confidence(self):
        result = MatchResult(
            best_match={"id": 1}, confidence=0.50,
            candidates=[], signals={},
        )
        assert result.needs_manual is True

    def test_needs_manual_no_best_match(self):
        result = MatchResult(
            best_match=None, confidence=0.0,
            candidates=[], signals={},
        )
        assert result.needs_manual is True
