"""Base class for all analytics tabs — shared header, no-data state, figure tracking."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

_log = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import EmptyState, KPICard
from ui.design_tokens import (
    ACCENT,
    BG_BASE,
    BG_SURFACE,
    BORDER_DEFAULT,
    BORDER_FAINT,
    BORDER_STRONG,
    FONT_FAMILY,
    SP,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.plotly_charts import _value_color
from ui.plotly_renderer import PlotlyChartWidget, get_render_manager

class _SparklineLabel(QLabel):
    """A ``QLabel`` that asynchronously renders a Plotly figure as its pixmap.

    The render is off-loaded to ``RenderManager`` so the GUI thread
    stays responsive even when many sparklines are rendered at once
    (each render is ~1 s on the GUI thread).  Stale renders (e.g. a
    refresh that happens before the previous render finishes) are
    dropped via tag comparison.

    A small per-instance LRU pixmap cache (max 2 entries) avoids
    re-rendering the same sparkline at the same size on view
    revisits — the common case after a menu navigation.
    """

    _connected = False  # class-level: connect the manager signal once
    CACHE_MAX_ENTRIES = 2

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setStyleSheet("background: transparent; border: none;")
        self._pending_tag: object | None = None
        self._target_w: int = 0
        self._target_h: int = 0
        self._scale: float = 1.0
        self._last_fig = None
        self._last_fig_id: int = 0
        from collections import OrderedDict
        self._pixmap_cache: OrderedDict = OrderedDict()
        self._owner = None
        # Connect the manager's signal exactly once per process; all
        # sparkline labels share the same delivery channel and each
        # instance filters by its own ``_pending_tag``.
        cls = type(self)
        if not cls._connected:
            get_render_manager().signals.delivered.connect(
                cls._on_delivered_global, Qt.QueuedConnection
            )
            cls._connected = True

    def render_async(
        self, fig, width: int, height: int, scale: float = 1.0
    ) -> None:
        """Queue a render of *fig* scaled to ``width x height`` pixels.

        Honours the per-instance LRU cache: if the same figure was
        already rendered at the same size, the cached pixmap is
        applied directly (no re-render needed).

        Defers to the first ``showEvent`` when the label has not
        been shown yet (saves a render call per sparkline when
        the tab is created off-screen).  The ``showEvent``
        re-runs ``render_async`` with the same arguments because
        ``_last_fig`` and ``_target_w``/``_target_h`` are preserved.

        Idempotency: ``render_async`` may be called multiple times
        in quick succession (e.g. when the parent layout is
        re-laid out, firing the ``showEvent`` again).  We use
        ``_pending_tag`` to skip the call when a render is
        already in flight — the in-flight render will populate
        the pixmap, and submitting another render would just
        waste render work.  This is the same pattern as
        ``PlotlyChartWidget.set_figure``.
        """
        w = int(width)
        h = int(height)
        fig_id = id(fig)
        if w <= 0 or h <= 0:
            return
        self._last_fig = fig
        self._last_fig_id = fig_id
        self._scale = float(scale)
        # ``_target_w``/``_target_h`` are stashed even when we defer
        # so the ``showEvent`` re-render uses the right size.
        self._target_w = w
        self._target_h = h
        # Defer to ``showEvent`` if the label has not been shown
        # yet.  This is the same guard as ``PlotlyChartWidget`` —
        # see the rationale there.  The sparkline's own ``showEvent``
        # re-issues the render with the stored target size.
        if not self.isVisible():
            return
        # LRU cache hit — apply directly.
        key = (fig_id, w, h)
        cached = self._pixmap_cache.get(key)
        if cached is not None and not cached.isNull():
            self._pixmap_cache.move_to_end(key)
            self._pending_tag = None
            self.setPixmap(cached)
            # Notify the owner on cache hits too — see the parallel
            # note in ``PlotlyChartWidget.set_figure``.
            if self._owner is not None and hasattr(self._owner, "_on_chart_rendered"):
                try:
                    self._owner._on_chart_rendered(self)
                except Exception:
                    _log.exception("Owner render notification failed")
            return
        # Skip if a render is already in flight — the in-flight
        # render will populate the pixmap.  Without this guard,
        # a re-fired ``showEvent`` would cancel the in-flight
        # render and start a new one — wasted render work.
        if self._pending_tag is not None:
            return
        # The SVG is generated at the label's display size; the scale
        # factor only affects the underlying pixmap density.
        self._pending_tag = get_render_manager().submit(fig, w, h, scale)

    def showEvent(self, event) -> None:
        """Re-render after first show.

        If ``render_async`` was called before the label was shown
        (e.g. during tab construction), the render was deferred.
        Re-issue it now that the label is visible.

        ``showEvent`` is also called on subsequent re-shows (e.g.
        after a tab-switch-back, or when the parent layout is
        re-laid out).  To avoid double-rendering in those cases
        we short-circuit when a render is already in flight or
        when a pixmap is already on the label.
        """
        super().showEvent(event)
        if self._last_fig is None or self._target_w <= 0:
            return
        # Skip if a render is already in flight — the in-flight
        # render will populate the pixmap.
        if self._pending_tag is not None:
            return
        # Skip if we already have a pixmap — a re-render would be
        # wasted work.  The cache check in ``render_async`` also
        # short-circuits, but checking the label directly is
        # cheaper and clearer.
        if self.pixmap() is not None and not self.pixmap().isNull():
            return
        self.render_async(self._last_fig, self._target_w, self._target_h, self._scale)

    def _cache_pixmap(self, fig_id: int, w: int, h: int, pixmap: QPixmap) -> None:
        if pixmap is None or pixmap.isNull() or w <= 0 or h <= 0:
            return
        key = (fig_id, w, h)
        if len(self._pixmap_cache) >= self.CACHE_MAX_ENTRIES:
            if key not in self._pixmap_cache:
                self._pixmap_cache.popitem(last=False)
        self._pixmap_cache[key] = pixmap
        self._pixmap_cache.move_to_end(key)

    def set_owner(self, owner) -> None:
        """Set the owning tab that should be notified on render completion.

        ``owner`` is expected to expose a ``_on_chart_rendered(widget)``
        method.  See ``PlotlyChartWidget.set_owner`` for the
        rationale.
        """
        self._owner = owner

    def owner(self):
        """Return the current owner (``None`` when not set)."""
        return self._owner

    @classmethod
    def _on_delivered_global(cls, tag, pixmap) -> None:
        """Dispatch a delivered pixmap to the right ``_SparklineLabel``.

        Qt invokes this once per render; we iterate the (small) set of
        live labels to find the owner.  In practice each tab has at
        most a few dozen sparklines, so the linear scan is cheap.
        """
        # Walk the QLabel parent hierarchy from the QApplication's
        # top-level widgets to find the matching instance.  This is
        # simpler (and faster) than maintaining a per-tag dict that
        # would need a callback-on-destroy hook.
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return
        for top in app.topLevelWidgets():
            for child in top.findChildren(cls):
                if child._pending_tag is tag:
                    child._apply(pixmap)
                    return

    def _apply(self, pixmap) -> None:
        """Set the scaled pixmap on this label."""
        self._pending_tag = None
        if pixmap is None or pixmap.isNull():
            return
        scaled = pixmap.scaled(
            self._target_w, self._target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Populate the cache BEFORE applying, so the next render
        # of the same figure at the same size is a free hit.
        self._cache_pixmap(
            self._last_fig_id,
            self._target_w, self._target_h, scaled,
        )
        self.setPixmap(scaled)
        # Notify the owning tab.  See ``PlotlyChartWidget`` for the
        # parallel mechanism on full charts.
        if self._owner is not None and hasattr(self._owner, "_on_chart_rendered"):
            try:
                self._owner._on_chart_rendered(self)
            except Exception:
                _log.exception("Owner render notification failed")


def _render_sparkline(fig, label: _SparklineLabel, width: int, height: int) -> None:
    """Backward-compat shim: queue a render on an existing ``_SparklineLabel``."""
    label.render_async(fig, width, height)


class BaseTab(QWidget):
    """Shared base for all 6 analytics tabs."""

    # Default sizes for charts when not overridden by the caller
    DEFAULT_GRID_COLUMNS = 3
    DEFAULT_TILE_HEIGHT = 130
    TOP_N_DISPLAY = 8  # max items shown in ranking charts

    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        self._svc = service
        self._figs: list = []

        # Signature of the data last rendered.  ``refresh()`` becomes a
        # no-op when this matches the current signature, so navigating
        # away and back does not re-render every chart.
        self._data_signature: tuple | None = None
        # Wall-clock timestamp of the most recent successful render.
        # Used by ``QtAnalyticsView.wakeup`` to decide whether the tab
        # is stale (e.g. because new trips were added in the DB while
        # the user was elsewhere).
        self._last_render_ts: float = 0.0
        # In-flight render counter used by the loading overlay.
        # ``_render_expected`` is set after ``_do_refresh`` returns
        # (when the chart widgets are already in the layout).  Each
        # ``PlotlyChartWidget`` / ``_SparklineLabel`` reports its
        # render completion via ``_on_chart_rendered``, which
        # increments ``_render_received``.  The tab notifies the
        # overlay (via ``_overlay_done_sink``) when the two are
        # equal.  ``_prewarmed`` is a flag the analytics view sets
        # to True when this tab was rendered as a background
        # pre-warm; the overlay is suppressed in that case.
        self._render_expected: int = 0
        self._render_received: int = 0
        self._overlay_sink = None
        self._overlay_done_sink = None
        self._prewarmed: bool = False
        # Session-level data cache: persists for the lifetime of the tab.
        self._session_cache: dict[str, Any] = {}

        # Discover the analytics view (if any) to inherit its period
        # selector value. The view exposes ``_current_period()`` which
        # returns ``(days, months, quarters)`` for the active filter.
        # When the tab is rendered standalone (e.g. in a unit test), we
        # fall back to the default 30-day period.
        self._cached_days: int = 30
        self._cached_months: int = 1
        self._cached_quarters: int = 1
        view = self._find_analytics_view()
        if view is not None and hasattr(view, "_current_period"):
            try:
                self._cached_days, self._cached_months, self._cached_quarters = view._current_period()
            except Exception:
                _log.debug("Could not read period from analytics view")

        # Build the scrollable content area (split out so the period
        # discovery above is reachable before the layout setup).
        self._setup_scroll()

    def _find_analytics_view(self):
        """Walk up the parent chain to find the QtAnalyticsView, if any."""
        from ui.views.analytics import QtAnalyticsView
        node = self.parent()
        while node is not None:
            if isinstance(node, QtAnalyticsView):
                return node
            node = node.parent()
        return None

    # ── Session cache ────────────────────────────────────────────────

    def cache_get(self, key: str, default: Any = None) -> Any:
        """Return cached *key* or *default* if not set."""
        return self._session_cache.get(key, default)

    def cache_set(self, key: str, value: Any) -> None:
        """Store *value* under *key* in the session cache."""
        self._session_cache[key] = value

    def invalidate_cache(self) -> None:
        """Clear session cache and reset data signature so next
        ``refresh()`` re-queries the DB."""
        self._session_cache.clear()
        self._data_signature = None

    def _refresh_period(self):
        """Re-read the period from the parent analytics view (called on refresh)."""
        view = self._find_analytics_view()
        if view is not None and hasattr(view, "_current_period"):
            try:
                self._cached_days, self._cached_months, self._cached_quarters = view._current_period()
            except Exception:
                _log.debug("Could not read period from analytics view")

    def _days(self) -> int:
        """Days of the currently selected period (default 30)."""
        return self._cached_days

    def _months(self) -> int:
        """Months of the currently selected period (default 1)."""
        return self._cached_months

    def _quarters(self) -> int:
        """Quarters of the currently selected period (default 1)."""
        return self._cached_quarters

    def _date_range(self) -> tuple[str | None, str | None]:
        """Return (from_date, to_date) strings for the active period filter.

        Returns (None, None) when ``days`` is 0 (the 'All' period).
        """
        days = self._cached_days
        if days <= 0:
            return None, None
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return from_date, to_date

    def _sparkline_values(self, data: list, key: str, default=0) -> list[float]:
        """Extract a list of float values from a list of dicts for a sparkline.

        data: list of dicts (e.g. from get_financial(12))
        key: dict key to extract from each row
        default: fallback value when key is missing
        """
        result: list[float] = []
        for row in data:
            val = row.get(key, default) if isinstance(row, dict) else default
            try:
                result.append(float(val or default))
            except (TypeError, ValueError):
                result.append(float(default))
        return result

    def _safe_fmt(self, value, fmt_spec=",.0f"):
        """Format a value safely, returning em-dash on failure (mock-safe)."""
        try:
            if value is None:
                return "\u2014"
            if "d" in fmt_spec:
                return f"{int(value):{fmt_spec}}"
            return f"{float(value):{fmt_spec}}"
        except (TypeError, ValueError, AttributeError):
            return "\u2014"

    def _safe_float(self, value):
        """Convert a value to float safely, returning 0.0 on failure."""
        try:
            return float(value or 0)
        except (TypeError, ValueError, AttributeError):
            return 0.0

    @staticmethod
    def _fmt_month_label(raw: str) -> str:
        """Format a month string (e.g. '2026-05' or timestamp) into 'Lun AAAA' format.
        
        Handles various input formats gracefully:
        - '2026-05' → 'Mai 2026' (using locale-aware month names)
        - ISO timestamps → month name + year
        - Falls back to raw string truncated to 7 chars
        """
        import calendar as _cal
        if not raw:
            return ""
        raw = str(raw).strip()
        if len(raw) >= 19 and ("-" in raw or ":" in raw):
            raw = raw[:7]
        if len(raw) >= 7 and raw[4] == "-":
            try:
                y = int(raw[:4])
                m = int(raw[5:7])
                if 1 <= m <= 12:
                    return f"{_cal.month_abbr[m]} {y}"
            except (ValueError, IndexError):
                pass
        return raw[:7] if len(raw) > 7 else raw

    def _setup_scroll(self):
        """Set up the scrollable content area. Called at the end of __init__."""
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Always show the vertical scrollbar so users can see that more
        # content is available. The bar is styled to be a thin, visible
        # overlay that doesn't crowd the layout.
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # A slightly-reserved gutter on the right side of the scroll area
        # so the scrollbar doesn't overlap chart cards.
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_BASE}; border: none; padding-right: 6px; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_STRONG};
                border-radius: 6px;
                min-height: 40px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {ACCENT};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px; background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        self._content = QWidget()
        self._content.setStyleSheet(f"background: {BG_BASE};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(SP["10"], SP["8"], SP["10"], SP["10"])
        self._content_layout.setSpacing(SP["4"])
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._content)
        self._outer.addWidget(self._scroll, 1)

    def _add_header(self, title_key: str, subtitle_key: str = ""):
        header = QWidget()
        header.setFixedHeight(56)
        hdr = QHBoxLayout(header)
        hdr.setContentsMargins(0, 0, 0, SP["3"])

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(t(title_key))
        title_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 18px; font-weight: 600;"
            f"font-family: '{FONT_FAMILY}';"
        )
        text_col.addWidget(title_lbl)
        if subtitle_key:
            sub = QLabel(t(subtitle_key))
            sub.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 13px;"
                f"font-family: '{FONT_FAMILY}';"
            )
            text_col.addWidget(sub)
        hdr.addLayout(text_col)
        hdr.addStretch()
        self._content_layout.addWidget(header)

        # Subtle hairline divider under header
        div = QFrame()
        div.setStyleSheet(f"background: {BORDER_FAINT}; max-height: 1px; min-height: 1px;")
        self._content_layout.addWidget(div)
        # Breathing room after the divider
        self._content_layout.addSpacing(SP["2"])

    def _add_no_data(self, message: str = ""):
        title = message or t("common.no_data")
        empty = EmptyState(
            self,
            icon_name="mdi6.chart-line",
            title=title,
            subtitle=t("analytics.empty_subtitle", default=""),
        )
        self._content_layout.addWidget(empty)

    def _add_kpi_row(self, kpis: list[dict]) -> QWidget:
        """Create a properly spaced KPI strip with N KPI cards in a row.

        kpis: list of dicts with keys: label, value, value_color (optional), subtitle (optional)
        """
        kpi_row = QWidget()
        kpi_layout = QHBoxLayout(kpi_row)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(SP["4"])
        for kpi in kpis:
            kpi_layout.addWidget(
                KPICard(
                    kpi_row,
                    label=kpi.get("label", ""),
                    value=kpi.get("value", ""),
                    value_color=kpi.get("value_color"),
                    subtitle=kpi.get("subtitle"),
                ),
                1,
            )
        self._content_layout.addWidget(kpi_row)
        return kpi_row

    def _add_kpi_row_with_sparklines(self, kpis: list[dict]) -> QWidget:
        """KPI strip where each card has an inline sparkline.

        kpis: list of dicts with keys:
          - label, value, value_color (optional), subtitle (optional)
          - sparkline_values: list of historical values (the trend)
          - sparkline_color (optional): override the trend line color
        """
        from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

        from ui.plotly_charts import make_sparkline_chart

        kpi_row = QWidget()
        kpi_layout = QHBoxLayout(kpi_row)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(SP["4"])

        for kpi in kpis:
            # Build a custom card with: label (top) + value (mid) + sparkline (bottom)
            card = QFrame()
            card.setObjectName("kpi-spark-card")
            card.setStyleSheet(
                f"QFrame#kpi-spark-card {{"
                f" background: {BG_SURFACE};"
                f" border: 1px solid {BORDER_DEFAULT};"
                f" border-radius: 8px;"
                f" }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(SP["2"], SP["2"], SP["2"], SP["1"])
            card_layout.setSpacing(SP["1"])

            # Label
            lbl = QLabel(kpi.get("label", ""))
            lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
                f" letter-spacing: 0.05em; background: transparent;"
            )
            card_layout.addWidget(lbl)

            # Value (the big number)
            value_color = kpi.get("value_color") or TEXT_PRIMARY
            val = QLabel(kpi.get("value", ""))
            val.setStyleSheet(
                f"color: {value_color}; font-size: 22px; font-weight: 700;"
                f" font-family: '{FONT_FAMILY}'; background: transparent; padding-top: 2px;"
            )
            card_layout.addWidget(val)

            # Subtitle (e.g. period-over-period delta) — small muted text
            subtitle_text = kpi.get("subtitle", "")
            if subtitle_text:
                sub_color = kpi.get("subtitle_color") or TEXT_MUTED
                sub = QLabel(subtitle_text)
                sub.setStyleSheet(
                    f"color: {sub_color}; font-size: 12px; font-weight: 600;"
                    f" font-family: '{FONT_FAMILY}'; background: transparent;"
                )
                card_layout.addWidget(sub)

            # Sparkline (the graphical trend) — Plotly SVG
            # The render is async so the GUI thread stays responsive even
            # when dozens of cards are rendered at once.
            spark_values = kpi.get("sparkline_values", [])
            if spark_values and len(spark_values) >= 2:
                spark_color = (
                    kpi.get("sparkline_color")
                    or _value_color(spark_values[-1] - (spark_values[0] if spark_values[0] else 0))
                )
                spark_fig = make_sparkline_chart(
                    values=spark_values,
                    color=spark_color,
                    show_area=True,
                    width=260,
                    height=45,
                )
                spark_label = _SparklineLabel()
                spark_label.setFixedHeight(36)
                # Register the owning tab so the sparkline's render-
                # delivery callback can notify the tab's loading
                # overlay.  See ``BaseTab._install_overlay``.
                spark_label.set_owner(self)
                card_layout.addWidget(spark_label)
                # Submit the render asynchronously; the pixmap is applied
                # to ``spark_label`` once the worker thread finishes.
                _render_sparkline(spark_fig, spark_label, width=260, height=36)

            kpi_layout.addWidget(card, 1)
        self._content_layout.addWidget(kpi_row)
        return kpi_row

    def _add_section_header(self, title: str, icon: str = ""):
        """Add a styled section header with an optional icon and title.

        Industrial / minimalistic: title-case, slightly emphasized text + 1px hairline.
        """
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, SP["3"], 0, SP["2"])
        header_layout.setSpacing(SP["2"])

        if icon:
            icon_label = QLabel(icon)
            icon_label.setStyleSheet(
                f"font-size: 14px; color: {TEXT_PRIMARY}; font-family: '{FONT_FAMILY}';"
            )
            header_layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
            f"letter-spacing: 0.04em; font-family: '{FONT_FAMILY}';"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self._content_layout.addWidget(header_widget)
        # 1px hairline divider (replaces the previous 2px accent bar)
        line = QFrame()
        line.setStyleSheet(f"background: {BORDER_FAINT}; max-height: 1px; min-height: 1px;")
        line.setFixedHeight(1)
        self._content_layout.addWidget(line)

    def _add_divider(self):
        """A subtle full-width hairline divider with breathing room."""
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, SP["3"], 0, SP["3"])
        line = QFrame()
        line.setStyleSheet(f"background: {BORDER_FAINT}; max-height: 1px; min-height: 1px;")
        line.setFixedHeight(1)
        wrapper_layout.addWidget(line)
        self._content_layout.addWidget(wrapper)


    # ── Plotly-aware chart embedding (Phase 3+) ──────────────────────

    def _build_plotly_chart_card(
        self,
        fig,
        title: str = "",
        min_height: int = 0,
    ) -> QFrame:
        """Build a card wrapping a Plotly figure via ``PlotlyChartWidget``.

        Drop-in replacement for ``_build_chart_card`` when the caller
        produces ``go.Figure`` objects instead of matplotlib figures.
        """
        card = QFrame(self)
        card.setObjectName("chart-card")
        card.setStyleSheet(
            f"QFrame#chart-card {{ background: transparent;"
            f" border: 1px solid {BORDER_DEFAULT};"
            f" border-radius: 8px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(SP["2"], SP["2"], SP["2"], SP["2"])
        card_layout.setSpacing(SP["1"])

        if title:
            title_lbl = QLabel(title, card)
            title_lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
                f"font-family: '{FONT_FAMILY}'; padding-bottom: 2px; background: transparent;"
            )
            card_layout.addWidget(title_lbl)

        chart_widget = PlotlyChartWidget(card, min_height=min_height)
        if min_height:
            chart_widget.setMinimumHeight(min_height)
        # Register the owning tab so the chart's render-delivery
        # callback can notify the tab's loading overlay.  See
        # ``BaseTab._install_overlay`` for the consumer side.
        chart_widget.set_owner(self)
        chart_widget.set_figure(fig)
        card_layout.addWidget(chart_widget, 1)

        return card

    def _add_plotly_chart(self, fig, title: str = ""):
        """Add a single full-width Plotly chart wrapped in a card."""
        card = self._build_plotly_chart_card(fig, title, min_height=180)
        self._content_layout.addWidget(card)

    def _add_plotly_chart_row(
        self,
        figures: list,
        titles: list[str] | None = None,
        columns: int = 2,
    ) -> list[Any]:
        """Add a row of N Plotly charts side by side, each wrapped in a card.

        figures: list of ``go.Figure`` objects.
        titles: optional list of titles for each chart.
        columns: how many charts per row (2 or 3).
        Returns list of ``PlotlyChartWidget`` instances.
        """
        row_widget = QWidget(self)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SP["4"])

        if titles is None:
            titles = [""] * len(figures)

        widgets = []
        for i, fig in enumerate(figures):
            card = QFrame(row_widget)
            card.setObjectName("chart-card")
            card.setStyleSheet(
                f"QFrame#chart-card {{ background: transparent;"
                f" border: 1px solid {BORDER_DEFAULT};"
                f" border-radius: 8px; }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(SP["3"], SP["3"], SP["3"], SP["3"])
            card_layout.setSpacing(SP["2"])

            if i < len(titles) and titles[i]:
                title_lbl = QLabel(titles[i], card)
                title_lbl.setStyleSheet(
                    f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;"
                    f"font-family: '{FONT_FAMILY}'; padding-bottom: 2px; background: transparent;"
                )
                card_layout.addWidget(title_lbl)

            chart_widget = PlotlyChartWidget(card, min_height=155)
            chart_widget.set_owner(self)
            chart_widget.set_figure(fig)
            card_layout.addWidget(chart_widget, 1)
            row_layout.addWidget(card, stretch=1)
            widgets.append(chart_widget)

        self._content_layout.addWidget(row_widget)
        return widgets

    def _add_plotly_chart_grid(
        self,
        figures: list,
        titles: list[str] | None = None,
        columns: int = 3,
    ) -> list[Any]:
        """Place N Plotly charts in a grid with *columns* charts per row.

        figures: list of ``go.Figure`` objects.
        titles: optional list of titles (one per chart).
        columns: charts per row (default 3).
        Returns a flat list of ``PlotlyChartWidget`` instances.
        """
        if titles is None:
            titles = [""] * len(figures)
        columns = max(1, int(columns))
        widgets: list[Any] = []
        for row_start in range(0, len(figures), columns):
            chunk = figures[row_start:row_start + columns]
            chunk_titles = titles[row_start:row_start + columns]
            widgets.extend(self._add_plotly_chart_row(chunk, chunk_titles, columns=columns))
        return widgets

    def _add_chart_or_kpi(
        self,
        data: list,
        title: str,
        kpi_value_fn,
        chart_fn,
        kpi_color: str = "",
        min_chart_points: int = 3,
    ):
        """Render a chart when data is rich, a KPI card when data is sparse.

        data: the data list (rows from a service query).
        title: title for the chart card OR label for the KPI card.
        kpi_value_fn: callable(data) -> (value_text, subtitle_text, value_color).
        chart_fn: callable(data) -> None. Must add the chart to the layout
            itself (using self._add_plotly_chart_grid or similar).
        kpi_color: default value color for the KPI when kpi_value_fn
            returns None for the color.
        min_chart_points: threshold below which we render a KPI instead
            of a full chart (default 3).
        """
        if not data:
            return
        if len(data) < min_chart_points:
            result = kpi_value_fn(data)
            value = result[0] if len(result) > 0 else ""
            subtitle = result[1] if len(result) > 1 else ""
            color = result[2] if len(result) > 2 else ""
            self._add_kpi_row([{
                "label": title,
                "value": value,
                "subtitle": subtitle or None,
                "value_color": color or kpi_color or None,
            }])
        else:
            chart_fn(data)

    # ── Lifecycle ───────────────────────────────────────────────────

    # Default staleness window: a tab is considered fresh if it was
    # rendered within this many seconds.  After that, ``wakeup`` will
    # re-render it to pick up DB changes that happened while the user
    # was elsewhere.
    DEFAULT_STALENESS_SECONDS = 300  # 5 minutes

    def cleanup(self, force: bool = False) -> None:
        """Remove rendered chart widgets from the content layout.

        By default this is a **no-op**: chart widgets and their
        rendered ``QPixmap`` objects are kept alive so re-entering the
        analytics view does not require a full SVG re-render.

        Pass ``force=True`` for an explicit teardown (e.g. when the
        data shape changes and the old widgets are no longer valid).
        """
        if not force:
            return
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _compute_signature(self) -> tuple | None:
        """Return a hashable signature of the current data inputs.

        Subclasses can override to include additional state (e.g. the
        selected chart key, the active filters).  The default returns
        the period tuple ``(days, months, quarters)``.

        Returns ``None`` to indicate "always re-render" (the old
        behaviour) — useful for tabs whose data cannot be cheaply
        hashed.
        """
        return (self._cached_days, self._cached_months, self._cached_quarters)

    def _is_stale(self, max_age_seconds: float | None = None) -> bool:
        """Return True if the tab's rendered data is older than *max_age_seconds*.

        Used by ``QtAnalyticsView.wakeup`` to decide whether to force a
        re-render (picking up DB changes that happened elsewhere).
        """
        if max_age_seconds is None:
            max_age_seconds = self.DEFAULT_STALENESS_SECONDS
        if self._last_render_ts == 0.0:
            return True  # never rendered
        return (time.time() - self._last_render_ts) > max_age_seconds

    def _mark_rendered(self) -> None:
        """Record that the tab was just rendered (signature + timestamp)."""
        self._data_signature = self._compute_signature()
        self._last_render_ts = time.time()

    def refresh(self, force: bool = False) -> None:
        """Rebuild chart widgets and re-render.

        ``force=False`` (the default) makes the call a no-op when the
        data signature is unchanged — so navigating away and back to
        analytics does not re-render every chart.

        Subclasses override ``_do_refresh()`` to load data and add
        chart widgets; the base class wraps it with the
        signature/cleanup bookkeeping.
        """
        # Re-read the period from the parent view FIRST so the signature
        # check below uses the current filter values, not stale ones from
        # construction time.
        self._refresh_period()
        if not force:
            sig = self._compute_signature()
            if sig is not None and sig == self._data_signature:
                return  # data unchanged — keep rendered pixmaps
        # Tear down the previous widget tree (the old ``_build`` +
        # ``_render`` calls always *append* widgets, so they must be
        # cleared first).
        self.cleanup(force=True)
        # Reset the in-flight render counter so the overlay (if any)
        # starts fresh for this render pass.
        self._render_received = 0
        try:
            self._do_refresh()
        except Exception as exc:
            _log.warning("Tab refresh failed — showing no-data state: %s", exc)
            self._add_no_data()
        # Count the chart widgets (full + sparkline) that this tab
        # has just enqueued.  Used by the loading overlay to know
        # when to hide.
        self._render_expected = self._count_render_targets()
        self._mark_rendered()
        # Notify the analytics view that the tab is now rendering.
        # The view is the only one that knows how to position the
        # overlay; the tab merely reports progress.
        if self._overlay_sink is not None:
            try:
                self._overlay_sink(self, self._render_expected)
            except Exception:
                _log.exception("Overlay sink notification failed")

    def _count_render_targets(self) -> int:
        """Return the number of render targets in this tab's layout.

        Render targets are ``PlotlyChartWidget`` and
        ``_SparklineLabel`` instances.  Both kinds submit
        SVG renders, so both count toward the expected total.
        """
        return (
            len(self.findChildren(PlotlyChartWidget))
            + len(self.findChildren(_SparklineLabel))
        )

    def _on_chart_rendered(self, _widget) -> None:
        """Called by ``PlotlyChartWidget`` / ``_SparklineLabel`` on render delivery.

        Bumps ``_render_received``.  When the count reaches
        ``_render_expected``, notifies the overlay (if any) that the
        tab is fully rendered.  Subclasses do not override this.
        """
        self._render_received += 1
        if (
            self._render_expected > 0
            and self._render_received >= self._render_expected
            and self._overlay_done_sink is not None
        ):
            try:
                self._overlay_done_sink(self)
            except Exception:
                _log.exception("Overlay done-sink notification failed")

    def _install_overlay(self, expected: int, sink, done_sink) -> None:
        """Install an overlay for this tab's current render.

        ``expected`` is the number of chart widgets that will be
        rendered.  ``sink`` is a callback ``(tab, expected) -> None``
        invoked immediately so the analytics view can show and
        position the overlay.  ``done_sink`` is a callback
        ``(tab) -> None`` invoked when the render count reaches
        ``expected`` so the analytics view can hide the overlay.

        Both sinks are stored on the tab so a future refresh pass
        can re-install the overlay if needed.
        """
        self._render_expected = expected
        self._render_received = 0
        self._overlay_sink = sink
        self._overlay_done_sink = done_sink
        # Kick the sink immediately so the overlay shows before any
        # render completes (avoids a flash of the chart area).
        if sink is not None:
            try:
                sink(self, expected)
            except Exception:
                _log.exception("Overlay sink notification failed")

    def _clear_overlay(self) -> None:
        """Detach the overlay sinks after a render is complete.

        Called by the analytics view once the overlay has been
        hidden, so the tab does not keep stale callbacks around.
        """
        self._overlay_sink = None
        self._overlay_done_sink = None

    def _do_refresh(self) -> None:
        """Override in subclasses — load data and render charts."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement _do_refresh()"
        )
