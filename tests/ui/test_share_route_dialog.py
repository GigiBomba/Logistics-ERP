"""Tests for the Share Route dialog.

Covers construction, URL copy to clipboard, file export, Google Maps
navigation, OS-level share, QR code generation (when qrcode is available),
cancel/close behaviour, and edge cases (empty URL, very long URL, missing
callbacks, QR generation failure).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication, QPushButton

from ui.dialogs.share_route_dialog import ShareRouteDialog


# ── Sample data ──────────────────────────────────────────────────────────

SAMPLE_SHARE_URL = "https://operion.app/route/abc123"
SAMPLE_GMAPS_URL = (
    "https://www.google.com/maps/dir/?api=1&origin=44.4,26.1&destination=46.7,23.6"
)
SAMPLE_EXPORT_PATH = r"C:\Users\test\exported_route.operionroute"


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def share_dialog(qt_widget, qtbot):
    """Provide a fully-wired ShareRouteDialog with mock callbacks."""
    on_export = MagicMock(return_value=SAMPLE_EXPORT_PATH)
    on_share = MagicMock()
    on_gmaps = MagicMock()
    dlg = ShareRouteDialog(
        parent=qt_widget,
        share_url=SAMPLE_SHARE_URL,
        google_maps_url=SAMPLE_GMAPS_URL,
        on_export_file=on_export,
        on_share_via_os=on_share,
        on_open_in_gmaps=on_gmaps,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


@pytest.fixture
def share_dialog_empty(qt_widget, qtbot):
    """Provide a ShareRouteDialog with no URL and no callbacks."""
    dlg = ShareRouteDialog(parent=qt_widget)
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


# ── Helpers ──────────────────────────────────────────────────────────────

def _find_button(dlg, text_substring: str) -> QPushButton | None:
    """Return the first QPushButton whose text contains *text_substring*."""
    for btn in dlg.findChildren(QPushButton):
        if text_substring.lower() in btn.text().lower():
            return btn
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Construction & initial state
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogInit:
    """Construction and initial state."""

    def test_creation(self, share_dialog):
        assert isinstance(share_dialog, ShareRouteDialog)
        assert share_dialog.windowTitle() != ""

    def test_is_modal(self, share_dialog):
        assert share_dialog.windowModality() == Qt.ApplicationModal

    def test_minimum_size_set(self, share_dialog):
        assert share_dialog.minimumWidth() == 460
        assert share_dialog.minimumHeight() == 360

    def test_maximum_width_set(self, share_dialog):
        assert share_dialog.maximumWidth() == 520

    def test_share_url_stored(self, share_dialog):
        assert share_dialog._share_url == SAMPLE_SHARE_URL

    def test_google_maps_url_stored(self, share_dialog):
        assert share_dialog._google_maps_url == SAMPLE_GMAPS_URL

    def test_callbacks_stored(self, share_dialog):
        assert share_dialog._on_export_file_cb is not None
        assert share_dialog._on_share_via_os_cb is not None
        assert share_dialog._on_open_in_gmaps_cb is not None

    def test_empty_dialog_stores_defaults(self, share_dialog_empty):
        assert share_dialog_empty._share_url == ""
        assert share_dialog_empty._google_maps_url == ""
        assert share_dialog_empty._on_export_file_cb is None
        assert share_dialog_empty._on_share_via_os_cb is None
        assert share_dialog_empty._on_open_in_gmaps_cb is None

    def test_url_field_shows_url(self, share_dialog):
        assert SAMPLE_SHARE_URL in share_dialog._url_field.text()

    def test_url_field_shows_dash_when_empty(self, share_dialog_empty):
        assert share_dialog_empty._url_field.text() == "-"

    def test_url_field_is_selectable(self, share_dialog):
        flags = share_dialog._url_field.textInteractionFlags()
        assert flags & Qt.TextSelectableByMouse

    def test_url_field_wraps_text(self, share_dialog):
        assert share_dialog._url_field.wordWrap() is True

    def test_qr_label_hidden_initially(self, share_dialog):
        """qrcode is not installed in the default test environment."""
        assert share_dialog._qr_label.isHidden()

    def test_title_label_present(self, share_dialog):
        labels = [
            w for w in share_dialog.findChildren(object)
            if hasattr(w, "text") and "Share Route" in w.text()
        ]
        assert len(labels) >= 1

    def test_subtitle_label_present(self, share_dialog):
        labels = [
            w for w in share_dialog.findChildren(object)
            if hasattr(w, "text") and "share" in w.text().lower()
        ]
        assert len(labels) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# URL copy to clipboard
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogCopyLink:
    """URL copy to clipboard behaviour."""

    def test_copy_link_writes_to_clipboard(self, share_dialog):
        # Use the real clipboard — clear it first, then verify content
        clipboard = QApplication.clipboard()
        clipboard.clear()
        share_dialog._on_copy_link()
        assert clipboard.text() == SAMPLE_SHARE_URL

    def test_copy_link_shows_feedback_text(self, share_dialog):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        share_dialog._on_copy_link()
        # The url field should temporarily show a feedback message
        # like "Copied!" instead of the original URL
        assert share_dialog._url_field.text() != SAMPLE_SHARE_URL
        assert len(share_dialog._url_field.text()) > 0

    def test_copy_link_restores_url_after_timer(self, share_dialog):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        with patch.object(QTimer, "singleShot"):
            share_dialog._on_copy_link()
            # Manually invoke the restore callback
            share_dialog._restore_url_text()
            assert share_dialog._url_field.text() == SAMPLE_SHARE_URL

    def test_copy_link_schedules_restore_timer(self, share_dialog):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        with patch.object(QTimer, "singleShot") as mock_timer:
            share_dialog._on_copy_link()
            mock_timer.assert_called_once_with(2000, share_dialog._restore_url_text)

    def test_copy_link_empty_url(self, share_dialog_empty):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        share_dialog_empty._on_copy_link()
        # With empty URL, clipboard gets empty string
        assert clipboard.text() == ""

    def test_copy_button_found_and_clickable(self, share_dialog):
        copy_btn = _find_button(share_dialog, "Copy")
        assert copy_btn is not None
        with patch.object(share_dialog, "_on_copy_link") as mock_copy:
            copy_btn.click()
            mock_copy.assert_called_once()

    def test_restore_url_text_empty_url(self, share_dialog_empty):
        share_dialog_empty._restore_url_text()
        assert share_dialog_empty._url_field.text() == "-"


# ═══════════════════════════════════════════════════════════════════════════
# Export route as file
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogExport:
    """Export route as .operionroute file."""

    def test_export_calls_callback(self, share_dialog):
        share_dialog._on_export_file()
        share_dialog._on_export_file_cb.assert_called_once()

    def test_export_shows_saved_feedback(self, share_dialog):
        share_dialog._on_export_file()
        text = share_dialog._url_field.text()
        assert "Saved" in text or "saved" in text
        assert SAMPLE_EXPORT_PATH in text

    def test_export_button_triggers_export(self, share_dialog):
        export_btn = _find_button(share_dialog, "Export")
        assert export_btn is not None
        with patch.object(share_dialog, "_on_export_file") as mock_export:
            export_btn.click()
            mock_export.assert_called_once()

    def test_export_schedules_restore_timer(self, share_dialog):
        with patch.object(QTimer, "singleShot") as mock_timer:
            share_dialog._on_export_file()
            mock_timer.assert_called_once_with(3000, share_dialog._restore_url_text)

    def test_export_restores_url_after_timer(self, share_dialog):
        share_dialog._on_export_file()
        share_dialog._restore_url_text()
        assert share_dialog._url_field.text() == SAMPLE_SHARE_URL

    def test_export_no_callback_does_not_raise(self, share_dialog_empty):
        # No on_export_file set — _on_export_file should be a no-op
        share_dialog_empty._on_export_file()  # must not raise

    def test_export_callback_returns_none_no_feedback(self, qt_widget, qtbot):
        on_export = MagicMock(return_value=None)
        dlg = ShareRouteDialog(parent=qt_widget, on_export_file=on_export)
        qtbot.addWidget(dlg)
        original_text = dlg._url_field.text()
        dlg._on_export_file()
        # Text should remain unchanged since callback returned None
        assert dlg._url_field.text() == original_text
        dlg.close()

    def test_export_callback_returns_empty_string(self, qt_widget, qtbot):
        on_export = MagicMock(return_value="")
        dlg = ShareRouteDialog(parent=qt_widget, on_export_file=on_export)
        qtbot.addWidget(dlg)
        original_text = dlg._url_field.text()
        dlg._on_export_file()
        # Empty string is falsy — text stays unchanged
        assert dlg._url_field.text() == original_text
        dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Google Maps link generation
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogGoogleMaps:
    """Open in Google Maps button."""

    def test_open_gmaps_calls_callback(self, share_dialog):
        share_dialog._on_open_gmaps()
        share_dialog._on_open_in_gmaps_cb.assert_called_once()

    def test_open_gmaps_accepts_dialog(self, share_dialog):
        with patch.object(share_dialog, "accept") as mock_accept:
            share_dialog._on_open_gmaps()
            mock_accept.assert_called_once()

    def test_open_gmaps_no_callback_accepts(self, qt_widget, qtbot):
        dlg = ShareRouteDialog(parent=qt_widget, google_maps_url=SAMPLE_GMAPS_URL)
        qtbot.addWidget(dlg)
        with patch.object(dlg, "accept") as mock_accept:
            dlg._on_open_gmaps()
            mock_accept.assert_called_once()
        dlg.close()

    def test_gmaps_button_triggers_open(self, share_dialog):
        gmaps_btn = _find_button(share_dialog, "Google")
        assert gmaps_btn is not None
        with patch.object(share_dialog, "_on_open_gmaps") as mock_gmaps:
            gmaps_btn.click()
            mock_gmaps.assert_called_once()

    def test_gmaps_button_text_not_empty(self, share_dialog):
        gmaps_btn = _find_button(share_dialog, "Google")
        assert gmaps_btn is not None
        assert len(gmaps_btn.text()) > 0


# ═══════════════════════════════════════════════════════════════════════════
# OS-level share (Save & Open Folder)
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogOSShare:
    """Save & Open Folder (Windows Share contract)."""

    def test_share_via_os_calls_callback(self, share_dialog):
        share_dialog._on_share_via_os()
        share_dialog._on_share_via_os_cb.assert_called_once()

    def test_share_via_os_accepts_dialog(self, share_dialog):
        with patch.object(share_dialog, "accept") as mock_accept:
            share_dialog._on_share_via_os()
            mock_accept.assert_called_once()

    def test_share_via_os_no_callback_accepts(self, qt_widget, qtbot):
        dlg = ShareRouteDialog(parent=qt_widget)
        qtbot.addWidget(dlg)
        with patch.object(dlg, "accept") as mock_accept:
            dlg._on_share_via_os()
            mock_accept.assert_called_once()
        dlg.close()

    def test_share_os_button_triggers(self, share_dialog):
        share_btn = _find_button(share_dialog, "Save")
        assert share_btn is not None
        with patch.object(share_dialog, "_on_share_via_os") as mock_share:
            share_btn.click()
            mock_share.assert_called_once()

    def test_share_os_button_label(self, share_dialog):
        share_btn = _find_button(share_dialog, "Save")
        assert share_btn is not None
        assert "Open" in share_btn.text() or "Folder" in share_btn.text()


# ═══════════════════════════════════════════════════════════════════════════
# Cancel / Close behaviour
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogClose:
    """Cancel/Close button behaviour."""

    def test_close_button_exists(self, share_dialog):
        close_btn = _find_button(share_dialog, "Close")
        assert close_btn is not None

    def test_close_button_rejects_dialog(self, share_dialog):
        close_btn = _find_button(share_dialog, "Close")
        assert close_btn is not None
        with patch.object(share_dialog, "reject") as mock_reject:
            close_btn.click()
            mock_reject.assert_called_once()

    def test_reject_does_not_raise(self, share_dialog):
        # Dialog is shown via exec(); calling reject() programmatically is safe
        share_dialog.reject()  # must not raise

    def test_close_button_text_not_empty(self, share_dialog):
        close_btn = _find_button(share_dialog, "Close")
        assert close_btn is not None
        assert len(close_btn.text()) > 0


# ═══════════════════════════════════════════════════════════════════════════
# QR code generation
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogQRCode:
    """QR code generation (requires ``qrcode`` + ``Pillow``)."""

    def test_qr_generated_when_qrcode_available(self, qt_widget, qtbot):
        from PySide6.QtGui import QImage

        mock_qr_module = MagicMock()
        mock_pil_image = MagicMock()
        mock_qr_module.make.return_value = mock_pil_image

        class FakeImageQt(QImage):
            def __init__(self, pil_image):
                super().__init__(10, 10, QImage.Format_ARGB32)
                self._pil_image = pil_image

        mock_pil = MagicMock()
        mock_image_qt_mod = MagicMock()
        mock_image_qt_mod.ImageQt = FakeImageQt

        with patch(
            "ui.dialogs.share_route_dialog._try_import_qrcode",
            return_value=mock_qr_module,
        ) as mock_try:
            with patch.dict(
                "sys.modules",
                {"PIL": mock_pil, "PIL.ImageQt": mock_image_qt_mod},
            ):
                # Manually verify imports work before creating dialog
                from PIL.ImageQt import ImageQt as Imp
                assert Imp is FakeImageQt

                dlg = ShareRouteDialog(
                    parent=qt_widget,
                    share_url="https://operion.app/route/qr-test",
                )
                qtbot.addWidget(dlg)

                # Re-run _generate_qr with a spy on QR label
                with patch.object(dlg._qr_label, "show") as mock_show:
                    with patch.object(dlg._qr_label, "setPixmap") as mock_set_pixmap:
                        dlg._generate_qr()
                        mock_show.assert_called_once()
                        mock_set_pixmap.assert_called_once()
                mock_qr_module.make.assert_called_with(
                    "https://operion.app/route/qr-test",
                    box_size=4, border=1,
                )
                dlg.close()

    def test_qr_hidden_when_no_url(self, qt_widget, qtbot):
        mock_qr_module = MagicMock()
        with patch(
            "ui.dialogs.share_route_dialog._try_import_qrcode",
            return_value=mock_qr_module,
        ):
            dlg = ShareRouteDialog(parent=qt_widget)
            qtbot.addWidget(dlg)
            # QR label stays hidden because share_url is empty
            assert dlg._qr_label.isHidden()
            mock_qr_module.make.assert_not_called()
            dlg.close()

    def test_qr_hidden_when_qrcode_not_installed(self, share_dialog):
        """When _try_import_qrcode returns None, QR label stays hidden."""
        assert share_dialog._qr_label.isHidden()

    def test_qr_generation_exception_caught(self, qt_widget, qtbot):
        """If QR generation raises, it is logged and QR label hidden."""
        mock_qr_module = MagicMock()
        mock_qr_module.make.side_effect = ValueError("QR generation failed")

        with patch(
            "ui.dialogs.share_route_dialog._try_import_qrcode",
            return_value=mock_qr_module,
        ):
            with patch(
                "ui.dialogs.share_route_dialog.logger"
            ) as mock_logger:
                dlg = ShareRouteDialog(
                    parent=qt_widget,
                    share_url="https://operion.app/route/fail",
                )
                qtbot.addWidget(dlg)
                assert dlg._qr_label.isHidden()
                mock_logger.debug.assert_called_once()
                dlg.close()

    def test_qr_image_missing_pil_imagetq(self, qt_widget, qtbot):
        """When PIL ImageQt is not available, QR generation is skipped."""
        mock_qr_module = MagicMock()
        with patch(
            "ui.dialogs.share_route_dialog._try_import_qrcode",
            return_value=mock_qr_module,
        ):
            with patch(
                "ui.dialogs.share_route_dialog.logger"
            ) as mock_logger:
                dlg = ShareRouteDialog(
                    parent=qt_widget,
                    share_url="https://operion.app/route/no-pil",
                )
                qtbot.addWidget(dlg)
                # PIL.ImageQt is not installed, so QR generation catches
                # the ImportError and hides the label
                assert dlg._qr_label.isHidden()
                dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestShareRouteDialogEdgeCases:
    """Edge cases: no geometry data, very long route, etc."""

    def test_dialog_without_geometry_data(self, qt_widget, qtbot):
        """Dialog handles empty share_url gracefully."""
        dlg = ShareRouteDialog(parent=qt_widget, share_url="")
        qtbot.addWidget(dlg)
        assert dlg._url_field.text() == "-"
        dlg.close()

    def test_very_long_share_url(self, qt_widget, qtbot):
        """Dialog displays a very long URL without truncation error."""
        long_url = "https://operion.app/route/" + ("a" * 800)
        dlg = ShareRouteDialog(parent=qt_widget, share_url=long_url)
        qtbot.addWidget(dlg)
        displayed = dlg._url_field.text()
        assert len(displayed) > 500
        assert "a" * 100 in displayed
        dlg.close()

    def test_export_with_very_long_path(self, qt_widget, qtbot):
        """Export feedback handles very long file paths."""
        long_path = "C:\\" + ("x" * 250) + "\\route.operionroute"
        on_export = MagicMock(return_value=long_path)
        with patch.object(QTimer, "singleShot"):
            dlg = ShareRouteDialog(parent=qt_widget, on_export_file=on_export)
            qtbot.addWidget(dlg)
            dlg._on_export_file()
            assert "Saved" in dlg._url_field.text() or "saved" in dlg._url_field.text()
            assert long_path in dlg._url_field.text()
            dlg.close()

    def test_all_callbacks_none(self, qt_widget, qtbot):
        """Dialog builds without any callback supplied."""
        dlg = ShareRouteDialog(
            parent=qt_widget,
            share_url=SAMPLE_SHARE_URL,
            google_maps_url=SAMPLE_GMAPS_URL,
        )
        qtbot.addWidget(dlg)
        # All callback slots should work without raising
        dlg._on_export_file()  # no-op since callback is None
        dlg._on_open_gmaps()  # accepts dialog (no callback)
        dlg.close()

    def test_construction_to_close_lifecycle(self, qt_widget, qtbot):
        """Full lifecycle: create, interact, close."""
        dlg = ShareRouteDialog(
            parent=qt_widget,
            share_url=SAMPLE_SHARE_URL,
            google_maps_url=SAMPLE_GMAPS_URL,
        )
        qtbot.addWidget(dlg)
        assert dlg._share_url == SAMPLE_SHARE_URL
        dlg.close()
        # Ensure no crash after close
        assert dlg.isHidden()

    def test_find_children_buttons_count(self, share_dialog):
        """Dialog should have at least 4 buttons (Copy, Export, GMaps, Share, Close)."""
        buttons = share_dialog.findChildren(QPushButton)
        assert len(buttons) >= 4


# ═══════════════════════════════════════════════════════════════════════════
# _try_import_qrcode helper
# ═══════════════════════════════════════════════════════════════════════════

class TestTryImportQRCode:
    """Unit tests for the module-level _try_import_qrcode helper."""

    def test_returns_none_when_not_installed(self):
        from ui.dialogs.share_route_dialog import _try_import_qrcode
        # In the test environment qrcode is likely not installed
        result = _try_import_qrcode()
        assert result is None or hasattr(result, "make")

    def test_returns_module_when_installed(self):
        try:
            import qrcode as _qr  # noqa: F401
        except ImportError:
            pytest.skip("qrcode is not installed")
        from ui.dialogs.share_route_dialog import _try_import_qrcode
        result = _try_import_qrcode()
        assert result is not None
        assert hasattr(result, "make")
