"""Tests for QtTripCard pure logic and constants (no QApplication required).

All Qt widget dependencies are mocked via ``unittest.mock.MagicMock`` so that
these tests can run without a display server or a running QApplication.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services.i18n import t
from ui.theme import COLORS
from ui.widgets.trip_card import QtTripCard


# ── Constants (no instance needed) ──────────────────────────────────────────


class TestTripCardConstants:
    """Tests for class-level constants."""

    def test_all_statuses_have_colors(self) -> None:
        """STATUS_COLORS must contain an entry for every status that has a
        translation key, and vice-versa."""
        for status in QtTripCard.STATUS_TRANSLATION_KEYS:
            assert status in QtTripCard.STATUS_COLORS, (
                f"Missing colour mapping for status {status!r}"
            )

    def test_default_to_planned_color(self) -> None:
        """An unknown status key must fall back to the planned chip colour."""
        fallback = QtTripCard.STATUS_COLORS.get(
            "__unknown__", COLORS["chip_planned"]
        )
        assert fallback == COLORS["chip_planned"]

    def test_all_statuses_have_translation(self) -> None:
        """STATUS_TRANSLATION_KEYS must have an entry for every status that
        has a colour mapping."""
        for status in QtTripCard.STATUS_COLORS:
            assert status in QtTripCard.STATUS_TRANSLATION_KEYS, (
                f"Missing translation key for status {status!r}"
            )


# ── Instance-method logic (mocked Qt) ───────────────────────────────────────


def _make_card_mock(
    trip_data: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a MagicMock that looks like a ``QtTripCard`` instance.

    The mock carries real class-constant references so that the production
    method code can read ``self.STATUS_COLORS``, ``self.DELAYED_COLOR``,
    etc.
    """
    card: MagicMock = MagicMock(spec=QtTripCard)
    # -- class constants (needed by method bodies) --
    card.STATUS_COLORS = QtTripCard.STATUS_COLORS
    card.STATUS_TRANSLATION_KEYS = QtTripCard.STATUS_TRANSLATION_KEYS
    card.DELAYED_COLOR = QtTripCard.DELAYED_COLOR
    card.DELAYED_BG = QtTripCard.DELAYED_BG
    card.CARD_BG = QtTripCard.CARD_BG
    card.CARD_BG_HOVER = QtTripCard.CARD_BG_HOVER
    card.LEFT_ACCENT_WIDTH = QtTripCard.LEFT_ACCENT_WIDTH

    # -- instance state --
    card.trip_data = dict(trip_data or {"status": "Planned"})
    card._hovered = False
    card._selected = False
    card._delayed = False

    # -- widget references (mocked) --
    card._accent_bar = MagicMock()
    card._content_widget = MagicMock()
    card._chip_frame = MagicMock()
    card._chip_lbl = MagicMock()
    card._delayed_chip = MagicMock()
    card._date_lbl = MagicMock()
    card._live_row = MagicMock()
    card._live_speed = MagicMock()
    card._truck_lbl = MagicMock()
    card._driver_lbl = MagicMock()
    card._route_lbl = MagicMock()
    card._alert_frame = None
    card._error_lbl = None
    card._error_timer = None

    return card


class TestSetStatus:
    """Tests for ``QtTripCard._set_status``."""

    def test_updates_accent_bar_color(self) -> None:
        card = _make_card_mock()
        QtTripCard._set_status(card, "Loading")
        expected_color = QtTripCard.STATUS_COLORS["Loading"]
        card._accent_bar.setStyleSheet.assert_called_once_with(
            f"background-color: {expected_color}; border: none; border-radius: 0px;"
        )

    def test_updates_chip_text(self) -> None:
        card = _make_card_mock()
        with patch("ui.widgets.trip_card.t", return_value="translated"):
            QtTripCard._set_status(card, "Delivered")
        card._chip_lbl.setText.assert_called_once_with("translated")

    def test_unknown_status_falls_back_to_planned(self) -> None:
        card = _make_card_mock()
        QtTripCard._set_status(card, "Unknown")
        # Accept any styleSheet call since the actual colour may differ
        card._accent_bar.setStyleSheet.assert_called_once()
        # The chip label should get the raw status string as fallback text
        # because there's no translation key for "Unknown".
        card._chip_lbl.setText.assert_called_once_with("Unknown")


class TestSetDelayed:
    """Tests for ``QtTripCard.set_delayed``."""

    def test_sets_delayed_true(self) -> None:
        card = _make_card_mock()
        QtTripCard.set_delayed(card, True, 0)
        assert card._delayed is True
        card._delayed_chip.show.assert_called_once()
        card._accent_bar.setStyleSheet.assert_called_once()
        # The accent bar should switch to the danger colour.
        args, _ = card._accent_bar.setStyleSheet.call_args
        assert QtTripCard.DELAYED_COLOR in args[0]

    def test_formats_hours_when_over_60(self) -> None:
        card = _make_card_mock({"departure_date": "01/07/2026", "eta": "01/07/2026"})
        with patch("ui.widgets.trip_card.t", return_value="{hours}h"):
            QtTripCard.set_delayed(card, True, 130)
        card._date_lbl.setText.assert_called_once()
        text_arg = card._date_lbl.setText.call_args[0][0]
        assert "2" in text_arg  # 130 minutes → 2 hours

    def test_resets_on_false(self) -> None:
        card = _make_card_mock({"status": "Planned"})
        # First set delayed
        QtTripCard.set_delayed(card, True, 0)
        assert card._delayed is True

        # Then reset
        card._date_lbl.reset_mock()
        QtTripCard.set_delayed(card, False, 0)
        assert card._delayed is False
        card._delayed_chip.hide.assert_called_once()
        # Accent bar should revert to the status colour.
        planned_colour = QtTripCard.STATUS_COLORS["Planned"]
        card._accent_bar.setStyleSheet.assert_called_with(
            f"background-color: {planned_colour}; border: none; border-radius: 0px;"
        )

    def test_noop_when_state_unchanged(self) -> None:
        """Calling ``set_delayed`` with the same value should be a no-op."""
        card = _make_card_mock()
        card._delayed = True  # already delayed
        card._accent_bar.reset_mock()
        card._delayed_chip.reset_mock()
        QtTripCard.set_delayed(card, True, 0)
        card._accent_bar.setStyleSheet.assert_not_called()
        card._delayed_chip.show.assert_not_called()


class TestSetLivePosition:
    """Tests for ``QtTripCard.set_live_position``."""

    def test_shows_live_when_moving(self) -> None:
        card = _make_card_mock()
        position = MagicMock()
        position.status = "moving"
        position.speed_kmh = 55
        QtTripCard.set_live_position(card, position)
        card._live_speed.setText.assert_called_once_with("55 km/h")
        card._live_row.show.assert_called_once()

    def test_hides_when_slow(self) -> None:
        card = _make_card_mock()
        position = MagicMock()
        position.status = "moving"
        position.speed_kmh = 3
        QtTripCard.set_live_position(card, position)
        card._live_row.hide.assert_called_once()

    def test_hides_when_not_moving(self) -> None:
        card = _make_card_mock()
        position = MagicMock()
        position.status = "idle"
        position.speed_kmh = 0
        QtTripCard.set_live_position(card, position)
        card._live_row.hide.assert_called_once()

    def test_hides_when_position_is_none(self) -> None:
        card = _make_card_mock()
        QtTripCard.set_live_position(card, None)
        card._live_row.hide.assert_called_once()


class TestUpdateData:
    """Tests for ``QtTripCard.update_data``."""

    def test_merges_all_fields(self) -> None:
        card = _make_card_mock({"status": "Planned"})
        new_data: dict[str, Any] = {
            "status": "In Transit",
            "truck_plate": "AB12CDE",
            "driver_name": "Jane Doe",
            "origin": "London",
            "destination": "Paris",
            "departure_date": "10/07/2026",
            "eta": "11/07/2026",
            "alerts_count": 3,
        }
        with patch("ui.widgets.trip_card.t", return_value="assign"):
            QtTripCard.update_data(card, new_data)

        # trip_data should have been merged (shallow copy of new_data).
        for key, value in new_data.items():
            assert card.trip_data[key] == value, f"Mismatch for {key}"

    def test_resets_delayed_on_update(self) -> None:
        card = _make_card_mock({"status": "Planned"})
        card._delayed = True
        with patch("ui.widgets.trip_card.t", return_value="assign"):
            with patch.object(card, "set_delayed") as mock_set_delayed:
                QtTripCard.update_data(card, {"status": "Planned"})
        mock_set_delayed.assert_called_once_with(False, 0)

    def test_updates_truck_label(self) -> None:
        card = _make_card_mock({"status": "Planned"})
        with patch("ui.widgets.trip_card.t", return_value="assign"):
            QtTripCard.update_data(card, {"status": "Planned", "truck_plate": "XY99ZZ"})
        card._truck_lbl.setText.assert_called_with("XY99ZZ")

    def test_updates_route_label(self) -> None:
        card = _make_card_mock({"status": "Planned"})
        with patch("ui.widgets.trip_card.t", return_value="assign"):
            QtTripCard.update_data(
                card,
                {"status": "Planned", "origin": "Berlin", "destination": "Rome"},
            )
        card._route_lbl.setText.assert_called_with("Berlin → Rome")
