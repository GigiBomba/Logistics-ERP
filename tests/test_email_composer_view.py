"""Tests for the email composer dialog (EmailComposerDialog)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def email_composer(qt_widget, qtbot):
    """Fixture with minimal arguments (no trip_id)."""
    dlg = __import__(
        "ui.views.email_composer_modal", fromlist=["EmailComposerDialog"]
    ).EmailComposerDialog(
        parent=qt_widget,
        db=MagicMock(),
    )
    qtbot.addWidget(dlg)
    yield dlg
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        dlg.close()


@pytest.fixture
def email_composer_with_trip(qt_widget, qtbot):
    """Fixture with a mock trip_id and supporting repos."""
    db = MagicMock()
    trip_repo = MagicMock()
    trip_repo.get_by_id.return_value = {"id": 42, "origin": "London", "destination": "Paris"}
    pipeline_repo = MagicMock()
    dlg = __import__(
        "ui.views.email_composer_modal", fromlist=["EmailComposerDialog"]
    ).EmailComposerDialog(
        parent=qt_widget,
        db=db,
        trip_id=42,
        prefs={},
        trip_repo=trip_repo,
        pipeline_repo=pipeline_repo,
    )
    qtbot.addWidget(dlg)
    yield dlg
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        dlg.close()


class TestEmailComposerDialog:
    """Suite of tests for EmailComposerDialog."""

    def test_creation(self, email_composer):
        """Dialog constructs without crashing."""
        assert email_composer.db is not None
        assert email_composer._trip_label is not None

    def test_standalone_title(self, email_composer):
        """Without trip_id, the dialog shows standalone title."""
        assert "Standalone" in email_composer._trip_label.text()

    def test_trip_title(self, email_composer_with_trip):
        """With trip_id, the dialog shows trip number."""
        assert "Trip #42" in email_composer_with_trip._trip_label.text()

    def test_to_combo_exists(self, email_composer):
        """Recipient combo box exists as '_to_combo'."""
        assert hasattr(email_composer, "_to_combo")

    def test_subject_edit_exists(self, email_composer):
        """Subject line edit exists as '_subject_edit'."""
        assert hasattr(email_composer, "_subject_edit")

    def test_body_edit_exists(self, email_composer):
        """Body plain text edit exists as '_body_edit'."""
        assert hasattr(email_composer, "_body_edit")

    def test_attachment_label_exists(self, email_composer):
        """Attachment label exists as '_attach_label'."""
        assert hasattr(email_composer, "_attach_label")

    def test_error_label_exists(self, email_composer):
        """Error label exists and is hidden by default."""
        assert hasattr(email_composer, "_error_label")
        assert not email_composer._error_label.isVisible()

    def test_send_button_exists(self, email_composer):
        """Send button exists as '_send_btn'."""
        assert hasattr(email_composer, "_send_btn")

    def test_save_draft_button_exists(self, email_composer):
        """Save draft button exists as '_save_draft_btn'."""
        assert hasattr(email_composer, "_save_draft_btn")

    def test_cancel_button_exists(self, email_composer):
        """Cancel button exists as '_cancel_btn'."""
        assert hasattr(email_composer, "_cancel_btn")

    def test_dialog_uses_exec(self, email_composer):
        """Dialog is a QDialog (can be shown modally via exec())."""
        from PySide6.QtWidgets import QDialog
        assert isinstance(email_composer, QDialog)

    def test_minimum_size(self, email_composer):
        """Dialog has a reasonable minimum size."""
        assert email_composer.minimumWidth() >= 400

    def test_validate_to_empty_shows_error(self, email_composer):
        """Empty 'to' field shows validation error."""
        email_composer._to_combo.setEditText("")
        result = email_composer._validate_to()
        assert result is None
        assert not email_composer._error_label.isHidden()

    def test_validate_to_invalid_email_shows_error(self, email_composer):
        """Invalid email shows validation error."""
        email_composer._to_combo.setEditText("not-an-email")
        result = email_composer._validate_to()
        assert result is None
        assert not email_composer._error_label.isHidden()

    def test_validate_to_valid_email_returns_address(self, email_composer):
        """Valid email passes validation."""
        email_composer._to_combo.setEditText("test@example.com")
        result = email_composer._validate_to()
        assert result == "test@example.com"
        assert email_composer._error_label.isHidden()

    def test_dialog_emits_sent_signal(self, qtbot, email_composer_with_trip):
        """_on_send_succeeded emits the 'sent' signal."""
        with qtbot.waitSignal(email_composer_with_trip.sent, timeout=500):
            email_composer_with_trip._on_send_succeeded(42)

    @patch("ui.views.email_composer_modal.QMessageBox")
    def test_save_draft_does_not_crash(self, mock_msgbox, email_composer):
        """_on_save_draft runs without error."""
        email_composer._package_id = 1
        email_composer._pipeline_repo = MagicMock()
        email_composer._on_save_draft()

    def test_prefill_disables_send_when_trip_missing(self, qt_widget, qtbot):
        """When trip_id is given but trip not found, send is disabled."""
        db = MagicMock()
        trip_repo = MagicMock()
        trip_repo.get_by_id.return_value = None
        dlg = __import__(
            "ui.views.email_composer_modal", fromlist=["EmailComposerDialog"]
        ).EmailComposerDialog(
            parent=qt_widget,
            db=db,
            trip_id=99,
            trip_repo=trip_repo,
        )
        qtbot.addWidget(dlg)
        assert not dlg._send_btn.isEnabled()
        assert not dlg._error_label.isHidden()
        dlg.close()
