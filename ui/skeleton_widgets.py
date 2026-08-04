"""Skeleton loading widgets for Operion ERP.

Provides placeholder UI that renders instantly while real data loads
in the background. Follows the Linear/GitHub skeleton pattern:

- Neutral pulsing rectangles that match final layout proportions.
- No text, no data-dependent rendering.
- Auto-hidden when the real content is populated.

Usage::

    from ui.skeleton_widgets import SkeletonCard, SkeletonTable, SkeletonChart

    class MyView(BaseView):
        def _load_data(self):
            self._show_skeletons()
            WorkerPool.run(
                fn=self._fetch_data,
                on_result=self._on_data_loaded,
                on_error=self._on_error,
            )

        def _on_data_loaded(self, data):
            self._hide_skeletons()
            self._populate_real_data(data)
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer, Property
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.design_tokens import (
    BG_ELEVATED,
    BG_OVERLAY,
    BORDER_FAINT,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    RADIUS_MD,
    RADIUS_SM,
    SP,
    SPINNER_MS,
)


# Parse design tokens at module level so set_pulse_opacity uses canonical colors
_SKELETON_BASE_RGB = tuple(
    int(COLOR_BG_OVERLAY.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)
)
_SKELETON_HOVER_RGB = tuple(
    int(COLOR_BG_HOVER.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)
)


class SkeletonWidget(QFrame):
    """Base skeleton widget with a pulsing animation effect.

    Provides a shimmer/pulse animation that draws attention to
    loading content.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int | None = None,
        height: int | None = None,
        rounded: bool = True,
    ):
        super().__init__(parent)
        self._pulse_opacity = 0.3
        if width:
            self.setFixedWidth(width)
        if height:
            self.setFixedHeight(height)
        if rounded:
            self.setStyleSheet(
                f"background: {BG_OVERLAY}; border-radius: {RADIUS_SM}px;"
                " border: 1px solid transparent;"
            )
        else:
            self.setStyleSheet(
                f"background: {BG_OVERLAY}; border: none;"
            )

        self._anim = QPropertyAnimation(self, b"pulse_opacity")
        self._anim.setDuration(SPINNER_MS)  # 800ms shimmer cycle
        self._anim.setStartValue(0.2)
        self._anim.setKeyValueAt(0.5, 0.6)
        self._anim.setEndValue(0.2)
        self._anim.setLoopCount(-1)  # Infinite
        self._anim.start()

    def get_pulse_opacity(self) -> float:
        return self._pulse_opacity

    def set_pulse_opacity(self, value: float) -> None:
        self._pulse_opacity = value
        # Interpolate between BG_OVERLAY (base) and BG_HOVER (shimmer peak)
        r1, g1, b1 = _SKELETON_BASE_RGB
        r2, g2, b2 = _SKELETON_HOVER_RGB
        t = max(0.0, min(1.0, value))
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        self.setStyleSheet(
            f"background: rgb({r}, {g}, {b});"
            " border-radius: 4px; border: none;"
        )

    pulse_opacity = Property(float, get_pulse_opacity, set_pulse_opacity)

    def stop_animation(self) -> None:
        if self._anim:
            self._anim.stop()
            self._anim.deleteLater()
            self._anim = None

    def deleteLater(self) -> None:
        self.stop_animation()
        super().deleteLater()


# ── Common skeleton shapes ────────────────────────────────────────────

class SkeletonLine(SkeletonWidget):
    """A single line of text placeholder."""

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 120,
        height: int = 12,
    ):
        super().__init__(parent, width=width, height=height, rounded=True)


class SkeletonCard(SkeletonWidget):
    """Card-shaped placeholder with title line + body block."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, rounded=True)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title line
        title = SkeletonLine(self, width=160, height=14)
        layout.addWidget(title)

        # Value block
        value = SkeletonWidget(self, height=32, rounded=True)
        value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(value)

        # Subtitle line
        sub = SkeletonLine(self, width=80, height=10)
        layout.addWidget(sub)

        layout.addStretch(1)


class SkeletonTable(SkeletonWidget):
    """Table-shaped placeholder with header row + data rows."""

    def __init__(
        self,
        parent: QWidget | None = None,
        rows: int = 5,
        columns: int = 4,
    ):
        super().__init__(parent, rounded=True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Header row
        hdr = QFrame()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(16)
        for _ in range(columns):
            w = SkeletonLine(hdr, width=60 + 40, height=14)
            hdr_layout.addWidget(w)
        layout.addWidget(hdr)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER_FAINT}; border: none;")
        layout.addWidget(div)

        # Data rows
        for _ in range(rows):
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(16)
            for col in range(columns):
                w = SkeletonLine(row, width=50 + col * 30, height=12)
                row_layout.addWidget(w)
            layout.addWidget(row)


class SkeletonChart(SkeletonWidget):
    """Chart-shaped placeholder with axes and bar/line hints."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, rounded=True)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        # Chart area: vertical bars
        chart_area = QFrame()
        chart_area.setStyleSheet("background: transparent;")
        chart_layout = QHBoxLayout(chart_area)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setAlignment(Qt.AlignBottom)

        heights = [60, 90, 40, 110, 70, 130, 50]
        for h in heights:
            bar = SkeletonWidget(chart_area, width=24, height=h, rounded=False)
            chart_layout.addWidget(bar)

        layout.addWidget(chart_area, 1)


class SkeletonKPIStrip(QFrame):
    """Strip of KPI card placeholders."""

    def __init__(self, parent: QWidget | None = None, card_count: int = 3):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["2"])

        for _ in range(card_count):
            card = SkeletonWidget(self, height=80, rounded=True)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(card)


class SkeletonPage(QFrame):
    """Full page skeleton layout that mirrors a typical Operion view."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_ELEVATED};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # Header
        hdr = SkeletonWidget(self, height=36, rounded=True)
        hdr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(hdr)

        # KPI strip
        kpi = SkeletonKPIStrip(self, card_count=3)
        layout.addWidget(kpi)

        # Main content split
        content = QFrame()
        content.setStyleSheet("background: transparent;")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        chart = SkeletonChart(content)
        content_layout.addWidget(chart, 6)

        side = QVBoxLayout()
        side.setSpacing(12)
        for _ in range(3):
            line = SkeletonWidget(content, height=40, rounded=True)
            line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            side.addWidget(line)
        side_widget = QFrame(content)
        side_widget.setLayout(side)
        content_layout.addWidget(side_widget, 4)

        layout.addWidget(content, 1)


# ── Helper to show/hide skeletons in a view ──────────────────────────

class SkeletonManager:
    """Manages skeleton visibility for a view.

    Usage::

        self._skel = SkeletonManager(self)

        # Show skeleton before background load
        self._skel.show()

        # Hide when data arrives
        self._skel.hide()
    """

    def __init__(self, parent_view: QWidget):
        self._parent = parent_view
        self._skeleton: SkeletonPage | None = None
        self._real_content: list[QWidget] = []

    def register_real_content(self, *widgets: QWidget) -> None:
        """Register widgets that should be hidden while skeleton is shown."""
        self._real_content.extend(widgets)

    def show(self) -> None:
        """Show skeleton overlay, hide real content."""
        if self._skeleton is None:
            self._skeleton = SkeletonPage(self._parent)
            self._skeleton.setGeometry(self._parent.rect())
        self._skeleton.show()
        self._skeleton.raise_()
        for w in self._real_content:
            w.hide()

    def hide(self) -> None:
        """Hide skeleton, show real content."""
        if self._skeleton:
            self._skeleton.hide()
        for w in self._real_content:
            w.show()

    def resize(self, w: int, h: int) -> None:
        if self._skeleton:
            self._skeleton.setGeometry(0, 0, w, h)
