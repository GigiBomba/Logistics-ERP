"""Tests for the login dialog."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import Qt

@pytest.fixture
def login_dialog(qt_widget, qtbot):
    dlg = __import__("ui.dialogs.login_dialog", fromlist=["QtLoginDialog"]).QtLoginDialog(
        parent=qt_widget,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtLoginDialog:
    def test_creation(self, login_dialog):
        assert login_dialog.windowTitle() is not None
        assert login_dialog._stack is not None

    def test_starts_on_page_0(self, login_dialog):
        assert login_dialog._stack.currentIndex() == 0

    def test_empty_email_shows_error(self, login_dialog):
        login_dialog._on_next_clicked()
        assert login_dialog._error_label.isVisible()

    def test_valid_email_advances_to_page_1(self, login_dialog):
        login_dialog._email_input.setText("admin@example.com")
        login_dialog._on_next_clicked()
        assert login_dialog._stack.currentIndex() == 1

    def test_invalid_email_format_shows_error(self, login_dialog):
        login_dialog._email_input.setText("not-an-email")
        login_dialog._on_next_clicked()
        assert login_dialog._error_label.isVisible()

    def test_back_button_returns_to_page_0(self, login_dialog):
        login_dialog._email_input.setText("admin@example.com")
        login_dialog._on_next_clicked()
        login_dialog._on_back_clicked()
        assert login_dialog._stack.currentIndex() == 0

    def test_empty_password_shows_error(self, login_dialog):
        login_dialog._email_input.setText("admin@example.com")
        login_dialog._on_next_clicked()
        login_dialog._password_input.setText("")
        login_dialog._on_login_clicked()
        assert login_dialog._error_label.isVisible()

    def test_cancel_rejects_dialog(self, login_dialog, qtbot):
        login_dialog._cancel_btn.click()
        assert login_dialog.result() == 0  # Rejected

    def test_busy_state_disables_inputs(self, login_dialog):
        login_dialog._set_busy(True)
        assert not login_dialog._email_input.isEnabled()
        assert not login_dialog._password_input.isEnabled()
        assert not login_dialog._login_btn.isEnabled()
        login_dialog._set_busy(False)
        assert login_dialog._email_input.isEnabled()

class TestLoginWorker:
    def test_creation(self):
        worker = __import__("ui.dialogs.login_dialog", fromlist=["_LoginWorker"])._LoginWorker(
            "admin@test.com", "password123"
        )
        assert worker._email == "admin@test.com"
        assert worker._password == "password123"

    def test_failed_login_emits_error(self, qt_widget, qtbot):
        worker = __import__("ui.dialogs.login_dialog", fromlist=["_LoginWorker"])._LoginWorker(
            "bad@test.com", "wrong"
        )
        results = []
        worker.finished.connect(lambda ok, msg: results.append((ok, msg)))
        worker.run()
        assert len(results) == 1
        assert results[0][0] is False
        assert len(results[0][1]) > 0
