"""Tests for the client revenue chart widget."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.plotly_charts import CHART_ACCENT, CHART_DANGER, CHART_SUCCESS
from ui.widgets.client_revenue_chart import QtClientRevenueChart


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.get_client_revenue_history.return_value = []
    return svc


SAMPLE_HISTORY = [
    {"month": "2026-07", "revenue": 5000, "profit": 1200},
    {"month": "2026-06", "revenue": 4500, "profit": 1100},
    {"month": "2026-05", "revenue": 6000, "profit": 1500},
]


def _setup_plotly_mock(mock_pcw):
    """Configure PlotlyChartWidget mock to return a real QWidget so that
    ``layout().addWidget(...)`` does not reject the value at the C++ level.
    """
    widget = QWidget()
    widget.set_figure = MagicMock()
    mock_pcw.return_value = widget
    return widget


class TestQtClientRevenueChart:
    """Core widget behaviour — init, build, refresh, cleanup."""

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_creation_with_service(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)
        assert chart.layout() is not None
        # _build() was called from __init__; chart rendering should have happened
        mock_make_chart.assert_called_once()

    @pytest.mark.xfail(
        reason="Source code _build() does not guard against service=None yet",
        strict=False,
    )
    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_creation_without_service(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot
    ):
        _setup_plotly_mock(mock_plotly_widget)
        chart = QtClientRevenueChart(qt_widget, service=None)
        qtbot.addWidget(chart)
        assert chart.layout() is not None

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_renders_chart(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        mock_make_chart.assert_called_once()
        args, kwargs = mock_make_chart.call_args
        months = args[0]
        series = args[1]

        assert months == ["05", "06", "07"]  # reversed, short
        assert len(series) == 2
        assert series[0][0] == "Revenue"
        assert series[1][0] == "Profit"
        # PlotlyChartWidget was instantiated and set_figure called
        mock_plotly_widget.return_value.set_figure.assert_called_once()

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_empty_history_shows_label(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = []
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        assert chart._chart_widget is None
        assert chart._empty_label is not None
        assert chart._empty_label.text() == "No revenue data yet"
        mock_make_chart.assert_not_called()

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_positive_profit_uses_success_color(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        args, _ = mock_make_chart.call_args
        series = args[1]
        # SAMPLE_HISTORY profits sum = 1200 + 1100 + 1500 = 3800 >= 0 → CHART_SUCCESS
        assert series[1][2] == CHART_SUCCESS

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_negative_profit_uses_danger_color(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = [
            {"month": "2026-07", "revenue": 5000, "profit": -200},
        ]
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        args, _ = mock_make_chart.call_args
        series = args[1]
        # profit sum = -200 < 0 → CHART_DANGER
        assert series[1][2] == CHART_DANGER

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_revenue_uses_accent_color(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        args, _ = mock_make_chart.call_args
        series = args[1]
        # Revenue bar always uses CHART_ACCENT
        assert series[0][2] == CHART_ACCENT

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_shortens_month_labels(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = [
            {"month": "2026-07", "revenue": 5000, "profit": 100},
        ]
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        args, _ = mock_make_chart.call_args
        months = args[0]
        # "2026-07" → last 2 chars → "07"
        assert months == ["07"]

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_handles_none_values(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = [
            {"month": "2026-07", "revenue": None, "profit": None},
        ]
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        args, _ = mock_make_chart.call_args
        series = args[1]
        # None should be treated as 0
        assert series[0][1] == [0]
        assert series[1][1] == [0]

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_refresh_switches_client(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)
        mock_service.reset_mock()
        mock_service.get_client_revenue_history.return_value = []

        chart.refresh(client_id=2)

        assert chart.client_id == 2
        mock_service.get_client_revenue_history.assert_called_once_with(2, months=12)

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_refresh_no_arg_reuses_client_id(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)
        mock_service.reset_mock()
        mock_service.get_client_revenue_history.return_value = []

        chart.refresh()

        assert chart.client_id == 1
        mock_service.get_client_revenue_history.assert_called_once_with(1, months=12)

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_clear_content_removes_all(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        chart._clear_content()

        assert chart.layout().count() == 0
        assert chart._chart_widget is None
        assert chart._empty_label is None

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_cleanup_calls_clear_content(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)

        chart.cleanup()

        assert chart.layout().count() == 0


class TestQtClientRevenueChartEdgeCases:
    """Edge cases and defensive behaviour."""

    @pytest.mark.xfail(
        reason="Source code _build() does not guard against missing 'month' key yet",
        strict=False,
    )
    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_revenue_history_with_missing_month_key(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = [
            {"revenue": 5000, "profit": 1200},  # missing "month"
        ]
        try:
            chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
            qtbot.addWidget(chart)
        except KeyError:
            pytest.fail("_build() raised KeyError when history entry lacks 'month' key")

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_build_with_no_layout(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = list(SAMPLE_HISTORY)
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)
        # _build() is called in __init__; if no layout exists it creates QVBoxLayout
        assert isinstance(chart.layout(), QVBoxLayout)

    @patch("ui.widgets.client_revenue_chart.PlotlyChartWidget")
    @patch("ui.widgets.client_revenue_chart.make_grouped_bar_chart")
    def test_service_returns_none_history(
        self, mock_make_chart, mock_plotly_widget, qt_widget, qtbot, mock_service
    ):
        _setup_plotly_mock(mock_plotly_widget)
        mock_service.get_client_revenue_history.return_value = None
        chart = QtClientRevenueChart(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(chart)
        # None is falsy → empty state label shown
        assert chart._empty_label is not None
        assert chart._empty_label.text() == "No revenue data yet"
        mock_make_chart.assert_not_called()
