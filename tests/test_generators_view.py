"""Tests for QtGeneratorsView — unified Invoice + CMR document generation UI.

This file replaces the earlier test that targeted the old button-based API.
The current view uses a QTabWidget with embedded sub-editors and a persistent
trip selector.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget, QWidget


# Helper widgets that look like the real sub-editors to the layout system
# (they are real QWidgets) while accepting method calls like ``wakeup()``.
class _MockInvoiceEditor(QWidget):
    """Quacks like QtInvoiceEditor — accepts wakeup calls."""
    def wakeup(self) -> None:
        pass
    def shutdown(self) -> None:
        pass

class _MockCmrFormView(QWidget):
    """Quacks like QtCmrFormView — accepts get_data / fill_from_trip."""
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._cmr_entries: dict = {}
    def get_data(self) -> dict:
        return {}
    def fill_from_trip(self, *args, **kwargs) -> None:
        pass

class _MockReceiptEditor(QWidget):
    """Quacks like QtReceiptEditor — accepts wakeup calls."""
    def wakeup(self) -> None:
        pass
    def shutdown(self) -> None:
        pass

class _MockProformaEditor(QWidget):
    """Quacks like QtProformaEditor."""
    pass


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_prefs():
    prefs = MagicMock()
    prefs.get_available_languages.return_value = ["en", "ro", "fr"]
    prefs.get_language_display_name.side_effect = (
        lambda c: {"en": "English", "ro": "Română", "fr": "Français"}.get(c, c)
    )
    return prefs


@pytest.fixture
def mock_trip_service():
    svc = MagicMock()
    svc.get_all.return_value = []
    return svc


@pytest.fixture
def mock_client_service():
    return MagicMock()


@pytest.fixture
def mock_fleet_service():
    return MagicMock()


@pytest.fixture
def mock_driver_repo():
    return MagicMock()


@pytest.fixture
def mock_services(
    mock_db, mock_prefs, mock_trip_service,
    mock_client_service, mock_fleet_service, mock_driver_repo,
):
    return {
        "db": mock_db,
        "prefs": mock_prefs,
        "trip_service": mock_trip_service,
        "client_service": mock_client_service,
        "fleet_service": mock_fleet_service,
        "driver_repo": mock_driver_repo,
    }


@pytest.fixture
def generators_view(qtbot, mock_services):
    """Create QtGeneratorsView with all sub-editors and services mocked.

    We patch all embedded sub-views (QtInvoiceEditor, QtCmrFormView,
    QtReceiptEditor, QtProformaEditor) with MagicMock instances that
    accept arbitrary attribute access (e.g. ``wakeup()`` is called during
    initial tab construction via the ``currentChanged`` signal).
    """
    patchers = [
        patch("ui.views.generators_view.QtInvoiceEditor",
              return_value=_MockInvoiceEditor()),
        patch("ui.views.generators_view.QtCmrFormView",
              return_value=_MockCmrFormView()),
        patch("ui.views.generators_view.QtReceiptEditor",
              return_value=_MockReceiptEditor()),
        # QtProformaEditor is imported inside _build_proforma_tab, so
        # we patch the source module rather than generators_view's ref.
        patch("ui.views.proforma_editor.QtProformaEditor",
              return_value=_MockProformaEditor()),
    ]
    for p in patchers:
        p.start()

    from ui.views.generators_view import QtGeneratorsView

    view = QtGeneratorsView(
        parent=None,
        db=mock_services["db"],
        prefs=mock_services["prefs"],
        client_service=mock_services["client_service"],
        fleet_service=mock_services["fleet_service"],
        trip_service=mock_services["trip_service"],
        driver_repo=mock_services["driver_repo"],
    )
    qtbot.addWidget(view)
    yield view

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================


class TestQtGeneratorsView:
    """Suite of tests for the QtGeneratorsView."""

    # ── Initialisation ─────────────────────────────────────────────────

    def test_initialization(self, generators_view):
        """Widget constructs without crashing and stores references."""
        assert generators_view is not None
        assert generators_view.db is not None
        assert generators_view.prefs is not None

    def test_header_built(self, generators_view):
        """Header section renders with title and trip selector."""
        assert hasattr(generators_view, "_trip_combo")
        assert generators_view._trip_combo is not None
        # Trip combo should exist as a QComboBox-like widget
        assert generators_view._trip_combo is not None

    def test_tab_widget_has_four_tabs(self, generators_view):
        """QTabWidget contains Invoice, CMR, Receipt, and Proforma tabs."""
        assert hasattr(generators_view, "_tab_widget")
        tw: QTabWidget = generators_view._tab_widget
        assert tw.count() == 4

    def test_invoice_tab_contains_editor(self, generators_view):
        """Invoice tab embeds the invoice editor widget."""
        assert hasattr(generators_view, "_full_invoice_editor")
        assert generators_view._full_invoice_editor is not None

    def test_cmr_tab_contains_form_view(self, generators_view):
        """CMR tab has a form view and right panel with copies."""
        assert hasattr(generators_view, "_cmr_form_view")
        assert generators_view._cmr_form_view is not None
        assert hasattr(generators_view, "_copy_labels")
        assert len(generators_view._copy_labels) == 4  # Sender, Consignee, Carrier, Administrative

    def test_receipt_tab_contains_editor(self, generators_view):
        """Receipt tab embeds the receipt editor."""
        assert hasattr(generators_view, "_receipt_editor")
        assert generators_view._receipt_editor is not None

    def test_language_combos_exist(self, generators_view):
        """CMR options card has primary and secondary language combos."""
        assert generators_view._cmr_lang1_combo is not None
        assert generators_view._cmr_lang2_combo is not None

    def test_status_label_exists(self, generators_view):
        """CMR status label is present in copies panel."""
        assert generators_view._cmr_status_lbl is not None

    # ── Tab switching ──────────────────────────────────────────────────

    def test_tab_switch_sets_built_flags(self, generators_view):
        """Switching tabs sets the lazy-init flags.

        Note: ``_on_tab_changed(0)`` fires during QTabWidget construction
        (when the first tab is added), so ``_invoice_built`` starts as
        ``True``.  The CMR and Receipt flags are ``False`` until visited.
        """
        assert generators_view._invoice_built is True
        assert generators_view._cmr_built is False
        assert generators_view._receipt_built is False

        tw = generators_view._tab_widget

        # Switch to CMR tab (index 1)
        tw.setCurrentIndex(1)
        assert generators_view._cmr_built is True

        # Switch to Receipt tab (index 2)
        tw.setCurrentIndex(2)
        assert generators_view._receipt_built is True

    # ── Trip combo ─────────────────────────────────────────────────────

    def test_trip_combo_populated(self, generators_view, mock_trip_service):
        """_refresh_trip_lists populates the combo from trip_service."""
        trips = [
            {"id": 1, "truck_number": "AB-01-ABC", "client_name": "Client A",
             "created_at": "2026-06-01T10:00:00"},
            {"id": 2, "truck_number": "CD-02-DEF", "client_name": "Client B",
             "created_at": "2026-06-02T12:00:00"},
        ]
        mock_trip_service.get_all.return_value = trips

        generators_view._refresh_trip_lists()

        assert generators_view._trip_combo.count() == 2
        assert generators_view._trip_map != {}

    def test_trip_combo_empty_state(self, generators_view, mock_trip_service):
        """When no trips exist, the combo is empty and no crash."""
        mock_trip_service.get_all.return_value = []
        generators_view._refresh_trip_lists()
        assert generators_view._trip_combo.count() == 0

    # ── CMR copy panel ─────────────────────────────────────────────────

    def test_cmr_copy_labels_built(self, generators_view):
        """All four copy suffixes are present in _copy_labels."""
        for suffix in ("Sender", "Consignee", "Carrier", "Administrative"):
            assert suffix in generators_view._copy_labels
            name_lbl, status_lbl, btn = generators_view._copy_labels[suffix]
            assert name_lbl is not None
            assert status_lbl is not None
            assert btn is not None
            assert btn.isEnabled() is False  # disabled before generation

    def test_update_copy_status_enables_button(self, generators_view):
        """_update_copy_status enables the open button for a given copy."""
        generators_view._update_copy_status("Sender", "/fake/path.pdf")
        name_lbl, status_lbl, btn = generators_view._copy_labels["Sender"]
        assert btn.isEnabled() is True

    # ── i18n ───────────────────────────────────────────────────────────

    def test_refresh_translations_does_not_crash(self, generators_view):
        """refresh_translations can be called safely."""
        generators_view.refresh_translations()

    def test_language_callback_registered(self, generators_view):
        """Language-change callback is registered on init."""
        assert generators_view._listener_registered is True
        assert generators_view._language_callback is not None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def test_shutdown_unregisters_listener(self, generators_view):
        """shutdown removes the i18n listener."""
        generators_view.shutdown()
        assert generators_view._listener_registered is False

    def test_wakeup_does_not_crash(self, generators_view):
        """wakeup() refreshes trip lists and re-registers listener."""
        generators_view.shutdown()
        generators_view.wakeup()
        assert generators_view._listener_registered is True

    def test_wakeup_calls_refresh(self, generators_view, mock_trip_service):
        """wakeup triggers trip list refresh."""
        mock_trip_service.get_all.reset_mock()
        generators_view.wakeup()
        mock_trip_service.get_all.assert_called()

    # ── Navigation data ────────────────────────────────────────────────

    def test_handle_nav_data_does_not_crash(self, generators_view):
        """handle_nav_data with trip_id does not crash when list is empty."""
        generators_view.handle_nav_data({"trip_id": 1})

    def test_handle_nav_data_selects_trip(self, generators_view, mock_trip_service):
        """handle_nav_data auto-selects the matching trip in the combo."""
        trips = [
            {"id": 5, "truck_number": "TR-01", "client_name": "Client",
             "created_at": "2026-06-01"},
        ]
        mock_trip_service.get_all.return_value = trips
        generators_view._refresh_trip_lists()

        generators_view.handle_nav_data({"trip_id": 5})
        # The combo should eventually show the matching label
        label = next(lab for lab, tid in generators_view._trip_map.items() if tid == 5)
        assert generators_view._trip_combo.currentText() == label

    # ── Auto-fill (defensive) ──────────────────────────────────────────

    def test_auto_fill_cmr_no_db(self, generators_view):
        """_auto_fill_cmr returns early when db is None."""
        generators_view.db = None
        generators_view._auto_fill_cmr({"id": 1})  # should not crash

    def test_auto_fill_cmr_duplicate_trip(self, generators_view):
        """_auto_fill_cmr skips if trip already filled."""
        generators_view._cmr_filled_trip_id = 1
        generators_view._auto_fill_cmr({"id": 1})  # should not crash or re-fill

    def test_auto_fill_receipt_no_db(self, generators_view):
        """_auto_fill_receipt returns early when db is None."""
        generators_view.db = None
        generators_view._auto_fill_receipt({"id": 1})  # should not crash

    # ── Collect CMR data ───────────────────────────────────────────────

    def test_collect_cmr_data_no_trip_selected(self, generators_view):
        """_collect_cmr_data returns None when no trip is selected."""
        result = generators_view._collect_cmr_data()
        assert result is None
