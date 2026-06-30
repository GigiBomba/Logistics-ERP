"""Client revenue chart — Plotly bar chart embedded in a QWidget.

Replaces ``ui/client_revenue_chart.py``. Uses ``PlotlyChartWidget`` for
rendering via kaleido SVG instead of matplotlib ``FigureCanvasQTAgg``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from services.i18n import t
from ui.plotly_charts import CHART_ACCENT, CHART_DANGER, CHART_SUCCESS, make_grouped_bar_chart
from ui.plotly_renderer import PlotlyChartWidget

class QtClientRevenueChart(QWidget):
    """Bar chart showing 12-month client revenue and profit history."""

    def __init__(
        self,
        parent: QWidget | None = None,
        service=None,
        client_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.client_id = client_id

        self._chart_widget: PlotlyChartWidget | None = None
        self._empty_label: QLabel | None = None

        self._build()

    # ── Public API ──────────────────────────────────────────────────────

    def refresh(self, client_id: int | None = None) -> None:
        if client_id is not None:
            self.client_id = client_id
        self._build()

    def cleanup(self) -> None:
        self._clear_content()

    def destroy(self) -> None:
        self.cleanup()
        super().deleteLater()

    # ── Build / render ──────────────────────────────────────────────────

    def _build(self) -> None:
        self._clear_content()

        if self.layout() is None:
            QVBoxLayout(self).setContentsMargins(0, 0, 0, 0)

        history = self.service.get_client_revenue_history(
            self.client_id, months=12
        )

        if not history:
            self._empty_label = QLabel(t("analytics.no_data", default="No revenue data yet"), self)
            self._empty_label.setProperty("fontRole", "muted")
            self._empty_label.setAlignment(Qt.AlignCenter)
            self.layout().addWidget(self._empty_label)
            return

        history.reverse()
        months = [r["month"] for r in history]
        revenues = [r["revenue"] or 0 for r in history]
        profits = [r["profit"] or 0 for r in history]

        short_months = [m[-2:] for m in months]
        profit_color = CHART_SUCCESS if sum(profits) >= 0 else CHART_DANGER

        fig = make_grouped_bar_chart(
            short_months,
            [
                ("Revenue", revenues, CHART_ACCENT),
                ("Profit", profits, profit_color),
            ],
            title="",
            horizontal=False,
            show_title=False,
        )

        self._chart_widget = PlotlyChartWidget(min_height=180)
        self._chart_widget.set_figure(fig)
        self.layout().addWidget(self._chart_widget)

    # ── Internal cleanup helpers ────────────────────────────────────────

    def _clear_content(self) -> None:
        layout = self.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Stop timers / cleanup on child widgets that support it
                if hasattr(widget, "stop"):
                    widget.stop()
                if hasattr(widget, "cleanup"):
                    widget.cleanup()
                if hasattr(widget, "destroy"):
                    widget.destroy()
                widget.setParent(None)
                widget.deleteLater()
        self._empty_label = None
        self._chart_widget = None
