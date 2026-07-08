"""PySide6 application shell: sidebar + main area (top bar + view container).

Replaces ``ui/app_shell.py``. Creates the root layout inside a ``QMainWindow``,
with a ``NavPanel`` on the left and a ``QStackedWidget`` view container on the
right, topped by a ``TopBar``.
"""

from __future__ import annotations

import contextlib
from typing import Any, Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.sidebar import Sidebar
from ui.widgets.topbar import TopBar

class AppShell:
    """Creates the overall window layout. Callers use ``view_container`` to add views."""

    def __init__(
        self,
        root: QMainWindow,
        db,
        on_nav_select: Callable[[str, dict[str, Any] | None], None] | None = None,
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
        central = QWidget(self.root)
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # ── Sidebar ─────────────────────────────────────────────────────────────
        self.nav = Sidebar(
            central,
            on_select=self._on_nav_select,
            prefs=self.prefs,
        )
        central_layout.addWidget(self.nav)

        # ── Main area ───────────────────────────────────────────────────────────
        self.main_area = QWidget(central)
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.top_bar = TopBar(self.main_area, ops=self.ops)
        self.top_bar.set_alert_navigate_callback(self._on_alert_navigate)
        main_layout.addWidget(self.top_bar)

        self.view_container = QStackedWidget(self.main_area)
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

    def _on_alert_navigate(self, destination: str, data: dict[str, Any] | None = None) -> None:
        """Navigate to a view — called from alert click if wired."""
        if self._on_nav_select:
            self._on_nav_select(destination, data)

    def destroy(self) -> None:
        with contextlib.suppress(Exception):
            self.top_bar.destroy()
        with contextlib.suppress(Exception):
            self.nav.destroy()
