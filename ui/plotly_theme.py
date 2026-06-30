"""Plotly dark theme template and color mapping for Operion ERP.

Maps every design token from ``ui.design_tokens`` into Plotly's layout
template system.  Registered as the named template ``"operion_dark"``
so any figure can opt in via ``fig.update_layout(template="operion_dark")``.

Usage
-----
    from ui.plotly_theme import apply_operion_theme
    fig = go.Figure(...)
    apply_operion_theme(fig)          # apply to one figure
    # -- or --
    import plotly.io as pio
    pio.templates.default = "operion_dark"  # apply globally
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from ui.design_tokens import (
    ACCENT,
    BG_BASE,
    BG_SURFACE,
    BORDER_DEFAULT,
    BORDER_FAINT,
    BORDER_STRONG,
    DANGER,
    FONT_FAMILY,
    INFO,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)

# ── Color palette (aliases for Plotly-facing code) ─────────────────

PLOTLY_ACCENT          = ACCENT          # "#6366f1"
PLOTLY_SECONDARY       = "#818cf8"
PLOTLY_SUCCESS         = SUCCESS         # "#22c55e"
PLOTLY_SUCCESS_LIGHT   = "#4ade80"
PLOTLY_WARNING         = WARNING         # "#f59e0b"
PLOTLY_WARNING_LIGHT   = "#fbbf24"
PLOTLY_DANGER          = DANGER          # "#ef4444"
PLOTLY_DANGER_LIGHT    = "#f87171"
PLOTLY_NEUTRAL         = "#9CA3AF"
PLOTLY_NEUTRAL_DIM     = "#1A1A20"
PLOTLY_INFO            = INFO            # "#3b82f6"
PLOTLY_INFO_LIGHT      = "#93c5fd"

PLOTLY_BG              = BG_SURFACE      # "#111113"
PLOTLY_GRID            = BORDER_DEFAULT  # "#27272a"
PLOTLY_TEXT            = TEXT_PRIMARY    # "#fafafa"
PLOTLY_AXIS_LINE       = BORDER_FAINT    # "#1c1c1f"

# RGB components for constructing rgba() fill colors
PLOTLY_ACCENT_RGB    = (99, 102, 241)
PLOTLY_SUCCESS_RGB   = (34, 197, 94)
PLOTLY_WARNING_RGB   = (245, 158, 11)
PLOTLY_DANGER_RGB    = (239, 68, 68)
PLOTLY_INFO_RGB      = (59, 130, 246)
PLOTLY_SECONDARY_RGB = (129, 140, 248)

# ── Chart size constants (pixels, matching old matplotlib inches×DPI) ──

PLOTLY_TILE_WIDTH  = 420
PLOTLY_TILE_HEIGHT = 170
PLOTLY_HALF_WIDTH  = 700
PLOTLY_HALF_HEIGHT = 300
PLOTLY_FULL_WIDTH  = 1000
PLOTLY_FULL_HEIGHT = 500
PLOTLY_WIDE_WIDTH  = 900
PLOTLY_WIDE_HEIGHT = 220


# ── Template builders ──────────────────────────────────────────────

def _make_base_layout() -> dict:
    """Return the base layout dict shared by all Operion charts."""
    return {
        "paper_bgcolor": BG_SURFACE,
        "plot_bgcolor": BG_SURFACE,
        "font": {"color": TEXT_PRIMARY, "family": FONT_FAMILY, "size": 12},
        "title": {
            "font": {"color": TEXT_PRIMARY, "family": FONT_FAMILY, "size": 13},
            "x": 0.0,
            "xanchor": "left",
        },
        "xaxis": {
            "gridcolor": BORDER_DEFAULT,
            "zerolinecolor": BORDER_DEFAULT,
            "linecolor": BORDER_FAINT,
            "title_font": {"color": TEXT_PRIMARY, "size": 11},
            "tickfont": {"color": TEXT_MUTED, "size": 10},
            "showgrid": True,
            "gridwidth": 0.5,
            "zerolinewidth": 0.5,
        },
        "yaxis": {
            "gridcolor": BORDER_DEFAULT,
            "zerolinecolor": BORDER_DEFAULT,
            "linecolor": BORDER_FAINT,
            "title_font": {"color": TEXT_PRIMARY, "size": 11},
            "tickfont": {"color": TEXT_MUTED, "size": 10},
            "showgrid": True,
            "gridwidth": 0.5,
            "zerolinewidth": 0.5,
        },
        "colorway": [
            ACCENT,
            PLOTLY_SECONDARY,
            SUCCESS,
            WARNING,
            DANGER,
            INFO,
        ],
        "margin": {"l": 50, "r": 20, "t": 35, "b": 40},
        "legend": {
            "font": {"color": TEXT_SECONDARY, "size": 10},
            "bgcolor": "rgba(0,0,0,0)",
            "bordercolor": BORDER_FAINT,
            "borderwidth": 0.5,
        },
        "bargap": 0.15,
        "bargroupgap": 0.1,
        "hoverlabel": {
            "bgcolor": BG_BASE,
            "font": {"color": TEXT_PRIMARY, "family": FONT_FAMILY, "size": 11},
            "bordercolor": BORDER_STRONG,
        },
    }


def create_operion_template() -> go.layout.Template:
    """Build the full Operion dark-chart Plotly template.

    This template applies to every built-in trace type so that
    hover-labels, text annotations, and subplot axes all inherit
    the correct dark-theme styling automatically.
    """
    base = _make_base_layout()

    # Apply the same axis config to every cartesian subplot axis
    axis_keys = [
        "xaxis", "xaxis2", "xaxis3", "xaxis4", "xaxis5", "xaxis6",
        "yaxis", "yaxis2", "yaxis3", "yaxis4", "yaxis5", "yaxis6",
    ]
    base_full = dict(base)
    base_full.update({k: dict(base["xaxis"]) for k in axis_keys})

    t = go.layout.Template()
    t.layout = go.Layout(**base_full)

    # Data trace defaults — ensure all traces pick up the correct
    # colour cycle, marker styling and text styling.
    scatter_defaults = {
        "marker": {"line": {"width": 0}},
        "textfont": {"color": TEXT_PRIMARY, "family": FONT_FAMILY},
    }
    bar_defaults = {
        "textfont": {"color": TEXT_PRIMARY, "family": FONT_FAMILY},
        "marker": {"line": {"width": 0}},
    }
    pie_defaults = {
        "textfont": {"color": TEXT_PRIMARY, "family": FONT_FAMILY},
        "marker": {"line": {"color": BG_SURFACE, "width": 1}},
    }
    heatmap_defaults = {
        "colorbar": {
            "tickfont": {"color": TEXT_MUTED, "size": 9},
            "title_font": {"color": TEXT_SECONDARY, "size": 10},
            "outlinecolor": BORDER_FAINT,
            "outlinewidth": 0.5,
        },
    }
    histogram_defaults = {
        "marker": {"line": {"width": 0}},
    }
    box_defaults = {
        "marker": {"color": ACCENT},
        "line": {"color": ACCENT},
    }
    waterfall_defaults = {
        "textfont": {"color": TEXT_PRIMARY, "family": FONT_FAMILY},
    }

    t.data.scatter = [go.Scatter(**scatter_defaults)]
    t.data.bar = [go.Bar(**bar_defaults)]
    t.data.pie = [go.Pie(**pie_defaults)]
    t.data.heatmap = [go.Heatmap(**heatmap_defaults)]
    t.data.histogram = [go.Histogram(**histogram_defaults)]
    t.data.box = [go.Box(**box_defaults)]
    t.data.waterfall = [go.Waterfall(**waterfall_defaults)]

    return t


def create_sparkline_template() -> go.layout.Template:
    """Build a minimal template for inline sparkline charts.

    Transparent background, no axes, no grid, no margins — just the
    trace line and optional area fill.
    """
    t = go.layout.Template()
    t.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis={"visible": False, "fixedrange": True, "showgrid": False, "zeroline": False},
        yaxis={"visible": False, "fixedrange": True, "showgrid": False, "zeroline": False},
        showlegend=False,
        font={"color": TEXT_PRIMARY, "family": FONT_FAMILY},
    )
    t.data.scatter = [go.Scatter(marker={"line": {"width": 0}})]
    return t


# ── Template registration ──────────────────────────────────────────

_OPERION_TEMPLATE = create_operion_template()
_SPARKLINE_TEMPLATE = create_sparkline_template()

pio.templates["operion_dark"] = _OPERION_TEMPLATE
pio.templates["operion_sparkline"] = _SPARKLINE_TEMPLATE


# ── Public helpers ─────────────────────────────────────────────────

# Defensive registration: ensure the template is always available, even if
# another module somehow cleared ``pio.templates`` or this module is imported
# before the ``pio.templates["operion_dark"] = _OPERION_TEMPLATE`` assignment
# in the section above runs (e.g. if a test mocks ``pio.templates``).
_ENSURE_TEMPLATE_SET = {
    "operion_dark": _OPERION_TEMPLATE,
    "operion_sparkline": _SPARKLINE_TEMPLATE,
}
for _tpl_name, _tpl_obj in _ENSURE_TEMPLATE_SET.items():
    if _tpl_name not in pio.templates:
        pio.templates[_tpl_name] = _tpl_obj


def apply_operion_theme(fig: go.Figure) -> go.Figure:
    """Apply the Operion dark template to *fig* in-place.  Returns *fig*."""
    fig.update_layout(template="operion_dark")
    return fig


def apply_sparkline_theme(fig: go.Figure) -> go.Figure:
    """Apply the transparent sparkline template to *fig* in-place."""
    fig.update_layout(template="operion_sparkline")
    return fig


def _value_color(value: float) -> str:
    """Return a semantic color string for a numeric value.

    Positive → green (SUCCESS), negative → red (DANGER), zero → amber (WARNING).
    Matches the original ``ui.charts._value_color`` behaviour.
    """
    if value is None:
        return PLOTLY_WARNING
    value = float(value)
    if value < 0:
        return PLOTLY_DANGER
    if value > 0:
        return PLOTLY_SUCCESS
    return PLOTLY_WARNING


def value_colors(values: list) -> list:
    """Return a list of semantic color strings, one per value.

    Used to colour-code bar / lollipop chart markers.
    """
    return [_value_color(v) for v in values]


def _hex_to_rgb_int(hex_color: str) -> str:
    """Convert ``#RRGGBB`` to a comma-separated RGB string ``R,G,B``."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _hex_to_rgb_tuple(hex_color: str) -> tuple:
    """Convert ``#RRGGBB`` to an (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_to_alpha(hex_color: str, alpha: float) -> str:
    """Convert a hex colour and alpha to an ``rgba(r,g,b,a)`` string."""
    return rgba(hex_color, alpha)


def rgba(color_hex: str, alpha: float) -> str:
    """Convert a hex colour (``#RRGGBB``) to an ``rgba(r,g,b,a)`` string."""
    h = color_hex.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
