"""Tests for the Share Receipt dialog.

Covers construction, file path copy to clipboard, save-as callback,
OS-open callback, cancel/close behaviour, and edge cases (empty path,
very long path, missing callbacks).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication, QPushButton

from ui.dialogs.share_receipt_dialog import ShareReceiptDialog


# ── Sample data ──────────────────────────────────────────────────────────

SAMPLE_FILE_PATH = r"C:\Users\test\receipts\REC-001.pdf"
SAMPLE_SAVE_PATH = r"C:\Users\test\saved_receipt.pdf"


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def share_dialog(qt_widget, qtbot):
    """Provide a fully-wired ShareReceiptDialog with mock callbacks."""
    on_save_as = MagicMock(return_value=SAMPLE_SAVE_PATH)
    on_open = MagicMock()
    dlg = ShareReceiptDialog(
        parent=qt_widget,
        file_path=SAMPLE_FILE_PATH,
        on_save_as=on_save_as,
        on_open=on_open,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


@pytest.fixture
def share_dialog_empty(qt_widget, qtbot):
    """Provide a ShareReceiptDialog with no file path and no callbacks."""
    dlg = ShareReceiptDialog(parent=qt_widget)
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

class TestShareReceiptDialogInit:
    """Construction and initial state."""

    def test_creation(self, share_dialog):
        assert isinstance(share_dialog, ShareReceiptDialog)
        assert share_dialog.windowTitle() != ""

    def test_is_modal(self, share_dialog):
        assert share_dialog.windowModality() == Qt.ApplicationModal

    def test_minimum_size_set(self, share_dialog):
        assert share_dialog.minimumWidth() == 460
        assert share_dialog.minimumHeight() == 300

    def test_maximum_width_set(self, share_dialog):
        assert share_dialog.maximumWidth() == 520

    def test_file_path_stored(self, share_dialog):
        assert share_dialog._file_path == SAMPLE_FILE_PATH

    def test_callbacks_stored(self, share_dialog):
        assert share_dialog._on_save_as_cb is not None
        assert share_dialog._on_open_cb is not None

    def test_empty_dialog_stores_defaults(self, share_dialog_empty):
        assert share_dialog_empty._file_path == ""
        assert share_dialog_empty._on_save_as_cb is None
        assert share_dialog_empty._on_open_cb is None

    def test_path_field_shows_path(self, share_dialog):
        assert SAMPLE_FILE_PATH in share_dialog._path_field.text()

    def test_path_field_shows_dash_when_empty(self, share_dialog_empty):
        assert share_dialog_empty._path_field.text() == "-"

    def test_path_field_is_selectable(self, share_dialog):
        flags = share_dialog._path_field.textInteractionFlags()
        assert flags & Qt.TextSelectableByMouse

    def test_path_field_wraps_text(self, share_dialog):
        assert share_dialog._path_field.wordWrap() is True

    def test_title_label_present(self, share_dialog):
        labels = [
            w for w in share_dialog.findChildren(object)
            if hasattr(w, "text") and "Share" in w.text()
        ]
        assert len(labels) >= 1

    def test_subtitle_label_present(self, share_dialog):
        labels = [
            w for w in share_dialog.findChildren(object)
            if hasattr(w, "text") and "PDF" in w.text()
        ]
        assert len(labels) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# File path copy to clipboard
# ═══════════════════════════════════════════════════════════════════════════

class TestShareReceiptDialogCopyPath:
    """File path copy to clipboard behaviour."""

    def test_copy_path_writes_to_clipboard(self, share_dialog):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        share_dialog._on_copy_path()
        assert clipboard.text() == SAMPLE_FILE_PATH

    def test_copy_path_shows_feedback_text(self, share_dialog):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        share_dialog._on_copy_path()
        assert share_dialog._path_field.text() != SAMPLE_FILE_PATH
        assert len(share_dialog._path_field.text()) > 0

    def test_copy_path_restores_path_after_timer(self, share_dialog):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        with patch.object(QTimer, "singleShot"):
            share_dialog._on_copy_path()
            share_dialog._restore_path_text()
            assert share_dialog._path_field.text() == SAMPLE_FILE_PATH

    def test_copy_path_schedules_restore_timer(self, share_dialog):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        with patch.object(QTimer, "singleShot") as mock_timer:
            share_dialog._on_copy_path()
            mock_timer.assert_called_once_with(
                2000, share_dialog._restore_path_text
            )

    def test_copy_path_empty_path(self, share_dialog_empty):
        clipboard = QApplication.clipboard()
        clipboard.clear()
        share_dialog_empty._on_copy_path()
        assert clipboard.text() == ""

    def test_copy_button_found_and_clickable(self, share_dialog):
        copy_btn = _find_button(share_dialog, "Copy")
        assert copy_btn is not None
        with patch.object(share_dialog, "_on_copy_path") as mock_copy:
            copy_btn.click()
            mock_copy.assert_called_once()

    def test_restore_path_text_empty_path(self, share_dialog_empty):
        share_dialog_empty._restore_path_text()
        assert share_dialog_empty._path_field.text() == "-"


# ═══════════════════════════════════════════════════════════════════════════
# Save As (copy PDF to user-selected location)
# ═══════════════════════════════════════════════════════════════════════════

class TestShareReceiptDialogSaveAs:
    """Save As behaviour."""

    def test_save_as_calls_callback(self, share_dialog):
        share_dialog._on_save_as()
        share_dialog._on_save_as_cb.assert_called_once_with(SAMPLE_FILE_PATH)

    def test_save_as_shows_saved_feedback(self, share_dialog):
        share_dialog._on_save_as()
        text = share_dialog._path_field.text()
        assert "Saved" in text or "saved" in text
        assert SAMPLE_SAVE_PATH in text

    def test_save_as_button_triggers_save_as(self, share_dialog):
        save_btn = _find_button(share_dialog, "Save")
        assert save_btn is not None
        with patch.object(share_dialog, "_on_save_as") as mock_save:
            save_btn.click()
            mock_save.assert_called_once()

    def test_save_as_schedules_restore_timer(self, share_dialog):
        with patch.object(QTimer, "singleShot") as mock_timer:
            share_dialog._on_save_as()
            mock_timer.assert_called_once_with(
                3000, share_dialog._restore_path_text
            )

    def test_save_as_restores_path_after_timer(self, share_dialog):
        share_dialog._on_save_as()
        share_dialog._restore_path_text()
        assert share_dialog._path_field.text() == SAMPLE_FILE_PATH

    def test_save_as_no_callback_does_not_raise(self, share_dialog_empty):
        share_dialog_empty._on_save_as()

    def test_save_as_callback_returns_none_no_feedback(self, qt_widget, qtbot):
        on_save = MagicMock(return_value=None)
        dlg = ShareReceiptDialog(
            parent=qt_widget,
            file_path=SAMPLE_FILE_PATH,
            on_save_as=on_save,
        )
        qtbot.addWidget(dlg)
        original_text = dlg._path_field.text()
        dlg._on_save_as()
        assert dlg._path_field.text() == original_text
        dlg.close()

    def test_save_as_callback_returns_empty_string(self, qt_widget, qtbot):
        on_save = MagicMock(return_value="")
        dlg = ShareReceiptDialog(
            parent=qt_widget,
            file_path=SAMPLE_FILE_PATH,
            on_save_as=on_save,
        )
        qtbot.addWidget(dlg)
        original_text = dlg._path_field.text()
        dlg._on_save_as()
        assert dlg._path_field.text() == original_text
        dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Open (OS default application)
# ═══════════════════════════════════════════════════════════════════════════

class TestShareReceiptDialogOpen:
    """Open button behaviour."""

    def test_open_calls_callback(self, share_dialog):
        share_dialog._on_open()
        share_dialog._on_open_cb.assert_called_once_with(SAMPLE_FILE_PATH)

    def test_open_accepts_dialog(self, share_dialog):
        with patch.object(share_dialog, "accept") as mock_accept:
            share_dialog._on_open()
            mock_accept.assert_called_once()

    def test_open_no_callback_accepts(self, qt_widget, qtbot):
        dlg = ShareReceiptDialog(parent=qt_widget, file_path=SAMPLE_FILE_PATH)
        qtbot.addWidget(dlg)
        with patch.object(dlg, "accept") as mock_accept:
            dlg._on_open()
            mock_accept.assert_called_once()
        dlg.close()

    def test_open_button_triggers_open(self, share_dialog):
        open_btn = _find_button(share_dialog, "Open")
        assert open_btn is not None
        with patch.object(share_dialog, "_on_open") as mock_open:
            open_btn.click()
            mock_open.assert_called_once()

    def test_open_button_text_not_empty(self, share_dialog):
        open_btn = _find_button(share_dialog, "Open")
        assert open_btn is not None
        assert len(open_btn.text()) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Cancel / Close behaviour
# ═══════════════════════════════════════════════════════════════════════════

class TestShareReceiptDialogClose:
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
        share_dialog.reject()

    def test_close_button_text_not_empty(self, share_dialog):
        close_btn = _find_button(share_dialog, "Close")
        assert close_btn is not None
        assert len(close_btn.text()) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestShareReceiptDialogEdgeCases:
    """Edge cases: empty path, very long path, missing callbacks, etc."""

    def test_dialog_without_file_path(self, qt_widget, qtbot):
        dlg = ShareReceiptDialog(parent=qt_widget, file_path="")
        qtbot.addWidget(dlg)
        assert dlg._path_field.text() == "-"
        dlg.close()

    def test_very_long_file_path(self, qt_widget, qtbot):
        long_path = "C:\\" + ("x" * 250) + "\\receipt.pdf"
        dlg = ShareReceiptDialog(parent=qt_widget, file_path=long_path)
        qtbot.addWidget(dlg)
        displayed = dlg._path_field.text()
        assert len(displayed) > 200
        assert "x" * 100 in displayed
        dlg.close()

    def test_all_callbacks_none(self, qt_widget, qtbot):
        dlg = ShareReceiptDialog(parent=qt_widget, file_path=SAMPLE_FILE_PATH)
        qtbot.addWidget(dlg)
        dlg._on_save_as()
        dlg._on_open()
        dlg.close()

    def test_construction_to_close_lifecycle(self, qt_widget, qtbot):
        dlg = ShareReceiptDialog(parent=qt_widget, file_path=SAMPLE_FILE_PATH)
        qtbot.addWidget(dlg)
        assert dlg._file_path == SAMPLE_FILE_PATH
        dlg.close()
        assert dlg.isHidden()

    def test_find_children_buttons_count(self, share_dialog):
        buttons = share_dialog.findChildren(QPushButton)
        assert len(buttons) >= 3
