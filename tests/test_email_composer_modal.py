"""Tests for the email composer modal."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def email_composer(qt_widget, qtbot):
    dlg = __import__("ui.views.email_composer_modal", fromlist=["EmailComposerDialog"]).EmailComposerDialog(
        parent=qt_widget,
        db=MagicMock(),
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


class TestEmailComposerDialog:
    def test_creation(self, email_composer):
        assert email_composer._db is not None

    def test_to_field_exists(self, email_composer):
        assert hasattr(email_composer, "_to_input")

    def test_subject_field_exists(self, email_composer):
        assert hasattr(email_composer, "_subject_input")

    def test_body_editor_exists(self, email_composer):
        assert hasattr(email_composer, "_body_editor")

    def test_send_button_exists(self, email_composer):
        assert hasattr(email_composer, "_btn_send")

    def test_attachment_list_exists(self, email_composer):
        assert hasattr(email_composer, "_attachment_list")

    def test_dialog_is_modal(self, email_composer):
        assert email_composer.isModal()
