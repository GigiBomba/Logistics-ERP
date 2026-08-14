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


class _SyncThread:
    """Thread replacement that runs the target synchronously in start()."""
    def __init__(self, target=None, daemon=False, name=None):
        self._target = target
    def start(self) -> None:
        if self._target:
            self._target()


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


@pytest.fixture
def generators_view_with_trip(qtbot, generators_view):
    """Pre-select a trip in the generators view.

    Switches to the CMR tab first so that CMR components
    (``_cmr_form_view``, ``_cmr_lang1_combo``, ``_copy_labels``, etc.)
    are built before the test runs.
    """
    # Build CMR tab content by switching to CMR tab (index 1)
    generators_view._tab_widget.setCurrentIndex(1)
    # Switch back so the tab state is neutral for tests
    generators_view._tab_widget.setCurrentIndex(0)

    generators_view._trip_combo.setCurrentIndex(0)
    generators_view._trip_combo.currentData = MagicMock(return_value=1)
    generators_view._trip_svc.get_by_id = MagicMock(
        return_value={"id": 1, "truck_number": "AB-01", "client_name": "Client", "route_history_v2_id": 42}
    )
    return generators_view


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
        generators_view._tab_widget.setCurrentIndex(1)  # Build CMR tab
        assert hasattr(generators_view, "_cmr_form_view")
        assert generators_view._cmr_form_view is not None
        assert hasattr(generators_view, "_copy_labels")
        assert len(generators_view._copy_labels) == 4  # Sender, Consignee, Carrier, Administrative

    def test_receipt_tab_contains_editor(self, generators_view):
        """Receipt tab embeds the receipt editor."""
        generators_view._tab_widget.setCurrentIndex(2)  # Build Receipt tab
        assert hasattr(generators_view, "_receipt_editor")
        assert generators_view._receipt_editor is not None

    def test_language_combos_exist(self, generators_view):
        """CMR options card has primary and secondary language combos."""
        generators_view._tab_widget.setCurrentIndex(1)  # Build CMR tab
        assert generators_view._cmr_lang1_combo is not None
        assert generators_view._cmr_lang2_combo is not None

    def test_status_label_exists(self, generators_view):
        """CMR status label is present in copies panel."""
        generators_view._tab_widget.setCurrentIndex(1)  # Build CMR tab
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

    def test_trip_combo_populated(self, generators_view, mock_trip_service, qtbot):
        """_refresh_trip_lists populates the combo from trip_service."""
        trips = [
            {"id": 1, "truck_number": "AB-01-ABC", "client_name": "Client A",
             "created_at": "2026-06-01T10:00:00"},
            {"id": 2, "truck_number": "CD-02-DEF", "client_name": "Client B",
             "created_at": "2026-06-02T12:00:00"},
        ]
        mock_trip_service.get_all.return_value = trips

        # _refresh_trip_lists runs get_all on the WorkerPool (async), so
        # wait for the result signal to deliver the trips before asserting.
        generators_view._refresh_trip_lists()
        qtbot.waitUntil(lambda: generators_view._trip_combo.count() == 2, timeout=3000)

        assert generators_view._trip_combo.count() == 2
        assert len(generators_view._trips_list) == 2

    def test_trip_combo_empty_state(self, generators_view, mock_trip_service):
        """When no trips exist, the combo is empty and no crash."""
        mock_trip_service.get_all.return_value = []
        generators_view._refresh_trip_lists()
        assert generators_view._trip_combo.count() == 0

    # ── CMR copy panel ─────────────────────────────────────────────────

    def test_cmr_copy_labels_built(self, generators_view):
        """All four copy suffixes are present in _copy_labels."""
        generators_view._tab_widget.setCurrentIndex(1)  # Build CMR tab
        for suffix in ("Sender", "Consignee", "Carrier", "Administrative"):
            assert suffix in generators_view._copy_labels
            name_lbl, status_lbl, btn = generators_view._copy_labels[suffix]
            assert name_lbl is not None
            assert status_lbl is not None
            assert btn is not None
            assert btn.isEnabled() is False  # disabled before generation

    def test_update_copy_status_enables_button(self, generators_view):
        """_update_copy_status enables the open button for a given copy."""
        generators_view._tab_widget.setCurrentIndex(1)  # Build CMR tab
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

    def test_wakeup_calls_refresh(self, generators_view, mock_trip_service, qtbot):
        """wakeup triggers trip list refresh."""
        mock_trip_service.get_all.reset_mock()
        generators_view.wakeup()
        # wakeup() schedules refresh on the WorkerPool (async).
        qtbot.waitUntil(lambda: mock_trip_service.get_all.called, timeout=3000)
        mock_trip_service.get_all.assert_called()

    # ── Navigation data ────────────────────────────────────────────────

    def test_handle_nav_data_does_not_crash(self, generators_view):
        """handle_nav_data with trip_id does not crash when list is empty."""
        generators_view.handle_nav_data({"trip_id": 1})

    def test_handle_nav_data_selects_trip(self, generators_view, mock_trip_service, qtbot):
        """handle_nav_data auto-selects the matching trip in the combo."""
        trips = [
            {"id": 5, "truck_number": "TR-01", "client_name": "Client",
             "created_at": "2026-06-01"},
        ]
        mock_trip_service.get_all.return_value = trips
        generators_view._refresh_trip_lists()

        generators_view.handle_nav_data({"trip_id": 5})
        # Wait for QTimer to fire and select the trip
        qtbot.waitUntil(lambda: generators_view._trip_combo.currentData() == 5, timeout=500)

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

    # ── Navigation data (tab parameter) ──────────────────────────────

    def test_handle_nav_data_with_tab_parameter(self, generators_view, qtbot):
        """handle_nav_data with tab parameter switches tab via QTimer."""
        with patch.object(generators_view._tab_widget, 'setCurrentIndex') as mock_set:
            generators_view.handle_nav_data({"tab": 1})
            qtbot.waitUntil(lambda: mock_set.called, timeout=500)
            mock_set.assert_called_once_with(1)

    # ── Trip combo labels ────────────────────────────────────────────

    def test_rebuild_trip_combo_labels_on_translation(self, generators_view, mock_trip_service, qtbot):
        """_rebuild_trip_combo_labels updates combo texts and preserves selection by ID."""
        trips = [
            {"id": 1, "truck_number": "AB-01", "client_name": "Client A",
             "created_at": "2026-06-01T10:00:00"},
        ]
        mock_trip_service.get_all.return_value = trips
        generators_view._refresh_trip_lists()
        qtbot.waitUntil(lambda: generators_view._trip_combo.count() == 1, timeout=3000)
        assert generators_view._trip_combo.count() == 1
        assert generators_view._trip_combo.currentData() == 1
        generators_view._rebuild_trip_combo_labels()
        # Selection preserved by ID after rebuild
        assert generators_view._trip_combo.currentData() == 1

    # ── Translation refresh ──────────────────────────────────────────

    def test_refresh_translations_updates_copy_status_words(self, generators_view):
        """refresh_translations shows 'generated' status for paths in _cmr_last_paths."""
        # Build CMR tab components by switching to it
        generators_view._tab_widget.setCurrentIndex(1)
        generators_view._tab_widget.setCurrentIndex(0)

        generators_view._cmr_last_paths["Sender"] = "/fake/path.pdf"
        generators_view.refresh_translations()
        name_lbl, status_lbl, btn = generators_view._copy_labels["Sender"]
        assert "generated" in status_lbl.text().lower()

    # ── Open actions ─────────────────────────────────────────────────

    def test_open_path_missing_file_does_not_crash(self, generators_view):
        """_open_path with a non-existent file does not crash and does not call os.startfile."""
        # create=True: ``os.startfile`` only exists on Windows — the mock must
        # be creatable on POSIX too (Linux CI), where _open_path must not call it.
        with patch("ui.views.generators_view.os.startfile", create=True) as mock_startfile:
            generators_view._open_path("/nonexistent/file.pdf")
            mock_startfile.assert_not_called()

    def test_open_copy_with_no_path(self, generators_view):
        """_open_copy with a suffix not in _cmr_last_paths does not crash."""
        generators_view._open_copy("Sender")


# =========================================================================
# Tests — CMR Generation
# =========================================================================


class TestCmrGeneration:
    """Suite of tests for CMR generation flow in QtGeneratorsView."""

    # ── Language extraction ──────────────────────────────────────────

    def test_collect_cmr_data_with_language_extraction(self, generators_view_with_trip):
        """_collect_cmr_data extracts language code from '(ro)' suffix in combo text."""
        view = generators_view_with_trip
        # Select an existing item that has a language code in parentheses
        idx = view._cmr_lang1_combo.findText("Română (ro)")
        if idx >= 0:
            view._cmr_lang1_combo.setCurrentIndex(idx)

        result = view._collect_cmr_data()
        assert result is not None
        assert result["cmr_language"] == "ro"

    def test_collect_cmr_data_without_language_suffix(self, generators_view_with_trip):
        """_collect_cmr_data uses full combo text when no '(code)' suffix present."""
        view = generators_view_with_trip
        # Add an item without any parenthesis suffix and select it
        view._cmr_lang1_combo.addItem("English")
        view._cmr_lang1_combo.setCurrentIndex(view._cmr_lang1_combo.count() - 1)

        result = view._collect_cmr_data()
        assert result is not None
        assert result["cmr_language"] == "English"

    # ── Generation flows ─────────────────────────────────────────────

    def test_generate_cmr_success_flow(self, generators_view_with_trip):
        """_generate_cmr on success hides progress bar and updates copy status."""
        view = generators_view_with_trip
        trip_data = {
            "trip_id": 1,
            "cmr_language": "ro",
            "generating_role": "consignor",
            "consignor_name": "Sender Inc",
            "consignor_address": "123 Main St",
            "carrier_name": "Carrier Inc",
            "carrier_license": "LIC-123",
            "carrier_instructions": "",
        }

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data.file_path = "/path/to/cmr.pdf"
        mock_result.errors = []

        view._cmr_doc_service = MagicMock()

        with patch.object(view, "_collect_cmr_data", return_value=trip_data):
            with patch("services.invoicing.cmr_generator.CMRGenerator") as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate.return_value = mock_result
                mock_gen_cls.return_value = mock_gen

                view._generate_cmr()

                # Progress bar hidden after success
                assert view._cmr_progress_bar.isVisible() is False
                # Status label updated
                assert view._cmr_status_lbl.text() != ""
                # Copy status updated for the generated copy
                _, _, btn = view._copy_labels["Sender"]
                assert btn.isEnabled() is True

    def test_generate_cmr_failure_shows_error(self, generators_view_with_trip):
        """_generate_cmr on failure calls QMessageBox.critical and hides progress bar."""
        view = generators_view_with_trip
        trip_data = {
            "trip_id": 1,
            "cmr_language": "ro",
            "generating_role": "consignor",
            "consignor_name": "",
            "consignor_address": "",
            "carrier_name": "",
            "carrier_license": "",
            "carrier_instructions": "",
        }

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = [MagicMock(message="Generation failed")]

        with patch.object(view, "_collect_cmr_data", return_value=trip_data):
            with patch("services.invoicing.cmr_generator.CMRGenerator") as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate.return_value = mock_result
                mock_gen_cls.return_value = mock_gen

                with patch("ui.views.generators_view.QMessageBox.critical") as mock_critical:
                    view._generate_cmr()
                    mock_critical.assert_called_once()
                    assert view._cmr_progress_bar.isVisible() is False

    def test_preview_cmr_shows_modal(self, generators_view_with_trip):
        """_preview_cmr calls _preview_modal with the generated file path."""
        view = generators_view_with_trip
        trip_data = {
            "trip_id": 1,
            "cmr_language": "ro",
            "generating_role": "consignor",
            "consignor_name": "",
            "consignor_address": "",
            "carrier_name": "",
            "carrier_license": "",
            "carrier_instructions": "",
        }

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data.file_path = "/path/to/cmr.pdf"
        mock_result.errors = []

        with patch.object(view, "_collect_cmr_data", return_value=trip_data):
            with patch("services.invoicing.cmr_generator.CMRGenerator") as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate.return_value = mock_result
                mock_gen_cls.return_value = mock_gen

                with patch("ui.views.generators_view.os.path.isfile", return_value=True):
                    with patch.object(view, "_preview_modal") as mock_preview:
                        view._preview_cmr()
                        mock_preview.assert_called_once_with("/path/to/cmr.pdf")
                        assert view._cmr_progress_bar.isVisible() is False

    def test_generate_all_copies_thread_flow(self, generators_view_with_trip, qtbot):
        """_generate_all_copies runs thread, updates status, and enables copy buttons."""
        view = generators_view_with_trip
        trip_data = {
            "trip_id": 1,
            "cmr_language": "ro",
            "generating_role": "consignor",
            "consignor_name": "",
            "consignor_address": "",
            "carrier_name": "",
            "carrier_license": "",
            "carrier_instructions": "",
        }

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data.cmr_number = "CMR-001"
        mock_result.errors = []

        with patch.object(view, "_collect_cmr_data", return_value=trip_data):
            with patch("services.invoicing.cmr_generator.CMRGenerator") as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate_all_copies.return_value = mock_result
                mock_gen_cls.return_value = mock_gen

                with patch("ui.views.generators_view.threading.Thread", _SyncThread):
                    with patch("ui.views.generators_view.QTimer.singleShot") as mock_timer:
                        mock_timer.side_effect = lambda delay, cb: cb()
                        with patch("ui.views.generators_view.os.path.isfile", return_value=True):
                            view._cmr_doc_service = MagicMock()
                            view._generate_all_copies()

                            # Status label shows success text
                            assert view._cmr_status_lbl is not None
                            assert view._cmr_status_lbl.text() != ""
                            # Progress bar hidden
                            assert view._cmr_progress_bar.isVisible() is False
                            # All copy buttons enabled
                            for suffix in ("Sender", "Consignee", "Carrier", "Administrative"):
                                _, _, btn = view._copy_labels[suffix]
                                assert btn.isEnabled() is True

    # ── Route stops ──────────────────────────────────────────────────

    def test_fill_stops_from_route(self, generators_view_with_trip):
        """_fill_stops_from_route populates place_of_loading and destination from route data."""
        view = generators_view_with_trip
        view._trip_svc.get_route_stops_json = MagicMock(
            return_value='[{"address": "Origin"}, {"address": "Dest"}]'
        )

        view._cmr_form_view._cmr_entries = {
            "place_of_loading": MagicMock(),
            "destination": MagicMock(),
        }

        with patch(
            "ui.views.generators_view.RouteService.parse_route_stops",
            return_value=("Origin City", "Dest City"),
        ):
            view._fill_stops_from_route(1)

            view._cmr_form_view._cmr_entries["place_of_loading"].setText.assert_called_once_with("Origin City")
            view._cmr_form_view._cmr_entries["destination"].setText.assert_called_once_with("Dest City")
