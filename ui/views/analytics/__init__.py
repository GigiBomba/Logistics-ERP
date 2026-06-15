"""Tabbed analytics view for Operion ERP.

Replaces the old single-page analytics_view.py with a QTabWidget hosting
6 lazy-loaded tabs: Financial, Fleet, Route, Client, Driver, Document.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
)

from services.analytics_service import AnalyticsService
from services.i18n import t, register_listener, unregister_listener
from ui.components import PageTitle, Label
from ui.design_tokens import SP
from ui.views.analytics.financial_tab import FinancialAnalyticsTab
from ui.views.analytics.fleet_tab import FleetAnalyticsTab
from ui.views.analytics.route_tab import RouteAnalyticsTab
from ui.views.analytics.client_tab import ClientAnalyticsTab
from ui.views.analytics.driver_tab import DriverAnalyticsTab
from ui.views.analytics.document_tab import DocumentAnalyticsTab

logger = logging.getLogger(__name__)

TAB_DEFS = [
    (FinancialAnalyticsTab, "analytics.tab_financial"),
    (FleetAnalyticsTab,      "analytics.tab_fleet"),
    (RouteAnalyticsTab,      "analytics.tab_route"),
    (ClientAnalyticsTab,     "analytics.tab_client"),
    (DriverAnalyticsTab,     "analytics.tab_driver"),
    (DocumentAnalyticsTab,   "analytics.tab_document"),
]


class QtAnalyticsView(QWidget):
    """Analytics dashboard with 6 tabbed views."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self._svc = AnalyticsService(db) if db else None
        self._tabs: Dict[int, QWidget] = {}

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr_l = QVBoxLayout(hdr)
        hdr_l.setContentsMargins(SP["10"], SP["2"], SP["10"], 0)
        hdr_l.setSpacing(SP["1"])
        hdr.setFixedHeight(72)
        hdr_l.addWidget(PageTitle(hdr, t("analytics.title")))
        hdr_l.addWidget(Label(hdr, t("analytics.subtitle", default=""), role="secondary"))
        outer.addWidget(hdr)

        # Tab widget
        self._tab_widget = QTabWidget()
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        for _, label_key in TAB_DEFS:
            placeholder = QWidget()
            self._tab_widget.addTab(placeholder, t(label_key))

        outer.addWidget(self._tab_widget, 1)
        self._refresh_tab_labels()

    def _on_tab_changed(self, index: int):
        if index < 0 or index >= len(TAB_DEFS):
            return
        if index not in self._tabs:
            cls, _ = TAB_DEFS[index]
            tab = cls(self._tab_widget, service=self._svc)
            placeholder = self._tab_widget.widget(index)
            layout = QVBoxLayout(placeholder)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(tab)
            self._tabs[index] = tab
            tab.refresh()

    def _refresh_tab_labels(self):
        for i, (_, label_key) in enumerate(TAB_DEFS):
            self._tab_widget.setTabText(i, t(label_key))

    def _on_language_changed(self, lang: str):
        self._refresh_tab_labels()

    def wakeup(self):
        if self._svc:
            self._svc.invalidate()
        current = self._tab_widget.currentIndex()
        tab = self._tabs.get(current)
        if tab and hasattr(tab, "refresh"):
            tab.refresh()

    def shutdown(self):
        try:
            unregister_listener(self._language_callback)
        except Exception:
            pass
        for tab in self._tabs.values():
            if hasattr(tab, "cleanup"):
                tab.cleanup()
