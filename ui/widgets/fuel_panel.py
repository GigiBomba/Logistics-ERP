"""Collapsible fuel price bar chart — PySide6 migration of ``ui/widgets/fuel_panel.py``.

Renders horizontal bars for each country's diesel price using QPainter in
``paintEvent()``. Bar colours reflect price thresholds (danger/warning/success).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.fuel_price_service import FuelPriceService
from services.i18n import t
from ui.theme import COLORS, S

# ──────────────────────────────────────────────────────────────────────────────
# Constants (mirror the original FuelPricePanel layout values)
# ──────────────────────────────────────────────────────────────────────────────
_BAR_HEIGHT = 16
_BAR_GAP = 4
_LABEL_WIDTH = 30
_MAX_COUNTRIES = 15
_TOP_MARGIN = 6


class _BarChartWidget(QFrame):
    """Custom-painted bar chart showing diesel prices.

    This inner widget handles all the QPainter drawing and receives price data
    from the parent ``QtFuelPricePanel``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prices: list[tuple[str, float]] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(0)

    # ── Public data setters ───────────────────────────────────────────────────

    def set_prices(self, prices: list[tuple[str, float]]) -> None:
        """Set the sorted list of ``(country_code, price)`` tuples and redraw."""
        self._prices = prices
        self._recalc_height()
        self.update()

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        """Paint horizontal bars for each country's diesel price."""
        if not self._prices:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        w = self.width()
        max_price = max(p for _, p in self._prices)
        # Available width for the bar itself
        bar_area_w = max(w - _LABEL_WIDTH - 60, 300)

        # Font for labels and price text
        font = QFont("Segoe UI", 11)
        painter.setFont(font)

        for i, (code, price) in enumerate(self._prices):
            y = _TOP_MARGIN + i * (_BAR_HEIGHT + _BAR_GAP)

            # ── Country code label (left-aligned, right of the left edge) ──
            painter.setPen(QColor(COLORS["text_primary"]))
            painter.drawText(
                4, y, _LABEL_WIDTH - 4, _BAR_HEIGHT,
                Qt.AlignLeft | Qt.AlignVCenter,
                code,
            )

            # ── Bar ───────────────────────────────────────────────────────
            bw = int((price / max_price) * bar_area_w) if max_price > 0 else 0
            color_str = (
                COLORS["danger"] if price > 1.8
                else COLORS["warning"] if price > 1.4
                else COLORS["success"]
            )
            painter.setBrush(QColor(color_str))
            painter.setPen(Qt.NoPen)
            painter.drawRect(_LABEL_WIDTH, y, bw, _BAR_HEIGHT)

            # ── Price label (to the right of the bar) ─────────────────────
            painter.setPen(QColor(COLORS["text_secondary"]))
            painter.drawText(
                _LABEL_WIDTH + bw + 4, y, 100, _BAR_HEIGHT,
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{price:.3f}\u20AC",
            )

        painter.end()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _recalc_height(self) -> None:
        count = len(self._prices)
        h = _TOP_MARGIN + count * (_BAR_HEIGHT + _BAR_GAP)
        self.setFixedHeight(h)
        self.setMinimumHeight(h)


class QtFuelPricePanel(QFrame):
    """Collapsible bar chart of diesel prices by country (PySide6).

    Mirrors the original ``FuelPricePanel`` from ``ui/widgets/fuel_panel.py``
    but uses QPainter in a ``paintEvent()`` instead of a tk.Canvas.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "fuel-panel")

        self._expanded = False
        self._fuel_service = FuelPriceService()

        self._build()
        self._update_status()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header row ────────────────────────────────────────────────────────
        header = QFrame()
        header.setProperty("role", "fuel-panel-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(S["3"], S["2"], S["3"], S["2"])
        header_layout.setSpacing(S["2"])

        title_lbl = QLabel(t("fuel.section_title"))
        title_lbl.setProperty("role", "section-header")
        title_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        header_layout.addWidget(title_lbl)

        header_layout.addStretch(1)

        self._status_lbl = QLabel("")
        self._status_lbl.setProperty("fontRole", "muted")
        self._status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(self._status_lbl)

        self._toggle_btn = QPushButton("\u25BC")  # ▼
        self._toggle_btn.setProperty("role", "fuel-toggle")
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self._toggle_btn)

        layout.addWidget(header)

        # ── Collapsible body containing the chart ─────────────────────────────
        self._body = QFrame()
        self._body.setProperty("role", "fuel-panel-body")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(S["3"], S["1"], S["3"], S["2"])
        body_layout.setSpacing(0)

        self._chart = _BarChartWidget(self._body)
        body_layout.addWidget(self._chart)

        # Start collapsed — body is hidden
        self._body.setVisible(False)
        layout.addWidget(self._body)

    # ── Public API ────────────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Release the fuel service reference."""
        self._fuel_service = None
        super().deleteLater()

    def refresh(self) -> None:
        """Update the status label and redraw the chart if expanded."""
        self._update_status()
        if self._expanded:
            self._draw_chart()

    # ── Toggle ────────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        """Show or hide the chart body."""
        self._expanded = not self._expanded
        if self._expanded:
            self._body.setVisible(True)
            self._toggle_btn.setText("\u25B2")  # ▲
            self._draw_chart()
        else:
            self._body.setVisible(False)
            self._toggle_btn.setText("\u25BC")  # ▼

    # ── Status ────────────────────────────────────────────────────────────────

    def _update_status(self) -> None:
        svc = self._fuel_service
        ts = svc.last_updated_str()
        age = svc.age_seconds()
        if age is not None:
            if age < 60:
                age_s = t("fuel.age_seconds").format(n=f"{age:.0f}")
            elif age < 3600:
                age_s = t("fuel.age_minutes").format(n=f"{age/60:.0f}")
            else:
                age_s = t("fuel.age_hours").format(n=f"{age/3600:.1f}")
            self._status_lbl.setText(t("fuel.updated_status").format(ts=ts, age=age_s))
        else:
            self._status_lbl.setText(t("fuel.not_fetched"))

    # ── Chart data / rendering ────────────────────────────────────────────────

    def _draw_chart(self) -> None:
        svc = self._fuel_service
        prices = svc.get_prices_all()
        if not prices:
            # No data — clear the chart; the empty label is handled inside
            # _BarChartWidget by simply not drawing anything.
            self._chart.set_prices([])
            return

        sorted_prices = sorted(
            [(c, p) for c, p in prices.items() if c != "DEFAULT"],
            key=lambda x: x[1],
            reverse=True,
        )[:_MAX_COUNTRIES]

        self._chart.set_prices(sorted_prices)
