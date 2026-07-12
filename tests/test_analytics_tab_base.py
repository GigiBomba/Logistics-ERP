"""Tests for the analytics BaseTab and _SparklineLabel."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.views.analytics._tab_base import BaseTab, _SparklineLabel, _render_sparkline


# ── BaseTab ────────────────────────────────────────────────────────────


class TestBaseTabCreation:
    def test_creation_without_service(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._svc is None
        assert tab._figs == []
        assert tab._data_signature is None
        assert tab._last_render_ts == 0.0
        assert tab._render_expected == 0
        assert tab._render_received == 0
        assert tab._cached_days == 30
        assert tab._cached_months == 1
        assert tab._cached_quarters == 1

    def test_creation_with_service(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        svc = MagicMock()
        tab = Stub(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        assert tab._svc is svc

    def test_content_layout_exists(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._content_layout is not None
        assert tab._content_layout.count() >= 0


class TestBaseTabHelpers:
    def test_days_default(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._days() == 30

    def test_months_default(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._months() == 1

    def test_quarters_default(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._quarters() == 1

    def test_date_range_with_days(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab._cached_days = 30
        from_date, to_date = tab._date_range()
        assert from_date is not None
        assert to_date is not None
        assert "-" in from_date
        assert "-" in to_date

    def test_date_range_all_time(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab._cached_days = 0
        from_date, to_date = tab._date_range()
        assert from_date is None
        assert to_date is None

    def test_safe_fmt_integer(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._safe_fmt(1234) == "1,234"

    def test_safe_fmt_float(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        result = tab._safe_fmt(1234.5, ".1f")
        assert result == "1234.5"

    def test_safe_fmt_none(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._safe_fmt(None) == "\u2014"

    def test_safe_fmt_bad_value(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._safe_fmt(object()) == "\u2014"

    def test_safe_float_normal(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._safe_float("42.5") == 42.5

    def test_safe_float_none(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._safe_float(None) == 0.0

    def test_safe_float_bad(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._safe_float("nope") == 0.0

    def test_sparkline_values(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        data = [{"val": 10}, {"val": 20}, {"val": 30}]
        result = tab._sparkline_values(data, "val")
        assert result == [10.0, 20.0, 30.0]

    def test_sparkline_values_missing_key(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        data = [{"other": 10}]
        result = tab._sparkline_values(data, "val")
        assert result == [0.0]

    def test_fmt_month_label_iso(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        result = tab._fmt_month_label("2026-05")
        # Should produce abbreviated month + year
        assert "2026" in result
        assert len(result) > 5

    def test_fmt_month_label_timestamp(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        result = tab._fmt_month_label("2026-05-15 10:30:00")
        assert "2026" in result

    def test_fmt_month_label_empty(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._fmt_month_label("") == ""

    def test_fmt_month_label_none(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._fmt_month_label(None) == ""


class TestBaseTabSessionCache:
    def test_cache_get_set(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab.cache_set("key1", "value1")
        assert tab.cache_get("key1") == "value1"
        assert tab.cache_get("missing", "default") == "default"

    def test_invalidate_cache(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab.cache_set("key1", "value1")
        tab._data_signature = (30, 1, 1)
        tab.invalidate_cache()
        assert tab.cache_get("key1") is None
        assert tab._data_signature is None


class TestBaseTabLayout:
    def test_add_header(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_header("analytics.tab_financial", "analytics.financial_subtitle")
        assert tab._content_layout.count() >= 3  # header + divider + spacing

    def test_add_no_data(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_no_data()
        assert tab._content_layout.count() >= 1

    def test_add_no_data_custom_message(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_no_data("Custom empty")
        assert tab._content_layout.count() >= 1

    def test_add_kpi_row(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        kpis = [
            {"label": "Revenue", "value": "10,000 €"},
            {"label": "Profit", "value": "2,000 €"},
        ]
        row = tab._add_kpi_row(kpis)
        assert row is not None
        assert tab._content_layout.count() >= 1

    def test_add_kpi_row_with_sparklines(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        kpis = [
            {
                "label": "Revenue",
                "value": "10,000 €",
                "subtitle": "+1,500 €",
                "sparkline_values": [100, 200, 300],
                "sparkline_color": "#6366f1",
            },
        ]
        row = tab._add_kpi_row_with_sparklines(kpis)
        assert row is not None
        # Should contain sparkline label inside
        sparklines = row.findChildren(_SparklineLabel)
        assert len(sparklines) == 1

    def test_add_section_header(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_section_header("Test Section")
        assert tab._content_layout.count() >= 2

    def test_add_section_header_with_icon(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_section_header("Test Section", icon="📊")
        assert tab._content_layout.count() >= 2

    def test_add_divider(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_divider()
        assert tab._content_layout.count() >= 1

    def test_scrollarea_setup(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._scroll is not None
        assert tab._scroll.widgetResizable() is True
        assert tab._scroll.frameShape() == QFrame.NoFrame


class TestBaseTabCleanup:
    def test_cleanup_default_is_noop(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        sentinel = QLabel("keep me")
        tab._content_layout.addWidget(sentinel)
        tab.cleanup()  # no force
        assert sentinel.parent() is not None
        assert tab._content_layout.count() == 1

    def test_cleanup_force_destroys(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab._content_layout.addWidget(QLabel("x"))
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0

    def test_cleanup_force_with_multiple_widgets(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        for _ in range(5):
            tab._content_layout.addWidget(QLabel("item"))
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


class TestBaseTabRefresh:
    def test_refresh_idempotent_same_signature(self, qt_widget, qtbot):
        call_count = {"n": 0}

        class Stub(BaseTab):
            def _do_refresh(self):
                call_count["n"] += 1

        tab = Stub(parent=qt_widget, service=None)
        tab.refresh()
        assert call_count["n"] == 1
        tab.refresh()
        assert call_count["n"] == 1  # no-op

    def test_refresh_force_reruns(self, qt_widget, qtbot):
        call_count = {"n": 0}

        class Stub(BaseTab):
            def _do_refresh(self):
                call_count["n"] += 1

        tab = Stub(parent=qt_widget, service=None)
        tab.refresh()
        tab.refresh(force=True)
        assert call_count["n"] == 2

    def test_refresh_on_error_shows_no_data(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                raise ValueError("db error")

        tab = Stub(parent=qt_widget, service=None)
        tab.refresh()
        # After error, _add_no_data should have been called
        assert tab._content_layout.count() >= 1

    def test_period_change_forces_refresh(self, qt_widget, qtbot):
        call_count = {"n": 0}

        class Stub(BaseTab):
            def _do_refresh(self):
                call_count["n"] += 1

        tab = Stub(parent=qt_widget, service=None)
        tab.refresh()
        tab.refresh()
        assert call_count["n"] == 1
        tab._cached_days = 90
        tab.refresh()
        assert call_count["n"] == 2


class TestBaseTabStaleness:
    def test_is_stale_never_rendered(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._is_stale() is True

    def test_is_stale_fresh(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab.refresh()
        assert tab._is_stale(60.0) is False

    def test_is_stale_after_window(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab.refresh()
        import time

        time.sleep(0.005)
        assert tab._is_stale(0.0) is True

    def test_compute_signature(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        sig = tab._compute_signature()
        assert sig == (30, 1, 1)

    def test_mark_rendered_sets_signature_and_ts(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab._mark_rendered()
        assert tab._data_signature == (30, 1, 1)
        assert tab._last_render_ts > 0


class TestBaseTabOverlay:
    def test_install_overlay(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        sink = MagicMock()
        done_sink = MagicMock()
        tab._install_overlay(expected=5, sink=sink, done_sink=done_sink)
        assert tab._render_expected == 5
        assert tab._render_received == 0
        sink.assert_called_once_with(tab, 5)

    def test_clear_overlay(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        tab._install_overlay(expected=3, sink=MagicMock(), done_sink=MagicMock())
        tab._clear_overlay()
        assert tab._overlay_sink is None
        assert tab._overlay_done_sink is None

    def test_on_chart_rendered_triggers_done_sink(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        done_sink = MagicMock()
        tab._install_overlay(expected=2, sink=MagicMock(), done_sink=done_sink)
        tab._on_chart_rendered(None)
        done_sink.assert_not_called()  # only 1 of 2
        tab._on_chart_rendered(None)
        done_sink.assert_called_once_with(tab)

    def test_count_render_targets(self, qt_widget, qtbot):
        from ui.plotly_renderer import PlotlyChartWidget

        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._count_render_targets() == 0
        # Add a PlotlyChartWidget
        pcw = PlotlyChartWidget(tab)
        tab._content_layout.addWidget(pcw)
        assert tab._count_render_targets() == 1
        # Add a _SparklineLabel
        sl = _SparklineLabel(tab)
        tab._content_layout.addWidget(sl)
        assert tab._count_render_targets() == 2


# ── _SparklineLabel ────────────────────────────────────────────────────


class TestSparklineLabel:
    def test_creation(self, qt_widget, qtbot):
        label = _SparklineLabel()
        qtbot.addWidget(label)
        assert label._pending_tag is None
        assert label._target_w == 0
        assert label._target_h == 0
        assert label._scale == 1.0
        assert label._last_fig is None
        assert label._owner is None

    def test_render_async_defers_when_hidden(self, qt_widget, qtbot):
        from ui.plotly_charts import make_sparkline_chart
        from ui.plotly_renderer import get_render_manager

        manager = get_render_manager()
        before = manager.stats()["total_requests"]
        label = _SparklineLabel()
        fig = make_sparkline_chart([1, 2, 3], color="#6366f1")
        label.render_async(fig, 260, 36)
        after = manager.stats()["total_requests"]
        assert after == before, "render_async on hidden label should defer"

    def test_render_async_zero_dimensions(self, qt_widget, qtbot):
        from ui.plotly_charts import make_sparkline_chart
        from ui.plotly_renderer import get_render_manager

        manager = get_render_manager()
        before = manager.stats()["total_requests"]
        label = _SparklineLabel()
        fig = make_sparkline_chart([1, 2, 3], color="#6366f1")
        label.render_async(fig, 0, 0)
        after = manager.stats()["total_requests"]
        assert after == before, "render_async with zero dims should be no-op"

    def test_render_async_cache_hit(self, qt_widget, qtbot):
        from ui.plotly_charts import make_sparkline_chart
        from ui.plotly_renderer import get_render_manager

        manager = get_render_manager()
        label = _SparklineLabel()
        label.show()
        fig = make_sparkline_chart([1, 2, 3], color="#6366f1")
        w, h = 260, 36
        # Pre-populate cache
        label._pixmap_cache[(id(fig), w, h)] = QPixmap(w, h)
        label._target_w = w
        label._target_h = h
        before = manager.stats()["total_requests"]
        label.render_async(fig, w, h)
        after = manager.stats()["total_requests"]
        assert after == before, "Cache hit should not submit a render"

    def test_set_owner_and_owner(self, qt_widget, qtbot):
        label = _SparklineLabel()
        qtbot.addWidget(label)
        owner = MagicMock()
        label.set_owner(owner)
        assert label.owner() is owner

    def test_cache_bounded(self, qt_widget, qtbot):
        label = _SparklineLabel()
        # Fill past the cache max
        for i in range(_SparklineLabel.CACHE_MAX_ENTRIES + 3):
            label._cache_pixmap(i, 100, 100, QPixmap(100, 100))
        assert len(label._pixmap_cache) <= _SparklineLabel.CACHE_MAX_ENTRIES

    def test_show_event_defers_when_no_fig(self, qt_widget, qtbot):
        label = _SparklineLabel()
        qtbot.addWidget(label)
        # Should not crash
        label.showEvent(None)

    def test_show_event_skips_when_pixmap_exists(self, qt_widget, qtbot):
        from ui.plotly_charts import make_sparkline_chart

        label = _SparklineLabel()
        qtbot.addWidget(label)
        fig = make_sparkline_chart([1, 2, 3], color="#6366f1")
        w, h = 260, 36
        label._last_fig = fig
        label._target_w = w
        label._target_h = h
        label.setPixmap(QPixmap(w, h))
        # Should not re-render since pixmap already set
        label.showEvent(None)
        # No crash = pass

    def test_show_event_skips_when_in_flight(self, qt_widget, qtbot):
        from ui.plotly_charts import make_sparkline_chart

        label = _SparklineLabel()
        qtbot.addWidget(label)
        fig = make_sparkline_chart([1, 2, 3], color="#6366f1")
        label._last_fig = fig
        label._target_w = 260
        label._target_h = 36
        label._pending_tag = object()
        # Should not re-render since a render is in flight
        label.showEvent(None)
        # No crash = pass


# ── _render_sparkline shim ──────────────────────────────────────────────


class TestRenderSparklineShim:
    def test_render_sparkline_defers_when_hidden(self, qt_widget, qtbot):
        from ui.plotly_charts import make_sparkline_chart
        from ui.plotly_renderer import get_render_manager

        manager = get_render_manager()
        before = manager.stats()["total_requests"]
        label = _SparklineLabel()
        fig = make_sparkline_chart([1, 2, 3], color="#6366f1")
        _render_sparkline(fig, label, 260, 36)
        after = manager.stats()["total_requests"]
        assert after == before, "_render_sparkline on hidden label should defer"


# ── Figure tracking ────────────────────────────────────────────────────


class TestBaseTabFigTracking:
    def test_figs_list_starts_empty(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        assert tab._figs == []

    def test_plotly_chart_card_returns_frame(self, qt_widget, qtbot):
        import plotly.graph_objects as go

        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        fig = go.Figure()
        card = tab._build_plotly_chart_card(fig, title="Test", min_height=180)
        assert card is not None
        assert isinstance(card, QFrame)

    def test_add_plotly_chart_adds_to_layout(self, qt_widget, qtbot):
        import plotly.graph_objects as go

        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        fig = go.Figure()
        tab._add_plotly_chart(fig, title="Test")
        assert tab._content_layout.count() >= 1

    def test_add_plotly_chart_row(self, qt_widget, qtbot):
        import plotly.graph_objects as go

        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        figs = [go.Figure(), go.Figure()]
        widgets = tab._add_plotly_chart_row(figs, titles=["A", "B"], columns=2)
        assert len(widgets) == 2

    def test_add_plotly_chart_grid(self, qt_widget, qtbot):
        import plotly.graph_objects as go

        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        figs = [go.Figure(), go.Figure(), go.Figure()]
        widgets = tab._add_plotly_chart_grid(figs, titles=["A", "B", "C"], columns=2)
        assert len(widgets) == 3


class TestBaseTabChartOrKpi:
    def test_chart_or_kpi_with_empty_data(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_chart_or_kpi(
            data=[],
            title="Test",
            kpi_value_fn=lambda d: ("42", "", ""),
            chart_fn=lambda d: None,
        )
        # No content added for empty data

    def test_chart_or_kpi_with_sparse_data_renders_kpi(self, qt_widget, qtbot):
        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._add_chart_or_kpi(
            data=[{"x": 1}],
            title="Sparse",
            kpi_value_fn=lambda d: ("42", "subtitle", "#22c55e"),
            chart_fn=lambda d: None,
            min_chart_points=3,
        )
        # Should have added a KPI row
        assert tab._content_layout.count() >= 1

    def test_chart_or_kpi_with_enough_data_calls_chart_fn(self, qt_widget, qtbot):
        chart_called = {"called": False}

        class Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = Stub(parent=qt_widget, service=None)
        qtbot.addWidget(tab)

        def chart_fn(data):
            chart_called["called"] = True

        tab._add_chart_or_kpi(
            data=[{"x": 1}, {"x": 2}, {"x": 3}],
            title="Enough",
            kpi_value_fn=lambda d: ("42", "", ""),
            chart_fn=chart_fn,
            min_chart_points=3,
        )
        assert chart_called["called"] is True
