"""PySide6 application shell: sidebar + main area (top bar + view container).

Replaces ``ui/app_shell.py``. Creates the root layout inside a ``QMainWindow``,
with a ``NavPanel`` on the left and a ``QStackedWidget`` view container on the
right, topped by a ``TopBar``.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
)

from ui.qt_widgets.qt_nav_panel import NavPanel
from ui.qt_widgets.qt_top_bar import TopBar


class AppShell:
    """Creates the overall window layout. Callers use ``view_container`` to add views."""

    def __init__(
        self,
        root: QMainWindow,
        db,
        on_nav_select: Optional[Callable[[str], None]] = None,
        prefs=None,
        ops=None,
    ):
        self.root = root
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._on_nav_select = on_nav_select

        self._build()

    def _build(self):
        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # ── Sidebar ─────────────────────────────────────────────────────────────
        self.nav = NavPanel(
            central,
            on_select=self._on_nav_select,
            prefs=self.prefs,
        )
        central_layout.addWidget(self.nav)

        # ── Main area ───────────────────────────────────────────────────────────
        self.main_area = QWidget()
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.top_bar = TopBar(self.main_area)
        self.top_bar.set_alert_navigate_callback(self._on_alert_navigate)
        main_layout.addWidget(self.top_bar)

        self.view_container = QStackedWidget()
        self.view_container.setProperty("role", "view-container")
        main_layout.addWidget(self.view_container, 1)

        central_layout.addWidget(self.main_area, 1)
        self.root.setCentralWidget(central)

    def set_breadcrumb(self, text: str) -> None:
        self.top_bar.set_breadcrumb(text)

    def set_fuel_status(self, text: str) -> None:
        """Update the fuel status label in the top bar."""
        self.top_bar.set_fuel_status(text)

    def set_alert_count(self, count: int) -> None:
        self.top_bar.set_alert_count(count)

    def _on_alert_navigate(self, destination: str) -> None:
        """Navigate to a view — called from alert click if wired."""
        if self._on_nav_select:
            self._on_nav_select(destination)

    def destroy(self) -> None:
        try:
            self.top_bar.destroy()
        except Exception:
            pass
        try:
            self.nav.destroy()
        except Exception:
            pass
