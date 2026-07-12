"""Tests for ``BoardStateMixin`` — pure logic + Qt integration.

Pure‑logic tests (no QApplication needed) verify data mapping, caching,
and stop-extraction logic.  The Qt integration section tests mixin
methods that interact with the GUI (error display, load-older, dispatch).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QStackedWidget, QWidget

from ui.views.dispatch_board.board_state import (
    BoardStateMixin,
    COLUMN_DEFS,
    STATUS_TO_COLUMN,
)


# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════


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


# ═════════════════════════════════════════════════════════════════════════════
# Instance-method logic (mocked Qt — no QApplication required)
# ═════════════════════════════════════════════════════════════════════════════


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


# ═════════════════════════════════════════════════════════════════════════════
# Qt integration — tests that need a QApplication / event loop
# ═════════════════════════════════════════════════════════════════════════════


class _QtBoardStateTestWidget(BoardStateMixin, QWidget):
    # Mixin must come before QWidget in MRO so that mixin methods
    # take priority over QWidget's defaults.
    """Minimal QWidget that combines with ``BoardStateMixin`` for Qt tests.

    Sets only the attributes the mixin methods under test actually read,
    avoiding the full ``QtDispatchBoardView`` initialisation.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Mixin-required state
        self._loading: bool = False
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

        self._board_stack = QStackedWidget(self)
        self._search_bar = MagicMock()
        self._alert_counts: dict[int, int] = {}
        self._all_card_data: list[dict[str, Any]] = []
        self._search_query: str = ""
        self._search_statuses: list[str] = []
        self._delivered_days: int = 30
        self._destroyed: bool = False
        self._status_cards: dict[str, Any] = {}

        # Service references (kept as None / mocked)
        self.ops = None
        self._trip_service = None
        self._fleet_repo = None
        self._driver_cache = {}
        self._route_cache = {}
        self._driver_repo = MagicMock()
        self._route_repo = MagicMock()

        # Cross-thread dispatch via direct call in test context.
        # In production this goes through a Signal so it runs on the GUI
        # thread.  For tests we call synchronously.
        self._dispatch = lambda fn: fn()

    # Stub methods used by QTimer.singleShot in _populate_columns that
    # are defined on the full QtDispatchBoardView (BoardActionsMixin +
    # other mixins) but not on this test widget alone.
    def _evaluate_all_delays(self) -> None:
        pass

    def _refresh_live_indicators(self) -> None:
        pass

    def _run_conflict_scan(self) -> None:
        pass

    def _refresh_side_panels(self) -> None:
        pass


@pytest.fixture
def qt_board_state(qtbot):
    """Create a ``_QtBoardStateTestWidget`` registered with ``qtbot``."""
    widget = _QtBoardStateTestWidget()
    qtbot.addWidget(widget)
    # Let any QTimer.singleShot callbacks settle
    qtbot.wait(50)
    yield widget


class TestBoardStateMixinWithQt:
    """Qt integration tests for ``BoardStateMixin`` methods that touch the GUI."""

    def test_initialization(self, qt_board_state):
        """Test widget initialises without crashing."""
        assert qt_board_state is not None
        assert qt_board_state._loading is False
        assert len(qt_board_state._columns) == 5

    def test_show_error_all(self, qt_board_state):
        """``_show_error_all`` calls ``show_error`` on every column."""
        qt_board_state._show_error_all("Test error")
        for col in qt_board_state._columns.values():
            col.show_error.assert_called_once_with("Test error")
        assert qt_board_state._loading is False

    def test_on_load_older_increases_days(self, qt_board_state):
        """``_on_load_older_delivered`` increments delivered_days by 30."""
        old = qt_board_state._delivered_days
        qt_board_state._on_load_older_delivered()
        assert qt_board_state._delivered_days == old + 30
        # Loading flag is immediately cleared because the synchronous
        # ``_dispatch`` mock runs ``_populate_columns`` inline.

    def test_tab_switch_alerts(self, qt_board_state):
        """Switching to the alerts tab calls alerts_panel.refresh."""
        qt_board_state._alerts_panel = MagicMock()
        qt_board_state._on_tab_switch("alerts")
        qt_board_state._alerts_panel.refresh.assert_called_once()

    def test_tab_switch_timeline(self, qt_board_state):
        """Switching to the timeline tab calls timeline.refresh."""
        qt_board_state._timeline = MagicMock()
        qt_board_state._on_tab_switch("timeline")
        qt_board_state._timeline.refresh.assert_called_once()

    def test_apply_filters_noop_with_empty_columns(self, qt_board_state):
        """``_apply_filters`` handles empty columns without crashing."""
        qt_board_state._apply_filters()
        # Should not raise

    def test_search_filter_updates_state(self, qt_board_state):
        """``_on_search_filter`` stores query and statuses."""
        with patch.object(qt_board_state, "_apply_filters") as mock_apply:
            qt_board_state._on_search_filter("test", ["Planned", "Loading"])
            assert qt_board_state._search_query == "test"
            assert qt_board_state._search_statuses == ["Planned", "Loading"]
            mock_apply.assert_called_once()
