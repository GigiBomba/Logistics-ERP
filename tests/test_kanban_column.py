"""Tests for QtKanbanColumn — drag-drop, states, card management."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def kanban_column(qt_widget, qtbot):
    """Create a QtKanbanColumn with default params."""
    from ui.widgets.kanban_column import QtKanbanColumn

    column = QtKanbanColumn(
        parent=qt_widget,
        status_key="Planned",
        title_key="dispatch_board.col_planned",
        accent_color="#6366F1",
        on_card_click=MagicMock(),
        on_drag_start=MagicMock(),
        on_assign_truck=MagicMock(),
        on_assign_driver=MagicMock(),
        on_select_changed=MagicMock(),
        on_assign_both=MagicMock(),
        show_load_older=True,
        on_load_older=MagicMock(),
        on_retry=MagicMock(),
    )
    qt_widget.show()  # Show parent so isVisible() works on children
    column.show()
    qtbot.addWidget(column)
    yield column
    column.destroy()


@pytest.fixture
def qt_trip_card(qt_widget, qtbot):
    """Create a minimal QtTripCard for testing card manipulation."""
    from ui.widgets.trip_card import QtTripCard

    card = QtTripCard(
        parent=qt_widget,
        trip_data={"trip_id_num": 42, "client": "Test"},
    )
    qt_widget.show()
    card.show()
    qtbot.addWidget(card)
    yield card
    card.deleteLater()


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    """Column init with correct properties."""

    def test_creation(self, kanban_column):
        assert kanban_column.status_key == "Planned"
        assert kanban_column.title_key == "dispatch_board.col_planned"
        assert kanban_column.accent_color == "#6366F1"

    def test_accepts_drops(self, kanban_column):
        assert kanban_column.acceptDrops() is True

    def test_default_state(self, kanban_column):
        assert kanban_column._state == "idle"
        assert kanban_column._cards == []

    def test_title_label_exists(self, kanban_column):
        assert kanban_column._title_label is not None

    def test_count_label_exists(self, kanban_column):
        assert kanban_column._count_label is not None

    def test_scroll_area_exists(self, kanban_column):
        assert kanban_column._scroll_area is not None

    def test_loading_widget_exists(self, kanban_column):
        assert kanban_column._loading_widget is not None

    def test_error_widget_exists(self, kanban_column):
        assert kanban_column._error_widget is not None

    def test_load_older_widget_created(self, kanban_column):
        assert kanban_column._load_older_widget is not None

    def test_load_older_hidden_when_disabled(self, qt_widget, qtbot):
        from ui.widgets.kanban_column import QtKanbanColumn
        column = QtKanbanColumn(
            parent=qt_widget,
            status_key="Planned",
            title_key="dispatch_board.col_planned",
            show_load_older=False,
        )
        qt_widget.show()
        column.show()
        qtbot.addWidget(column)
        assert column._load_older_widget is None
        column.destroy()

    def test_status_color_fallback(self, qt_widget, qtbot):
        from ui.widgets.kanban_column import QtKanbanColumn
        column = QtKanbanColumn(
            parent=qt_widget,
            status_key="UnknownStatus",
            title_key="x",
        )
        qt_widget.show()
        column.show()
        qtbot.addWidget(column)
        assert column.accent_color is not None  # Falls back to chip_planned
        column.destroy()


# =========================================================================
# set_trips / card management
# =========================================================================


class TestSetTrips:
    """Setting trips populates, reuses, and removes cards."""

    def test_set_trips_populates(self, kanban_column):
        trips = [
            {"trip_id_num": 1, "client": "A"},
            {"trip_id_num": 2, "client": "B"},
        ]
        kanban_column.set_trips(trips)
        assert len(kanban_column._cards) == 2

    def test_set_trips_empty_clears(self, kanban_column):
        kanban_column.set_trips([{"trip_id_num": 1}])
        assert len(kanban_column._cards) == 1
        kanban_column.set_trips([])
        assert len(kanban_column._cards) == 0

    def test_set_trips_reuses_existing_cards(self, kanban_column):
        trips = [{"trip_id_num": 1, "client": "A"}]
        kanban_column.set_trips(trips)
        original_card = kanban_column._cards[0]

        # Same trip_id_num — should reuse card
        trips2 = [{"trip_id_num": 1, "client": "B"}]
        kanban_column.set_trips(trips2)
        assert len(kanban_column._cards) == 1
        assert kanban_column._cards[0] is original_card  # reused

    def test_set_trips_removes_stale_cards(self, kanban_column):
        kanban_column.set_trips([
            {"trip_id_num": 1, "client": "A"},
            {"trip_id_num": 2, "client": "B"},
        ])
        assert len(kanban_column._cards) == 2

        # Remove card 2
        kanban_column.set_trips([{"trip_id_num": 1, "client": "A"}])
        assert len(kanban_column._cards) == 1
        assert kanban_column._cards[0].trip_data["trip_id_num"] == 1

    def test_set_trips_hides_loading_and_error(self, kanban_column):
        kanban_column.show_loading()
        assert kanban_column._state == "loading"
        kanban_column.set_trips([{"trip_id_num": 1}])
        assert kanban_column._state == "idle"
        assert kanban_column._loading_widget.isHidden()
        assert kanban_column._error_widget.isHidden()

    def test_set_trips_updates_count(self, kanban_column):
        kanban_column.set_trips([{"trip_id_num": 1}, {"trip_id_num": 2}])
        assert "\u2022 2" in kanban_column._count_label.text()

    def test_set_trips_shows_load_older_when_enabled(self, kanban_column):
        assert kanban_column._load_older_widget is not None
        kanban_column.set_trips([{"trip_id_num": 1}])
        assert kanban_column._load_older_widget.isVisible()


# =========================================================================
# add_card / remove_card
# =========================================================================


class TestCardManipulation:
    """Individual card add/remove."""

    def test_add_card_appends(self, kanban_column, qt_trip_card):
        kanban_column.add_card(qt_trip_card)
        assert len(kanban_column._cards) == 1

    def test_add_card_at_index(self, kanban_column, qt_trip_card):
        card2 = qt_trip_card  # first card
        from ui.widgets.trip_card import QtTripCard
        card1 = QtTripCard(
            kanban_column._scroll_area.widget(),
            {"trip_id_num": 1, "client": "First"},
        )
        kanban_column.add_card(card1, index=0)
        kanban_column.add_card(card2, index=0)  # insert at top
        assert len(kanban_column._cards) == 2
        assert kanban_column._cards[0] is card2  # card2 should be first

    def test_add_card_at_out_of_bounds_index(self, kanban_column, qt_trip_card):
        """Index larger than list appends."""
        kanban_column.add_card(qt_trip_card, index=999)
        assert len(kanban_column._cards) == 1

    def test_add_card_updates_count(self, kanban_column, qt_trip_card):
        kanban_column.add_card(qt_trip_card)
        assert "\u2022 1" in kanban_column._count_label.text()

    def test_remove_card_removes(self, kanban_column, qt_trip_card):
        kanban_column.add_card(qt_trip_card)
        assert len(kanban_column._cards) == 1
        kanban_column.remove_card(qt_trip_card)
        assert len(kanban_column._cards) == 0

    def test_remove_card_not_in_list_does_nothing(self, kanban_column, qt_trip_card):
        """Removing a card not in the list does not crash."""
        kanban_column.remove_card(qt_trip_card)  # not added

    def test_remove_card_updates_count(self, kanban_column, qt_trip_card):
        kanban_column.add_card(qt_trip_card)
        kanban_column.remove_card(qt_trip_card)
        assert "\u2022 0" in kanban_column._count_label.text()

    def test_add_card_hides_overlays(self, kanban_column, qt_trip_card):
        kanban_column.show_error("test error")
        assert kanban_column._state == "error"
        kanban_column.add_card(qt_trip_card)
        assert kanban_column._error_widget.isHidden()
        assert kanban_column._loading_widget.isHidden()


# =========================================================================
# Loading / Error states
# =========================================================================


class TestStates:
    """Loading and error state transitions."""

    def test_show_loading_clears_cards(self, kanban_column):
        kanban_column.set_trips([{"trip_id_num": 1}])
        assert len(kanban_column._cards) == 1
        kanban_column.show_loading()
        assert len(kanban_column._cards) == 0
        assert kanban_column._state == "loading"

    def test_show_loading_shows_widget(self, kanban_column):
        kanban_column.show_loading()
        assert kanban_column._loading_widget.isVisible()
        assert kanban_column._error_widget.isHidden()

    def test_show_loading_updates_count(self, kanban_column):
        kanban_column.show_loading()
        assert "\u2022" in kanban_column._count_label.text()

    def test_show_loading_hides_load_older(self, kanban_column):
        kanban_column.show_loading()
        if kanban_column._load_older_widget:
            assert kanban_column._load_older_widget.isHidden()

    def test_show_error_clears_cards(self, kanban_column):
        kanban_column.set_trips([{"trip_id_num": 1}])
        kanban_column.show_error("Something went wrong")
        assert len(kanban_column._cards) == 0
        assert kanban_column._state == "error"

    def test_show_error_shows_widget(self, kanban_column):
        kanban_column.show_error("Something went wrong")
        assert kanban_column._error_widget.isVisible()
        assert kanban_column._loading_widget.isHidden()

    def test_show_error_sets_message(self, kanban_column):
        msg = "Network error: connection lost"
        kanban_column.show_error(msg)
        assert kanban_column._error_label.text() == msg

    def test_show_error_updates_count(self, kanban_column):
        kanban_column.show_error("err")
        assert "\u26a0" in kanban_column._count_label.text()

    def test_show_error_hides_load_older(self, kanban_column):
        kanban_column.show_error("err")
        if kanban_column._load_older_widget:
            assert kanban_column._load_older_widget.isHidden()

    def test_retry_button_triggers_callback(self, kanban_column):
        kanban_column.show_error("err")
        kanban_column._retry_btn.click()
        kanban_column._on_retry.assert_called_once()

    def test_load_older_button_triggers_callback(self, kanban_column):
        kanban_column._load_older_btn.click()
        kanban_column._on_load_older.assert_called_once()


# =========================================================================
# Drag-and-drop
# =========================================================================


class TestDragDrop:
    """Drag-and-drop event handling."""

    def test_drag_enter_accepts_text(self, kanban_column):
        mime = QMimeData()
        mime.setText("42")
        event = QDragEnterEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dragEnterEvent(event)
        assert event.isAccepted()

    def test_drag_enter_ignores_no_text(self, kanban_column):
        mime = QMimeData()
        event = QDragEnterEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dragEnterEvent(event)
        assert not event.isAccepted()

    def test_drag_move_accepts_text(self, kanban_column):
        mime = QMimeData()
        mime.setText("42")
        event = QDragMoveEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dragMoveEvent(event)
        assert event.isAccepted()

    def test_drag_move_ignores_no_text(self, kanban_column):
        mime = QMimeData()
        event = QDragMoveEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dragMoveEvent(event)
        assert not event.isAccepted()

    def test_drop_emits_tripDropped(self, kanban_column, qtbot):
        """Drop with valid int text emits tripDropped signal."""
        with qtbot.waitSignal(kanban_column.tripDropped, timeout=500) as blocker:
            mime = QMimeData()
            mime.setText("42")
            event = QDropEvent(
                kanban_column.pos(), Qt.CopyAction, mime,
                Qt.LeftButton, Qt.NoModifier,
            )
            kanban_column.dropEvent(event)
        assert blocker.args[0] == 42

    def test_drop_ignores_non_numeric(self, kanban_column):
        mime = QMimeData()
        mime.setText("not-a-number")
        event = QDropEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dropEvent(event)
        assert not event.isAccepted()

    def test_drop_ignores_no_text(self, kanban_column):
        mime = QMimeData()
        event = QDropEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dropEvent(event)
        assert not event.isAccepted()

    def test_drag_enter_highlights_valid(self, kanban_column, qtbot):
        mime = QMimeData()
        mime.setText("42")
        event = QDragEnterEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dragEnterEvent(event)
        # After drag enter, the column should have a stylesheet set
        assert "border" in (kanban_column.styleSheet() or "")

    def test_drag_leave_removes_highlight(self, kanban_column, qtbot):
        from PySide6.QtGui import QDragLeaveEvent

        # First trigger a drag enter to set highlight
        mime = QMimeData()
        mime.setText("42")
        enter_event = QDragEnterEvent(
            kanban_column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        kanban_column.dragEnterEvent(enter_event)
        assert kanban_column.styleSheet() != ""

        # Now leave event should clear it
        leave_event = QDragLeaveEvent()
        kanban_column.dragLeaveEvent(leave_event)
        assert kanban_column.styleSheet() == ""


# =========================================================================
# Highlight methods
# =========================================================================


class TestHighlight:
    """Drop-zone highlighting."""

    def test_highlight_drop_zone(self, kanban_column):
        kanban_column.highlight_drop_zone()
        ss = kanban_column.styleSheet()
        assert "border" in ss
        assert kanban_column.accent_color in ss

    def test_unhighlight_drop_zone(self, kanban_column):
        kanban_column.highlight_drop_zone()
        kanban_column.unhighlight_drop_zone()
        assert kanban_column.styleSheet() == ""

    def test_highlight_valid(self, kanban_column):
        kanban_column.highlight_valid()
        ss = kanban_column.styleSheet()
        assert "border" in ss

    def test_highlight_invalid(self, kanban_column):
        kanban_column.highlight_invalid()
        ss = kanban_column.styleSheet()
        assert "border" in ss


# =========================================================================
# refresh_title
# =========================================================================


class TestRefreshTitle:
    """Title refresh updates i18n strings."""

    def test_refresh_title_updates_title_label(self, kanban_column):
        kanban_column.refresh_title()
        assert kanban_column._title_label.text() is not None

    def test_refresh_title_updates_retry_button(self, kanban_column):
        kanban_column.refresh_title()
        assert kanban_column._retry_btn.text() is not None

    def test_refresh_title_updates_load_older(self, kanban_column):
        assert kanban_column._load_older_widget is not None
        kanban_column.refresh_title()
        assert kanban_column._load_older_btn.text() is not None


# =========================================================================
# Internal helpers
# =========================================================================


class TestInternalHelpers:
    """Internal helpers for layout indices and counts."""

    def test_card_layout_start_index(self, kanban_column):
        assert kanban_column._card_layout_start_index() == 2

    def test_update_count(self, kanban_column):
        kanban_column._update_count()
        assert "\u2022 0" in kanban_column._count_label.text()

    def test_clear_cards_removes_all(self, kanban_column, qt_trip_card):
        kanban_column.add_card(qt_trip_card)
        assert len(kanban_column._cards) == 1
        kanban_column._clear_cards()
        assert len(kanban_column._cards) == 0
        assert kanban_column._loading_widget.isHidden()
        assert kanban_column._error_widget.isHidden()


# =========================================================================
# destroy
# =========================================================================


class TestDestroy:
    """Cleanup nullifies callbacks and schedules deletion."""

    def test_destroy_clears_callbacks(self, kanban_column):
        kanban_column.destroy()
        assert kanban_column._on_card_click is None
        assert kanban_column._on_drag_start is None
        assert kanban_column._on_assign_truck is None
        assert kanban_column._on_assign_driver is None
        assert kanban_column._on_select_changed is None
        assert kanban_column._on_assign_both is None
        assert kanban_column._on_load_older is None
        assert kanban_column._on_retry is None

    def test_destroy_clears_cards(self, kanban_column):
        kanban_column.set_trips([{"trip_id_num": 1}])
        kanban_column.destroy()
        # After destroy, _cards should be empty
        assert len(kanban_column._cards) == 0


# =========================================================================
# Edge cases — callbacks None
# =========================================================================


class TestCallbacksNone:
    """Handles gracefully when callbacks are None."""

    def test_retry_without_callback(self, qt_widget, qtbot):
        from ui.widgets.kanban_column import QtKanbanColumn
        column = QtKanbanColumn(
            parent=qt_widget,
            status_key="Planned",
            title_key="x",
            on_retry=None,
        )
        qt_widget.show()
        column.show()
        qtbot.addWidget(column)
        column._handle_retry()  # must not crash
        column.destroy()

    def test_load_older_without_callback(self, qt_widget, qtbot):
        from ui.widgets.kanban_column import QtKanbanColumn
        column = QtKanbanColumn(
            parent=qt_widget,
            status_key="Planned",
            title_key="x",
            show_load_older=True,
            on_load_older=None,
        )
        qt_widget.show()
        column.show()
        qtbot.addWidget(column)
        column._handle_load_older()  # must not crash
        column.destroy()

    def test_set_trips_with_no_callbacks(self, qt_widget, qtbot):
        from ui.widgets.kanban_column import QtKanbanColumn
        column = QtKanbanColumn(
            parent=qt_widget,
            status_key="Planned",
            title_key="x",
        )
        qt_widget.show()
        column.show()
        qtbot.addWidget(column)
        column.set_trips([{"trip_id_num": 1, "client": "NoCB"}])
        assert len(column._cards) == 1
        column.destroy()


# =========================================================================
# Edge cases — empty / repeated operations
# =========================================================================


class TestEdgeCases:
    """Repeated or empty operations are safe."""

    def test_show_loading_twice(self, kanban_column):
        kanban_column.show_loading()
        kanban_column.show_loading()  # must not crash

    def test_show_error_twice(self, kanban_column):
        kanban_column.show_error("first")
        kanban_column.show_error("second")  # must not crash
        assert kanban_column._error_label.text() == "second"

    def test_clear_cards_when_empty(self, kanban_column):
        kanban_column._clear_cards()  # must not crash
        assert len(kanban_column._cards) == 0

    def test_set_trips_repeatedly(self, kanban_column):
        for i in range(5):
            kanban_column.set_trips([{"trip_id_num": i}])
        assert len(kanban_column._cards) == 1
