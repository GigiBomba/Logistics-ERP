"""Tests for ``BoardActionsMixin`` pure logic (no QApplication required).

All Qt widget dependencies are mocked via ``unittest.mock.MagicMock`` so that
these tests can run without a display server or a running QApplication.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services.operations.event_bus import VALID_TRANSITIONS
from ui.views.dispatch_board.board_actions import BoardActionsMixin


# ── Helpers ──────────────────────────────────────────────────────────────────


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


# ── _is_trip_delayed ────────────────────────────────────────────────────────


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


# ── _evaluate_all_delays ────────────────────────────────────────────────────


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


# ── _handle_transition ──────────────────────────────────────────────────────


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


# ── _score_items ────────────────────────────────────────────────────────────


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
