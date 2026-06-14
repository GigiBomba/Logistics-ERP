"""Client revenue chart — matplotlib bar chart embedded in a QWidget.

Replaces ``ui/client_revenue_chart.py``. Uses ``FigureCanvasQTAgg`` instead
of ``FigureCanvasTkAgg`` and QVBoxLayout instead of CTkFrame pack geometry.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from ui.theme import COLORS


class QtClientRevenueChart(QWidget):
    """Bar chart showing 12-month client revenue and profit history.

    Uses the service's ``get_client_revenue_history(client_id, months=12)``
    to fetch data and renders a grouped bar chart via matplotlib.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        service=None,
        client_id: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.client_id = client_id

        self._fig = None
        self._mpl_canvas: Optional[FigureCanvas] = None
        self._empty_label: Optional[QLabel] = None

        self._build()

    # ── Public API ──────────────────────────────────────────────────────────────

    def refresh(self, client_id: Optional[int] = None) -> None:
        """Rebuild the chart, optionally switching to a different client."""
        if client_id is not None:
            self.client_id = client_id
        self._build()

    def cleanup(self) -> None:
        """Release matplotlib resources and clear child widgets."""
        self._destroy_canvas()
        self._clear_content()

    def destroy(self) -> None:
        """Clean up resources and schedule widget deletion."""
        self.cleanup()
        super().deleteLater()

    # ── Build / render ─────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Fetch data and build the chart or show an empty-state label."""
        self._destroy_canvas()
        self._clear_content()

        # Ensure a single layout exists on this widget
        if self.layout() is None:
            QVBoxLayout(self).setContentsMargins(0, 0, 0, 0)

        history = self.service.get_client_revenue_history(
            self.client_id, months=12
        )

        if not history:
            self._empty_label = QLabel("No revenue data yet", self)
            self._empty_label.setProperty("fontRole", "muted")
            self._empty_label.setAlignment(Qt.AlignCenter)
            self.layout().addWidget(self._empty_label)
            return

        history.reverse()
        months = [r["month"] for r in history]
        revenues = [r["revenue"] or 0 for r in history]
        profits = [r["profit"] or 0 for r in history]

        plt.style.use("dark_background")
        self._fig, ax = plt.subplots(figsize=(5, 2.2), dpi=95)
        self._fig.patch.set_facecolor(COLORS["bg_base"])
        ax.set_facecolor(COLORS["bg_base"])

        x = range(len(months))
        width = 0.35
        ax.bar(
            [i - width / 2 for i in x],
            revenues,
            width,
            label="Revenue",
            color=COLORS["accent"],
            alpha=0.85,
        )
        ax.bar(
            [i + width / 2 for i in x],
            profits,
            width,
            label="Profit",
            color=COLORS["success"]
            if sum(profits) >= 0
            else COLORS["danger"],
            alpha=0.85,
        )

        short_months = [m[-2:] for m in months]
        ax.set_xticks(x)
        ax.set_xticklabels(
            short_months, fontsize=7, color=COLORS["text_muted"]
        )
        ax.tick_params(colors=COLORS["text_muted"], labelsize=7, pad=2)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v/1000:.0f}k" if v else "0")
        )
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(COLORS["border"])
        ax.spines["bottom"].set_color(COLORS["border"])
        ax.legend(
            fontsize=7,
            framealpha=0.3,
            facecolor=COLORS["bg_surface"],
            edgecolor=COLORS["border"],
            labelcolor=COLORS["text_primary"],
        )
        self._fig.tight_layout(pad=0.8)

        self._mpl_canvas = FigureCanvas(self._fig)
        self.layout().addWidget(self._mpl_canvas)
        self._mpl_canvas.draw()

    # ── Internal cleanup helpers ───────────────────────────────────────────────

    def _destroy_canvas(self) -> None:
        """Close the matplotlib figure and delete the canvas widget."""
        if self._mpl_canvas is not None:
            try:
                self._mpl_canvas.setParent(None)
                self._mpl_canvas.deleteLater()
            except Exception:
                pass
            self._mpl_canvas = None
        if self._fig is not None:
            try:
                plt.close(self._fig)
            except Exception:
                pass
            self._fig = None

    def _clear_content(self) -> None:
        """Remove all child widgets from the current layout."""
        layout = self.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._empty_label = None
