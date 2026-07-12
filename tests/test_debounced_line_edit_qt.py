"""pytest-qt tests for DebouncedLineEdit — real QWidget tests.

Extends the pure-logic tests in ``test_debounced_line_edit_logic.py`` with
real QApplication-backed pytest-qt fixtures and QTimer-based verification.

Tests
-----
- Creation with default parameters
- Placeholder text is set correctly
- Debounce timer fires after delay
- debouncedTextChanged signal emits correct text
- Multiple keystrokes reset the timer (only one emission)
- Custom delay_ms parameter
- textChanged behavior (fires on every keystroke, unlike debounced)
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt, QTimer


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def edit(qtbot):
    """Create a DebouncedLineEdit with default params."""
    from ui.widgets.debounced_line_edit import DebouncedLineEdit

    e = DebouncedLineEdit(placeholder="Search...", delay_ms=200)
    qtbot.addWidget(e)
    yield e


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    """Widget initializes correctly."""

    def test_creation(self, edit):
        assert edit is not None
        assert isinstance(edit, object)  # placeholder, actual type is DebouncedLineEdit

    def test_placeholder_text(self, edit):
        assert edit.placeholderText() == "Search..."

    def test_default_placeholder(self, qtbot):
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        e = DebouncedLineEdit()
        qtbot.addWidget(e)
        assert e.placeholderText() == ""

    def test_default_delay(self, qtbot):
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        e = DebouncedLineEdit(placeholder="Test")
        qtbot.addWidget(e)
        assert e._delay_ms == 300

    def test_custom_delay(self, qtbot):
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        e = DebouncedLineEdit(delay_ms=500)
        qtbot.addWidget(e)
        assert e._delay_ms == 500

    def test_timer_is_single_shot(self, edit):
        assert edit._debounce_timer.isSingleShot() is True

    def test_timer_not_running_initially(self, edit):
        assert edit._debounce_timer.isActive() is False

    def test_initial_text_empty(self, edit):
        assert edit.text() == ""


# =========================================================================
# Debounced signal emission
# =========================================================================


class TestDebounceSignal:
    """debouncedTextChanged fires after the debounce delay."""

    def test_signal_emits_after_delay(self, qtbot, edit):
        """Typing text triggers the debounced signal after the delay."""
        received = []
        edit.debouncedTextChanged.connect(received.append)

        edit.setText("hello")
        assert received == []  # not yet

        qtbot.wait(250)  # > delay_ms of 200
        assert received == ["hello"]

    def test_signal_does_not_emit_immediately(self, qtbot, edit):
        """debouncedTextChanged should NOT fire synchronously on setText."""
        received = []
        edit.debouncedTextChanged.connect(received.append)

        edit.setText("test")
        assert received == []  # must be empty

    def test_multiple_changes_only_one_emission(self, qtbot, edit):
        """Type multiple characters — only one debounced emission."""
        received = []
        edit.debouncedTextChanged.connect(received.append)

        edit.setText("a")
        edit.setText("ab")
        edit.setText("abc")
        edit.setText("abcd")

        qtbot.wait(250)
        assert received == ["abcd"]

    def test_signal_with_empty_string(self, qtbot, edit):
        """Clearing the text should emit debouncedTextChanged('')."""
        received = []
        edit.debouncedTextChanged.connect(received.append)

        edit.setText("something")
        qtbot.wait(250)
        assert received == ["something"]

        edit.clear()
        qtbot.wait(250)
        assert received == ["something", ""]

    def test_custom_delay_respected(self, qtbot):
        """A longer delay should not fire before the delay elapses."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        e = DebouncedLineEdit(delay_ms=400)
        qtbot.addWidget(e)

        received = []
        e.debouncedTextChanged.connect(received.append)

        e.setText("slow")
        qtbot.wait(200)  # less than 400
        assert received == []  # should not have fired yet

        qtbot.wait(250)  # total 450 > 400
        assert received == ["slow"]

    def test_very_short_delay(self, qtbot):
        """A very short delay (10ms) fires almost immediately."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        e = DebouncedLineEdit(delay_ms=10)
        qtbot.addWidget(e)

        received = []
        e.debouncedTextChanged.connect(received.append)

        e.setText("fast")
        qtbot.wait(20)
        assert received == ["fast"]


# =========================================================================
# textChanged (undebounced) behavior
# =========================================================================


class TestTextChanged:
    """The inherited textChanged signal fires on every change."""

    def test_text_changed_fires_on_every_change(self, qtbot, edit):
        """textChanged is the standard QLineEdit signal — fires immediately."""
        received = []
        edit.textChanged.connect(received.append)

        edit.setText("a")
        assert "a" in received

        edit.setText("ab")
        assert "ab" in received

    def test_text_changed_and_debounced_both_work(self, qtbot, edit):
        """Both signals work: textChanged immediately, debounced after delay."""
        raw = []
        debounced = []
        edit.textChanged.connect(raw.append)
        edit.debouncedTextChanged.connect(debounced.append)

        edit.setText("hello")
        assert "hello" in raw
        assert debounced == []  # debounced not yet

        qtbot.wait(250)
        assert "hello" in debounced


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    """Edge cases for debounced line edit."""

    def test_no_parent(self, qtbot):
        """Creating without a parent should not crash."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        e = DebouncedLineEdit()
        qtbot.addWidget(e)
        assert e.parent() is None

    def test_empty_placeholder(self, qtbot):
        """Explicit empty placeholder."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        e = DebouncedLineEdit(placeholder="")
        qtbot.addWidget(e)
        assert e.placeholderText() == ""

    def test_setText_empty_after_text(self, qtbot, edit):
        """Setting text to empty after having text should debounce correctly."""
        received = []
        edit.debouncedTextChanged.connect(received.append)

        edit.setText("data")
        qtbot.wait(250)
        assert received == ["data"]

        edit.setText("")
        qtbot.wait(250)
        # Should emit '' after the delay
        assert "" in received
