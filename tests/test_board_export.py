"""Tests for the dispatch board export."""
from __future__ import annotations
import re
from unittest.mock import MagicMock, patch
import pytest

# ── Ensure translations are loaded for .format() calls in export functions ──


@pytest.fixture(autouse=True)
def _load_translations():
    """Reload translations after reset_singletons clears them."""
    from services.i18n import load_translations
    load_translations()


class TestBoardExport:
    def test_module_importable(self):
        from ui.dispatch import board_export
        assert board_export is not None

    def test_export_csv_mocked(self, monkeypatch):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName", lambda *a, **kw: ("test.csv", "CSV (*.csv)"))
        try:
            export_csv(MagicMock(), [], MagicMock())
        except Exception:
            pass

    def test_export_csv_with_data(self, monkeypatch):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName", lambda *a, **kw: ("test.csv", "CSV (*.csv)"))
        trips = [
            {"id": 1, "client": "Test", "status": "planned", "truck": "AG01ABC"},
            {"id": 2, "client": "ACME", "status": "in_transit", "truck": "AG02XYZ"},
        ]
        try:
            export_csv(MagicMock(), trips, MagicMock())
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
# New test classes below — do not modify the tests above
# ═══════════════════════════════════════════════════════════════════════


# ── Export fixtures ──────────────────────────────────────────────────


@pytest.fixture
def card_data():
    return [
        {
            "trip_id": "T1", "trip_id_num": 1, "status": "Planned",
            "truck_plate": "AB12CDE", "driver_name": "John",
            "origin": "Bucharest", "destination": "Cluj",
            "departure_date": "2026-07-20", "eta": "2026-07-22", "alerts_count": 0,
        },
        {
            "trip_id": "T2", "trip_id_num": 2, "status": "Loading",
            "truck_plate": "XY99ZZZ", "driver_name": "Jane",
            "origin": "Sibiu", "destination": "Iasi",
            "departure_date": "2026-07-21", "eta": "2026-07-23", "alerts_count": 2,
        },
    ]


@pytest.fixture
def show_toast():
    return MagicMock()


@pytest.fixture
def qt_parent(qtbot):
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    qtbot.addWidget(w)
    yield w
    w.close()


# ═══════════════════════════════════════════════════════════════════════
# TestExportCSV
# ═══════════════════════════════════════════════════════════════════════


class TestExportCSV:
    """CSV export via export_csv()."""

    def test_export_csv_with_data(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.csv", "CSV files (*.csv)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_csv(qt_parent, card_data, show_toast)
            mock_export_cls.return_value.generate_dispatch_board_csv.assert_called_once_with(
                card_data, "/tmp/test.csv",
            )

    def test_export_csv_empty_data_shows_toast(self, show_toast, qt_parent):
        from ui.dispatch.board_export import export_csv
        export_csv(qt_parent, [], show_toast)
        show_toast.assert_called_once()
        args, _ = show_toast.call_args
        assert args[1] == "error"

    def test_export_csv_dialog_cancelled(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("", ""),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_csv(qt_parent, card_data, show_toast)
            mock_export_cls.return_value.generate_dispatch_board_csv.assert_not_called()

    def test_export_csv_service_throws_shows_toast(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.csv", "CSV files (*.csv)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            mock_export_cls.return_value.generate_dispatch_board_csv.side_effect = RuntimeError("IO error")
            export_csv(qt_parent, card_data, show_toast)
            show_toast.assert_called_once()
            args, _ = show_toast.call_args
            assert args[1] == "error"

    def test_export_csv_success_shows_toast(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.csv", "CSV files (*.csv)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            mock_export_cls.return_value.generate_dispatch_board_csv.return_value = "/tmp/test.csv"
            export_csv(qt_parent, card_data, show_toast)
            show_toast.assert_called_once()
            args, _ = show_toast.call_args
            assert args[1] == "success"


# ═══════════════════════════════════════════════════════════════════════
# TestExportPDF
# ═══════════════════════════════════════════════════════════════════════


class TestExportPDF:
    """PDF export via export_pdf()."""

    def test_export_pdf_with_data(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_pdf
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.pdf", "PDF files (*.pdf)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_pdf(qt_parent, card_data, show_toast)
            mock_export_cls.return_value.generate_dispatch_board_pdf.assert_called_once_with(
                card_data, "/tmp/test.pdf",
            )

    def test_export_pdf_empty_data(self, show_toast, qt_parent):
        from ui.dispatch.board_export import export_pdf
        export_pdf(qt_parent, [], show_toast)
        show_toast.assert_called_once()
        args, _ = show_toast.call_args
        assert args[1] == "error"

    def test_export_pdf_dialog_cancelled(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_pdf
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("", ""),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_pdf(qt_parent, card_data, show_toast)
            mock_export_cls.return_value.generate_dispatch_board_pdf.assert_not_called()

    def test_export_pdf_service_throws(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_pdf
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.pdf", "PDF files (*.pdf)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            mock_export_cls.return_value.generate_dispatch_board_pdf.side_effect = RuntimeError("PDF error")
            export_pdf(qt_parent, card_data, show_toast)
            show_toast.assert_called_once()
            args, _ = show_toast.call_args
            assert args[1] == "error"

    def test_export_pdf_success_toast(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_pdf
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.pdf", "PDF files (*.pdf)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            mock_export_cls.return_value.generate_dispatch_board_pdf.return_value = "/tmp/test.pdf"
            export_pdf(qt_parent, card_data, show_toast)
            show_toast.assert_called_once()
            args, _ = show_toast.call_args
            assert args[1] == "success"


# ═══════════════════════════════════════════════════════════════════════
# TestExportServiceIntegration
# ═══════════════════════════════════════════════════════════════════════


class TestExportServiceIntegration:
    """Verifies that ExportService is the single I/O delegate."""

    def test_export_csv_delegates_to_service(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.csv", "CSV files (*.csv)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_csv(qt_parent, card_data, show_toast)
            mock_export_cls.return_value.generate_dispatch_board_csv.assert_called_once()
            assert mock_export_cls.return_value.generate_dispatch_board_pdf.call_count == 0

    def test_export_pdf_delegates_to_service(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_pdf
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.pdf", "PDF files (*.pdf)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_pdf(qt_parent, card_data, show_toast)
            mock_export_cls.return_value.generate_dispatch_board_pdf.assert_called_once()
            assert mock_export_cls.return_value.generate_dispatch_board_csv.call_count == 0

    def test_default_filename_includes_date(self, monkeypatch, show_toast, card_data, qt_parent):
        """Verify the default filename pattern dispatch_board_YYYYMMDD_HHMMSS.{csv,pdf}."""
        from ui.dispatch.board_export import export_csv, export_pdf
        saved_kwargs = []

        def _capture_dialog(*args, **kwargs):
            saved_kwargs.append(kwargs)
            return ("", "")

        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            _capture_dialog,
        )
        # Test CSV default filename
        with patch("ui.dispatch.board_export.ExportService"):
            export_csv(qt_parent, card_data, show_toast)
        assert len(saved_kwargs) >= 1
        default_name = saved_kwargs[0].get("dir", "")
        if not default_name:
            # Some PySide6 versions pass dir as positional arg
            pass
        # Try capturing via the first positional arg pattern instead
        saved_kwargs.clear()
        csv_defaults = []

        def _capture2(*args):
            csv_defaults.append(args[2] if len(args) > 2 else "")
            return ("", "")

        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            _capture2,
        )
        with patch("ui.dispatch.board_export.ExportService"):
            export_csv(qt_parent, card_data, show_toast)
        assert len(csv_defaults) >= 1
        assert re.match(r"dispatch_board_\d{8}_\d{6}\.csv$", csv_defaults[0]), (
            f"Unexpected CSV default filename: {csv_defaults[0]}"
        )

        # Test PDF default filename
        pdf_defaults = []

        def _capture3(*args):
            pdf_defaults.append(args[2] if len(args) > 2 else "")
            return ("", "")

        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            _capture3,
        )
        with patch("ui.dispatch.board_export.ExportService"):
            export_pdf(qt_parent, card_data, show_toast)
        assert len(pdf_defaults) >= 1
        assert re.match(r"dispatch_board_\d{8}_\d{6}\.pdf$", pdf_defaults[0]), (
            f"Unexpected PDF default filename: {pdf_defaults[0]}"
        )


# ═══════════════════════════════════════════════════════════════════════
# TestExportToastMessages
# ═══════════════════════════════════════════════════════════════════════


class TestExportToastMessages:
    """Toast severity and invocation correctness."""

    def test_toast_called_with_correct_severity(self, monkeypatch, card_data, qt_parent):
        from ui.dispatch.board_export import export_csv
        show_toast = MagicMock()
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("/tmp/test.csv", "CSV files (*.csv)"),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_csv(qt_parent, card_data, show_toast)
            show_toast.assert_called_once()
            assert show_toast.call_args[0][1] == "success"

        show_toast.reset_mock()

        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            mock_export_cls.return_value.generate_dispatch_board_csv.side_effect = RuntimeError("fail")
            export_csv(qt_parent, card_data, show_toast)
            show_toast.assert_called_once()
            assert show_toast.call_args[0][1] == "error"

    def test_toast_not_called_on_cancel(self, monkeypatch, show_toast, card_data, qt_parent):
        from ui.dispatch.board_export import export_csv
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **kw: ("", ""),
        )
        with patch("ui.dispatch.board_export.ExportService") as mock_export_cls:
            export_csv(qt_parent, card_data, show_toast)
            show_toast.assert_not_called()
            mock_export_cls.return_value.generate_dispatch_board_csv.assert_not_called()
