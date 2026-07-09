"""Tests for ``clear_layout`` utility (no QApplication required).

All Qt dependencies (``QLayout``) are mocked via ``unittest.mock.MagicMock``
so that these tests can run without a display server or a running QApplication.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ui.widgets.layout_utils import clear_layout


# ── Tests ───────────────────────────────────────────────────────────────────


class TestClearLayout:
    """Tests for ``clear_layout``."""

    def test_removes_all_widgets(self) -> None:
        """``clear_layout`` should iterate through every item in the layout
        and call ``takeAt`` for each one."""
        layout: Any = MagicMock()
        # count() returns decreasing values so the while loop terminates
        layout.count.side_effect = [3, 2, 1, 0]
        # Simulate three items: return a non-None widget for each.
        items = [
            MagicMock(widget=MagicMock()),
            MagicMock(widget=MagicMock()),
            MagicMock(widget=MagicMock()),
        ]
        layout.takeAt.side_effect = items

        clear_layout(layout)

        assert layout.takeAt.call_count == 3, "takeAt should be called 3 times"
        assert layout.count.call_count >= 4

    def test_calls_delete_later_on_widgets(self) -> None:
        """Every widget extracted from the layout should have
        ``deleteLater`` called."""
        layout: Any = MagicMock()
        layout.count.side_effect = [2, 1, 0]

        widget_a = MagicMock()
        widget_b = MagicMock()
        items = [
            MagicMock(widget=MagicMock(return_value=widget_a)),
            MagicMock(widget=MagicMock(return_value=widget_b)),
        ]
        layout.takeAt.side_effect = items

        clear_layout(layout)

        widget_a.deleteLater.assert_called_once()
        widget_b.deleteLater.assert_called_once()

    def test_empty_layout_does_not_crash(self) -> None:
        """Calling ``clear_layout`` on a layout with no items should be
        a no-op (not raise)."""
        layout: Any = MagicMock()
        layout.count.return_value = 0

        # Should not raise any exception.
        clear_layout(layout)

        layout.takeAt.assert_not_called()

    def test_skips_items_without_widgets(self) -> None:
        """Layout items that are spacers or sub-layouts (no widget) should
        be skipped without error."""
        layout: Any = MagicMock()
        layout.count.side_effect = [2, 1, 0]

        # First item has no widget (spacer), second has a widget.
        items = [
            MagicMock(widget=MagicMock(return_value=None)),
            MagicMock(widget=MagicMock()),
        ]
        layout.takeAt.side_effect = items

        # Should not raise.
        clear_layout(layout)

        # Only the second item should have deleteLater called.
        items[1].widget().deleteLater.assert_called_once()
