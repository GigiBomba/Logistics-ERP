"""Shared matplotlib chart utilities for Operion ERP.

Provides consistent dark-themed styling and factory functions for every
chart in the application. Import from views instead of inlining matplotlib.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from ui.design_tokens import (
    BG_SURFACE, BG_ELEVATED, BORDER_DEFAULT, BORDER_FAINT,
    TEXT_MUTED, TEXT_SECONDARY, TEXT_PRIMARY,
    ACCENT, ACCENT_DIM, SUCCESS, WARNING, DANGER, INFO,
    FONT_FAMILY,
)

logger = logging.getLogger(__name__)

# ── Chart palette ───────────────────────────────────────────────────
CHART_ACCENT = ACCENT
CHART_SECONDARY = "#818cf8"
CHART_SUCCESS = SUCCESS
CHART_WARNING = WARNING
CHART_DANGER = DANGER
CHART_INFO = INFO

# ── Global style ────────────────────────────────────────────────────


def apply_dark_style(fig: Figure, ax: Optional[Axes] = None) -> None:
    """Apply consistent dark theme to a matplotlib figure and axes."""
    fig.patch.set_facecolor(BG_SURFACE)
    if ax is None:
        return
    ax.set_facecolor(BG_SURFACE)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    ax.xaxis.label.set_color(TEXT_SECONDARY)
    ax.yaxis.label.set_color(TEXT_SECONDARY)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER_DEFAULT)
        spine.set_linewidth(0.5)
    ax.grid(axis="y", color=BORDER_FAINT, linewidth=0.5, alpha=0.7)


def apply_empty_state(ax: Axes, message: str) -> None:
    """Hide axes and show a centered 'no data' message."""
    ax.set_facecolor(BG_SURFACE)
    ax.set_axis_off()
    ax.set_visible(True)
    ax.text(0.5, 0.5, message,
            ha="center", va="center",
            transform=ax.transAxes,
            fontsize=11, color=TEXT_MUTED,
            fontfamily=FONT_FAMILY)


def apply_global_empty(fig: Figure, message: str) -> None:
    """Hide all subplot axes and show a centered message on the figure."""
    fig.patch.set_facecolor(BG_SURFACE)
    if hasattr(fig, "axes") and fig.axes:
        for ax in fig.axes:
            ax.set_visible(False)
            ax.set_axis_off()
    fig.text(0.5, 0.55, "\u2014",
             ha="center", va="center",
             fontsize=32, color=BORDER_DEFAULT,
             fontfamily=FONT_FAMILY)
    fig.text(0.5, 0.42, message,
             ha="center", va="center",
             fontsize=11, color=TEXT_MUTED,
             fontfamily=FONT_FAMILY)


# ── Chart factories ─────────────────────────────────────────────────


def make_bar_chart(
    fig: Figure,
    ax: Axes,
    labels: List[str],
    values: List[float],
    title: str,
    color: str = CHART_ACCENT,
    horizontal: bool = True,
    highlight_max: bool = False,
    empty_message: str = "",
) -> None:
    """Draw a bar chart with dark theme styling."""
    apply_dark_style(fig, ax)
    if not labels or not values:
        apply_empty_state(ax, empty_message)
        return
    colors = [color] * len(labels)
    if highlight_max and values:
        colors[values.index(max(values))] = CHART_SECONDARY
    if horizontal:
        ax.barh(labels, values, color=colors)
    else:
        ax.bar(labels, values, color=colors)
        ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.set_title(title, color=TEXT_SECONDARY, fontsize=10, fontfamily=FONT_FAMILY)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER_DEFAULT)


def make_line_chart(
    fig: Figure,
    ax: Axes,
    x_labels: List[str],
    y_series: List[Tuple[List[float], str, str]],
    title: str,
    empty_message: str = "",
) -> None:
    """Draw a line chart with fill, one or more series."""
    apply_dark_style(fig, ax)
    if not x_labels or not y_series:
        apply_empty_state(ax, empty_message)
        return
    valid = False
    idx = list(range(len(x_labels)))
    for values, label, color in y_series:
        if values and len(values) == len(x_labels):
            ax.plot(idx, values, color=color, label=label, linewidth=2)
            ax.fill_between(idx, 0, values, alpha=0.1, color=color)
            valid = True
    if not valid:
        apply_empty_state(ax, empty_message)
        return
    ax.set_xticks(idx)
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=7)
    ax.legend(loc="upper left", fontsize=7, facecolor=BG_ELEVATED,
              edgecolor=BORDER_DEFAULT, labelcolor=TEXT_SECONDARY)
    ax.set_title(title, color=TEXT_SECONDARY, fontsize=10, fontfamily=FONT_FAMILY)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER_DEFAULT)


def make_pie_chart(
    fig: Figure,
    ax: Axes,
    sizes: List[float],
    labels: List[str],
    title: str,
    colors: Optional[List[str]] = None,
    empty_message: str = "",
) -> None:
    """Draw a pie/donut chart with dark theme styling."""
    apply_dark_style(fig, ax)
    if not sizes or sum(sizes) == 0:
        apply_empty_state(ax, empty_message)
        return
    pie_colors = colors or [CHART_ACCENT, CHART_SECONDARY, CHART_SUCCESS,
                             CHART_WARNING, CHART_DANGER, CHART_INFO]
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.0f%%",
        colors=pie_colors[:len(sizes)],
        textprops={"color": TEXT_SECONDARY, "fontsize": 8},
    )
    for at in autotexts:
        at.set_color(TEXT_PRIMARY)
    ax.set_title(title, color=TEXT_SECONDARY, fontsize=10, fontfamily=FONT_FAMILY)


def make_trend_chart(
    fig: Figure,
    ax: Axes,
    x_labels: List[str],
    values: List[float],
    title: str,
    color: str = ACCENT,
    empty_message: str = "",
) -> None:
    """Draw a single-series line chart with area fill."""
    apply_dark_style(fig, ax)
    if not x_labels or not values:
        apply_empty_state(ax, empty_message)
        return
    idx = list(range(len(x_labels)))
    ax.plot(idx, values, color=color, linewidth=2, marker="o", markersize=3)
    ax.fill_between(idx, 0, values, alpha=0.1, color=color)
    ax.set_xticks(idx)
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=7)
    ax.set_title(title, color=TEXT_SECONDARY, fontsize=10, fontfamily=FONT_FAMILY)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER_DEFAULT)


def make_cost_per_truck_chart(
    fig: Figure,
    ax: Axes,
    labels: List[str],
    costs: List[float],
    title: str,
    empty_message: str = "",
) -> None:
    """Draw a horizontal cost breakdown chart (specialised for maintenance)."""
    apply_dark_style(fig, ax)
    if not labels or not costs:
        apply_empty_state(ax, empty_message)
        return
    colors_grad = [ACCENT] * len(labels)
    if costs:
        colors_grad[costs.index(max(costs))] = CHART_DANGER
    ax.barh(labels, costs, color=colors_grad)
    ax.set_title(title, color=TEXT_SECONDARY, fontsize=10, fontfamily=FONT_FAMILY)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER_DEFAULT)


def make_fleet_status_chart(
    fig: Figure,
    ax: Axes,
    labels: List[str],
    counts: List[int],
    title: str,
    empty_message: str = "",
) -> None:
    """Draw a horizontal fleet status bar chart."""
    apply_dark_style(fig, ax)
    if not labels or not counts:
        apply_empty_state(ax, empty_message)
        return
    status_colors = {
        "active": SUCCESS, "in_progress": ACCENT, "on_trip": ACCENT,
        "idle": TEXT_MUTED, "maintenance": WARNING, "inactive": DANGER,
        "cancelled": DANGER,
    }
    colors_list = [status_colors.get(l.lower().replace(" ", "_"), TEXT_MUTED) for l in labels]
    ax.barh(labels, counts, color=colors_list)
    ax.set_title(title, color=TEXT_SECONDARY, fontsize=10, fontfamily=FONT_FAMILY)
    ax.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER_DEFAULT)
