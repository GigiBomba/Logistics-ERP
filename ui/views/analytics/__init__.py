"""Tabbed analytics view for Operion ERP.

Hosts 6 analytics tabs (Financial, Fleet, Route, Client, Driver, Document).
Tabs are lazy-loaded on demand — only the first (visible) tab is loaded on
startup; remaining tabs load when the user clicks them.
"""

from __future__ import annotations

import contextlib
import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.i18n import register_listener, t, unregister_listener
from ui.components import Label, PageTitle
from ui.performance_timer import PerfTimer
from ui.design_tokens import (
    ACCENT,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER_DEFAULT,
    BORDER_FAINT,
    FONT_FAMILY,
    SP,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.views.analytics.client_tab import ClientAnalyticsTab
from ui.views.analytics.document_tab import DocumentAnalyticsTab
from ui.views.analytics.driver_tab import DriverAnalyticsTab
from ui.views.analytics.financial_tab import FinancialAnalyticsTab
from ui.views.analytics.fleet_tab import FleetAnalyticsTab
from ui.views.analytics.route_tab import RouteAnalyticsTab
from ui.widgets.loading_overlay import LoadingOverlay

logger = logging.getLogger(__name__)

TAB_DEFS = [
    (FinancialAnalyticsTab, "analytics.tab_financial"),
    (FleetAnalyticsTab,      "analytics.tab_fleet"),
    (RouteAnalyticsTab,      "analytics.tab_route"),
    (ClientAnalyticsTab,     "analytics.tab_client"),
    (DriverAnalyticsTab,     "analytics.tab_driver"),
    (DocumentAnalyticsTab,   "analytics.tab_document"),
]

PERIOD_DEFS = [
    ("analytics.period_30d", 30, 1, 1),
    ("analytics.period_90d", 90, 3, 3),
    ("analytics.period_6m",  180, 6, 6),
    ("analytics.period_1y",  365, 12, 12),
    ("analytics.period_all", 0,  24, 24),
]

DEFAULT_PERIOD_INDEX = 0


class QtAnalyticsView(QWidget):
    """Analytics dashboard — lazy-loaded tabs with startup overlay."""

    STALENESS_SECONDS = 300

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs=None,
        analytics_service=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self._svc = analytics_service
        self._tabs: dict[int, QWidget] = {}
        self._period_index: int = DEFAULT_PERIOD_INDEX
        self._first_open: bool = True
        self._shutting_down: bool = False
        self._tabs_loaded: int = 0
        self._total_tabs: int = len(TAB_DEFS)

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()

        # Full-window loading overlay (created but hidden until _start_loading)
        self._loading_overlay = LoadingOverlay(self, text="Loading analytics\u2026")
        self._load_started = False

    def showEvent(self, event):
        """Start loading tabs when the view is first shown (lazy)."""
        super().showEvent(event)
        if self._load_started:
            return
        self._start_loading()

    def _start_loading(self) -> None:
        """Load only the first (visible) tab — rest are lazy-loaded on demand."""
        if self._load_started:
            return
        self._load_started = True
        # Load only the initially visible tab (index 0)
        self._loading_overlay.show()
        self._loading_overlay.set_progress(0, 1)
        self._load_tab(0)
        self._tabs_loaded = 1
        self._loading_overlay.set_progress(self._tabs_loaded, self._total_tabs)
        self._loading_overlay.mark_done()
        self._loading_overlay.hide()

    def _build_ui(self):
        self.setAccessibleName("Analytics")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr = QWidget()
        hdr_l = QVBoxLayout(hdr)
        hdr_l.setContentsMargins(SP["10"], SP["2"], SP["10"], 0)
        hdr_l.setSpacing(SP["1"])
        hdr.setFixedHeight(72)
        hdr_l.addWidget(PageTitle(hdr, t("analytics.title")))
        hdr_l.addWidget(Label(hdr, t("analytics.subtitle", default=""), role="secondary"))
        outer.addWidget(hdr)

        self._period_strip = self._build_period_strip()
        outer.addWidget(self._period_strip)

        self._tab_widget = QTabWidget()
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._tab_widget.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {BG_SURFACE}; }}"
            f"QTabBar::tab {{ background: transparent; color: {TEXT_MUTED}; padding: 8px 16px; border: none; font-family: '{FONT_FAMILY}'; font-size: 13px; }}"
            f"QTabBar::tab:selected {{ color: {TEXT_PRIMARY}; border-bottom: 2px solid {ACCENT}; }}"
            f"QTabBar::tab:hover {{ color: {TEXT_PRIMARY}; }}"
        )

        for _, label_key in TAB_DEFS:
            placeholder = QWidget()
            self._tab_widget.addTab(placeholder, t(label_key))

        outer.addWidget(self._tab_widget, 1)
        self._refresh_tab_labels()
        self._refresh_period_strip()

    def _load_tab(self, index: int) -> None:
        """Create and render tab *index*."""
        with PerfTimer(f"analytics.load_tab_{index}"):
            if getattr(self, "_shutting_down", False):
                return
            if index >= len(TAB_DEFS) or index in self._tabs:
                return
            cls, _ = TAB_DEFS[index]
            tab = cls(self._tab_widget, service=self._svc)
            placeholder = self._tab_widget.widget(index)
            layout = QVBoxLayout(placeholder)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(tab)
            self._tabs[index] = tab
            tab.refresh()
            self._tabs_loaded += 1
            overlay = getattr(self, '_loading_overlay', None)
            if overlay is not None:
                overlay.set_progress(self._tabs_loaded, self._total_tabs)
                if self._tabs_loaded >= self._total_tabs:
                    overlay.mark_done()
                    overlay.hide()

    # ── Period strip ─────────────────────────────────────────────────

    def _build_period_strip(self) -> QWidget:
        strip = QWidget()
        strip.setObjectName("period-strip")
        strip.setStyleSheet(
            f"QWidget#period-strip {{ background: {BG_SURFACE};"
            f" border-bottom: 1px solid {BORDER_FAINT}; }}"
        )
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(SP["10"], SP["2"], SP["10"], SP["2"])
        layout.setSpacing(SP["2"])

        label = Label(strip, "PERIOADA", role="muted")
        label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
            f" letter-spacing: 0.08em; font-family: '{FONT_FAMILY}';"
            f" text-transform: uppercase; padding-right: {SP['2']}px;"
        )
        layout.addWidget(label)

        # Segmented control: pill group container
        pill_group = QWidget()
        pill_group.setStyleSheet(
            f"QWidget {{ background: {BG_ELEVATED};"
            f" border: 1px solid {BORDER_DEFAULT};"
            f" border-radius: 6px; }}"
        )
        pill_layout = QHBoxLayout(pill_group)
        pill_layout.setContentsMargins(2, 2, 2, 2)
        pill_layout.setSpacing(0)

        self._period_buttons: list[QPushButton] = []
        self._period_group = QButtonGroup(pill_group)
        self._period_group.setExclusive(True)
        for idx, (key, _days, _q, _m) in enumerate(PERIOD_DEFS):
            btn = QPushButton(t(key))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{"
                f" background: transparent;"
                f" color: {TEXT_SECONDARY};"
                f" border: none;"
                f" border-radius: 4px;"
                f" padding: 4px 12px;"
                f" font-size: 12px;"
                f" font-family: '{FONT_FAMILY}';"
                f" }}"
                f"QPushButton:hover {{"
                f" color: {TEXT_PRIMARY};"
                f" }}"
                f"QPushButton:checked {{"
                f" background: {ACCENT};"
                f" color: white;"
                f" font-weight: 600;"
                f" }}"
            )
            btn.clicked.connect(lambda _checked=False, i=idx: self._on_period_changed(i))
            self._period_group.addButton(btn, idx)
            self._period_buttons.append(btn)
            pill_layout.addWidget(btn)

        layout.addWidget(pill_group)

        self._refresh_btn = QPushButton("\u21bb")
        self._refresh_btn.setToolTip(t("analytics.refresh_tooltip", default="Refresh data"))
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setFixedWidth(32)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{"
            f" background: transparent;"
            f" color: {TEXT_SECONDARY};"
            f" border: 1px solid {BORDER_DEFAULT};"
            f" border-radius: 4px;"
            f" padding: 4px 8px;"
            f" font-size: 14px;"
            f" font-family: '{FONT_FAMILY}';"
            f" }}"
            f"QPushButton:hover {{"
            f" background: {BG_ELEVATED};"
            f" color: {TEXT_PRIMARY};"
            f" }}"
        )
        self._refresh_btn.clicked.connect(self._on_explicit_refresh)
        layout.addWidget(self._refresh_btn)

        layout.addStretch(1)
        return strip

    def _refresh_period_strip(self):
        for idx, btn in enumerate(self._period_buttons):
            btn.setChecked(idx == self._period_index)
            btn.setText(t(PERIOD_DEFS[idx][0]))

    def _on_period_changed(self, index: int):
        if index == self._period_index:
            return
        self._period_index = index
        if self._svc:
            self._svc.invalidate()
        # Refresh ALL loaded tabs so tab-switch shows correct period data
        for tab in self._tabs.values():
            if hasattr(tab, "refresh"):
                tab.refresh()

    def _current_period(self):
        _key, days, quarters, months = PERIOD_DEFS[self._period_index]
        return days, months, quarters

    # ── Tab switching (lazy-loads tabs on demand via currentChanged) ──

    def _on_tab_changed(self, index: int) -> None:
        """Lazy-load tab when user clicks it — only load what's visible."""
        with PerfTimer(f"analytics.tab_changed_{index}"):
            if index < 0 or index >= len(TAB_DEFS):
                return
            # Load tab if not yet created
            if index not in self._tabs:
                overlay = getattr(self, '_loading_overlay', None)
                if overlay is not None:
                    overlay.show()
                    overlay.set_progress(self._tabs_loaded, self._total_tabs)
                self._load_tab(index)
                self._tabs_loaded += 1
                if overlay is not None:
                    overlay.set_progress(self._tabs_loaded, self._total_tabs)
                    if self._tabs_loaded >= self._total_tabs:
                        overlay.mark_done()
                    overlay.hide()

    def _refresh_tab_labels(self):
        for i, (_, label_key) in enumerate(TAB_DEFS):
            self._tab_widget.setTabText(i, t(label_key))
        self._refresh_period_strip()

    def _on_language_changed(self, lang: str):
        self._refresh_tab_labels()

    # ── Lifecycle ────────────────────────────────────────────────────

    def wakeup(self):
        if self._first_open:
            self._first_open = False
            return
        current = self._tab_widget.currentIndex()
        tab = self._tabs.get(current)
        if tab is None:
            return
        if tab._last_render_ts == 0.0 or tab._is_stale(self.STALENESS_SECONDS):
            tab.refresh(force=False)

    def shutdown(self):
        self._shutting_down = True
        with contextlib.suppress(Exception):
            unregister_listener(self._language_callback)
        for tab in self._tabs.values():
            if hasattr(tab, "cleanup"):
                tab.cleanup()
        self._tabs.clear()

    def _on_explicit_refresh(self):
        if self._svc is not None:
            self._svc.invalidate()
        # Start refresh button spin animation
        self._start_refresh_spin()
        current = self._tab_widget.currentIndex()
        tab = self._tabs.get(current)
        if tab and hasattr(tab, "refresh"):
            tab.refresh(force=True)

    def _start_refresh_spin(self) -> None:
        """Animate the refresh button while data reloads."""
        if not hasattr(self, "_refresh_spin_frames"):
            self._refresh_spin_frames = ["\u21bb", "\u21ba", "\u21b2", "\u21b3"]
            self._refresh_spin_idx = 0
            self._refresh_spin_timer = QTimer(self)
            self._refresh_spin_timer.setInterval(80)
            def _tick():
                self._refresh_spin_idx = (self._refresh_spin_idx + 1) % len(self._refresh_spin_frames)
                self._refresh_btn.setText(self._refresh_spin_frames[self._refresh_spin_idx])
            self._refresh_spin_timer.timeout.connect(_tick)
            # Auto-stop safety timeout after 4 seconds
            self._refresh_stop_timer = QTimer(self)
            self._refresh_stop_timer.setSingleShot(True)
            self._refresh_stop_timer.timeout.connect(self._stop_refresh_spin)
        self._refresh_spin_timer.start()
        self._refresh_stop_timer.start(10000)  # 10s safety timeout

    def _stop_refresh_spin(self) -> None:
        """Stop the refresh button animation and restore the icon."""
        if hasattr(self, "_refresh_spin_timer"):
            self._refresh_spin_timer.stop()
        self._refresh_btn.setText("\u21bb")
