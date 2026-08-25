"""Verify the "chart interiors" blind spot programmatically.

Builds every chart factory in ui/plotly_charts.py with sample data, then
extracts all colors and font sizes from the resulting figures and checks
them against the design-token set. This closes the audit blind spot that
chart interiors (series colors, axis labels, legends, typography) could
not be evidenced because the harness patches the SVG renderer.

Usage:
    python tools/verify_chart_interiors.py
"""
from __future__ import annotations

import os
import re
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ui import design_tokens as dt
from ui import plotly_charts as pc
from ui import plotly_theme as pt

# ── Token sets ──────────────────────────────────────────────────────
TOKEN_HEX = set()
for _k, _v in vars(dt).items():
    if isinstance(_v, str) and _v.startswith("#"):
        TOKEN_HEX.add(_v.upper())
for _k, _v in vars(pt).items():
    if isinstance(_v, str) and _v.startswith("#"):
        TOKEN_HEX.add(_v.upper())

TOKEN_RGB = set()
for _hex in TOKEN_HEX:
    h = _hex.lstrip("#")
    TOKEN_RGB.add(tuple(int(h[i : i + 2], 16) for i in (0, 2, 4)))

FONT_SCALE = {10, 11, 12, 13, 16, 22, 26, 32}


def _collect(obj, colors: set, fonts: set, in_font: bool = False) -> None:
    if isinstance(obj, dict):
        # Skip Plotly's built-in template (default colorway/colorscales are
        # embedded in the figure JSON but never rendered by our charts).
        if "template" in obj:
            obj = {k: v for k, v in obj.items() if k != "template"}
        for k, v in obj.items():
            _collect(v, colors, fonts, in_font=(k == "font") or in_font)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, colors, fonts, in_font)
    elif isinstance(obj, str):
        s = obj.strip()
        if s.startswith("#"):
            colors.add(s)
        elif s.startswith("rgb"):
            colors.add(s)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        # Only treat numbers inside a "font" dict as font sizes.
        if in_font and 6 <= obj <= 40:
            fonts.add(int(obj))


def _check_color(c: str) -> str | None:
    """Return a reason string if *c* is not token-backed, else None."""
    if c.startswith("#"):
        return None if c.upper() in TOKEN_HEX else f"non-token hex {c}"
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", c)
    if m:
        rgb = tuple(int(m.group(i)) for i in (1, 2, 3))
        if rgb == (0, 0, 0):
            return None  # transparent
        return None if rgb in TOKEN_RGB else f"non-token rgb {c}"
    return f"unrecognized color {c}"


def main() -> int:
    builders = {
        "bar": lambda: pc.make_bar_chart(["A", "B", "C"], [1, 2, 3]),
        "line": lambda: pc.make_line_chart(["A", "B", "C"], [([1, 2, 3], "S1", "#6366F1")]),
        "pie": lambda: pc.make_pie_chart([1, 2, 3], ["A", "B", "C"]),
        "trend": lambda: pc.make_trend_chart(["A", "B", "C"], [1, 2, 3]),
        "lollipop": lambda: pc.make_lollipop_chart(["A", "B", "C"], [1, 2, 3]),
        "histogram": lambda: pc.make_histogram_chart([1, 2, 3, 4, 5]),
        "stacked_area": lambda: pc.make_stacked_area_chart(["A", "B"], [("S1", [1, 2], "#6366F1")]),
        "bullet": lambda: pc.make_bullet_chart(80, 100),
        "calendar_heatmap": lambda: pc.make_calendar_heatmap(
            [("2026-01-01", 1), ("2026-01-02", 2)]
        ),
        "sparkline": lambda: pc.make_sparkline_chart([1, 2, 3]),
        "cost_per_truck": lambda: pc.make_cost_per_truck_chart(["A", "B"], [1, 2]),
        "fleet_status": lambda: pc.make_fleet_status_chart(["Active", "Idle"], [5, 2]),
        "grouped_bar": lambda: pc.make_grouped_bar_chart(
            ["A", "B"], [("S1", [1, 2], "#6366F1"), ("S2", [3, 4], "#10B981")]
        ),
        "stacked_bar": lambda: pc.make_stacked_bar_chart(
            ["A", "B"], [("S1", [1, 2], "#6366F1"), ("S2", [3, 4], "#10B981")]
        ),
        "scatter": lambda: pc.make_scatter_chart([1, 2, 3], [1, 2, 3], ["a", "b", "c"]),
        "heatmap": lambda: pc.make_heatmap_chart(["A", "B"], ["X", "Y"], [[1, 2], [3, 4]]),
        "waterfall": lambda: pc.make_waterfall_chart(["Rev", "Cost", "Net"], [100, -30, 70]),
        "box": lambda: pc.make_box_plot(["A", "B"], [[1, 2, 3], [4, 5, 6]]),
        "area": lambda: pc.make_area_chart(["A", "B", "C"], [1, 2, 3]),
        "treemap": lambda: pc.make_treemap_chart(["RO", "HU"], [10, 20]),
    }

    all_issues: dict[str, list[str]] = {}
    for name, build in builders.items():
        try:
            fig = build()
            colors: set = set()
            fonts: set = set()
            _collect(fig.to_plotly_json(), colors, fonts)
            issues = []
            for c in sorted(colors):
                reason = _check_color(c)
                if reason:
                    issues.append(reason)
            off_fonts = sorted(f for f in fonts if f not in FONT_SCALE)
            if off_fonts:
                issues.append(f"off-scale font sizes: {off_fonts}")
            all_issues[name] = issues
            status = "OK" if not issues else "ISSUES"
            print(f"  {name}: {status} ({len(colors)} colors, {len(fonts)} font sizes)")
            for i in issues:
                print(f"      - {i}")
        except Exception as e:  # noqa: BLE001
            all_issues[name] = [f"ERROR: {e}"]
            print(f"  {name}: ERROR {e}")

    total_issues = sum(len(v) for v in all_issues.values())
    print(f"\nChart interior verification: {'PASS' if total_issues == 0 else f'{total_issues} issue(s)'}")
    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
