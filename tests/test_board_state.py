"""Tests for ``BoardStateMixin`` pure logic (no QApplication required).

All Qt widget dependencies are mocked via ``unittest.mock.MagicMock`` so that
these tests can run without a display server or a running QApplication.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ui.views.dispatch_board.board_state import (
    BoardStateMixin,
    COLUMN_DEFS,
    STATUS_TO_COLUMN,
)


# ── Constants ────────────────────────────────────────────────────────────────


class TestStatusToColumn:
    """Tests for the ``STATUS_TO_COLUMN`` mapping."""

    def test_maps_standard_statuses(self) -> None:
        """Well-known statuses map to themselves."""
        for status in ("Planned", "Loading", "In Transit", "Delivered", "Cancelled"):
            assert STATUS_TO_COLUMN.get(status) == status, (
                f"Expected {status!r} to map to itself"
            )

    def test_maps_aliases(self) -> None:
        """Alias statuses map to their canonical column name."""
        assert STATUS_TO_COLUMN.get("Scheduled") == "Planned"
        assert STATUS_TO_COLUMN.get("Pending") == "Planned"
        assert STATUS_TO_COLUMN.get("Preparing") == "Loading"
        assert STATUS_TO_COLUMN.get("Pickup") == "Loading"
        assert STATUS_TO_COLUMN.get("InTransit") == "In Transit"
        assert STATUS_TO_COLUMN.get("Active") == "In Transit"
        assert STATUS_TO_COLUMN.get("InProgress") == "In Transit"
        assert STATUS_TO_COLUMN.get("Completed") == "Delivered"
        assert STATUS_TO_COLUMN.get("Done") == "Delivered"
        assert STATUS_TO_COLUMN.get("Invoiced") == "Delivered"
        assert STATUS_TO_COLUMN.get("Paid") == "Delivered"

    def test_unknown_status_returns_none(self) -> None:
        """An unmapped status should return ``None`` via ``.get()``."""
        assert STATUS_TO_COLUMN.get("__bogus__") is None


class TestColumnDefs:
    """Tests for the ``COLUMN_DEFS`` constant."""

    def test_includes_all_canonical_statuses(self) -> None:
        """Every canonical column appears in ``COLUMN_DEFS``."""
        statuses_in_defs = {entry[0] for entry in COLUMN_DEFS}
        for status in ("Planned", "Loading", "In Transit", "Delivered", "Cancelled"):
            assert status in statuses_in_defs


# ── Instance-method logic (mocked Qt) ───────────────────────────────────────


def _make_state_mock() -> MagicMock:
    """Build a MagicMock that looks like a ``BoardStateMixin`` instance.

    The mock carries real class-constant references and pre-populated caches
    so that the production method code can read ``self._driver_cache``,
    ``self._route_cache``, etc.
    """
    state: MagicMock = MagicMock(spec=BoardStateMixin)
    state._driver_cache = {}
    state._route_cache = {}
    state._alert_counts = {}
    state._driver_repo = MagicMock()
    state._route_repo = MagicMock()
    return state


# ── _build_card_data ────────────────────────────────────────────────────────


class TestBuildCardData:
    """Tests for ``BoardStateMixin._build_card_data``."""

    def test_builds_with_resolved_driver(self) -> None:
        """When a trip has a ``driver_id`` but no ``driver_name``, the mixin
        should resolve the name via the driver repo."""
        state = _make_state_mock()
        state._resolve_driver_name = MagicMock(return_value="Resolved Name")
        state._resolve_route = MagicMock(return_value=("", ""))

        trip: dict[str, Any] = {
            "id": 42,
            "status": "Planned",
            "driver_id": 99,
            "driver_name": "",
            "truck_number": "AB123",
        }
        with patch("ui.views.dispatch_board.board_state.t", return_value="T"):
            card_data = BoardStateMixin._build_card_data(state, trip)
        state._resolve_driver_name.assert_called_once_with(99)
        assert card_data["driver_name"] == "Resolved Name"
        assert card_data["trip_id_num"] == 42

    def test_builds_with_resolved_route(self) -> None:
        """When a trip has a ``route_history_v2_id``, the mixin should resolve
        origin/destination via the route repo."""
        state = _make_state_mock()
        state._resolve_route = MagicMock(return_value=("Berlin", "Paris"))

        trip: dict[str, Any] = {
            "id": 7,
            "status": "In Transit",
            "route_history_v2_id": 101,
        }
        with patch("ui.views.dispatch_board.board_state.t", return_value="T"):
            card_data = BoardStateMixin._build_card_data(state, trip)
        state._resolve_route.assert_called_once_with(trip)
        assert card_data["origin"] == "Berlin"
        assert card_data["destination"] == "Paris"

    def test_builds_with_alerts_count(self) -> None:
        """The returned dict should include the pre-loaded alert count."""
        state = _make_state_mock()
        state._alert_counts = {1: 3, 2: 0}
        state._resolve_driver_name = MagicMock(return_value="")
        state._resolve_route = MagicMock(return_value=("", ""))

        trip: dict[str, Any] = {"id": 1, "status": "Loading"}
        with patch("ui.views.dispatch_board.board_state.t", return_value="T"):
            card_data = BoardStateMixin._build_card_data(state, trip)
        assert card_data["alerts_count"] == 3

    def test_builds_with_zero_alerts_when_missing(self) -> None:
        """A trip with no alert entries gets zero for alerts_count."""
        state = _make_state_mock()
        state._alert_counts = {}
        state._resolve_driver_name = MagicMock(return_value="")
        state._resolve_route = MagicMock(return_value=("", ""))

        trip: dict[str, Any] = {"id": 999, "status": "Cancelled"}
        with patch("ui.views.dispatch_board.board_state.t", return_value="T"):
            card_data = BoardStateMixin._build_card_data(state, trip)
        assert card_data["alerts_count"] == 0


# ── _resolve_driver_name ────────────────────────────────────────────────────


class TestResolveDriverName:
    """Tests for ``BoardStateMixin._resolve_driver_name``."""

    def test_cache_hit_returns_cached(self) -> None:
        state = _make_state_mock()
        state._driver_cache[42] = {"name": "Cached Driver"}
        result = BoardStateMixin._resolve_driver_name(state, 42)
        assert result == "Cached Driver"
        state._driver_repo.get_by_id.assert_not_called()

    def test_cache_hit_none_returns_empty(self) -> None:
        """A cached ``None`` value should result in an empty string."""
        state = _make_state_mock()
        state._driver_cache[42] = None
        result = BoardStateMixin._resolve_driver_name(state, 42)
        assert result == ""

    def test_repo_call_on_miss(self) -> None:
        state = _make_state_mock()
        state._driver_repo.get_by_id.return_value = {"name": "Repo Driver"}
        result = BoardStateMixin._resolve_driver_name(state, 99)
        state._driver_repo.get_by_id.assert_called_once_with(99)
        assert result == "Repo Driver"
        assert state._driver_cache[99] == {"name": "Repo Driver"}

    def test_repo_returns_none(self) -> None:
        """When the repo returns ``None``, cache it and return empty string."""
        state = _make_state_mock()
        state._driver_repo.get_by_id.return_value = None
        result = BoardStateMixin._resolve_driver_name(state, 55)
        assert result == ""
        assert state._driver_cache[55] is None


# ── _resolve_route ──────────────────────────────────────────────────────────


class TestResolveRoute:
    """Tests for ``BoardStateMixin._resolve_route``."""

    def test_cache_hit_returns_cached(self) -> None:
        state = _make_state_mock()
        state._route_cache["10"] = {"origin": "Madrid", "destination": "Barcelona"}
        trip = {"route_history_v2_id": 10}
        origin, dest = BoardStateMixin._resolve_route(state, trip)
        assert origin == "Madrid"
        assert dest == "Barcelona"
        state._route_repo.get_by_id.assert_not_called()

    def test_cache_hit_none_returns_empty(self) -> None:
        state = _make_state_mock()
        state._route_cache["10"] = None
        trip = {"route_history_v2_id": 10}
        origin, dest = BoardStateMixin._resolve_route(state, trip)
        assert origin == ""
        assert dest == ""

    def test_no_route_id_returns_empty(self) -> None:
        state = _make_state_mock()
        trip: dict[str, Any] = {}
        origin, dest = BoardStateMixin._resolve_route(state, trip)
        assert origin == ""
        assert dest == ""


# ── _extract_stops ──────────────────────────────────────────────────────────


class TestExtractStops:
    """Tests for ``BoardStateMixin._extract_stops``."""

    def test_from_route_summary_json(self) -> None:
        """If the route has a ``route_summary_json`` key, use it."""
        state = _make_state_mock()
        route: dict[str, Any] = {
            "route_summary_json": '{"origin": "London", "destination": "Dover"}',
        }
        origin, dest = BoardStateMixin._extract_stops(state, route)
        assert origin == "London"
        assert dest == "Dover"

    def test_from_route_summary_json_dict(self) -> None:
        """The summary may already be a parsed dict."""
        state = _make_state_mock()
        route: dict[str, Any] = {
            "route_summary_json": {"origin": "Lyon", "destination": "Marseille"},
        }
        origin, dest = BoardStateMixin._extract_stops(state, route)
        assert origin == "Lyon"
        assert dest == "Marseille"

    def test_from_stops_list(self) -> None:
        """Fall back to ``stops_json`` when there is no summary."""
        state = _make_state_mock()
        stops_json = json.dumps([
            {"address": "Warsaw"},
            {"address": "somewhere"},
            {"address": "Krakow"},
        ])
        route: dict[str, Any] = {"stops_json": stops_json}
        origin, dest = BoardStateMixin._extract_stops(state, route)
        assert origin == "Warsaw"
        assert dest == "Krakow"

    def test_from_stops_list_array_with_label(self) -> None:
        """``stops_json`` entries may use ``label`` instead of ``address``."""
        state = _make_state_mock()
        stops_json = json.dumps([
            {"label": "Amsterdam"},
            {"label": "Rotterdam"},
        ])
        route: dict[str, Any] = {"stops_json": stops_json}
        origin, dest = BoardStateMixin._extract_stops(state, route)
        assert origin == "Amsterdam"
        assert dest == "Rotterdam"

    def test_empty_when_no_data(self) -> None:
        """Both origin and destination should be empty when there is no
        stop data at all."""
        state = _make_state_mock()
        route: dict[str, Any] = {}
        origin, dest = BoardStateMixin._extract_stops(state, route)
        assert origin == ""
        assert dest == ""
