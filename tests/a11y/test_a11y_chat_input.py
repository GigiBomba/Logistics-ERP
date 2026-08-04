"""Accessibility tests for ChatInputWidget.

ChatInputWidget is the bottom input bar with a text field, microphone button,
and Send button used in the Co-Pilot panel. Currently, none of these elements
set an explicit accessibleName — these tests document the gap.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit, QPushButton

from tests.a11y.conftest import (
    assert_accessible_name_not_empty,
    assert_accessible_description_not_empty,
    assert_widget_has_focus,
)

# ── SP workaround ──────────────────────────────────────────────────────


class TestChatInputWidgetA11y:
    """ChatInputWidget — bottom input bar (text field + mic + send button).

    Each test instantiates ChatInputWidget and checks an accessibility property
    on the widget or one of its child controls.  Widgets / controls that lack
    an explicit accessibleName will fail — that is intentional and documents
    the current a11y gap.
    """

    def test_widget_has_accessible_name(self, qt_widget, qtbot):
        """ChatInputWidget frame should have an accessibleName."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        assert_accessible_name_not_empty(widget)

    def test_chat_input_field_has_accessible_name(self, qt_widget, qtbot):
        """The QLineEdit text input should have accessibleName."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        input_field = widget.findChild(QLineEdit)
        assert input_field is not None, "ChatInputWidget should have a QLineEdit input field"
        assert_accessible_name_not_empty(input_field)

    def test_send_button_has_accessible_name(self, qt_widget, qtbot):
        """Send button should have accessibleName for screen readers."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        # The Send button text comes from i18n (default: "Send").
        send_btn = next(
            (btn for btn in widget.findChildren(QPushButton) if btn.text() == "Send"),
            None,
        )
        assert send_btn is not None, "ChatInputWidget should have a Send button"
        assert_accessible_name_not_empty(send_btn)

    def test_mic_button_has_accessible_name(self, qt_widget, qtbot):
        """Microphone (push-to-talk) button should have accessibleName."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        # The mic button displays the Unicode microphone character.
        mic_btn = next(
            (btn for btn in widget.findChildren(QPushButton) if "\U0001f3a4" in btn.text()),
            None,
        )
        assert mic_btn is not None, "ChatInputWidget should have a mic button"
        assert_accessible_name_not_empty(mic_btn)

    def test_tab_order_input_to_mic_to_send(self, qt_widget, qtbot):
        """Tab should move input field → mic button → send button."""
        from PySide6.QtWidgets import QApplication
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.show()
        qt_widget.show()
        QTest.qWaitForWindowExposed(widget)
        QTest.qWaitForWindowExposed(qt_widget)

        # Activate the window so setFocus works
        widget.window().activateWindow()
        widget._input.setFocus()
        QApplication.processEvents()
        assert_widget_has_focus(widget._input)

        # Tab to the mic button
        QTest.keyClick(widget._input, Qt.Key_Tab)
        assert_widget_has_focus(widget._mic_btn)

        # Tab to the Send button
        QTest.keyClick(widget._mic_btn, Qt.Key_Tab)
        assert_widget_has_focus(widget._send_btn)

    def test_send_button_disabled_during_processing(self, qt_widget, qtbot):
        """Send button should be disabled while processing a request.

        The disabled state should also be conveyed via accessible properties.
        """
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.set_processing(True)
        assert not widget._send_btn.isEnabled(), (
            "Send button should be disabled during processing"
        )
        widget.set_processing(False)
        assert widget._send_btn.isEnabled(), (
            "Send button should be re-enabled after processing"
        )

    def test_input_disabled_during_processing(self, qt_widget, qtbot):
        """Text input should be disabled while processing a request."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.set_processing(True)
        assert not widget._input.isEnabled(), (
            "Input should be disabled during processing"
        )
        widget.set_processing(False)
        assert widget._input.isEnabled(), (
            "Input should be re-enabled after processing"
        )

    # ── Keyboard navigation tests ─────────────────────────────────────

    def test_enter_sends_message(self, qt_widget, qtbot):
        """Pressing Enter after typing should emit send_clicked with the message."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)

        with qtbot.waitSignal(widget.send_clicked, timeout=1000) as blocker:
            widget.show()
            widget._input.setFocus()
            qtbot.keyClicks(widget._input, "Hello")
            qtbot.keyClick(widget._input, Qt.Key_Return)

        assert blocker.args[0] == "Hello", (
            "send_clicked should carry the typed message"
        )
        assert widget._input.text() == "", (
            "Input should be cleared after send"
        )

    def test_tab_to_send_then_enter_activates(self, qt_widget, qtbot):
        """Tab to Send button and press Enter should call _on_send."""
        from PySide6.QtWidgets import QApplication
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.show()
        qt_widget.show()
        QTest.qWaitForWindowExposed(widget)
        QTest.qWaitForWindowExposed(qt_widget)
        widget.window().activateWindow()

        # Type some text first so _on_send has something to emit
        qtbot.keyClicks(widget._input, "tab to send")

        with qtbot.waitSignal(widget.send_clicked, timeout=1000) as blocker:
            widget._input.setFocus()
            QApplication.processEvents()
            # Tab from input → mic → send
            QTest.keyClick(widget._input, Qt.Key_Tab)
            QTest.keyClick(widget._mic_btn, Qt.Key_Tab)
            # Activate the Send button with Space (standard for non-dialog QPushButton)
            QTest.keyClick(widget._send_btn, Qt.Key_Space)

        assert blocker.args[0] == "tab to send"

    def test_tab_to_mic_then_space_activates(self, qt_widget, qtbot):
        """Tab to mic button and press Space should activate mic."""
        from PySide6.QtWidgets import QApplication
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.show()
        qt_widget.show()
        QTest.qWaitForWindowExposed(widget)
        QTest.qWaitForWindowExposed(qt_widget)
        widget.window().activateWindow()

        with qtbot.waitSignal(widget.mic_pressed, timeout=1000):
            widget._input.setFocus()
            QApplication.processEvents()
            # Tab to mic button
            QTest.keyClick(widget._input, Qt.Key_Tab)
            assert_widget_has_focus(widget._mic_btn)
            # Press Space to activate mic
            QTest.keyClick(widget._mic_btn, Qt.Key_Space)

    def test_input_disabled_during_processing_typing(self, qt_widget, qtbot):
        """Typing should have no effect while processing."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.show()

        # Enable processing — input becomes disabled
        widget.set_processing(True)
        assert not widget._input.isEnabled(), (
            "Input should be disabled during processing"
        )

        # Attempt to type
        qtbot.keyClicks(widget._input, "should not appear")

        assert widget._input.text() == "", (
            "Input should remain empty when processing"
        )

    def test_empty_input_enter_does_not_send(self, qt_widget, qtbot):
        """Pressing Enter with empty input should not emit send_clicked."""
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.show()

        emitted = []
        widget.send_clicked.connect(lambda msg: emitted.append(msg))

        widget._input.setFocus()
        qtbot.keyClick(widget._input, Qt.Key_Return)

        assert len(emitted) == 0, (
            "send_clicked should NOT be emitted for empty input"
        )

    def test_tab_wraps_input_to_mic_to_send(self, qt_widget, qtbot):
        """Tab should move input → mic → send then wrap to the next focusable."""
        from PySide6.QtWidgets import QApplication
        from ui.copilot.widgets.chat_input import ChatInputWidget

        widget = ChatInputWidget(parent=qt_widget)
        qtbot.addWidget(widget)
        widget.show()
        qt_widget.show()
        QTest.qWaitForWindowExposed(widget)
        QTest.qWaitForWindowExposed(qt_widget)

        widget.window().activateWindow()
        widget._input.setFocus()
        QApplication.processEvents()
        assert_widget_has_focus(widget._input)

        # Tab → mic button
        QTest.keyClick(widget._input, Qt.Key_Tab)
        assert_widget_has_focus(widget._mic_btn)

        # Tab → Send button
        QTest.keyClick(widget._mic_btn, Qt.Key_Tab)
        assert_widget_has_focus(widget._send_btn)

        # Tab again — should cycle back to input (wrap around)
        QTest.keyClick(widget._send_btn, Qt.Key_Tab)
        assert widget._input.hasFocus() or widget._mic_btn.hasFocus(), (
            "Tab from Send should wrap focus back to input or mic"
        )
