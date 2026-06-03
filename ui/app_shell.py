"""AppShell — root window layout: sidebar + main area (top bar + view container)."""
import customtkinter as ctk
from ui.theme import COLORS
from ui.widgets.nav_panel import NavPanel
from ui.widgets.top_bar import TopBar


class AppShell:
    """Creates the overall window layout. Callers use .view_container to pack views."""

    def __init__(self, root, db, on_nav_select=None, prefs=None, ops=None):
        self.root = root
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._on_nav_select = on_nav_select

        self.root.configure(fg_color=COLORS["bg_base"])

        # ── Sidebar ─────────────────────────────────────────────────────
        self.nav = NavPanel(
            self.root,
            on_select=self._on_nav_select,
            prefs=self.prefs,
        )
        self.nav.pack(side="left", fill="y")

        # ── Main area ────────────────────────────────────────────────────
        self.main_area = ctk.CTkFrame(self.root, fg_color=COLORS["bg_base"])
        self.main_area.pack(side="left", fill="both", expand=True)

        # Top bar
        self.top_bar = TopBar(self.main_area)
        self.top_bar.pack(fill="x", side="top")
        self.top_bar.set_alert_navigate_callback(self._on_alert_navigate)

        # View container — all views pack into here
        self.view_container = ctk.CTkFrame(
            self.main_area, fg_color=COLORS["bg_base"]
        )
        self.view_container.pack(fill="both", expand=True)

    def set_breadcrumb(self, text: str):
        self.top_bar.set_breadcrumb(text)

    def set_alert_count(self, count: int):
        self.top_bar.set_alert_count(count)

    def _on_alert_navigate(self, destination):
        """Navigate to a view — called from AlertPanel on alert click."""
        if self._on_nav_select:
            self._on_nav_select(destination)

    def destroy(self):
        try:
            self.top_bar.destroy()
        except Exception:
            pass
