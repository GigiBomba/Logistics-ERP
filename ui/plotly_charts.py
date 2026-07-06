"""Shared Plotly chart utilities for Operion ERP.

Drop-in replacement for ``ui/charts.py`` using Plotly instead of matplotlib.
Every factory accepts the same data parameters and returns a ``go.Figure``.

Signature changes from matplotlib version:
  * Removed ``fig: Figure, ax: Axes`` — Plotly figures are self-contained.
  * All functions **return** ``go.Figure`` instead of mutating in-place.
  * ``show_title`` controls ``fig.update_layout(title=...)``.
  * ``empty_message`` returns a placeholder ``go.Figure`` via
    :func:`ui.plotly_renderer.empty_figure`.
"""

from __future__ import annotations

import calendar
import logging
import math
from datetime import datetime, timedelta

import numpy as np
import plotly.graph_objects as go

from services.i18n import t as _t
from ui.design_tokens import (
    BG_ELEVATED,
    BG_SURFACE,
    BORDER_DEFAULT,
    BORDER_FAINT,
    DANGER_DIM,
    FONT_FAMILY,
    FONT_MONO,
    SUCCESS_DIM,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.plotly_renderer import empty_figure
from ui.plotly_theme import (
    PLOTLY_ACCENT,
    PLOTLY_DANGER,
    PLOTLY_DANGER_LIGHT,
    PLOTLY_INFO,
    PLOTLY_NEUTRAL,
    PLOTLY_SECONDARY,
    PLOTLY_SUCCESS,
    PLOTLY_SUCCESS_LIGHT,
    PLOTLY_WARNING,
    PLOTLY_WARNING_LIGHT,
    _hex_to_alpha,
    _hex_to_rgb_int,
    _hex_to_rgb_tuple,
    apply_operion_theme,
)

logger = logging.getLogger(__name__)

# ── Re-export constants for backward compatibility ───────────────────

CHART_ACCENT = PLOTLY_ACCENT
CHART_SECONDARY = PLOTLY_SECONDARY
CHART_SUCCESS = PLOTLY_SUCCESS
CHART_SUCCESS_LIGHT = PLOTLY_SUCCESS_LIGHT
CHART_WARNING = PLOTLY_WARNING
CHART_WARNING_LIGHT = PLOTLY_WARNING_LIGHT
CHART_DANGER = PLOTLY_DANGER
CHART_DANGER_LIGHT = PLOTLY_DANGER_LIGHT
CHART_INFO = PLOTLY_INFO


def _value_color(delta: float | None) -> str:
    """Return a hex colour for a numeric delta — green if > 0, warning if 0/None, red if < 0."""
    if delta is None or delta == 0:
        return PLOTLY_WARNING
    return PLOTLY_SUCCESS if delta > 0 else PLOTLY_DANGER


def _value_colors(values: list) -> list[str]:
    """Return a list of hex colours: green if > 0, warning if 0, red if < 0."""
    return [
        PLOTLY_WARNING if v is None or v == 0 else PLOTLY_SUCCESS if v > 0 else PLOTLY_DANGER
        for v in values
    ]

# Legacy sizing (pixel equivalents of old inch-based sizes)
CHART_FIGSIZE_TILE = (420, 170)
CHART_FIGSIZE_WIDE = (900, 220)
CHART_FIGSIZE_HALF = (700, 300)
CHART_FIGSIZE_FULL = (1000, 500)
CHART_DPI = 100

# ── Internal helpers ─────────────────────────────────────────────────


def _sanitize_labels(labels: list) -> list:
    return [str(label) if label is not None else "" for label in labels]


def _sanitize_values(values: list) -> list:
    return [float(v) if v is not None else 0.0 for v in values]


def _format_value(value, is_currency: bool = False) -> str:
    if value is None:
        return "0"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0"
    # Guard against non-finite values that would produce garbled output
    if not math.isfinite(value):
        return "0"
    suffix = "\u20ac" if is_currency else ""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M{suffix}"
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}k{suffix}"
    return f"{value:,.0f}{suffix}"


def _resolved_color(color, n: int) -> list:
    """If *color* is a single string, repeat it *n* times."""
    if isinstance(color, (list, tuple)):
        return list(color)
    return [color] * n


def _apply_common_layout(
    fig: go.Figure,
    title: str,
    show_title: bool,
    is_currency: bool = False,
    horizontal: bool = False,
) -> None:
    """Apply Operion dark theme and optional title/currency formatting.

    When *horizontal* is ``True`` (orientation="h"), values are on the
    X-axis, so the currency prefix is applied to ``xaxis`` instead of
    ``yaxis`` — otherwise the prefix would appear on label text.
    """
    apply_operion_theme(fig)
    if show_title and title:
        fig.update_layout(title={"text": title})
    fig.update_layout(autosize=True, margin={
        "t": 30 if show_title and title else 10,
        "b": 30,
        "l": 150 if horizontal else 50,
        "r": 30,
    })
    if is_currency:
        axis = "xaxis" if horizontal else "yaxis"
        fig.update_layout(
            {axis: {"tickprefix": "\u20ac", "tickformat": ",.0f"}},
        )


def _empty_or_data(
    items: list,
    empty_message: str,
    title: str,
    show_title: bool,
) -> go.Figure | None:
    """Return an empty figure if *items* is falsy, else None."""
    if not items:
        fig = empty_figure(empty_message)
        if show_title and title:
            fig.update_layout(title={"text": title})
        return fig
    return None


# ═══════════════════════════════════════════════════════════════════
# Chart factories
# ═══════════════════════════════════════════════════════════════════


def make_bar_chart(
    labels: list[str],
    values: list[float],
    title: str = "",
    color: str | list[str] = CHART_ACCENT,
    horizontal: bool = True,
    highlight_max: bool = False,
    empty_message: str = "",
    is_currency: bool = False,
    show_title: bool = True,
    max_bar_width: float = 0.0,
) -> go.Figure:
    """Premium bar chart — horizontal or vertical with value annotations."""
    labels = _sanitize_labels(labels)
    values = _sanitize_values(values)
    if not labels or not values:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    colors = _resolved_color(color, len(labels))
    if highlight_max and values:
        try:
            max_val = max(values)
            colors = [
                PLOTLY_SECONDARY if v == max_val else c
                for v, c in zip(values, colors)
            ]
        except ValueError:
            pass

    text_vals = [_format_value(v, is_currency) for v in values]

    bar_width = max_bar_width if max_bar_width > 0 else 0.6

    if horizontal:
        # Sort descending so biggest bar at top
        paired = sorted(zip(labels, values, colors, text_vals), key=lambda x: x[1], reverse=True)
        labels = [p[0] for p in paired]
        values = [p[1] for p in paired]
        colors = [p[2] for p in paired]
        text_vals = [p[3] for p in paired]

        fig = go.Figure(
            go.Bar(
                x=values,
                y=labels,
                orientation="h",
                marker={"color": colors},
                text=text_vals,
                textposition="outside",
                textfont={"color": TEXT_PRIMARY, "size": 10, "family": FONT_MONO},
                width=bar_width,
            )
        )
    else:
        fig = go.Figure(
            go.Bar(
                x=labels,
                y=values,
                marker={"color": colors},
                text=text_vals,
                textposition="outside",
                textfont={"color": TEXT_PRIMARY, "size": 10, "family": FONT_MONO},
                width=bar_width,
            )
        )

    _apply_common_layout(fig, title, show_title, is_currency, horizontal)
    if horizontal:
        fig.update_layout(yaxis={"autorange": "reversed"})
    return fig


def make_line_chart(
    x_labels: list[str],
    y_series: list[tuple[list[float], str, str]],
    title: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Multi-series line chart with fill and markers."""
    x_labels = _sanitize_labels(x_labels)
    if not x_labels or not y_series:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    fig = go.Figure()
    single_point = len(x_labels) < 2

    for values, label, color in y_series:
        values = _sanitize_values(values)
        if len(values) != len(x_labels):
            continue
        if single_point:
            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=values,
                    mode="markers",
                    name=label,
                    marker={"color": color, "size": 10, "line": {"color": BG_ELEVATED, "width": 1.2}},
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=values,
                    mode="lines+markers",
                    name=label,
                    line={"color": color, "width": 2},
                    marker={"size": 5, "color": BG_ELEVATED, "line": {"color": color, "width": 1.2}},
                    fill="tozeroy",
                    fillcolor=f"rgba({_hex_to_rgb_int(color)},0.12)",
                )
            )

    if not fig.data:
        return empty_figure(empty_message)

    _apply_common_layout(fig, title, show_title)
    return fig


def make_pie_chart(
    sizes: list[float],
    labels: list[str],
    title: str = "",
    colors: list[str] | None = None,
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Donut chart with center total and percentage labels.

    Maintains a square aspect ratio so the pie does not stretch.
    Long labels are truncated at 22 chars to reduce overlap.
    """
    sizes = _sanitize_values(sizes)
    labels = _sanitize_labels(labels)
    if not sizes or sum(sizes) == 0:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    pie_colors = colors or [
        CHART_ACCENT,
        CHART_SECONDARY,
        CHART_SUCCESS,
        CHART_WARNING,
        CHART_DANGER,
        CHART_INFO,
    ]
    total = sum(sizes)

    # Cap long labels so they don't overflow the slice
    truncated = [lbl if len(lbl) <= 22 else lbl[:20] + "\u2026" for lbl in labels]

    fig = go.Figure(
        go.Pie(
            labels=truncated,
            values=sizes,
            hole=0.4,
            marker={"colors": pie_colors[: len(sizes)], "line": {"color": BG_ELEVATED, "width": 2}},
            texttemplate="%{label}<br> %{percent:.1%}",
            textfont={"color": TEXT_SECONDARY, "size": 10, "family": FONT_FAMILY},
            insidetextfont={"color": TEXT_PRIMARY, "size": 10, "family": FONT_FAMILY},
            insidetextorientation="auto",
            sort=False,
        )
    )
    fig.add_annotation(
        text=_format_value(total),
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"color": TEXT_PRIMARY, "size": 13, "family": FONT_MONO},
    )

    _apply_common_layout(fig, title, show_title)
    fig.update_layout(
        width=260,
        height=260,
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
        legend={
            "font": {"color": TEXT_SECONDARY, "size": 10, "family": FONT_FAMILY},
            "orientation": "v",
            "x": 1.02,
            "y": 0.5,
            "xanchor": "left",
            "yanchor": "middle",
        },
    )
    fig.update_traces(textposition="outside")
    return fig


def make_trend_chart(
    x_labels: list[str],
    values: list[float],
    title: str = "",
    color: str = "",
    empty_message: str = "",
    show_title: bool = True,
    is_currency: bool = False,
) -> go.Figure:
    """Single-series line chart with area fill."""
    x_labels = _sanitize_labels(x_labels)
    values = _sanitize_values(values)
    if not x_labels or not values:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]
    if not color:
        color = PLOTLY_ACCENT

    text_vals = [_format_value(v, is_currency) for v in values]

    if len(values) < 2:
        # Single point → bar
        fig = go.Figure(
            go.Bar(
                x=x_labels,
                y=values,
                marker_color=color,
                text=text_vals,
                textposition="outside",
                textfont={"color": TEXT_PRIMARY, "size": 10, "family": FONT_MONO},
                width=0.4,
            )
        )
    elif max(values) == min(values):
        # Flat line
        flat = values[0]
        # Pre-build the layout with the operion theme so add_hline has
        # valid axes to reference.
        fig = go.Figure()
        apply_operion_theme(fig)
        fig.add_hline(y=flat, line={"color": color, "width": 2})
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=values,
                mode="markers",
                marker={"size": 8, "color": BG_ELEVATED, "line": {"color": color, "width": 1.5}},
                showlegend=False,
            )
        )
    else:
        alpha_hex = _hex_to_alpha(color, 0.15)
        fig = go.Figure(
            go.Scatter(
                x=x_labels,
                y=values,
                mode="lines+markers",
                line={"color": color, "width": 2},
                marker={"size": 5, "color": BG_ELEVATED, "line": {"color": color, "width": 1.2}},
                fill="tozeroy",
                fillcolor=alpha_hex,
            )
        )

    _apply_common_layout(fig, title, show_title, is_currency)
    return fig


def make_lollipop_chart(
    labels: list[str],
    values: list[float],
    title: str = "",
    color: str | list[str] = CHART_ACCENT,
    empty_message: str = "",
    is_currency: bool = False,
    show_title: bool = True,
    max_items: int = 10,
) -> go.Figure:
    """Ranked horizontal bar chart — sorted descending, biggest at top."""
    labels = _sanitize_labels(labels)
    values = _sanitize_values(values)
    if not labels or not values:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    # Pair colors and text with values BEFORE sorting so they stay aligned.
    colors_raw = _resolved_color(color, len(values))
    text_vals = [_format_value(v, is_currency) for v in values]
    paired = sorted(zip(labels, values, colors_raw, text_vals), key=lambda x: x[1], reverse=True)
    if len(paired) > max_items:
        paired = paired[:max_items]
    labels = [p[0] for p in paired]
    values = [p[1] for p in paired]
    colors = [p[2] for p in paired]
    text_vals = [p[3] for p in paired]

    # Lollipop: line stems (scatter lines) + dot markers (scatter)
    # with value labels rendered as separated scatter text traces.
    # Using scatter lines instead of bars prevents stems from overlapping
    # the y-axis labels at x=0.
    fig = go.Figure()

    # Stems: one line per category from a small negative offset to the value.
    # Starting at x=0 overlaps the y-axis tick labels, so we shift the origin
    # slightly left to create breathing room.
    stem_start = -max(abs(v) for v in values) * 0.03
    stem_x, stem_y = [], []
    for i, v in enumerate(values):
        stem_x += [stem_start, v, None]
        stem_y += [labels[i], labels[i], None]
    fig.add_trace(
        go.Scatter(
            x=stem_x, y=stem_y,
            mode="lines",
            line={"color": TEXT_MUTED, "width": 2},
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Split positive/negative marker traces so text can be positioned
    # per side: "middle right" for positive, "middle left" for negative.
    pos_x, pos_y, pos_txt, pos_clr = [], [], [], []
    neg_x, neg_y, neg_txt, neg_clr = [], [], [], []
    for i, v in enumerate(values):
        if v >= 0:
            pos_x.append(v)
            pos_y.append(labels[i])
            pos_txt.append(text_vals[i])
            pos_clr.append(colors[i])
        else:
            neg_x.append(v)
            neg_y.append(labels[i])
            neg_txt.append(text_vals[i])
            neg_clr.append(colors[i])
    if pos_x:
        fig.add_trace(
            go.Scatter(
                x=pos_x, y=pos_y,
                mode="markers+text",
                text=pos_txt,
                textposition="middle right",
                textfont={"color": TEXT_PRIMARY, "size": 9, "family": FONT_MONO},
                marker={"color": pos_clr, "size": 12, "line": {"color": BG_ELEVATED, "width": 1}},
                showlegend=False,
            )
        )
    if neg_x:
        fig.add_trace(
            go.Scatter(
                x=neg_x, y=neg_y,
                mode="markers+text",
                text=neg_txt,
                textposition="middle left",
                textfont={"color": TEXT_PRIMARY, "size": 9, "family": FONT_MONO},
                marker={"color": neg_clr, "size": 12, "line": {"color": BG_ELEVATED, "width": 1}},
                showlegend=False,
            )
        )

    _apply_common_layout(fig, title, show_title, is_currency, horizontal=True)
    fig.update_layout(
        yaxis={"autorange": "reversed", "automargin": True},
    )

    # Text-overflow guard: extend the x-axis range so value annotations
    # never get clipped.  15 % padding on the maximum (and minimum)
    # keeps labels visible regardless of bar length.
    if values:
        vmax = max(values)
        vmin = min(values)
        pad = max(abs(vmax), abs(vmin), 1.0) * 0.15
        fig.update_xaxes(range=[vmin - pad, vmax + pad])
    return fig


def make_histogram_chart(
    values: list[float],
    title: str = "",
    bins: int = 20,
    color: str = "",
    x_label: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Frequency distribution histogram with gradient opacity bars."""
    values = _sanitize_values(values)
    values = [v for v in values if v > 0]
    if not values:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]
    if not color:
        color = PLOTLY_ACCENT

    # Use log-spaced bins if values span multiple orders of magnitude
    vmin = min(values)
    vmax = max(values)
    use_log = vmax > 0 and vmin > 0 and (vmax / max(vmin, 1)) > 50

    if use_log:
        # Pass explicit log-spaced bin edges via size (not start/end, which
        # don't auto-compute with log axis).
        log_edges = np.logspace(
            np.log10(max(vmin, 0.1)),
            np.log10(vmax),
            bins + 1,
        )
        (log_edges[-1] - log_edges[0]) / bins
        fig = go.Figure(
            go.Histogram(
                x=values,
                nbinsx=bins,
                marker={"color": color, "line": {"color": BG_ELEVATED, "width": 0.8}},
                opacity=0.85,
            )
        )
        fig.update_xaxes(type="log", range=[np.log10(log_edges[0]), np.log10(log_edges[-1])])
    else:
        fig = go.Figure(
            go.Histogram(
                x=values,
                nbinsx=bins,
                marker={"color": color, "line": {"color": BG_ELEVATED, "width": 0.8}},
                opacity=0.85,
            )
        )

    _apply_common_layout(fig, title, show_title)
    if x_label:
        fig.update_xaxes(title=x_label)
    fig.update_yaxes(title=_t("common.count", default="Count"))
    return fig


def make_stacked_area_chart(
    x_labels: list[str],
    groups: list[tuple[str, list[float], str]],
    title: str = "",
    empty_message: str = "",
    is_currency: bool = False,
    show_title: bool = True,
) -> go.Figure:
    """Stacked area chart — composition changing over time."""
    x_labels = _sanitize_labels(x_labels)
    if not x_labels or not groups:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    fig = go.Figure()
    valid = False
    for label, vals, color in groups:
        vals = _sanitize_values(vals)
        if len(vals) != len(x_labels):
            continue
        valid = True
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=vals,
                mode="lines",
                name=label,
                line={"color": color, "width": 0.5},
                stackgroup="one",
                fillcolor=color,
                opacity=0.7,
            )
        )

    if not valid:
        return empty_figure(empty_message)

    _apply_common_layout(fig, title, show_title, is_currency)
    return fig


def make_bullet_chart(
    value: float,
    target: float,
    title: str = "",
    label: str = "",
    ranges: list[tuple[float, str]] | None = None,
    show_title: bool = True,
) -> go.Figure:
    """Bullet chart — single KPI value against a target with banded background."""
    if target <= 0:
        return empty_figure("No target")

    if ranges is None:
        ranges = [(0.5, DANGER_DIM), (0.8, BORDER_DEFAULT), (1.0, SUCCESS_DIM)]

    pct = value / target
    bar_color = PLOTLY_SUCCESS if pct >= 1.0 else PLOTLY_WARNING if pct >= 0.7 else PLOTLY_DANGER

    fig = go.Figure()

    # Background bands
    for threshold, band_color in ranges:
        fig.add_trace(
            go.Bar(
                y=[""],  # single horizontal bar
                x=[threshold * target],
                orientation="h",
                marker={"color": band_color, "line": {"width": 0}},
                width=0.6,
                opacity=0.7,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Actual value bar
    fig.add_trace(
        go.Bar(
            y=[""],
            x=[min(value, target * 1.1)],
            orientation="h",
            marker={"color": bar_color, "line": {"color": BG_ELEVATED, "width": 0.6}},
            width=0.3,
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Target marker line
    fig.add_vline(
        x=target,
        line={"color": TEXT_PRIMARY, "width": 1, "dash": "dash"},
        opacity=0.7,
    )

    # Percentage annotation
    fig.add_annotation(
        x=target * 1.1,
        y=0,
        text=f"{pct * 100:.0f}%",
        showarrow=False,
        font={"color": TEXT_PRIMARY, "size": 11, "family": FONT_MONO},
        xanchor="left",
    )

    fig.update_layout(
        barmode="overlay",
        xaxis={"range": [0, target * 1.25]},
        yaxis={"showticklabels": False, "showgrid": False, "zeroline": False},
        showlegend=False,
    )

    _apply_common_layout(fig, title, show_title)
    if label:
        fig.add_annotation(
            text=label,
            x=0,
            y=1.1,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": TEXT_SECONDARY, "size": 9, "family": FONT_FAMILY},
        )
    return fig


def make_calendar_heatmap(
    daily_values: list[tuple[str, float]],
    title: str = "",
    color_map: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """GitHub-style calendar heatmap showing daily activity."""
    if not daily_values:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    if not color_map:
        color_map = PLOTLY_ACCENT

    data: dict[str, float] = {}
    for d, v in daily_values:
        if d:
            data[d] = float(v) if v is not None else 0.0

    if not data:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    dates = sorted(data.keys())
    try:
        start = datetime.strptime(dates[0], "%Y-%m-%d")
        end = datetime.strptime(dates[-1], "%Y-%m-%d")
    except (ValueError, TypeError):
        return empty_figure(empty_message or "Invalid date format")

    days_list = []
    d = start
    while d <= end:
        days_list.append(d)
        d = d + timedelta(days=1)

    n_weeks = (len(days_list) + start.weekday() + 6) // 7
    grid: list = [[None] * n_weeks for _ in range(7)]
    # Track the month(s) seen in each week column so the x-axis can
    # place a month label at the column where a month first appears.
    week_months: list[set] = [set() for _ in range(n_weeks)]
    for i, day in enumerate(days_list):
        wk = (i + start.weekday()) // 7
        grid[day.weekday()][wk] = data.get(day.strftime("%Y-%m-%d"), 0.0)
        week_months[wk].add(day.month)

    max_v = max(max((c for c in row if c is not None), default=0) for row in grid)
    if max_v == 0:
        max_v = 1

    # Build heatmap data
    z = []
    # Locale-aware short day labels: ``calendar.day_abbr`` is [Mon, Tue, ...]
    # when the C locale is active and follows the active locale otherwise.
    # We resolve them eagerly here so that a locale change between calls
    # is reflected (calendar.day_abbr is a mutable list).
    y_labels = [calendar.day_abbr[i] or ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i]
                for i in range(7)]
    for r in range(7):
        row_vals = []
        for c in range(n_weeks):
            v = grid[r][c]
            row_vals.append(v if v is not None else -1)
        z.append(row_vals)

    # Custom colorscale: transparent for missing, gradient for values
    r, g, b = _hex_to_rgb_tuple(color_map)
    colorscale = [
        [0.0, BG_SURFACE],
        [0.001, f"rgba({r},{g},{b},0.2)"],
        [0.3, f"rgba({r},{g},{b},0.5)"],
        [0.7, f"rgba({r},{g},{b},0.8)"],
        [1.0, f"rgba({r},{g},{b},1.0)"],
    ]

    # x-axis: show month label at the first week of each month, hide the
    # rest.  We use the locale-aware short month name from
    # ``calendar.month_abbr`` (index 0 is the empty string).
    x_vals = list(range(n_weeks))
    x_ticktext: list[str] = []
    x_tickvals: list[int] = []
    seen_months: set = set()
    for wk_idx, months in enumerate(week_months):
        # Pick the earliest month in this column that we haven't shown yet.
        for month_idx in sorted(months):
            if month_idx not in seen_months:
                seen_months.add(month_idx)
                month_name = calendar.month_abbr[month_idx] or [
                    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                ][month_idx]
                x_tickvals.append(wk_idx)
                x_ticktext.append(month_name)
                break  # one label per column

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x_vals,
            y=y_labels,
            colorscale=colorscale,
            zmin=0,
            zmax=max_v,
            showscale=False,
            xgap=2,
            ygap=2,
        )
    )

    fig.update_layout(
        yaxis={"autorange": "reversed"},
        xaxis={
            "tickmode": "array",
            "tickvals": x_tickvals,
            "ticktext": x_ticktext,
            "showgrid": False,
            "zeroline": False,
            "side": "top",
            "tickfont": {"color": TEXT_MUTED, "size": 10},
        },
    )

    _apply_common_layout(fig, title, show_title)
    return fig


def make_sparkline_chart(
    values: list[float],
    color: str = "",
    show_area: bool = True,
    width: float = 2.0,
    height: float = 0.4,
) -> go.Figure:
    """Compact sparkline — no axes, no labels, just the trend shape."""
    if not color:
        color = PLOTLY_ACCENT
    values = _sanitize_values(values)
    if not values:
        values = [0.0]

    r, g, b = _hex_to_rgb_tuple(color)

    if len(values) < 2:
        fig = go.Figure(
            go.Scatter(
                x=[0],
                y=[values[0]],
                mode="markers",
                marker={"color": color, "size": 8},
                showlegend=False,
            )
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            xaxis={"visible": False, "fixedrange": True},
            yaxis={"visible": False, "fixedrange": True},
            showlegend=False,
            width=int(width * 100),
            height=int(height * 100),
        )
        return fig
    else:
        fig = go.Figure(
            go.Scatter(
                y=values,
                mode="lines",
                line={"color": color, "width": 2},
                fill="tozeroy" if show_area else None,
                fillcolor=f"rgba({r},{g},{b},0.25)" if show_area else None,
            )
        )
        # Last point dot
        fig.add_trace(
            go.Scatter(
                x=[len(values) - 1],
                y=[values[-1]],
                mode="markers",
                marker={"color": color, "size": 8},
                showlegend=False,
            )
        )

    # Strip all chrome
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis={"visible": False, "fixedrange": True},
        yaxis={"visible": False, "fixedrange": True},
        showlegend=False,
        width=int(width * 100),
        height=int(height * 100),
    )
    return fig


def make_cost_per_truck_chart(
    labels: list[str],
    costs: list[float],
    title: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Horizontal cost breakdown chart with accent highlight for maximum."""
    labels = _sanitize_labels(labels)
    costs = _sanitize_values(costs)
    if not labels or not costs:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    colors = [PLOTLY_ACCENT] * len(labels)
    if costs:
        max_cost = max(costs)
        colors = [
            PLOTLY_DANGER if c == max_cost else clr for c, clr in zip(costs, colors)
        ]

    text_vals = [_format_value(c) for c in costs]

    paired = sorted(zip(labels, costs, colors, text_vals), key=lambda x: x[1], reverse=True)
    labels = [p[0] for p in paired]
    costs = [p[1] for p in paired]
    colors = [p[2] for p in paired]
    text_vals = [p[3] for p in paired]

    fig = go.Figure(
        go.Bar(
            x=costs,
            y=labels,
            orientation="h",
            marker={"color": colors},
            text=text_vals,
            textposition="outside",
            textfont={"color": TEXT_SECONDARY, "size": 10, "family": FONT_MONO},
            width=0.6,
        )
    )

    _apply_common_layout(fig, title, show_title)
    fig.update_layout(yaxis={"autorange": "reversed"})
    return fig


def make_fleet_status_chart(
    labels: list[str],
    counts: list[int],
    title: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Horizontal fleet status bar chart with semantic colors."""
    labels = _sanitize_labels(labels)
    counts = [int(c) if c is not None else 0 for c in counts]
    if not labels or not counts:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    status_colors: dict = {
        "active": PLOTLY_SUCCESS,
        "in_progress": PLOTLY_ACCENT,
        "on_trip": PLOTLY_ACCENT,
        "idle": TEXT_MUTED,
        "maintenance": PLOTLY_WARNING,
        "inactive": PLOTLY_DANGER,
        "cancelled": PLOTLY_NEUTRAL,
    }
    colors = [
        status_colors.get(lbl.lower().replace(" ", "_"), TEXT_MUTED) for lbl in labels
    ]
    text_vals = [_format_value(c) for c in counts]

    paired = sorted(zip(labels, counts, colors, text_vals), key=lambda x: x[1], reverse=True)
    labels = [p[0] for p in paired]
    counts = [p[1] for p in paired]
    colors = [p[2] for p in paired]
    text_vals = [p[3] for p in paired]

    fig = go.Figure(
        go.Bar(
            x=counts,
            y=labels,
            orientation="h",
            marker={"color": colors},
            text=text_vals,
            textposition="outside",
            textfont={"color": TEXT_SECONDARY, "size": 10, "family": FONT_MONO},
            width=0.6,
        )
    )

    _apply_common_layout(fig, title, show_title)
    fig.update_layout(yaxis={"autorange": "reversed"})
    return fig


def make_grouped_bar_chart(
    labels: list[str],
    groups: list[tuple[str, list[float], str]],
    title: str = "",
    horizontal: bool = True,
    empty_message: str = "",
    is_currency: bool = False,
    show_title: bool = True,
) -> go.Figure:
    """Grouped bar chart — multiple series side-by-side per label."""
    labels = _sanitize_labels(labels)
    if not labels or not groups:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    fig = go.Figure()
    valid = False
    for series_name, vals, color in groups:
        vals = _sanitize_values(vals)
        if len(vals) != len(labels):
            continue
        valid = True
        if horizontal:
            fig.add_trace(
                go.Bar(
                    name=series_name,
                    y=labels,
                    x=vals,
                    orientation="h",
                    marker_color=color,
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    name=series_name,
                    x=labels,
                    y=vals,
                    marker_color=color,
                )
            )

    if not valid:
        return empty_figure(empty_message)

    fig.update_layout(barmode="group", bargap=0.15, bargroupgap=0.1)
    if horizontal:
        fig.update_layout(yaxis={"autorange": "reversed"})

    _apply_common_layout(fig, title, show_title, is_currency, horizontal)
    return fig


def make_stacked_bar_chart(
    labels: list[str],
    groups: list[tuple[str, list[float], str]],
    title: str = "",
    horizontal: bool = True,
    empty_message: str = "",
    is_currency: bool = False,
    show_title: bool = True,
) -> go.Figure:
    """Stacked bar chart — multiple series stacked per label."""
    labels = _sanitize_labels(labels)
    if not labels or not groups:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    fig = go.Figure()
    valid = False
    for series_name, vals, color in groups:
        vals = _sanitize_values(vals)
        if len(vals) != len(labels):
            continue
        valid = True
        if horizontal:
            fig.add_trace(
                go.Bar(
                    name=series_name,
                    y=labels,
                    x=vals,
                    orientation="h",
                    marker_color=color,
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    name=series_name,
                    x=labels,
                    y=vals,
                    marker_color=color,
                )
            )

    if not valid:
        return empty_figure(empty_message)

    fig.update_layout(barmode="stack")
    if horizontal:
        fig.update_layout(yaxis={"autorange": "reversed"})

    _apply_common_layout(fig, title, show_title, is_currency)
    return fig


def make_scatter_chart(
    x_values: list[float],
    y_values: list[float],
    labels: list[str],
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    color: str = "",
    empty_message: str = "",
    is_currency: bool = False,
    show_title: bool = True,
) -> go.Figure:
    """Scatter chart with optional trend line — correlation analysis."""
    x_values = _sanitize_values(x_values)
    y_values = _sanitize_values(y_values)
    labels = _sanitize_labels(labels)
    if not x_values or not y_values or len(x_values) != len(y_values):
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]
    if not color:
        color = PLOTLY_ACCENT

    fig = go.Figure(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="markers",
            text=labels,
            marker={"color": color, "size": 8, "opacity": 0.7, "line": {"color": BG_ELEVATED, "width": 1.2}},
            hovertemplate="%{text}<br>x: %{x}<br>y: %{y}<extra></extra>",
        )
    )

    # OLS trend line
    if len(x_values) > 2:
        try:
            z = np.polyfit(x_values, y_values, 1)
            p = np.poly1d(z)
            x_sorted = sorted(x_values)
            fig.add_trace(
                go.Scatter(
                    x=x_sorted,
                    y=p(x_sorted).tolist(),
                    mode="lines",
                    line={"color": color, "width": 1.2, "dash": "dash"},
                    opacity=0.4,
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
        except Exception:
            pass

    _apply_common_layout(fig, title, show_title, is_currency)
    if x_label:
        fig.update_xaxes(title=x_label)
    if y_label:
        fig.update_yaxes(title=y_label)
    return fig


def make_heatmap_chart(
    x_labels: list[str],
    y_labels: list[str],
    data: list[list[float]],
    title: str = "",
    color_map: str = "YlOrRd",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """2D heatmap with value annotations — e.g., route corridor density."""
    if not x_labels or not y_labels or not data:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    try:
        data_array = np.array(data, dtype=float)
        if data_array.shape != (len(y_labels), len(x_labels)):
            return empty_figure(empty_message)
    except Exception:
        return empty_figure(empty_message)

    # Annotation overlap guard: only render per-cell value text when
    # the cell count is small enough that labels remain readable.  The
    # constant below was chosen empirically — at >100 cells the labels
    # overlap and become illegible; below that threshold the small text
    # is still distinguishable.
    n_cells = len(x_labels) * len(y_labels)
    if n_cells > 100:
        # Datasets larger than the threshold are visualized without
        # cell-level annotations; the colour bar conveys the magnitude.
        annotations: list = []
    else:
        annotations = []
        for i in range(len(y_labels)):
            for j in range(len(x_labels)):
                val = data_array[i, j]
                annotations.append(
                    go.layout.Annotation(
                        text=f"{val:.0f}",
                        x=x_labels[j],
                        y=y_labels[i],
                        xref="x",
                        yref="y",
                        showarrow=False,
                        font={"color": TEXT_PRIMARY, "size": 7, "family": FONT_FAMILY},
                    )
                )

    fig = go.Figure(
        go.Heatmap(
            z=data_array.tolist(),
            x=x_labels,
            y=y_labels,
            colorscale=color_map,
            opacity=0.85,
            showscale=True,
            colorbar={
                "tickfont": {"color": TEXT_MUTED, "size": 9},
                "outlinecolor": BORDER_FAINT,
                "outlinewidth": 0.5,
            },
        )
    )
    if annotations:
        fig.update_layout(annotations=annotations)

    _apply_common_layout(fig, title, show_title)
    return fig


def make_waterfall_chart(
    labels: list[str],
    values: list[float],
    title: str = "",
    empty_message: str = "",
    is_currency: bool = False,
    show_title: bool = True,
) -> go.Figure:
    """Waterfall chart — revenue breakdown with connecting lines.

    labels: step names (e.g., ["Revenue", "Fuel", "Toll", "Salary", "Extra", "Net"])
    values: each step's contribution. First and last are absolute, intermediates are deltas.
    """
    labels = _sanitize_labels(labels)
    values = _sanitize_values(values)
    if not labels or not values or len(labels) != len(values):
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]
    # With a single item there is no "first" vs "last" — treat as a plain
    # bar.  Plotly's Waterfall rejects "total" when there is no other
    # measure in the series.
    if len(values) == 1:
        fig = go.Figure(
            go.Bar(
                x=labels,
                y=values,
                marker_color=PLOTLY_ACCENT,
                text=[_format_value(values[0], is_currency)],
                textposition="outside",
                textfont={"color": TEXT_PRIMARY, "size": 9, "family": FONT_MONO},
            )
        )
        _apply_common_layout(fig, title, show_title, is_currency, horizontal=False)
        return fig

    # Build measure array for Plotly's native Waterfall
    measure: list = []
    for i in range(len(values)):
        if i == 0:
            measure.append("absolute")
        elif i == len(values) - 1:
            measure.append("total")
        else:
            measure.append("relative")

    text_vals = [_format_value(v, is_currency) for v in values]

    fig = go.Figure(
        go.Waterfall(
            x=labels,
            y=values,
            measure=measure,
            text=text_vals,
            textposition="inside",
            textfont={"color": TEXT_PRIMARY, "size": 9, "family": FONT_MONO},
            connector={"line": {"color": TEXT_MUTED, "width": 0.5, "dash": "dot"}},
            increasing={"marker": {"color": PLOTLY_SUCCESS}},
            decreasing={"marker": {"color": PLOTLY_DANGER}},
            totals={"marker": {"color": PLOTLY_ACCENT}},
        )
    )

    _apply_common_layout(fig, title, show_title, is_currency)
    return fig


def make_box_plot(
    labels: list[str],
    data: list[list[float]],
    title: str = "",
    color: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Box plot — distribution per group (e.g., trip distance by truck)."""
    if not color:
        color = PLOTLY_ACCENT
    if not labels or not data:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    fig = go.Figure()
    valid = False
    for label, values in zip(labels, data):
        vals = _sanitize_values(values)
        # Skip groups with no data — a single 0.0 would produce a misleading
        # degenerate box.
        if not vals:
            continue
        valid = True
        fig.add_trace(
            go.Box(
                y=vals,
                name=label,
                marker={"color": color},
                line={"color": color},
                fillcolor=color,
                opacity=0.6,
                boxmean=False,
            )
        )

    if not valid:
        return empty_figure(empty_message)

    _apply_common_layout(fig, title, show_title)
    return fig


def make_area_chart(
    x_labels: list[str],
    values: list[float],
    title: str = "",
    color: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Area chart — cumulative-style single series with fill."""
    x_labels = _sanitize_labels(x_labels)
    values = _sanitize_values(values)
    if not x_labels or not values:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]
    if not color:
        color = PLOTLY_ACCENT

    alpha_hex = _hex_to_alpha(color, 0.22)

    if len(values) < 2:
        fig = go.Figure(
            go.Scatter(
                x=x_labels,
                y=values,
                mode="markers",
                marker={"color": color, "size": 12, "line": {"color": BG_ELEVATED, "width": 1.2}},
            )
        )
    elif max(values) == min(values):
        flat = values[0]
        # Pre-build the layout with the operion theme so add_hline has
        # valid axes to reference.
        fig = go.Figure()
        apply_operion_theme(fig)
        fig.add_hline(y=flat, line={"color": color, "width": 2})
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=values,
                mode="markers",
                marker={"size": 8, "color": BG_ELEVATED, "line": {"color": color, "width": 1.5}},
                showlegend=False,
            )
        )
    else:
        fig = go.Figure(
            go.Scatter(
                x=x_labels,
                y=values,
                mode="lines+markers",
                line={"color": color, "width": 2},
                marker={"size": 5, "color": BG_ELEVATED, "line": {"color": color, "width": 1.2}},
                fill="tozeroy",
                fillcolor=alpha_hex,
            )
        )

    _apply_common_layout(fig, title, show_title)
    return fig


def make_treemap_chart(
    labels: list[str],
    values: list[float],
    colors: list[str] | None = None,
    title: str = "",
    root_label: str = "",
    empty_message: str = "",
    show_title: bool = True,
) -> go.Figure:
    """Treemap chart — sized by *values*, colored by *colors*.

    labels: country/entity names (leaf nodes).
    values: numeric values controlling tile area.
    colors: optional list of hex colors (one per label). Falls back to
            CHART_ACCENT if omitted.
    root_label: parent node label displayed at top-left.
    """
    labels = _sanitize_labels(labels)
    values = _sanitize_values(values)
    if not labels or not values or sum(values) == 0:
        return _empty_or_data([], empty_message, title, show_title)  # type: ignore[return-value]

    if colors is None:
        colors = [CHART_ACCENT] * len(labels)
    elif len(colors) < len(labels):
        colors = list(colors) + [CHART_ACCENT] * (len(labels) - len(colors))

    root = root_label or _t("analytics.all_countries", default="All Countries")

    fig = go.Figure(
        go.Treemap(
            labels=[root] + list(labels),
            parents=[""] + [root] * len(labels),
            values=[sum(values)] + list(values),
            marker={"colors": [BG_SURFACE] + list(colors[:len(labels)])},
            textfont={"color": TEXT_PRIMARY, "size": 11, "family": FONT_FAMILY},
            branchvalues="total",
            hovertemplate="%{label}<br>%{value:,.0f} €<extra></extra>",
        )
    )

    _apply_common_layout(fig, title, show_title)
    fig.update_layout(
        margin={"t": 10, "b": 10, "l": 10, "r": 10},
    )
    return fig


# ── Color utility helpers are imported from ui.plotly_theme ────────
