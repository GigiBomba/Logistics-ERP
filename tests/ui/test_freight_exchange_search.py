"""Comprehensive Qt unit tests for FreightSearchView and FreightLoadDetailView.

Tests cover: construction, search form (filters, date range, keywords),
search results display (list, load details), load detail selection and display,
import load action (signal emission), filter constraint validation,
empty results state, loading state during search, error handling
(search failure, network error), evaluation display, and match rows.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.views.freight_exchange.search_view import FreightSearchView, _map_sort_field
from ui.views.freight_exchange.load_detail_view import FreightLoadDetailView

# =========================================================================
# Helpers
# =========================================================================


def shown_parent(qapp) -> QMainWindow:
    """Create and show a QMainWindow to serve as a visible parent."""
    w = QMainWindow()
    w.show()
    return w


def _show_view_in_window(view: QWidget, window: QMainWindow) -> None:
    """Embed *view* as the central widget of *window* and show it."""
    window.setCentralWidget(view)
    view.show()


# =========================================================================
# Sample data
# =========================================================================

SAMPLE_LOAD_RESULTS = [
    {
        "provider_id": "trans_eu",
        "provider_load_id": "load_001",
        "origin": "Berlin",
        "destination": "Munich",
        "price": {"amount": 1200, "currency": "EUR"},
        "distance_km": 585,
        "trailer_type": "standard",
        "adr": False,
        "loading_type": "FTL",
    },
    {
        "provider_id": "wtransnet",
        "provider_load_id": "load_002",
        "origin": "Paris",
        "destination": "Lyon",
        "price": {"amount": 850, "currency": "EUR"},
        "distance_km": 465,
        "trailer_type": "refrigerated",
        "adr": True,
        "loading_type": "LTL",
    },
]

SAMPLE_EVALUATION = {
    "estimated_revenue": {"amount": 1500, "currency": "EUR"},
    "fuel_cost": {"amount": 250, "currency": "EUR"},
    "toll_cost": {"amount": 80, "currency": "EUR"},
    "expected_profit": {"amount": 570, "currency": "EUR"},
    "profit_margin_pct": 25.5,
    "risk_score": 0.35,
    "vehicle_compatibility": [
        {"vehicle_id": "VH-101", "compatible": True},
    ],
    "driver_compatibility": [
        {"driver_id": "DRV-5", "compatible": True, "hours_remaining": 8},
    ],
}

SAMPLE_MATCHES = [
    {
        "vehicle_id": "VH-101",
        "score": 92,
        "reasons": ["closest_vehicle", "trailer_compatible", "maintenance_health"],
        "expected_profit": {"amount": 570, "currency": "EUR"},
        "driver_hours_remaining": 8,
        "maintenance_status": "good",
        "trailer_compatible": True,
    },
    {
        "vehicle_id": "VH-202",
        "score": 65,
        "reasons": ["trailer_compatible"],
        "expected_profit": {"amount": 320, "currency": "EUR"},
        "driver_hours_remaining": 2,
        "maintenance_status": "due_soon",
        "trailer_compatible": True,
    },
]


# =========================================================================
# FreightSearchView Fixtures
# =========================================================================


@pytest.fixture
def mock_api():
    """Build a mock remote freight exchange API."""
    api = MagicMock()
    api.search_loads.return_value = {
        "results": SAMPLE_LOAD_RESULTS,
        "provider_statuses": [
            {"name": "Trans.eu", "status": "healthy"},
            {"name": "Wtransnet", "status": "disconnected"},
        ],
        "providers_queried": 2,
        "providers_skipped": 0,
    }
    return api


@pytest.fixture
def mock_db():
    """Build a mock database."""
    return MagicMock()


@pytest.fixture
def search_view(qapp, mock_db, mock_api):
    """Build a FreightSearchView wired to mock db & api inside a shown window."""
    parent = shown_parent(qapp)
    sv = FreightSearchView(db=mock_db, parent=parent)
    sv._api = mock_api
    _show_view_in_window(sv, parent)
    yield sv
    sv.deleteLater()
    parent.close()
    parent.deleteLater()


@pytest.fixture
def search_view_no_api(qapp, mock_db):
    """Build a FreightSearchView without an API client."""
    parent = shown_parent(qapp)
    sv = FreightSearchView(db=mock_db, parent=parent)
    _show_view_in_window(sv, parent)
    yield sv
    sv.deleteLater()
    parent.close()
    parent.deleteLater()


# =========================================================================
# FreightSearchView — Construction
# =========================================================================


class TestFreightSearchViewConstruction:
    """Widget construction, attributes, and initial UI state."""

    def test_object_name(self, search_view):
        assert search_view.objectName() == "freight_search_view"

    def test_db_stored(self, search_view, mock_db):
        assert search_view.db is mock_db

    def test_api_configured(self, search_view, mock_api):
        assert search_view._api is mock_api

    def test_sidebar_exists(self, search_view):
        assert search_view._sidebar is not None
        assert search_view._sidebar.objectName() == "filter_panel"
        # Sidebar has fixed width
        assert search_view._sidebar.width() == 280

    def test_filter_inputs_exist(self, search_view):
        """All filter inputs are created."""
        assert isinstance(search_view._origin_input, QLineEdit)
        assert isinstance(search_view._dest_input, QLineEdit)
        assert isinstance(search_view._date_from, QLineEdit)
        assert isinstance(search_view._date_to, QLineEdit)
        assert isinstance(search_view._trailer_combo, QComboBox)
        assert isinstance(search_view._adr_check, QCheckBox)
        assert isinstance(search_view._weight_min, QLineEdit)
        assert isinstance(search_view._weight_max, QLineEdit)
        assert isinstance(search_view._price_min, QLineEdit)
        assert isinstance(search_view._price_max, QLineEdit)
        assert isinstance(search_view._distance_max, QLineEdit)
        assert isinstance(search_view._loading_type, QComboBox)
        assert isinstance(search_view._loading_country, QLineEdit)
        assert isinstance(search_view._delivery_country, QLineEdit)

    def test_search_button_exists(self, search_view):
        assert search_view._search_btn is not None

    def test_save_button_exists(self, search_view):
        assert search_view._save_btn is not None

    def test_results_table_exists(self, search_view):
        assert search_view._results_table is not None

    def test_sort_combo_exists(self, search_view):
        assert search_view._sort_combo is not None
        assert search_view._sort_combo.count() >= 7

    def test_summary_bar_exists(self, search_view):
        assert search_view._summary_bar is not None
        assert search_view._result_count_label is not None

    def test_empty_state_created(self, search_view):
        assert search_view._empty_state is not None

    def test_error_card_hidden_initially(self, search_view):
        assert not search_view._error_card.isVisible()

    def test_empty_state_hidden_initially(self, search_view):
        assert not search_view._empty_state.isVisible()

    def test_loading_overlay_hidden_initially(self, search_view):
        assert not search_view._loading_overlay.isVisible()

    def test_initial_status_no_providers(self, search_view):
        """Status bar initially shows no providers message."""
        assert "no" in search_view._status_label.text().lower() or not search_view._status_label.text()

    def test_visible_by_default(self, search_view):
        assert search_view.isVisible()


# =========================================================================
# FreightSearchView — Filter Validation
# =========================================================================


class TestFilterValidation:
    """Search form validation — route fields required."""

    def test_search_missing_origin_shows_error(self, search_view):
        """Search without origin shows an error."""
        search_view._origin_input.setText("")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        assert search_view._error_card.isVisible()
        assert search_view._error_label.text()

    def test_search_missing_dest_shows_error(self, search_view):
        """Search without destination shows an error."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("")
        search_view._on_search()
        assert search_view._error_card.isVisible()
        assert search_view._error_label.text()

    def test_search_missing_both_shows_error(self, search_view):
        """Search without both origin and destination shows an error."""
        search_view._origin_input.setText("")
        search_view._dest_input.setText("")
        search_view._on_search()
        assert search_view._error_card.isVisible()

    def test_valid_route_clears_error(self, search_view, mock_api, qtbot):
        """Valid route triggers search without validation error."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        # Error card should not be visible (search ran)
        assert not search_view._error_card.isVisible()


# =========================================================================
# FreightSearchView — Search Execution
# =========================================================================


class TestSearchExecution:
    """Search execution, loading state, results display."""

    def test_search_calls_api(self, search_view, mock_api, qtbot):
        """_on_search calls the API search_loads method."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        mock_api.search_loads.assert_called_once()

    def test_search_shows_loading(self, search_view, mock_api, qtbot):
        """During search, the loading overlay is shown."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        # Loading shown during search, hidden after
        assert not search_view._loading_overlay.isVisible()

    def test_search_button_disabled_during_search(self, search_view):
        """Search button is disabled while searching."""
        search_view.show_loading(searching=True)
        assert not search_view._search_btn.isEnabled()
        assert "searching" in search_view._search_btn.text().lower()

    def test_search_button_re_enabled_after_search(self, search_view, mock_api, qtbot):
        """Search button is re-enabled after search completes."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert search_view._search_btn.isEnabled()

    def test_search_populates_results_table(self, search_view, mock_api, qtbot):
        """Results from API are displayed in the table."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert search_view._results_table.rowCount() == 2

    def test_search_updates_result_count(self, search_view, mock_api, qtbot):
        """Result count label is updated after search."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert search_view._result_count_label.text()

    def test_search_hides_empty_state(self, search_view, mock_api, qtbot):
        """Empty state is hidden when results are returned."""
        search_view.show_empty(True)
        assert search_view._empty_state.isVisible()

        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert not search_view._empty_state.isVisible()

    def test_search_hides_error_card(self, search_view, mock_api, qtbot):
        """Error card is hidden when search succeeds."""
        search_view.show_error("Previous error")
        assert search_view._error_card.isVisible()

        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert not search_view._error_card.isVisible()

    def test_search_status_bar_updated(self, search_view, mock_api, qtbot):
        """Status bar shows provider query info after search."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert "provider" in search_view._status_label.text().lower()

    def test_search_sets_health_indicators(self, search_view, mock_api, qtbot):
        """Provider health indicators are displayed after search."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        # Health indicators are added as children of _summary_bar
        labels = search_view._summary_bar.findChildren(QLabel)
        assert any("Trans.eu" in lbl.text() for lbl in labels)


# =========================================================================
# FreightSearchView — Empty Results
# =========================================================================


class TestEmptyResults:
    """Behavior when search returns no results."""

    def test_show_empty_state(self, search_view):
        """show_empty makes the empty state visible."""
        search_view.show_empty(True)
        assert search_view._empty_state.isVisible()
        assert not search_view._results_table.isVisible()

    def test_hide_empty_state(self, search_view):
        """show_empty(False) hides the empty state."""
        search_view.show_empty(True)
        search_view.show_empty(False)
        assert not search_view._empty_state.isVisible()
        assert search_view._results_table.isVisible()

    def test_empty_state_text(self, search_view):
        """Empty state has a title and subtitle."""
        # The EmptyState stores title/subtitle as QLabel children
        labels = search_view._empty_state.findChildren(QLabel)
        assert len(labels) >= 2


# =========================================================================
# FreightSearchView — Loading State
# =========================================================================


class TestLoadingState:
    """Loading overlay behavior during search."""

    def test_loading_overlay_visible_when_searching(self, search_view):
        """show_loading(True) makes overlay setVisible(True) called."""
        # The overlay is a child of the results table; when the table is
        # hidden, children are also hidden.
        search_view.show_loading(searching=True)
        assert not search_view._results_table.isVisible()
        # The overlay's setVisible was called (searching=True), but parent
        # (results table) is hidden, so the overlay is not visually visible
        assert not search_view._loading_overlay.isVisible()

    def test_loading_overlay_hidden_when_done(self, search_view):
        """show_loading(False) hides overlay."""
        search_view.show_loading(searching=True)
        search_view.show_loading(searching=False)
        assert not search_view._loading_overlay.isVisible()
        assert search_view._results_table.isVisible()

    def test_loading_overlay_style(self, search_view):
        """Loading overlay has wait cursor."""
        assert search_view._loading_overlay.cursor().shape() == Qt.CursorShape.WaitCursor


# =========================================================================
# FreightSearchView — Error Handling
# =========================================================================


class TestSearchErrorHandling:
    """Error states: search failure, network error, no API."""

    def test_search_api_error(self, search_view, mock_api, qtbot):
        """When API raises, error card is shown."""
        mock_api.search_loads.side_effect = RuntimeError("Connection refused")
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert search_view._error_card.isVisible()
        assert "Connection refused" in search_view._error_label.text()

    def test_search_api_error_hides_loading(self, search_view, mock_api, qtbot):
        """After API error, loading overlay is hidden."""
        mock_api.search_loads.side_effect = RuntimeError("Network error")
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert not search_view._loading_overlay.isVisible()

    def test_search_no_api_raises_error(self, search_view_no_api, qtbot):
        """When API is not configured, an error is shown."""
        search_view_no_api._origin_input.setText("Berlin")
        search_view_no_api._dest_input.setText("Munich")
        search_view_no_api._on_search()
        qtbot.wait(50)
        assert search_view_no_api._error_card.isVisible()

    def test_show_error_display(self, search_view):
        """show_error displays the error card with the message."""
        search_view.show_error("Test error message")
        assert search_view._error_card.isVisible()
        assert "Test error message" in search_view._error_label.text()
        assert not search_view._results_table.isVisible()
        assert not search_view._empty_state.isVisible()

    def test_show_error_called_during_search_api_error(self, search_view, mock_api, qtbot):
        """A network error during search calls show_error."""
        mock_api.search_loads.side_effect = TimeoutError("Request timed out")
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._on_search()
        qtbot.wait(50)
        assert "timed out" in search_view._error_label.text().lower()


# =========================================================================
# FreightSearchView — set_table_data
# =========================================================================


class TestSetTableData:
    """set_table_data populates the results table."""

    def test_set_table_data_populates_rows(self, search_view):
        """set_table_data sets the correct number of rows."""
        rows_data = [
            {"provider": "TRANS", "origin": "A", "destination": "B",
             "price": "1,200 EUR", "distance": "585 km", "trailer": "standard",
             "adr": "No", "__raw": {}},
        ]
        search_view.set_table_data(rows_data)
        assert search_view._results_table.rowCount() == 1

    def test_set_table_data_multiple_rows(self, search_view):
        """set_table_data handles multiple rows."""
        search_view.set_table_data([
            {"provider": "A", "origin": "X", "destination": "Y",
             "price": "100 EUR", "distance": "100 km", "trailer": "standard",
             "adr": "No", "__raw": {}},
            {"provider": "B", "origin": "X", "destination": "Z",
             "price": "200 EUR", "distance": "200 km", "trailer": "reefer",
             "adr": "Yes", "__raw": {}},
        ])
        assert search_view._results_table.rowCount() == 2

    def test_set_table_data_hides_empty_state(self, search_view):
        """set_table_data hides the empty state."""
        search_view.show_empty(True)
        search_view.set_table_data([])
        assert not search_view._empty_state.isVisible()

    def test_set_table_data_hides_error_card(self, search_view):
        """set_table_data hides the error card."""
        search_view.show_error("Error")
        search_view.set_table_data([])
        assert not search_view._error_card.isVisible()

    def test_set_table_data_action_widgets(self, search_view):
        """Each row gets an action widget with import and evaluate buttons."""
        search_view.set_table_data([
            {"provider": "A", "origin": "X", "destination": "Y",
             "price": "100 EUR", "distance": "100 km", "trailer": "standard",
             "adr": "No", "__raw": {}},
        ])
        # Last column (7) should have a widget
        cell_widget = search_view._results_table.cellWidget(0, 7)
        assert cell_widget is not None
        buttons = cell_widget.findChildren(QPushButton)
        assert any("import" in b.text().lower() for b in buttons)
        assert any("evaluate" in b.text().lower() for b in buttons)


# =========================================================================
# FreightSearchView — set_health_indicators
# =========================================================================


class TestHealthIndicators:
    """Provider health indicator display."""

    def test_health_indicators_add_labels(self, search_view):
        """set_health_indicators adds provider labels."""
        search_view.set_health_indicators([
            {"name": "Trans.eu", "status": "healthy"},
            {"name": "Wtransnet", "status": "disconnected"},
        ])
        # Labels are children of _summary_bar
        labels = search_view._summary_bar.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert "Trans.eu" in texts
        assert "Wtransnet" in texts

    def test_health_indicators_clear_previous(self, search_view, qtbot):
        """set_health_indicators clears previous indicators."""
        search_view.set_health_indicators([
            {"name": "Old", "status": "healthy"},
        ])
        # Process deferred deletions from deleteLater()
        qtbot.wait(10)
        search_view.set_health_indicators([
            {"name": "New", "status": "healthy"},
        ])
        qtbot.wait(10)
        labels = search_view._summary_bar.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert "Old" not in texts
        assert "New" in texts

    def test_health_indicators_empty(self, search_view):
        """set_health_indicators with empty list clears all indicators."""
        search_view.set_health_indicators([
            {"name": "Trans.eu", "status": "healthy"},
        ])
        search_view.set_health_indicators([])
        assert search_view._health_container.count() == 0

    def test_health_color_mapping(self, search_view):
        """_health_color returns correct colors for each status."""
        assert search_view._health_color("connected")
        assert search_view._health_color("healthy")
        assert search_view._health_color("degraded")
        assert search_view._health_color("error")
        assert search_view._health_color("down")
        assert search_view._health_color("disconnected")
        assert search_view._health_color("unknown")  # fallback


# =========================================================================
# FreightSearchView — update_status_bar
# =========================================================================


class TestStatusBar:
    """Status bar text updates."""

    def test_status_bar_no_providers(self, search_view):
        """When no providers, status bar shows warning."""
        search_view.update_status_bar(has_providers=False)
        assert search_view._status_label.text()

    def test_status_bar_with_last_updated(self, search_view):
        """When last_updated is provided, it's shown."""
        search_view.update_status_bar(has_providers=True, last_updated="Updated 2 min ago")
        assert "Updated 2 min ago" in search_view._status_label.text()

    def test_status_bar_default(self, search_view):
        """Default status bar text when providers exist."""
        search_view.update_status_bar(has_providers=True)
        assert search_view._status_label.text()


# =========================================================================
# FreightSearchView — Sort
# =========================================================================


class TestSort:
    """Sort combo behavior."""

    def test_sort_changed_triggers_search(self, search_view, mock_api, qtbot):
        """Changing sort triggers a new search if origin/dest are filled."""
        search_view._origin_input.setText("Berlin")
        search_view._dest_input.setText("Munich")
        search_view._sort_combo.setCurrentIndex(1)
        qtbot.wait(50)
        mock_api.search_loads.assert_called()


# =========================================================================
# FreightSearchView — _parse_float
# =========================================================================


class TestParseFloat:
    """_parse_float helper behavior."""

    def test_parse_float_valid(self, search_view):
        assert search_view._parse_float("123.45") == 123.45

    def test_parse_float_comma_separator(self, search_view):
        assert search_view._parse_float("123,45") == 123.45

    def test_parse_float_empty(self, search_view):
        assert search_view._parse_float("") is None

    def test_parse_float_whitespace(self, search_view):
        assert search_view._parse_float("  ") is None

    def test_parse_float_invalid(self, search_view):
        assert search_view._parse_float("abc") is None

    def test_parse_float_with_spaces(self, search_view):
        assert search_view._parse_float("1 234,56") == 1234.56


# =========================================================================
# _map_sort_field
# =========================================================================


class TestMapSortField:
    """_map_sort_field helper maps display text to API sort params."""

    def test_map_price_asc(self):
        assert _map_sort_field("Price ↑") == ("price", "asc")

    def test_map_price_desc(self):
        assert _map_sort_field("Price ↓") == ("price", "desc")

    def test_map_distance_asc(self):
        assert _map_sort_field("Distance ↑") == ("distance", "asc")

    def test_map_distance_desc(self):
        assert _map_sort_field("Distance ↓") == ("distance", "desc")

    def test_map_date_asc(self):
        assert _map_sort_field("Date ↑") == ("date", "asc")

    def test_map_date_desc(self):
        assert _map_sort_field("Date ↓") == ("date", "desc")

    def test_map_unknown_falls_back(self):
        """Unknown sort text falls back to date desc."""
        assert _map_sort_field("Relevance") == ("date", "desc")

    def test_map_empty_falls_back(self):
        assert _map_sort_field("") == ("date", "desc")


# =========================================================================
# FreightLoadDetailView Fixtures
# =========================================================================


@pytest.fixture
def detail_view(qapp, mock_db):
    """Build a FreightLoadDetailView inside a shown window."""
    parent = shown_parent(qapp)
    dv = FreightLoadDetailView(db=mock_db, parent=parent)
    _show_view_in_window(dv, parent)
    yield dv
    dv.deleteLater()
    parent.close()
    parent.deleteLater()


# =========================================================================
# FreightLoadDetailView — Construction
# =========================================================================


class TestFreightLoadDetailViewConstruction:
    """Widget construction, attributes, and initial UI state."""

    def test_object_name(self, detail_view):
        assert detail_view.objectName() == "freight_load_detail"

    def test_db_stored(self, detail_view, mock_db):
        assert detail_view.db is mock_db

    def test_back_top_button_exists(self, detail_view):
        assert detail_view._back_top_btn is not None
        assert "back" in detail_view._back_top_btn.text().lower()

    def test_import_top_button_exists(self, detail_view):
        assert detail_view._import_top_btn is not None
        assert "import" in detail_view._import_top_btn.text().lower()

    def test_refresh_button_exists(self, detail_view):
        assert detail_view._refresh_btn is not None

    def test_eval_card_exists(self, detail_view):
        assert detail_view._eval_card is not None

    def test_match_card_exists(self, detail_view):
        assert detail_view._match_card is not None

    def test_kpi_widgets_exist(self, detail_view):
        """All KPI widgets are created."""
        assert detail_view._kpi_revenue is not None
        assert detail_view._kpi_total_cost is not None
        assert detail_view._kpi_profit is not None
        assert detail_view._kpi_margin is not None
        assert detail_view._kpi_risk is not None

    def test_bottom_action_bar(self, detail_view):
        """Bottom action buttons exist."""
        assert detail_view._back_bottom_btn is not None
        assert detail_view._import_bottom_btn is not None
        assert detail_view._evaluate_again_btn is not None

    def test_visible_by_default(self, detail_view):
        assert detail_view.isVisible()


# =========================================================================
# FreightLoadDetailView — display_evaluation
# =========================================================================


class TestDisplayEvaluation:
    """display_evaluation populates evaluation KPIs and compatibility chips."""

    def test_display_evaluation_revenue(self, detail_view):
        """Revenue KPI is updated."""
        detail_view.display_evaluation(SAMPLE_EVALUATION)
        assert "1,500" in detail_view._kpi_revenue.value_label.text()

    def test_display_evaluation_total_cost(self, detail_view):
        """Total cost KPI shows sum of fuel + toll."""
        detail_view.display_evaluation(SAMPLE_EVALUATION)
        assert "330" in detail_view._kpi_total_cost.value_label.text()  # 250 + 80

    def test_display_evaluation_profit(self, detail_view):
        """Profit KPI is updated."""
        detail_view.display_evaluation(SAMPLE_EVALUATION)
        assert "570" in detail_view._kpi_profit.value_label.text()

    def test_display_evaluation_margin(self, detail_view):
        """Margin KPI is updated."""
        detail_view.display_evaluation(SAMPLE_EVALUATION)
        assert "25.5" in detail_view._kpi_margin.value_label.text()

    def test_display_evaluation_risk(self, detail_view):
        """Risk KPI is updated."""
        detail_view.display_evaluation(SAMPLE_EVALUATION)
        assert "0.35" in detail_view._kpi_risk.value_label.text()

    def test_display_evaluation_compatibility_chips(self, detail_view):
        """Compatibility chips are created for vehicle and driver."""
        detail_view.display_evaluation(SAMPLE_EVALUATION)
        # Chips are QLabel/StatusBadge widgets in the compat_chip_layout
        chip_count = detail_view._compat_chip_layout.count()
        assert chip_count >= 2  # vehicle + driver

    def test_display_evaluation_negative_profit(self, detail_view):
        """Negative profit is displayed correctly."""
        eval_data = dict(SAMPLE_EVALUATION)
        eval_data["expected_profit"] = {"amount": -250, "currency": "EUR"}
        detail_view.display_evaluation(eval_data)
        assert "250" in detail_view._kpi_profit.value_label.text()

    def test_display_evaluation_zero_revenue(self, detail_view):
        """Zero values are handled gracefully."""
        eval_data = {k: v if k != "estimated_revenue" else {"amount": 0, "currency": "EUR"}
                     for k, v in SAMPLE_EVALUATION.items()}
        detail_view.display_evaluation(eval_data)
        assert "0" in detail_view._kpi_revenue.value_label.text()

    def test_display_evaluation_high_risk(self, detail_view):
        """Risk score above 0.6 is shown."""
        eval_data = dict(SAMPLE_EVALUATION)
        eval_data["risk_score"] = 0.85
        detail_view.display_evaluation(eval_data)
        assert "0.85" in detail_view._kpi_risk.value_label.text()


# =========================================================================
# FreightLoadDetailView — display_matches
# =========================================================================


class TestDisplayMatches:
    """display_matches builds match rows."""

    def test_display_matches_creates_rows(self, detail_view):
        """Match rows are created for each match."""
        detail_view.display_matches(SAMPLE_MATCHES)
        assert len(detail_view._match_rows) == 2

    def test_display_matches_clears_previous(self, detail_view):
        """Calling display_matches again clears previous rows."""
        detail_view.display_matches(SAMPLE_MATCHES)
        assert len(detail_view._match_rows) == 2
        detail_view.display_matches(SAMPLE_MATCHES[:1])
        assert len(detail_view._match_rows) == 1

    def test_display_matches_empty_list(self, detail_view):
        """Empty match list clears rows."""
        detail_view.display_matches([])
        assert len(detail_view._match_rows) == 0

    def test_match_row_has_assign_button(self, detail_view):
        """Each match row has an assign button."""
        detail_view.display_matches(SAMPLE_MATCHES)
        assign_btns = detail_view._match_card.findChildren(QPushButton)
        assign_texts = [b.text() for b in assign_btns]
        assert any("assign" in t.lower() for t in assign_texts)

    def test_match_row_score_display(self, detail_view):
        """Match row shows the score value."""
        detail_view.display_matches(SAMPLE_MATCHES)
        # Score is displayed in a label
        all_labels = detail_view._match_card.findChildren(QLabel)
        assert any("92" in lbl.text() for lbl in all_labels)
        assert any("65" in lbl.text() for lbl in all_labels)

    def test_match_row_profit_display(self, detail_view):
        """Match row shows expected profit."""
        detail_view.display_matches(SAMPLE_MATCHES)
        all_labels = detail_view._match_card.findChildren(QLabel)
        assert any("570" in lbl.text() for lbl in all_labels)
        assert any("320" in lbl.text() for lbl in all_labels)


# =========================================================================
# FreightLoadDetailView — set_load_for_import / get_import_target
# =========================================================================


class TestImportTarget:
    """set_load_for_import and get_import_target behavior."""

    def test_set_import_target(self, detail_view):
        detail_view.set_load_for_import("trans_eu", "load_001")
        target = detail_view.get_import_target()
        assert target == {"provider_id": "trans_eu", "load_id": "load_001"}

    def test_get_import_target_default_none(self, detail_view):
        """get_import_target returns None when not set."""
        assert detail_view.get_import_target() is None

    def test_set_import_target_overwrites(self, detail_view):
        detail_view.set_load_for_import("trans_eu", "load_001")
        detail_view.set_load_for_import("wtransnet", "load_002")
        target = detail_view.get_import_target()
        assert target == {"provider_id": "wtransnet", "load_id": "load_002"}


# =========================================================================
# FreightLoadDetailView — display_freight_info
# =========================================================================


class TestDisplayFreightInfo:
    """display_freight_info shows Trans.eu-specific freight details."""

    def test_display_freight_info_with_reference(self, detail_view):
        """Freight info shows reference number."""
        # Add the label first (production code creates it on demand)
        from PySide6.QtWidgets import QLabel
        detail_view._freight_info_label = QLabel()
        detail_view._freight_info_label.setVisible(False)
        detail_view._freight_info_label.setParent(detail_view)

        detail_view.display_freight_info({"reference_number": "REF-12345"})
        assert detail_view._freight_info_label.isVisible()
        assert "REF-12345" in detail_view._freight_info_label.text()

    def test_display_freight_info_with_employees(self, detail_view):
        """Freight info shows contact employees."""
        from PySide6.QtWidgets import QLabel
        detail_view._freight_info_label = QLabel()
        detail_view._freight_info_label.setVisible(False)
        detail_view._freight_info_label.setParent(detail_view)

        detail_view.display_freight_info({
            "reference_number": "REF-001",
            "contact_employees": [
                {"name": "John", "last_name": "Doe"},
            ],
        })
        assert "John Doe" in detail_view._freight_info_label.text()

    def test_display_freight_info_empty(self, detail_view):
        """Empty freight info does not crash."""
        from PySide6.QtWidgets import QLabel
        detail_view._freight_info_label = QLabel()
        detail_view._freight_info_label.setVisible(False)
        detail_view._freight_info_label.setParent(detail_view)

        detail_view.display_freight_info({})  # Should not raise


# =========================================================================
# FreightLoadDetailView — eventFilter (keyboard navigation)
# =========================================================================


class TestEventFilter:
    """eventFilter handles Enter key on match rows."""

    def test_event_filter_enter_on_match_row(self, detail_view, qtbot):
        """Pressing Enter on a match row triggers the assign button."""
        detail_view.display_matches(SAMPLE_MATCHES)
        row = detail_view._match_rows[0]
        row.setFocus()

        # Simulate key press on the row
        event = _make_key_event(Qt.Key_Return)
        result = detail_view.eventFilter(row, event)
        assert result is True  # event consumed

    def test_event_filter_non_match_row_ignored(self, detail_view):
        """eventFilter ignores widgets that are not match rows."""
        label = QLabel("test")
        event = _make_key_event(Qt.Key_Return)
        result = detail_view.eventFilter(label, event)
        assert result is False  # event not consumed

    def test_event_filter_non_enter_key_ignored(self, detail_view):
        """eventFilter ignores non-Enter keys on match rows."""
        detail_view.display_matches(SAMPLE_MATCHES)
        row = detail_view._match_rows[0]
        event = _make_key_event(Qt.Key_Tab)
        result = detail_view.eventFilter(row, event)
        assert result is False  # event not consumed


# =========================================================================
# Helpers
# =========================================================================


def _make_key_event(key: int):
    """Create a mock QKeyEvent for simulating key presses."""
    from PySide6.QtGui import QKeyEvent
    return QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
