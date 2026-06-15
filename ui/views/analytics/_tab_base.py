"""Base class for all analytics tabs — shared header, no-data state, figure tracking."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QScrollArea,
    QFrame,
)

from ui.design_tokens import (
    BG_BASE, BG_SURFACE, BORDER_DEFAULT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    SP, FONT_FAMILY,
)
from services.i18n import t


class BaseTab(QWidget):
    """Shared base for all 6 analytics tabs."""

    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        self._svc = service
        self._figs: List = []

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(SP["10"], SP["6"], SP["10"], SP["10"])
        self._content_layout.setSpacing(SP["6"])
        self._content_layout.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._content)
        self._outer.addWidget(self._scroll, 1)

    def _add_header(self, title_key: str, subtitle_key: str = ""):
        header = QWidget()
        header.setFixedHeight(56)
        hdr = QHBoxLayout(header)
        hdr.setContentsMargins(0, 0, 0, SP["2"])

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(t(title_key))
        title_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 600;"
            f"font-family: '{FONT_FAMILY}';"
        )
        text_col.addWidget(title_lbl)
        if subtitle_key:
            sub = QLabel(t(subtitle_key))
            sub.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px;"
                f"font-family: '{FONT_FAMILY}';"
            )
            text_col.addWidget(sub)
        hdr.addLayout(text_col)
        hdr.addStretch()
        self._content_layout.addWidget(header)

        div = QFrame()
        div.setStyleSheet(f"background: {BORDER_DEFAULT}; max-height: 1px; min-height: 1px;")
        self._content_layout.addWidget(div)

    def _add_no_data(self, message: str = ""):
        lbl = QLabel(message or t("common.no_data"))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; padding: 40px;"
            f"font-family: '{FONT_FAMILY}';"
        )
        self._content_layout.addWidget(lbl)

    def _track_figure(self, fig):
        self._figs.append(fig)

    def cleanup(self):
        import matplotlib.pyplot as plt
        for fig in self._figs:
            try:
                plt.close(fig)
            except Exception:
                pass
        self._figs.clear()
        # Clear content layout
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def refresh(self):
        """Override in subclasses — load data and render charts."""
        pass
