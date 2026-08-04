"""Accessibility tests for QtLoginDialog.

QtLoginDialog already has accessibleName set on the dialog ("Login") and key
children: email input ("Email address"), password input ("Password"), and login
button ("Login").
"""
from __future__ import annotations

from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name,
    assert_accessible_name_not_empty,
    assert_widget_has_focus,
    collect_focusable_children,
)


class TestQtLoginDialogA11y:
    """QtLoginDialog — modal dialog for admin authentication."""

    def test_dialog_accessible_name(self, qt_widget, qtbot):
        """QtLoginDialog should expose accessibleName 'Login'."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name(dialog, "Login")

    def test_dialog_accessible_description(self, qt_widget, qtbot):
        """QtLoginDialog should expose an accessibleDescription (gap)."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_description_not_empty(dialog)

    def test_email_input_accessible_name(self, qt_widget, qtbot):
        """Email input should have accessibleName 'Email address'."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name(dialog._email_input, "Email address")

    def test_password_input_accessible_name(self, qt_widget, qtbot):
        """Password input should have accessibleName 'Password'."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog._email_input.setText("admin@example.com")
        dialog._on_next_clicked()
        assert_accessible_name(dialog._password_input, "Password")

    def test_login_button_accessible_name(self, qt_widget, qtbot):
        """Login button should have accessibleName 'Login'."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog._email_input.setText("admin@example.com")
        dialog._on_next_clicked()
        assert_accessible_name(dialog._login_btn, "Login")

    def test_cancel_button_accessible_name(self, qt_widget, qtbot):
        """Cancel button should have an accessibleName (gap)."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog._cancel_btn)

    def test_email_input_accessible_description(self, qt_widget, qtbot):
        """Email input should have an accessibleDescription (gap)."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_description_not_empty(dialog._email_input)

    # ── Keyboard navigation ────────────────────────────────────────────

    def test_tab_order_email_to_next(self, qt_widget, qtbot):
        """Tab from email input lands on the Next button."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        page_0 = dialog._stack.widget(0)
        next_btn = page_0.findChild(QPushButton)
        assert next_btn is not None, "Next button not found on page 0"

        dialog._email_input.setFocus()
        assert_widget_has_focus(dialog._email_input)

        QTest.keyClick(dialog._email_input, Qt.Key_Tab)
        assert_widget_has_focus(next_btn)

    def test_enter_on_email_advances_to_password(self, qt_widget, qtbot):
        """Enter on email with valid input advances to password page."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()

        qtbot.keyClicks(dialog._email_input, "admin@test.com")
        qtbot.keyClick(dialog._email_input, Qt.Key_Return)

        assert dialog._stack.currentIndex() == 1, (
            "Should be on password page after Enter"
        )

    def test_enter_on_password_triggers_login(self, qt_widget, qtbot):
        """Enter on password calls _on_login_clicked."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog._email_input.setText("admin@test.com")
        dialog._on_next_clicked()
        assert dialog._stack.currentIndex() == 1, (
            "Should be on password page"
        )

        qtbot.keyClicks(dialog._password_input, "pass")
        with mock.patch.object(dialog, "_on_login_clicked") as mock_login:
            qtbot.keyClick(dialog._password_input, Qt.Key_Return)
            mock_login.assert_called_once()

    def test_escape_dismisses_dialog(self, qt_widget, qtbot):
        """Escape key dismisses the dialog with Rejected."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        QTest.keyClick(dialog, Qt.Key_Escape)
        assert dialog.result() == QDialog.Rejected, (
            "Dialog should be rejected on Escape"
        )

    def test_tab_wraps_on_page_0(self, qt_widget, qtbot):
        """Tab order on page 0: email → Next → Cancel → cycles."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()

        page_0 = dialog._stack.widget(0)
        next_btn = page_0.findChild(QPushButton)
        assert next_btn is not None, "Next button not found on page 0"

        focusable = collect_focusable_children(dialog)
        assert dialog._email_input in focusable
        assert next_btn in focusable
        assert dialog._cancel_btn in focusable

        email_idx = focusable.index(dialog._email_input)
        next_idx = focusable.index(next_btn)
        cancel_idx = focusable.index(dialog._cancel_btn)

        assert email_idx < next_idx < cancel_idx, (
            f"Expected email ({email_idx}) < Next ({next_idx}) < Cancel ({cancel_idx})"
        )

    def test_password_echo_mode_preserved(self, qt_widget, qtbot):
        """Password echo mode remains Password during keyboard interaction."""
        from ui.dialogs.login_dialog import QtLoginDialog

        dialog = QtLoginDialog(parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog._email_input.setText("admin@test.com")
        dialog._on_next_clicked()

        assert dialog._password_input.echoMode() == QLineEdit.EchoMode.Password

        qtbot.keyClicks(dialog._password_input, "secret123")
        assert dialog._password_input.echoMode() == QLineEdit.EchoMode.Password
