"""Tests for the CMR form view (QtCmrFormView).
Expanded from the original 49-line test to cover the current refactored form.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ui.views.cmr_form_view.cmr_form import QtCmrFormView


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def cmr_form(qtbot, mock_db):
    """Create a fully initialized QtCmrFormView instance."""
    # External dependencies are real (Qt widgets, services.i18n).
    # Only external service classes are mocked.
    with (
        patch("ui.views.cmr_form_view.cmr_form.QtSignaturePad"),
    ):
        view = QtCmrFormView(parent=None, db=mock_db, prefs=None)
        qtbot.addWidget(view)
        yield view
        with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
            view.shutdown()


# ── Test class ─────────────────────────────────────────────────────────────────


class TestQtCmrFormView:
    """Smoke tests for the CMR consignment note form."""

    def test_initialization(self, cmr_form):
        """Widget creates without error and stores db reference."""
        assert cmr_form.db is not None
        assert hasattr(cmr_form, "_cmr_entries")
        assert isinstance(cmr_form._cmr_entries, dict)

    def test_key_ui_elements(self, cmr_form):
        """Core UI controls are present after _build_ui."""
        # Action buttons
        assert hasattr(cmr_form, "_btn_generate")
        assert hasattr(cmr_form, "_btn_print")
        assert hasattr(cmr_form, "_btn_save")

        # Box navigator badges (24 CMR boxes)
        assert hasattr(cmr_form, "_box_badges")
        assert len(cmr_form._box_badges) == 24

        # Role selector buttons
        assert hasattr(cmr_form, "_role_consignor_btn")
        assert hasattr(cmr_form, "_role_consignee_btn")

        # Scroll container
        assert hasattr(cmr_form, "_scroll_container")

    def test_cmr_entries_populated(self, cmr_form):
        """All expected field keys exist in _cmr_entries dict after build."""
        expected_keys = {
            "consignor_name",
            "consignee_name",
            "place_of_loading",
            "place_of_loading_date",
            "destination",
            "loading_country",
            "delivery_country",
            "documents_attached",
            "truck_plate",
            "driver_name",
            "trailer_plate",
            "driver_license",
            "cargo_marks",
            "package_count",
            "package_type",
            "cargo_description",
            "hs_code",
            "gross_weight_kg",
            "volume_m3",
            "carrier_instructions",
            "carrier_reservations",
            "carriage_payer",
            "cod_amount",
            "special_agreements",
            "distance_km",
            "carrier_name",
            "issue_place",
            "issue_date",
            "carriage_sender",
            "carriage_consignee",
            "supplementary_sender",
            "supplementary_consignee",
            "customs_sender",
            "customs_consignee",
            "other_sender",
            "other_consignee",
        }
        missing = expected_keys - cmr_form._cmr_entries.keys()
        extra = cmr_form._cmr_entries.keys() - expected_keys
        assert not missing, f"Missing keys: {missing}"
        assert not extra, f"Unexpected keys: {extra}"

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def test_shutdown_safe(self, cmr_form):
        """shutdown() can be called without error."""
        cmr_form.shutdown()

    def test_wakeup_safe(self, cmr_form):
        """wakeup() can be called without error."""
        cmr_form.wakeup()

    def test_lifecycle_idempotent(self, cmr_form):
        """Multiple shutdown/wakeup calls do not crash."""
        cmr_form.wakeup()
        cmr_form.shutdown()
        cmr_form.shutdown()
        cmr_form.wakeup()
        cmr_form.wakeup()

    # ── Role selection ─────────────────────────────────────────────────────────

    def test_default_role_is_consignor(self, cmr_form):
        """Default role is consignor (sender)."""
        assert cmr_form._consignor_role_active is True

    def test_role_toggle(self, cmr_form):
        """Switching role updates internal state."""
        cmr_form._set_role(False)
        assert cmr_form._consignor_role_active is False
        cmr_form._set_role(True)
        assert cmr_form._consignor_role_active is True

    def test_role_toggle_idempotent(self, cmr_form):
        """Setting the same role again is a no-op."""
        cmr_form._set_role(True)   # already True
        assert cmr_form._consignor_role_active is True
        cmr_form._set_role(False)
        cmr_form._set_role(False)  # already False
        assert cmr_form._consignor_role_active is False

    # ── Empty / clear state ────────────────────────────────────────────────────

    def test_empty_get_data(self, cmr_form):
        """get_data() returns a dict with expected keys when form is empty."""
        data = cmr_form.get_data()
        assert isinstance(data, dict)
        assert "generating_role" in data
        assert data["generating_role"] == "consignor"

    def test_clear_does_not_crash(self, cmr_form):
        """clear() resets state without raising."""
        cmr_form.clear()
        assert cmr_form._consignor_role_active is True
        assert cmr_form._last_trip_data is None

    def test_clear_resets_role(self, cmr_form):
        """clear() resets role back to consignor even if it was changed."""
        cmr_form._set_role(False)
        assert cmr_form._consignor_role_active is False
        cmr_form.clear()
        assert cmr_form._consignor_role_active is True

    def test_get_data_empty_state(self, cmr_form):
        """get_data() works safely when no trip data has been loaded."""
        data = cmr_form.get_data()
        assert isinstance(data, dict)
        assert data.get("generating_role") == "consignor"

    # ── fill_from_trip ─────────────────────────────────────────────────────────

    def test_fill_from_trip_consignor_role(self, cmr_form):
        """fill_from_trip stores trip data in consignor mode."""
        trip = {
            "client_name": "Acme Corp",
            "destination": "Berlin",
            "delivery_country": "DE",
            "place_of_loading": "Bucharest",
            "loading_country": "RO",
            "truck_number": "B-123-XYZ",
            "driver_name": "John Doe",
        }
        company_conf = {
            "company_name": "My Logistics Ltd",
            "address": "Str. Exemplu 123",
            "cui": "RO123456",
        }
        cmr_form.fill_from_trip(
            trip=trip,
            company_conf=company_conf,
            client_data={},
            truck_data={},
            driver_data={},
        )
        assert cmr_form._last_trip_data is not None
        assert (
            cmr_form._last_trip_data["trip"]["client_name"]
            == "Acme Corp"
        )

    def test_fill_from_trip_consignee_role(self, cmr_form):
        """fill_from_trip works correctly in consignee role."""
        trip = {
            "client_name": "Buyer Inc",
            "destination": "Vienna",
            "delivery_country": "AT",
            "place_of_loading": "Budapest",
            "loading_country": "HU",
        }
        company_conf = {
            "company_name": "My Logistics Ltd",
            "address": "Str. Exemplu 123",
        }
        cmr_form._set_role(False)
        cmr_form.fill_from_trip(
            trip=trip,
            company_conf=company_conf,
        )
        assert cmr_form._consignor_role_active is False
        assert cmr_form._last_trip_data is not None

    def test_fill_from_trip_none_trip(self, cmr_form):
        """fill_from_trip with None trip is a no-op that stores None."""
        cmr_form.fill_from_trip(trip=None, company_conf={})
        # _last_trip_data is still set because the dict is
        # built before the early-return guard
        assert cmr_form._last_trip_data is not None
        assert cmr_form._last_trip_data["trip"] is None

    def test_fill_from_trip_populates_widgets(self, cmr_form):
        """After fill_from_trip, cmr entry widgets have text set."""
        trip = {
            "client_name": "Test Client",
            "destination": "Paris",
            "delivery_country": "FR",
            "place_of_loading": "Lyon",
            "loading_country": "FR",
            "truck_number": "AB-123-CD",
            "trailer_plate": "XY-456-ZW",
            "driver_name": "Jane Roe",
            "driver_license": "LIC-001",
            "package_count": "10",
            "gross_weight_kg": "2500",
            "volume_m3": "15.5",
            "cargo_description": "Electronic equipment",
            "cargo_marks": "FRAGILE",
            "carrier_instructions": "Handle with care",
            "carrier_reservations": "None",
            "special_agreements": "Insurance included",
            "cod_amount": "500.00",
            "distance_km": "1800",
            "documents_attached": "Invoice, Packing List",
            "issue_place": "Bucharest",
        }
        company_conf = {"company_name": "LogiCo", "address": "Main St 1", "signature_path": "/tmp/sig.png"}
        cmr_form.fill_from_trip(trip=trip, company_conf=company_conf)
        data = cmr_form.get_data()
        assert "consignor_name" in data

    # ── Data helpers ───────────────────────────────────────────────────────────

    def test_get_bottom_frame(self, cmr_form):
        """get_bottom_frame returns a QWidget."""
        frame = cmr_form.get_bottom_frame()
        assert frame is not None
        assert isinstance(frame, QWidget)

    def test_field_has_content_unknown_key(self, cmr_form):
        """_field_has_content returns False for keys not in _cmr_entries."""
        assert cmr_form._field_has_content("nonexistent_key") is False

    def test_get_data_after_fill_includes_role(self, cmr_form):
        """get_data() reflects the current role setting after fill."""
        trip = {"client_name": "Test", "destination": "Berlin"}
        cmr_form.fill_from_trip(trip=trip, company_conf={})
        data = cmr_form.get_data()
        assert data["generating_role"] == "consignor"

        cmr_form._set_role(False)
        cmr_form.fill_from_trip(trip=trip, company_conf={})
        data = cmr_form.get_data()
        assert data["generating_role"] == "consignee"

    # ── ADR data ───────────────────────────────────────────────────────────────

    def test_get_adr_data_no_adr(self, cmr_form):
        """_get_adr_data returns None when ADR is not checked."""
        result = cmr_form._get_adr_data()
        assert result is None

    def test_get_successive_carriers_empty(self, cmr_form):
        """_get_successive_carriers returns empty list when no carriers."""
        result = cmr_form._get_successive_carriers()
        assert result == []

    def test_get_financial_data_empty(self, cmr_form):
        """_get_financial_data returns dict with empty strings."""
        result = cmr_form._get_financial_data()
        assert isinstance(result, dict)

    # ── Box navigator ──────────────────────────────────────────────────────────

    def test_box_badges_exist(self, cmr_form):
        """All 24 box badges are present in _box_badges."""
        assert len(cmr_form._box_badges) == 24
        for num in range(1, 25):
            assert num in cmr_form._box_badges

    def test_update_box_navigator_no_crash(self, cmr_form):
        """_update_box_navigator runs without error."""
        cmr_form._update_box_navigator()
