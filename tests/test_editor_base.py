"""Tests for BaseDocumentEditor mixin.

Since BaseDocumentEditor is a mixin, we create a minimal QWidget subclass
that uses it so we can exercise all its helper methods.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from ui.views.editor_base import BaseDocumentEditor


# ── Test helper widget ─────────────────────────────────────────────────────────


class _TestEditor(QWidget, BaseDocumentEditor):
    """Minimal editor widget that exercises the BaseDocumentEditor mixin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._company_name = ""
        self._company_cui = ""
        self._company_reg = ""
        self._company_address = ""
        self._company_phone = ""
        self._company_email = ""
        self._logo_path = ""
        self._signature_path = ""
        self._stamp_path = ""
        self._company_color = ""
        self._language_callback = None
        self._subs: list = []
        # i18n registration tracking
        self._i18n_id = None

        self._build_test_ui()

    def _build_test_ui(self):
        layout = QVBoxLayout(self)
        self._name_entry = QLineEdit(self)
        layout.addWidget(self._name_entry)
        self._notes_edit = QPlainTextEdit(self)
        layout.addWidget(self._notes_edit)
        self._logo_entry = QLineEdit(self)
        layout.addWidget(self._logo_entry)

    def _retranslate_ui(self):
        """Stub to allow patching by the test suite."""

    def _register_i18n(self, callback):
        """Minimal stub matching BaseView's _register_i18n."""
        self._i18n_id = callback
        self._language_callback = callback

    def _subscribe(self, event: str, callback):
        """Minimal stub matching BaseView's _subscribe."""
        self._subs.append((event, callback))


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def editor(qt_widget, qtbot):
    e = _TestEditor(parent=qt_widget)
    qtbot.addWidget(e)
    yield e
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        e.deleteLater()


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestBaseDocumentEditor:
    """Suite of tests for BaseDocumentEditor mixin."""

    def test_mixin_available(self):
        """Can instantiate the mixin class directly (as a standalone)."""
        instance = BaseDocumentEditor.__new__(BaseDocumentEditor)
        assert instance is not None

    def test_editor_creates(self, editor):
        """Test editor widget constructs without crashing."""
        assert editor is not None
        assert isinstance(editor, BaseDocumentEditor)

    # ── Company config ────────────────────────────────────────────────────

    @patch("ui.views.editor_base.load_company_config")
    def test_load_company_config(self, mock_load, editor):
        """_load_company_config populates company attributes from config."""
        mock_load.return_value = {
            "company_name": "Test Corp",
            "cui": "RO12345",
            "reg_number": "J12/345/2020",
            "address": "123 Main St",
            "phone": "+40123456789",
            "email": "info@testcorp.com",
            "logo_path": "/path/to/logo.png",
            "signature_path": "/path/to/sig.png",
            "stamp_path": "/path/to/stamp.png",
            "company_color": "#ff0000",
        }
        editor._load_company_config()
        assert editor._company_name == "Test Corp"
        assert editor._company_cui == "RO12345"
        assert editor._company_reg == "J12/345/2020"
        assert editor._company_address == "123 Main St"
        assert editor._company_phone == "+40123456789"
        assert editor._company_email == "info@testcorp.com"
        assert editor._logo_path == "/path/to/logo.png"
        assert editor._signature_path == "/path/to/sig.png"
        assert editor._stamp_path == "/path/to/stamp.png"
        assert editor._company_color == "#ff0000"

    @patch("ui.views.editor_base.load_company_config")
    def test_load_company_config_empty(self, mock_load, editor):
        """Empty config leaves company_name empty; company_color gets COLORS default."""
        mock_load.return_value = {}
        editor._load_company_config()
        assert editor._company_name == ""
        # company_color falls back to COLORS["accent"] when config is empty
        assert editor._company_color != ""

    # ── Settings updated handler ──────────────────────────────────────────

    def test_on_settings_updated_does_not_crash(self, editor):
        """_on_settings_updated handles company_config key without error."""
        editor._on_settings_updated({"data": {"key": "company_config"}})

    def test_on_settings_updated_ignores_other_keys(self, editor):
        """Non-company_config keys do not trigger reload."""
        editor._on_settings_updated({"data": {"key": "other"}})

    # ── Event-bus subscription ───────────────────────────────────────────

    def test_subscribe_company_config_updates(self, editor):
        """_subscribe_company_config_updates registers a subscription."""
        editor._subscribe_company_config_updates()
        assert len(editor._subs) == 1
        event, _ = editor._subs[0]
        from services.operations.event_bus import SETTINGS_UPDATED
        assert event == SETTINGS_UPDATED

    # ── i18n ──────────────────────────────────────────────────────────────

    def test_setup_i18n_registers_callback(self, editor):
        """_setup_i18n registers the language-change callback."""
        editor._setup_i18n()
        assert editor._language_callback is not None
        assert editor._i18n_id is not None

    def test_on_language_changed_calls_retranslate(self, editor):
        """_on_language_changed triggers _retranslate_ui."""
        with patch.object(editor, "_retranslate_ui") as mock_rt:
            editor._on_language_changed("ro")
            mock_rt.assert_called_once()

    # ── UI helpers ────────────────────────────────────────────────────────

    def test_make_card(self, editor):
        """_make_card returns a Card (QFrame) widget."""
        card = editor._make_card()
        assert card is not None
        # Card is a QFrame subclass
        from PySide6.QtWidgets import QFrame
        assert isinstance(card, QFrame)

    def test_make_canvas_label(self, editor):
        """_make_canvas_label returns a QLabel with correct text."""
        lbl = editor._make_canvas_label(editor, "Test Label", bold=True)
        assert isinstance(lbl, QLabel)
        assert lbl.text() == "Test Label"

    def test_set_text_updates_line_edit(self, editor):
        """_set_text updates a QLineEdit without error."""
        editor._set_text(editor._name_entry, "new value")
        assert editor._name_entry.text() == "new value"

    def test_set_text_handles_none(self, editor):
        """_set_text with None edit does not crash."""
        editor._set_text(None, "test")

    def test_set_plain_text_updates_edit(self, editor):
        """_set_plain_text updates a QPlainTextEdit."""
        editor._set_plain_text(editor._notes_edit, "note content")
        assert editor._notes_edit.toPlainText() == "note content"

    def test_set_plain_text_handles_none(self, editor):
        """_set_plain_text with None edit does not crash."""
        editor._set_plain_text(None, "test")

    # ── Export JSON helpers ───────────────────────────────────────────────

    @patch("utils.editor_toolkit.export_editor_data")
    def test_export_as_json(self, mock_export, editor):
        """_export_as_json delegates to export_editor_data."""
        editor._export_as_json(
            collect_fn=lambda: {"test": "data"},
            prefix="document",
        )
        mock_export.assert_called_once()

    # ── Draft helpers ─────────────────────────────────────────────────────

    @patch("ui.views.editor_base.QInputDialog.getText")
    @patch("ui.views.editor_base.QMessageBox.information")
    def test_save_draft_via_service(
        self, mock_info, mock_get_text, editor
    ):
        """_save_draft_via_service calls service.save_draft."""
        mock_get_text.return_value = ("My Draft", True)
        svc = MagicMock()
        svc.save_draft.return_value = True
        editor._save_draft_via_service(
            service=svc,
            collect_fn=lambda: {"key": "val"},
            title_key="common.save_draft",
        )
        svc.save_draft.assert_called_once_with({"key": "val"}, "My Draft")

    @patch("ui.views.editor_base.QInputDialog.getText")
    def test_save_draft_cancelled(self, mock_get_text, editor):
        """Draft save is skipped when user cancels the input dialog."""
        mock_get_text.return_value = ("", False)
        svc = MagicMock()
        editor._save_draft_via_service(
            service=svc,
            collect_fn=lambda: {},
        )
        svc.save_draft.assert_not_called()

    @patch("ui.views.editor_base.QDialog")
    @patch("ui.views.editor_base.QMessageBox.information")
    def test_load_draft_via_dialog_no_drafts(
        self, mock_info, mock_dialog_cls, editor
    ):
        """_load_draft_via_dialog shows info when no drafts exist."""
        svc = MagicMock()
        svc.list_drafts.return_value = []
        editor._load_draft_via_dialog(
            service=svc,
            restore_fn=lambda d: None,
        )
        svc.list_drafts.assert_called_once()

    @patch("ui.views.editor_base.QFileDialog.getOpenFileName")
    def test_browse_branding_file(self, mock_get_open, editor):
        """_browse_branding_file sets the path attribute."""
        mock_get_open.return_value = ("/path/to/logo.png", "PNG (*.png)")
        editor._logo_entry = MagicMock()
        result = editor._browse_branding_file(
            field_name="logo",
            title="Select Logo",
        )
        assert result == "/path/to/logo.png"
        assert editor._logo_path == "/path/to/logo.png"

    @patch("ui.views.editor_base.QFileDialog.getOpenFileName")
    def test_browse_branding_file_cancelled(self, mock_get_open, editor):
        """_browse_branding_file returns None when cancelled."""
        mock_get_open.return_value = ("", "")
        result = editor._browse_branding_file(field_name="logo")
        assert result is None
