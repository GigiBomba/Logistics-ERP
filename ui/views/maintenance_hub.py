"""PySide6 unified maintenance hub — one page, two tabs.

Merges the previously split ``maintenance`` (analytics: charts/costs) and
``maintenance_control`` (operational KPIs/filters/alerts/tachograph status)
pages into a single tabbed view so operators no longer have to hunt between
two separate sidebar entries.

The two sub-views are hosted **as-is** (their internals are untouched); this
module only composes them inside a ``QTabWidget`` and forwards the lifecycle
(wakeup/shutdown/tab-change) so their data stays fresh and their event-bus
subscriptions are torn down cleanly.
"""
from __future__ import annotations

import contextlib
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QTabWidget, QVBoxLayout, QWidget

from services.i18n import t
from ui.base_view import BaseView
from ui.views.maintenance_analytics_view import QtMaintenanceAnalyticsView
from ui.views.maintenance_control_panel import QtMaintenanceControlPanel

logger = logging.getLogger(__name__)


class QtMaintenanceHub(BaseView):
    """Unified maintenance page with a Control and an Analytics tab.

    Tab labels are translated via ``t()`` (English defaults only — no
    translation data is added here).  The active tab's view is woken on hub
    activation and on every tab change; both sub-views are shut down when the
    hub shuts down.  Each sub-view construction is isolated so a failure in
    one tab never prevents the other from rendering.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        repo=None,
        prefs=None,
        ops=None,
        control_service=None,
        maintenance_service=None,
        api_client=None,
    ):
        super().__init__(parent)
        self.db = db
        self.repo = repo
        self.prefs = prefs
        self.ops = ops
        self.control_service = control_service
        self.maintenance_service = maintenance_service
        self._api_client = api_client

        self._control_view = None
        self._analytics_view = None

        self._build_ui()
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._register_i18n(self._on_language_changed)

    # ── UI construction ────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setAccessibleName("Maintenance hub")
        self._container = QWidget()
        self._container.setObjectName("maintenance-hub-container")
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget(self._container)
        self._tabs.setObjectName("maintenance-hub-tabs")
        self._tabs.setDocumentMode(True)

        self._control_view = self._build_control_tab()
        self._analytics_view = self._build_analytics_tab()

        layout.addWidget(self._tabs)

        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

    def _build_control_tab(self):
        """Host ``QtMaintenanceControlPanel`` with the factory's original args."""
        page = QWidget(self._tabs)
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        try:
            view = QtMaintenanceControlPanel(
                page,
                db=self.db,
                prefs=self.prefs,
                ops=self.ops,
                control_service=self.control_service,
                maintenance_service=self.maintenance_service,
                api_client=self._api_client,
            )
            pl.addWidget(view)
        except Exception:
            logger.exception("Failed to build maintenance control tab")
            pl.addWidget(self._error_label(t("maint.tab_control", default="Control")))
            view = None
        self._tabs.addTab(page, t("maint.tab_control", default="Control"))
        return view

    def _build_analytics_tab(self):
        """Host ``QtMaintenanceAnalyticsView`` with the factory's original args."""
        page = QWidget(self._tabs)
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        try:
            view = QtMaintenanceAnalyticsView(
                page,
                db=self.db,
                repo=self.repo,
            )
            pl.addWidget(view)
        except Exception:
            logger.exception("Failed to build maintenance analytics tab")
            pl.addWidget(self._error_label(t("maint.tab_analytics", default="Analytics")))
            view = None
        self._tabs.addTab(page, t("maint.tab_analytics", default="Analytics"))
        return view

    def _error_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "muted")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    # ── Lifecycle ──────────────────────────────────────────────────

    def _current_view(self):
        """Return the view currently shown in the active tab (or ``None``)."""
        index = self._tabs.currentIndex()
        views = (self._control_view, self._analytics_view)
        if 0 <= index < len(views):
            return views[index]
        return None

    def _on_tab_changed(self, index: int) -> None:
        """Wake the newly shown tab's view so its data refreshes."""
        view = self._current_view()
        if view is not None:
            with contextlib.suppress(Exception):
                view.wakeup()

    def wakeup(self) -> None:
        """Forward activation to the active tab's view only."""
        if self._shutdown_flag:
            return
        view = self._current_view()
        if view is not None:
            with contextlib.suppress(Exception):
                view.wakeup()

    def shutdown(self) -> None:
        """Shut down both sub-views, then the hub's own lifecycle."""
        super().shutdown()
        for view in (self._control_view, self._analytics_view):
            if view is not None and hasattr(view, "shutdown"):
                with contextlib.suppress(Exception):
                    view.shutdown()

    # ── i18n ───────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        try:
            self._tabs.setTabText(0, t("maint.tab_control", default="Control"))
            self._tabs.setTabText(1, t("maint.tab_analytics", default="Analytics"))
        except Exception:
            logger.debug("Could not refresh maintenance hub tab labels", exc_info=True)
