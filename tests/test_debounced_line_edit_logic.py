"""Tests for ``DebouncedLineEdit`` pure logic (no QApplication required).

All Qt dependencies (``QTimer``, ``QLineEdit``, ``Signal``) are mocked via
``unittest.mock.MagicMock`` so that these tests can run without a display
server or a running QApplication.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# We patch ``QTimer`` so that the module under test doesn't create real
# Qt timer objects, which would require a running QApplication.
@pytest.fixture(autouse=True)
def _mock_qt():
    """Replace ``QTimer`` with a plain MagicMock for the duration of every
    test in this module.

    ``QLineEdit`` is *not* patched at module level because the class is
    typically already loaded by other imports.  Instead the ``edit``
    fixture below creates an instance entirely via ``MagicMock`` so that
    no real Qt widget is constructed.
    """
    with patch("ui.widgets.debounced_line_edit.QTimer") as mock_timer:
        # ``QTimer(self)`` should return a fresh MagicMock every time.
        mock_timer.side_effect = lambda *a, **kw: MagicMock()
        yield


@pytest.fixture
def edit() -> Any:
    """Return a stand-in with the same shape as ``DebouncedLineEdit``.

    We use ``MagicMock(spec=…)`` so that every test gets an object that
    passes ``isinstance(…, DebouncedLineEdit)`` checks if needed, without
    constructing any real Qt widget (which would require a QApplication).
    """
    from ui.widgets.debounced_line_edit import DebouncedLineEdit

    inst = MagicMock(spec=DebouncedLineEdit)
    inst._debounce_timer = MagicMock()
    inst._delay_ms = 300
    inst.debouncedTextChanged = MagicMock()
    inst.textChanged = MagicMock()
    # Simulate the initial text being empty (as it would after construction).
    inst.text = MagicMock(return_value="")
    return inst


# ── Tests ───────────────────────────────────────────────────────────────────


class TestDebouncedLineEdit:
    """Tests for ``DebouncedLineEdit`` logic."""

    def test_starts_timer_on_text_change(self, edit: Any) -> None:
        """When the text changes, the debounce timer should be started."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        edit._debounce_timer = MagicMock()
        DebouncedLineEdit._on_text_changed(edit, "hello")
        edit._debounce_timer.start.assert_called_once_with(300)

    def test_resets_timer_on_subsequent_changes(self, edit: Any) -> None:
        """Each text change should restart the timer."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        edit._debounce_timer = MagicMock()
        DebouncedLineEdit._on_text_changed(edit, "a")
        edit._debounce_timer.start.assert_called_once_with(300)

        edit._debounce_timer.reset_mock()
        DebouncedLineEdit._on_text_changed(edit, "ab")
        edit._debounce_timer.start.assert_called_once_with(300)

    def test_emits_signal_with_current_text(self, edit: Any) -> None:
        """When the timer fires, ``_emit_debounced`` should emit the
        current text."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        edit.debouncedTextChanged = MagicMock()
        edit._debounce_timer = MagicMock()

        # Simulate what happens when the timer fires.
        edit.text = MagicMock(return_value="final text")
        DebouncedLineEdit._emit_debounced(edit)
        edit.debouncedTextChanged.emit.assert_called_once_with("final text")

    def test_placeholder_text(self) -> None:
        """The placeholder text should be forwarded to ``setPlaceholderText``
        during construction."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        spy = MagicMock()
        with patch("PySide6.QtWidgets.QLineEdit.__init__", return_value=None):
            with patch.object(DebouncedLineEdit, "setPlaceholderText", spy):
                with patch.object(DebouncedLineEdit, "textChanged"):
                    inst = DebouncedLineEdit.__new__(DebouncedLineEdit)
                    DebouncedLineEdit.__init__(
                        inst, placeholder="Type here...", delay_ms=200
                    )
        spy.assert_called_once_with("Type here...")

    def test_timer_is_single_shot(self) -> None:
        """The debounce timer should be configured as single-shot so that
        it only fires once after the last change."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        with patch("PySide6.QtWidgets.QLineEdit.__init__", return_value=None):
            with patch.object(DebouncedLineEdit, "setPlaceholderText"):
                with patch.object(DebouncedLineEdit, "textChanged"):
                    from unittest.mock import MagicMock as _MM
                    with patch("ui.widgets.debounced_line_edit.QTimer") as mt:
                        fake_timer = _MM()
                        mt.side_effect = lambda *a, **kw: fake_timer

                        inst = DebouncedLineEdit.__new__(DebouncedLineEdit)
                        DebouncedLineEdit.__init__(inst)

        assert fake_timer.setSingleShot.called, (
            "setSingleShot should have been called during __init__"
        )
        call_args = fake_timer.setSingleShot.call_args
        assert call_args is not None
        args = call_args[0] if call_args[0] else ()
        assert True in args, "setSingleShot should have been called with True"
