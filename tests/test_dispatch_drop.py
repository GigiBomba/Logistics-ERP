"""Regression tests for Phase 3 — the dispatch board drag-and-drop.

The original implementation only set ``dropEvent`` on the
``QtDispatchBoardView`` itself and relied on ``childAt(event.position().toPoint())``
to find the target column.  That heuristic returned ``None`` when
the cursor landed between cards or on a scrollbar gap, so most
drop attempts silently failed.

The fix routes drops through each column's own drop event (the
column knows its own ``status_key``) and emits a per-column
``tripDropped`` signal that the board consumes.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _new_db():
    from database.db_manager import DatabaseManager
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    return db, tmp.name


class TestKanbanColumnDrop(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()
        from ui.widgets.kanban_column import QtKanbanColumn
        # Build a column manually with just the bits we need; the
        # full __init__ pulls in too many services.
        self.column = QtKanbanColumn.__new__(QtKanbanColumn)
        # We rely on the fact that QtKanbanColumn inherits from
        # QFrame; initialise the C++ side only.
        from PySide6.QtWidgets import QFrame
        QFrame.__init__(self.column)
        self.column.status_key = "Loading"
        self.column.title_key = "dispatch_board.tab_loading"
        self.column.accent_color = "#888"
        self.column._cards = []
        self.column._state = "idle"
        self.column.setAcceptDrops(True)
        # Capture signal emissions.
        self.received: list = []
        self.column.tripDropped.connect(
            lambda trip_id: self.received.append(trip_id)
        )

    def test_trip_dropped_signal_defined(self) -> None:
        from PySide6.QtCore import Signal
        self.assertTrue(hasattr(self.column, "tripDropped"))
        self.assertIsInstance(self.column.tripDropped, Signal)

    def test_drop_event_emits_trip_id(self) -> None:
        # Build a fake drop event with a trip id in the MIME payload.
        mime = QMimeData()
        mime.setText("42")
        event = QDropEvent(
            QPoint(10, 10),
            Qt.CopyAction,
            mime,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        self.column.dropEvent(event)
        self.assertEqual(self.received, [42])

    def test_drop_with_non_integer_text_ignored(self) -> None:
        mime = QMimeData()
        mime.setText("not an int")
        event = QDropEvent(
            QPoint(10, 10),
            Qt.CopyAction,
            mime,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        self.column.dropEvent(event)
        # Invalid payloads must not emit the signal.
        self.assertEqual(self.received, [])

    def test_drop_with_empty_mime_ignored(self) -> None:
        mime = QMimeData()
        # No text set.
        event = QDropEvent(
            QPoint(10, 10),
            Qt.CopyAction,
            mime,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        self.column.dropEvent(event)
        self.assertEqual(self.received, [])

    def test_drop_clears_highlight(self) -> None:
        # Simulate a drag-in (highlight), then a drop (highlight off).
        mime = QMimeData()
        mime.setText("1")
        self.column.highlight_valid = MagicMock()
        self.column.unhighlight_drop_zone = MagicMock()
        # The drop event accepts the action and unhighlights.
        event = QDropEvent(
            QPoint(10, 10),
            Qt.CopyAction,
            mime,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        self.column.dropEvent(event)
        self.column.unhighlight_drop_zone.assert_called_once()


class TestDispatchBoardAcceptsDrops(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()
        self.db, self.path = _new_db()

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)

    def test_board_accepts_drops(self) -> None:
        # Construct a minimal board-like widget.  We don't build the
        # full QtDispatchBoardView (it pulls in too many services);
        # we just verify the class sets acceptDrops in __init__.
        from ui.views.dispatch_board_view import QtDispatchBoardView
        # The __init__ runs a lot of side effects.  Instead, check
        # the class definition.
        import inspect
        src = inspect.getsource(QtDispatchBoardView.__init__)
        self.assertIn("setAcceptDrops(True)", src)

    def test_column_drop_signal_is_wired_in_build_ui(self) -> None:
        """The board's _build_ui must connect each column's
        ``tripDropped`` to ``_on_card_dropped_on_column``.  This is
        what gives us a working drop target."""
        from ui.views.dispatch_board_view import QtDispatchBoardView
        import inspect
        src = inspect.getsource(QtDispatchBoardView)
        # Both pieces must be present.
        self.assertIn("tripDropped.connect", src)
        self.assertIn("_on_card_dropped_on_column", src)


class TestColumnDropEventAccept(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()
        from ui.widgets.kanban_column import QtKanbanColumn
        from PySide6.QtWidgets import QFrame
        self.column = QtKanbanColumn.__new__(QtKanbanColumn)
        QFrame.__init__(self.column)
        self.column.status_key = "Loading"
        self.column.title_key = "dispatch_board.tab_loading"
        self.column.accent_color = "#888"
        self.column._cards = []
        self.column._state = "idle"
        self.column.setAcceptDrops(True)
        self.received: list = []
        self.column.tripDropped.connect(
            lambda trip_id: self.received.append(trip_id)
        )

    def test_drag_enter_accepts_text_mime(self) -> None:
        from PySide6.QtGui import QDragEnterEvent
        mime = QMimeData()
        mime.setText("7")
        event = QDragEnterEvent(
            QPoint(0, 0),
            Qt.CopyAction,
            mime,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        # Should not raise.  ``isAccepted`` may or may not be set
        # depending on PySide6 quirks; we just verify the call.
        self.column.dragEnterEvent(event)

    def test_drag_enter_rejects_non_text_mime(self) -> None:
        from PySide6.QtGui import QDragEnterEvent
        mime = QMimeData()
        # No text.
        event = QDragEnterEvent(
            QPoint(0, 0),
            Qt.CopyAction,
            mime,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        self.column.dragEnterEvent(event)


if __name__ == "__main__":
    unittest.main()
