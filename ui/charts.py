"""DEPRECATED — legacy matplotlib chart utilities for Operion ERP.

.. deprecated::
    This module is kept only as a backwards-compatible stub.  The
    original matplotlib implementation has been removed because the
    entire chart layer has been migrated to Plotly.

    Migrate any remaining callers to:

    * ``ui.plotly_charts`` — chart factory functions (``make_*_chart``).
    * ``ui.plotly_renderer`` — Qt widget ``PlotlyChartWidget`` and
      helpers ``empty_figure`` / ``figure_to_qpixmap``.

    Attempting to use any of the original factory functions will raise
    ``NotImplementedError``.  No matplotlib symbols are imported by this
    module, so removing the matplotlib dependency from the project
    requirements is safe.

Migration history
=================
Phase 0: Decision — Plotly SVG rendering chosen over QWebEngineView.
Phase 1: Foundation — ``ui/plotly_theme.py`` + ``ui/plotly_renderer.py``.
Phase 2: ``ui/plotly_charts.py`` (19 chart factories).
Phase 3: ``_tab_base.py`` plotly-aware helpers.
Phase 4: 6 analytics tab files rewritten.
Phase 5: KPI sparklines migrated to Plotly SVG.
Phase 6: Analytics layout test suite rewritten.
Phase 7: Standalone ``fleet_tab.py`` and ``maintenance_analytics_view.py``
migrated, old helpers removed from ``_tab_base.py``.
Phase 8 (this file): ``ui/charts.py`` retired; matplotlib removed from
``requirements.txt``.
"""
from __future__ import annotations



def _unavailable(*_args, **_kwargs):
    raise NotImplementedError(
        "ui.charts has been retired. Use ui.plotly_charts and "
        "ui.plotly_renderer instead. See the module docstring for the "
        "Plotly migration history."
    )


# ── Chart factory functions (all raise NotImplementedError) ──
make_trend_chart = _unavailable
make_bar_chart = _unavailable
make_line_chart = _unavailable
make_pie_chart = _unavailable
make_horizontal_bar = _unavailable
make_stacked_bar = _unavailable
make_grouped_bar = _unavailable
make_scatter_chart = _unavailable
make_histogram = _unavailable
make_box_plot = _unavailable
make_heatmap = _unavailable
make_waterfall = _unavailable
make_bullet = _unavailable
make_calendar_heatmap = _unavailable
make_lollipop = _unavailable
make_fleet_status = _unavailable
make_cost_per_truck = _unavailable
make_top_clients = _unavailable
make_client_profit = _unavailable
make_sparkline = _unavailable
apply_dark_style = _unavailable
apply_empty_state = _unavailable
empty_chart_message = _unavailable

# ── Public constants (kept for reference, raise on access) ──
def __getattr__(name):
    # The old module exposed CHART_FIGSIZE_* tuples and colour
    # constants.  Returning the stub value lets import statements like
    # ``from ui.charts import CHART_FIGSIZE_TILE`` succeed at parse
    # time but break the moment the symbol is *used*.  This catches
    # forgotten callers without breaking ``import ui.charts``.
    if name.startswith("CHART_FIGSIZE_") or name.startswith("CHART_"):
        return _unavailable
    raise AttributeError(
        f"module 'ui.charts' has no attribute {name!r} "
        "(module has been retired; use ui.plotly_charts and ui.plotly_renderer)"
    )
