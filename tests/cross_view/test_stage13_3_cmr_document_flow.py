"""Tests for CMR document flow across generators view and CMR form.

Stage 13.3 — Document Center / CMR Form / Email Integration.

Tests that trip selection auto-fills the CMR form, CMR generation
registers documents via DocumentService, errors show critical dialogs,
and preview shows the modal.  Uses the same mocking patterns as
``tests/test_generators_view.py``.
"""

from __future__ import annotations
import contextlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget


# ── SP workaround (see test_cmr_form_view.py) ─────────────────────────────────



# ── Mock sub-editor widgets ───────────────────────────────────────────────────
# These are real QWidgets so that layout / parent-ownership code in
# QtGeneratorsView does not crash.  Each quacks like the real editor class.

class _MockInvoiceEditor(QWidget):
    """Quacks like QtInvoiceEditor — accepts wakeup / shutdown calls."""
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
    """Quacks like QtReceiptEditor — accepts wakeup / shutdown calls."""
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
def generators_view(qtbot):
    """Create QtGeneratorsView with all sub-editors and services mocked.

    This fixture is equivalent to the one in ``tests/test_generators_view.py``
    and uses the same mocking strategy — embeded sub-editors are replaced
    with lightweight QWidget stand-ins.
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

    # Suppress MainWindow warmup: replace _create_module so the
    # already-scheduled warmup timer does not crash with a MagicMock
    # during teardown (the timer was set by a previous test that
    # created a MainWindow).
    _warmup_fix = None
    try:
        import ui.main_window as _mw
        _orig_create = _mw.MainWindow._create_module

        def _safe_create(self, key):
            w = QWidget()
            self.app_shell.view_container.addWidget(w)
            return {"frame": w, "obj": w}

        _mw.MainWindow._create_module = _safe_create
        _warmup_fix = (_mw.MainWindow, _orig_create)
    except Exception:
        pass

    from ui.views.generators_view import QtGeneratorsView

    view = QtGeneratorsView(
        parent=None,
        db=MagicMock(),
        prefs=MagicMock(),
        client_service=MagicMock(),
        fleet_service=MagicMock(),
        trip_service=MagicMock(),
        driver_repo=MagicMock(),
    )
    qtbot.addWidget(view)
    yield view

    with contextlib.suppress(Exception):
        view.shutdown()
    for p in patchers:
        p.stop()
    if _warmup_fix is not None:
        cls, orig = _warmup_fix
        try:
            cls._create_module = orig
        except Exception:
            pass


@pytest.fixture
def generators_view_with_cmr(qtbot, generators_view):
    """Pre-build the CMR tab and wire up a mock CMR form view.

    Switches to the CMR tab first so that ``_cmr_form_view``,
    ``_cmr_lang1_combo``, ``_copy_labels``, etc. are constructed.
    The ``fill_from_trip`` method on the CMR form view is replaced
    with a MagicMock that tests can assert against.
    """
    # Build CMR tab content by switching to CMR tab (index 1)
    generators_view._tab_widget.setCurrentIndex(1)
    # Switch back so the tab state is neutral for tests
    generators_view._tab_widget.setCurrentIndex(0)

    # Replace fill_from_trip with a MagicMock for assertion
    generators_view._cmr_form_view.fill_from_trip = MagicMock()

    return generators_view


# =========================================================================
# Tests
# =========================================================================


class TestCmrDocumentFlow:
    """CMR document flow across generators view and CMR form.

    Tests cover the integration points between trip selection,
    CMR auto-fill, CMR generation, error handling, and preview.
    """

    # ── Trip selection auto-fills CMR ───────────────────────────────────

    def test_trip_selection_autofills_cmr(
        self, generators_view_with_cmr,
    ):
        """Selecting a trip in the combo auto-fills the CMR form."""
        view = generators_view_with_cmr

        # Replace the trip service with a fully controlled mock
        mock_trip_svc = MagicMock()

        trips = [
            {"id": 1, "truck_number": "AB-01", "client_name": "Client A",
             "created_at": "2026-06-01T10:00:00"},
        ]
        mock_trip_svc.get_all.return_value = trips

        trip_data = {
            "id": 1, "truck_number": "AB-01", "client_name": "Client A",
            "client_id": 42, "truck_id": 99, "driver_id": 5,
        }
        mock_trip_svc.get_by_id.return_value = trip_data

        # Attach to the view's private instance slot
        view._trip_svc_instance = mock_trip_svc

        # Populate the combo synchronously (WorkerPool.run is async,
        # so we call the result handler directly to avoid timing issues).
        view._on_trips_loaded(trips)
        assert view._trip_combo.count() == 1

        # Mock supporting services so _auto_fill_cmr does not crash
        view._client_svc.get_by_id.return_value = {"name": "Client A"}
        view._fleet_svc.get_truck.return_value = {"plate_number": "AB-01"}
        view._driver_repo.get_by_id.return_value = {"name": "John Doe"}

        # ── Select the trip in the combo ────────────────────────────
        # This triggers currentTextChanged → _on_global_trip_selected
        # → _auto_fill_cmr → _cmr_form_view.fill_from_trip
        with patch(
            "services.invoicing.config_manager.load_company_config",
            return_value={},
        ):
            view._trip_combo.setCurrentIndex(0)

        # Verify fill_from_trip was called with the correct trip data
        view._cmr_form_view.fill_from_trip.assert_called_once()
        args, _ = view._cmr_form_view.fill_from_trip.call_args
        assert isinstance(args[0], dict), (
            "fill_from_trip must receive a trip dict as first positional arg, "
            f"got {type(args[0]).__name__}: {args[0]!r}"
        )
        assert args[0]["id"] == 1
        assert args[0]["truck_number"] == "AB-01"

    # ── CMR generation registers document ──────────────────────────────

    def test_cmr_generation_registers_document(
        self, generators_view_with_cmr,
    ):
        """Successful CMR generation registers the document."""
        view = generators_view_with_cmr
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
        mock_result.data.file_path = "/path/to/cmr_trip_1.pdf"
        mock_result.errors = []

        # Wire a real MagicMock as the document service
        view._cmr_doc_service = MagicMock()

        with patch.object(view, "_collect_cmr_data",
                          return_value=trip_data):
            with patch("services.invoicing.cmr_generator.CMRGenerator"
                       ) as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate.return_value = mock_result
                mock_gen_cls.return_value = mock_gen

                view._generate_cmr()

                view._cmr_doc_service.register_existing \
                    .assert_called_once_with(
                        "/path/to/cmr_trip_1.pdf",
                        title="CMR Trip #1",
                        category="trips",
                        entity_type="trip",
                        entity_id=1,
                        tags=["cmr", "generated"],
                    )

    # ── CMR generation error shows critical dialog ─────────────────────

    def test_cmr_generation_error_shows_critical(
        self, generators_view_with_cmr,
    ):
        """Failed CMR generation calls QMessageBox.critical."""
        view = generators_view_with_cmr
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
        mock_result.errors = [MagicMock(message="PDF generation failed")]

        with patch.object(view, "_collect_cmr_data",
                          return_value=trip_data):
            with patch("services.invoicing.cmr_generator.CMRGenerator"
                       ) as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate.return_value = mock_result
                mock_gen_cls.return_value = mock_gen

                with patch(
                    "ui.views.generators_view.QMessageBox.critical",
                ) as mock_critical:
                    view._generate_cmr()
                    mock_critical.assert_called_once()

    # ── CMR preview shows modal ────────────────────────────────────────

    def test_cmr_preview_shows_modal(
        self, generators_view_with_cmr,
    ):
        """Preview CMR calls _preview_modal with the generated file path."""
        view = generators_view_with_cmr
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
        mock_result.data.file_path = "/path/to/cmr_preview.pdf"
        mock_result.errors = []

        with patch.object(view, "_collect_cmr_data",
                          return_value=trip_data):
            with patch("services.invoicing.cmr_generator.CMRGenerator"
                       ) as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate.return_value = mock_result
                mock_gen_cls.return_value = mock_gen

                with patch(
                    "ui.views.generators_view.os.path.isfile",
                    return_value=True,
                ):
                    with patch.object(
                        view, "_preview_modal",
                    ) as mock_preview:
                        view._preview_cmr()
                        mock_preview.assert_called_once_with(
                            "/path/to/cmr_preview.pdf",
                        )
