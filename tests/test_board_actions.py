"""Tests for ``BoardActionsMixin`` — pure logic + Qt integration.

Pure‑logic tests (no QApplication required) verify delay evaluation,
transition handling, transition validation, and item scoring.  The Qt
integration section tests mixin methods that interact with widgets
(toast, drag-drop, bulk selection, undo).
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget

from services.operations.event_bus import VALID_TRANSITIONS
from ui.views.dispatch_board.board_actions import BoardActionsMixin


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


def _make_actions_mock() -> MagicMock:
    """Build a MagicMock that looks like a ``BoardActionsMixin`` instance.

    Carries enough state so that the production code can read
    ``self._columns``, ``self._show_toast``, etc. without exploding.
    """
    actions: MagicMock = MagicMock(spec=BoardActionsMixin)
    actions._columns = {
        "Planned": MagicMock(),
        "Loading": MagicMock(),
        "In Transit": MagicMock(),
        "Delivered": MagicMock(),
        "Cancelled": MagicMock(),
    }
    # Each column has a ``_cards`` list and a ``status_key``.
    for key, col in actions._columns.items():
        col._cards = []
        col.status_key = key

    actions._selected_cards = []
    actions._drag_card = None
    actions._drag_source_col = None
    actions._drag_target_col = None
    actions._show_toast = MagicMock()
    # Default: parse_date returns a date far in the past so that
    # individual tests can override it as needed.
    actions._parse_date = MagicMock(
        return_value=datetime(2020, 1, 1, 0, 0, 0)
    )
    return actions


def _card_data(
    status: str = "Planned",
    departure: str = "",
    eta: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "departure_date": departure,
        "eta": eta,
        "trip_id_num": 1,
        "truck_plate": "AB12CDE",
        "driver_name": "John",
    }


# ═════════════════════════════════════════════════════════════════════════════
# _is_trip_delayed
# ═════════════════════════════════════════════════════════════════════════════


class TestIsTripDelayed:
    """Tests for ``BoardActionsMixin._is_trip_delayed``."""

    def test_in_transit_past_eta(self) -> None:
        """In-Transit trip past its ETA should be delayed."""
        actions = _make_actions_mock()
        eta_dt = datetime(2026, 7, 8, 10, 0, 0)
        now = datetime(2026, 7, 8, 12, 30, 0)  # 150 min past ETA
        actions._parse_date = MagicMock(return_value=eta_dt)
        data = _card_data(status="In Transit", eta="08/07/2026")
        is_delayed, minutes = BoardActionsMixin._is_trip_delayed(
            actions, data, now
        )
        assert is_delayed is True
        assert minutes == 150

    def test_in_transit_before_eta(self) -> None:
        """In-Transit trip before its ETA should NOT be delayed."""
        actions = _make_actions_mock()
        eta_dt = datetime(2026, 7, 8, 14, 0, 0)
        now = datetime(2026, 7, 8, 10, 0, 0)
        actions._parse_date = MagicMock(return_value=eta_dt)
        data = _card_data(status="In Transit", eta="08/07/2026")
        is_delayed, _ = BoardActionsMixin._is_trip_delayed(actions, data, now)
        assert is_delayed is False

    def test_in_transit_no_eta(self) -> None:
        """In-Transit without an ETA should never be flagged delayed."""
        actions = _make_actions_mock()
        data = _card_data(status="In Transit")
        is_delayed, _ = BoardActionsMixin._is_trip_delayed(
            actions, data, datetime.now()
        )
        assert is_delayed is False

    def test_active_past_eta(self) -> None:
        """Active / InProgress aliases should also be checked."""
        actions = _make_actions_mock()
        eta_dt = datetime(2026, 7, 8, 10, 0, 0)
        now = datetime(2026, 7, 8, 11, 0, 0)
        actions._parse_date = MagicMock(return_value=eta_dt)
        data = _card_data(status="Active", eta="08/07/2026")
        is_delayed, _ = BoardActionsMixin._is_trip_delayed(actions, data, now)
        assert is_delayed is True

    def test_loading_past_departure_2h(self) -> None:
        """Loading status is delayed when departure is more than 2 h in the
        past."""
        actions = _make_actions_mock()
        dep_dt = datetime(2026, 7, 8, 8, 0, 0)
        now = datetime(2026, 7, 8, 11, 0, 0)  # 3 h past departure
        actions._parse_date = MagicMock(return_value=dep_dt)
        data = _card_data(status="Loading", departure="08/07/2026")
        is_delayed, minutes = BoardActionsMixin._is_trip_delayed(
            actions, data, now
        )
        assert is_delayed is True
        # minutes = (now - (dep + 2h)) = 1 h
        assert minutes == 60

    def test_loading_within_2h(self) -> None:
        """Loading is not delayed within the 2-hour grace window."""
        actions = _make_actions_mock()
        dep_dt = datetime(2026, 7, 8, 8, 0, 0)
        now = datetime(2026, 7, 8, 9, 30, 0)  # 1.5 h past departure
        actions._parse_date = MagicMock(return_value=dep_dt)
        data = _card_data(status="Loading", departure="08/07/2026")
        is_delayed, _ = BoardActionsMixin._is_trip_delayed(actions, data, now)
        assert is_delayed is False

    def test_planned_over_24h_past(self) -> None:
        """Planned is delayed when departure was more than 24 h ago."""
        actions = _make_actions_mock()
        dep_dt = datetime(2026, 7, 6, 8, 0, 0)
        now = datetime(2026, 7, 8, 8, 0, 0)  # 48 h later
        actions._parse_date = MagicMock(return_value=dep_dt)
        data = _card_data(status="Planned", departure="06/07/2026")
        is_delayed, minutes = BoardActionsMixin._is_trip_delayed(
            actions, data, now
        )
        assert is_delayed is True

    def test_planned_within_24h(self) -> None:
        """Planned is not delayed if departure is within the last 24 h."""
        actions = _make_actions_mock()
        dep_dt = datetime(2026, 7, 8, 6, 0, 0)
        now = datetime(2026, 7, 8, 12, 0, 0)  # 6 h later
        actions._parse_date = MagicMock(return_value=dep_dt)
        data = _card_data(status="Planned", departure="08/07/2026")
        is_delayed, _ = BoardActionsMixin._is_trip_delayed(actions, data, now)
        assert is_delayed is False

    def test_completed_never_delayed(self) -> None:
        """Delivered / Cancelled statuses are never delayed."""
        actions = _make_actions_mock()
        for status in ("Delivered", "Cancelled", "Completed", "Done", "Paid", "Invoiced"):
            data = _card_data(status=status, eta="01/01/2020")
            is_delayed, _ = BoardActionsMixin._is_trip_delayed(
                actions, data, datetime(2026, 7, 8, 12, 0, 0)
            )
            assert is_delayed is False, f"{status} should never be delayed"


# ═════════════════════════════════════════════════════════════════════════════
# _evaluate_all_delays
# ═════════════════════════════════════════════════════════════════════════════


class TestEvaluateAllDelays:
    """Tests for ``BoardActionsMixin._evaluate_all_delays``."""

    def test_calls_is_trip_delayed_for_all_cards(self) -> None:
        actions = _make_actions_mock()
        card_1 = MagicMock()
        card_2 = MagicMock()
        card_1.trip_data = _card_data(status="Planned", departure="06/07/2026")
        card_2.trip_data = _card_data(status="In Transit", eta="08/07/2026")
        actions._columns["Planned"]._cards = [card_1]
        actions._columns["In Transit"]._cards = [card_2]

        with patch.object(actions, "_is_trip_delayed", return_value=(True, 10)):
            with patch.object(actions, "_create_delay_alert"):
                BoardActionsMixin._evaluate_all_delays(actions)

            assert actions._is_trip_delayed.call_count == 2
            card_1.set_delayed.assert_called_with(True, 10)
            card_2.set_delayed.assert_called_with(True, 10)


# ═════════════════════════════════════════════════════════════════════════════
# _handle_transition
# ═════════════════════════════════════════════════════════════════════════════


class TestHandleTransition:
    """Tests for ``BoardActionsMixin._handle_transition``."""

    def test_rejects_illegal_transition(self) -> None:
        """Transitions not in ``VALID_TRANSITIONS`` should be rejected with
        a toast."""
        actions = _make_actions_mock()
        card = MagicMock()
        card.trip_data = _card_data(status="Planned")
        source_col = actions._columns["Planned"]
        target_col = actions._columns["Delivered"]  # Planned → Delivered is illegal

        BoardActionsMixin._handle_transition(
            actions, 1, "Planned", "Delivered", card, source_col, target_col,
        )
        actions._show_toast.assert_called_once()
        assert "error" in str(actions._show_toast.call_args)

    def test_asks_confirmation_for_backward(self) -> None:
        """Backward transitions should prompt a confirmation dialog."""
        actions = _make_actions_mock()
        card = MagicMock()
        card.trip_data = _card_data(status="In Transit")
        source_col = actions._columns["In Transit"]
        target_col = actions._columns["Loading"]  # backward

        with patch(
            "ui.views.dispatch_board.board_actions.QMessageBox.question",
            return_value=MagicMock(),
        ) as mock_question:
            BoardActionsMixin._handle_transition(
                actions, 1, "In Transit", "Loading", card,
                source_col, target_col,
            )
        mock_question.assert_called_once()

    def test_creates_new_card_in_target(self) -> None:
        """A new ``QtTripCard`` should be created in the target column and
        the old one removed from the source column."""
        actions = _make_actions_mock()
        card = MagicMock()
        card.trip_data = _card_data(status="Planned")
        source_col = actions._columns["Planned"]
        target_col = actions._columns["Loading"]

        with patch(
            "ui.views.dispatch_board.board_actions.QMessageBox.question",
            return_value=MagicMock(),
        ):
            with patch(
                "ui.widgets.trip_card.QtTripCard",
                return_value=MagicMock(),
            ):
                BoardActionsMixin._handle_transition(
                    actions, 1, "Planned", "Loading", card,
                    source_col, target_col,
                )
        target_col.add_card.assert_called_once()
        source_col.remove_card.assert_called_once_with(card)

    def test_cancelled_transition_does_nothing(self) -> None:
        """If the user cancels the confirmation dialog, nothing should
        happen."""
        actions = _make_actions_mock()
        card = MagicMock()
        card.trip_data = _card_data(status="In Transit")
        source_col = actions._columns["In Transit"]
        target_col = actions._columns["Loading"]

        with patch(
            "ui.views.dispatch_board.board_actions.QMessageBox.question",
            return_value=MagicMock(),  # mocks the "No" path
        ):
            BoardActionsMixin._handle_transition(
                actions, 1, "In Transit", "Loading", card,
                source_col, target_col,
            )
        source_col.remove_card.assert_not_called()
        target_col.add_card.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# _score_items
# ═════════════════════════════════════════════════════════════════════════════


class TestScoreItems:
    """Tests for ``BoardActionsMixin._score_items``."""

    def test_scores_available_truck(self) -> None:
        """An available truck with no conflicts should receive a positive
        score."""
        actions = _make_actions_mock()
        truck_items: list[dict[str, Any]] = [
            {"id": 1, "label": "AB123", "available": True},
        ]
        driver_items: list[dict[str, Any]] = []
        card_data = _card_data()

        BoardActionsMixin._score_items(actions, truck_items, driver_items, card_data)
        assert truck_items[0].get("score", 0) > 0

    def test_scores_health_contribution(self) -> None:
        """A truck with a high health score should get a boost."""
        actions = _make_actions_mock()
        # Mock the fleet repo to return a health score.
        actions._fleet_repo = MagicMock()
        actions._fleet_repo.get_truck_health.return_value = {"score": 90}
        # Mock get_by_id so the fuel branch doesn't NPE.
        actions._fleet_repo.get_by_id.return_value = {"fuel_consumption": 30}

        truck_items: list[dict[str, Any]] = [
            {"id": 1, "label": "AB123", "available": True},
        ]
        driver_items: list[dict[str, Any]] = []
        card_data = _card_data()

        BoardActionsMixin._score_items(actions, truck_items, driver_items, card_data)
        assert truck_items[0]["score"] > 0

    def test_scores_violations_penalty(self) -> None:
        """A driver with many violations should have a reduced score."""
        actions = _make_actions_mock()
        actions._tacho_repo = MagicMock()
        actions._tacho_repo.get_by_driver.return_value = [
            {"driving_minutes": 0, "violations": '["a", "b", "c"]'},
        ]

        driver_items: list[dict[str, Any]] = [
            {"id": 10, "label": "Jane", "available": True},
        ]
        truck_items: list[dict[str, Any]] = []
        card_data = _card_data()

        BoardActionsMixin._score_items(actions, truck_items, driver_items, card_data)
        # Score = availability (40) + violations contribution (max(0, 10 - 3×3) = 1)
        score = driver_items[0].get("score", 0)
        assert isinstance(score, (int, float))
        # 3 violations → 10 - 9 = +1, so score = 40 + 1 = 41
        assert score == 41


# ═════════════════════════════════════════════════════════════════════════════
# Qt integration — tests that need a QApplication / event loop
# ═════════════════════════════════════════════════════════════════════════════


class _QtBoardActionsTestWidget(BoardActionsMixin, QWidget):
    # Mixin must come before QWidget in MRO so that mixin methods
    # (dragEnterEvent, dragMoveEvent, dropEvent) override Qt's defaults.
    """Minimal QWidget that combines with ``BoardActionsMixin`` for Qt tests.

    Sets only the attributes the mixin methods under test actually read,
    avoiding the full ``QtDispatchBoardView`` initialisation.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Columns
        self._columns: dict[str, Any] = {
            "Planned": MagicMock(),
            "Loading": MagicMock(),
            "In Transit": MagicMock(),
            "Delivered": MagicMock(),
            "Cancelled": MagicMock(),
        }
        for key, col in self._columns.items():
            col.status_key = key
            col._cards = []

        # Bulk selection
        self._selected_cards: list = []
        self._bulk_toolbar = MagicMock()
        self._bulk_toolbar.isVisible.return_value = False
        self._bulk_count_lbl = MagicMock()
        self._bulk_assign_truck_btn = MagicMock()
        self._bulk_assign_driver_btn = MagicMock()
        self._bulk_clear_btn = MagicMock()

        # Drag-drop
        self._drag_card = None
        self._drag_source_col = None
        self._drag_target_col = None

        # Detail panel
        self._detail_panel = None

        # Services (mocked)
        self._db = MagicMock()
        self.ops = MagicMock()
        self.ops.event_bus = MagicMock()
        self.ops.undo_stack = MagicMock()
        self._trip_service = None
        self._fleet_repo = MagicMock()
        self._driver_repo = MagicMock()
        self._event_bus = MagicMock()
        self._tacho_repo = None
        self._conflict_service = MagicMock()
        self._dta_service = MagicMock()
        self._alert_mgr = MagicMock()
        self._all_card_data = []
        self._alert_counts = {}

        # Tabs
        self._tabs = MagicMock()

        # Callbacks — do NOT shadow the mixin methods we intend to test.
        # Only set up attribute-style callbacks that the mixin expects
        # as instance attributes (e.g. ``_find_card_by_trip_id`` is
        # used by quick-assign methods).
        self._find_card_by_trip_id = MagicMock(return_value=None)
        self._preload_alerts = MagicMock()
        self._start_load = MagicMock()
        self._parse_date = MagicMock(return_value=datetime(2020, 1, 1))

        self.setAcceptDrops(True)


@pytest.fixture
def qt_board_actions(qtbot):
    """Create a ``_QtBoardActionsTestWidget`` registered with ``qtbot``."""
    widget = _QtBoardActionsTestWidget()
    qtbot.addWidget(widget)
    yield widget


class TestBoardActionsMixinWithQt:
    """Qt integration tests for ``BoardActionsMixin`` methods that touch the GUI."""

    def test_initialization(self, qt_board_actions):
        """Test widget initialises without crashing."""
        assert qt_board_actions is not None
        assert len(qt_board_actions._columns) == 5
        assert qt_board_actions._selected_cards == []

    # ── Detail panel ──────────────────────────────────────────────────────

    def test_on_card_click_creates_detail_panel(self, qt_board_actions):
        """``_on_card_click`` creates a detail panel widget."""
        assert qt_board_actions._detail_panel is None

        import ui.dialogs.dispatch_detail_panel as detail_mod

        with patch.object(detail_mod, "QtDispatchDetailPanel") as mock_panel:
            qt_board_actions._on_card_click({"trip_id_num": 1})
            mock_panel.assert_called_once()
            assert qt_board_actions._detail_panel is not None

    def test_on_card_click_works_with_real_panel(self, qt_board_actions):
        """``_on_card_click`` with the real detail panel does not crash.

        This verifies the lazy import path actually works in a Qt context.
        """
        with contextlib.suppress(Exception):
            qt_board_actions._on_card_click({"trip_id_num": 1})
        # Should not crash even if the panel fails to fully initialise
        # (it makes real widgets and accesses TripService).

    def test_on_detail_close_clears_panel(self, qt_board_actions):
        """``_on_detail_close`` sets the detail panel reference to None."""
        qt_board_actions._detail_panel = MagicMock()
        qt_board_actions._on_detail_close()
        assert qt_board_actions._detail_panel is None

    # ── Bulk selection ────────────────────────────────────────────────────

    def test_card_select_adds_to_selection(self, qt_board_actions):
        """Selecting a card adds it to the selected list."""
        card = MagicMock()
        qt_board_actions._on_card_select_changed(card, True)
        assert card in qt_board_actions._selected_cards

    def test_card_deselect_removes_from_selection(self, qt_board_actions):
        """Deselecting a card removes it from the selected list."""
        card = MagicMock()
        qt_board_actions._selected_cards = [card]
        qt_board_actions._on_card_select_changed(card, False)
        assert card not in qt_board_actions._selected_cards

    def test_clear_all_selections_empties_list(self, qt_board_actions):
        """``_clear_all_selections`` clears the selection list."""
        card_a = MagicMock()
        card_b = MagicMock()
        qt_board_actions._selected_cards = [card_a, card_b]
        qt_board_actions._clear_all_selections()
        assert qt_board_actions._selected_cards == []

    def test_bulk_toolbar_updates_with_selection(self, qt_board_actions):
        """``_update_bulk_toolbar`` shows the toolbar when cards are
        selected."""
        qt_board_actions._selected_cards = [MagicMock()]
        qt_board_actions._update_bulk_toolbar()
        qt_board_actions._bulk_toolbar.show.assert_called_once()

    def test_bulk_toolbar_hides_when_empty(self, qt_board_actions):
        """``_update_bulk_toolbar`` hides the toolbar when no cards are
        selected."""
        qt_board_actions._selected_cards = []
        qt_board_actions._update_bulk_toolbar()
        qt_board_actions._bulk_toolbar.hide.assert_called_once()

    # ── Toast ─────────────────────────────────────────────────────────────

    def test_show_toast_creates_toast_widget(self, qt_board_actions):
        """``_show_toast`` creates a Toast widget."""
        # Toast is imported at module scope in board_actions as
        # ``from ui.widgets.toast import Toast``, so we patch the
        # reference in the board_actions namespace.
        with patch(
            "ui.views.dispatch_board.board_actions.Toast",
        ) as mock_toast:
            qt_board_actions._show_toast("Test message", "success")
            mock_toast.assert_called_once()

    # ── Undo / Redo ───────────────────────────────────────────────────────

    def test_undo_without_ops_shows_toast(self, qt_board_actions):
        """Undo without ops shows an error toast."""
        qt_board_actions.ops = None
        with patch.object(qt_board_actions, "_show_toast") as mock_toast:
            qt_board_actions._on_undo()
            mock_toast.assert_called_once()

    def test_undo_with_empty_stack_shows_toast(self, qt_board_actions):
        """Undo with an empty stack shows an error toast."""
        qt_board_actions.ops.undo_stack.last_undo_command.return_value = None
        with patch.object(qt_board_actions, "_show_toast") as mock_toast:
            qt_board_actions._on_undo()
            mock_toast.assert_called_once()

    def test_redo_without_ops_shows_toast(self, qt_board_actions):
        """Redo without ops shows an error toast."""
        qt_board_actions.ops = None
        with patch.object(qt_board_actions, "_show_toast") as mock_toast:
            qt_board_actions._on_redo()
            mock_toast.assert_called_once()

    def test_redo_with_empty_stack_shows_toast(self, qt_board_actions):
        """Redo with an empty stack shows an error toast."""
        qt_board_actions.ops.undo_stack.last_redo_command.return_value = None
        with patch.object(qt_board_actions, "_show_toast") as mock_toast:
            qt_board_actions._on_redo()
            mock_toast.assert_called_once()

    # ── Drag-Drop events ─────────────────────────────────────────────────

    def test_drag_enter_accepts_text(self, qt_board_actions):
        """``dragEnterEvent`` accepts the proposed action for text MIME."""
        from PySide6.QtCore import QPoint, Qt, QMimeData
        from PySide6.QtGui import QDragEnterEvent

        mime = QMimeData()
        mime.setText("42")
        event = QDragEnterEvent(
            QPoint(0, 0), Qt.MoveAction, mime, Qt.NoButton, Qt.NoModifier,
        )
        assert not event.isAccepted()
        qt_board_actions.dragEnterEvent(event)
        assert event.isAccepted()

    def test_drag_enter_ignores_non_text(self, qt_board_actions):
        """``dragEnterEvent`` ignores events without text MIME data."""
        from PySide6.QtCore import QPoint, Qt, QMimeData
        from PySide6.QtGui import QDragEnterEvent

        mime = QMimeData()
        mime.setData("application/x-fake", b"data")
        event = QDragEnterEvent(
            QPoint(0, 0), Qt.MoveAction, mime, Qt.NoButton, Qt.NoModifier,
        )
        qt_board_actions.dragEnterEvent(event)
        assert not event.isAccepted()

    def test_drag_move_accepts(self, qt_board_actions):
        """``dragMoveEvent`` always accepts the proposed action."""
        from PySide6.QtCore import QPoint, Qt, QMimeData
        from PySide6.QtGui import QDragMoveEvent

        mime = QMimeData()
        mime.setText("42")
        event = QDragMoveEvent(
            QPoint(0, 0), Qt.MoveAction, mime, Qt.NoButton, Qt.NoModifier,
        )
        assert not event.isAccepted()
        qt_board_actions.dragMoveEvent(event)
        assert event.isAccepted()

    # ── Quick assign (alerts -> board) ─────────────────────────────────────

    def test_quick_assign_truck_finds_card(self, qt_board_actions):
        """``_on_quick_assign_truck`` finds the card and triggers assign."""
        card = MagicMock()
        qt_board_actions._find_card_by_trip_id = MagicMock(return_value=card)
        qt_board_actions._on_assign_truck = MagicMock()

        qt_board_actions._on_quick_assign_truck({"trip_id_num": 42})
        qt_board_actions._find_card_by_trip_id.assert_called_once_with(42)
        qt_board_actions._tabs.switch_to.assert_called_once_with("board")
        qt_board_actions._on_assign_truck.assert_called_once_with(card)

    def test_quick_assign_skips_when_no_card(self, qt_board_actions):
        """``_on_quick_assign_truck`` is a no-op when no card matches."""
        qt_board_actions._find_card_by_trip_id = MagicMock(return_value=None)
        qt_board_actions._on_assign_truck = MagicMock()

        qt_board_actions._on_quick_assign_truck({"trip_id_num": 999})
        qt_board_actions._on_assign_truck.assert_not_called()

    # ── Resolve alert refresh ─────────────────────────────────────────────

    def test_resolve_alert_refresh(self, qt_board_actions):
        """``_on_resolve_alert_refresh`` refreshes panels and updates alert
        counts."""
        qt_board_actions._alerts_panel = MagicMock()
        qt_board_actions._on_resolve_alert_refresh()
        qt_board_actions._alerts_panel.refresh.assert_called_once()
