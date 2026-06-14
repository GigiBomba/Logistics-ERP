"""Collapsible sidebar navigation for Operion ERP.

Replaces ui/widgets/nav_panel.py. Uses qtawesome icons, no emoji.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
)

try:
    import qtawesome as qta
    _HAS_QTAWESOME = True
except ImportError:
    qta = None
    _HAS_QTAWESOME = False

from ui.design_tokens import (
    BG_SURFACE, BG_ELEVATED, BG_BASE,
    BORDER_DEFAULT, ACCENT, ACCENT_TEXT, ACCENT_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED,
    SP, RADIUS,
)
from services.i18n import t, register_listener, unregister_listener

logger = logging.getLogger(__name__)

ITEM_H = 36

# ── Icon mapping (qtawesome) ─────────────────────────────────────────
# Nav items MUST use qtawesome icons — no emoji, no colored squares.
NAV_ICONS = {
    "overview":           "fa5s.home",
    "analytics":          "fa5s.chart-line",
    "route_planner":      "fa5s.map-marked-alt",
    "calculator":         "fa5s.calculator",
    "dispatch_board":     "fa5s.truck-loading",
    "tracking":           "fa5s.map-marker-alt",
    "fleet":              "fa5s.truck-moving",
    "driver_manager":     "fa5s.user",
    "clients":            "fa5s.users",
    "documents":          "fa5s.folder-open",
    "maintenance":        "fa5s.wrench",
    "maintenance_control": "fa5s.tools",
    "tachograph":         "fa5s.hdd",
    "invoices":           "fa5s.file-invoice-dollar",
    "history":            "fa5s.clipboard-list",
    "route_history":      "fa5s.archive",
    "settings":           "fa5s.cog",
}


def _qt_pixmap(icon_name: str, color: str, size: int = 16):
    """Return a QPixmap for the icon, falling back to a colored square."""
    if _HAS_QTAWESOME:
        return qta.icon(icon_name, color=color).pixmap(size, size)
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return pm


class Sidebar(QFrame):
    """Collapsible sidebar navigation panel."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_select: Optional[Callable[[str], None]] = None,
        prefs=None,
    ):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_COLLAPSED)
        self._on_select = on_select
        self._prefs = prefs

        self._expanded = False
        self._active_key: Optional[str] = None

        self._groups: List[str] = []
        self._items: Dict[str, QFrame] = {}
        self._labels: Dict[str, QLabel] = {}
        self._group_labels: Dict[str, QLabel] = {}
        self._item_i18n_keys: Dict[str, str] = {}
        self._group_i18n_keys: Dict[str, str] = {}
        self._settings_item: Optional[str] = None

        self._build()
        self._load_state()

        self._language_callback = self._on_language_changed
        register_listener(self._language_callback)

    # ── Persistence ─────────────────────────────────────────────

    def _load_state(self):
        if self._prefs is None:
            return
        try:
            raw = self._prefs._get_setting("sidebar_expanded")
            if raw is not None:
                self._expanded = raw.lower() == "true"
                self._set_width_immediate(
                    SIDEBAR_EXPANDED if self._expanded else SIDEBAR_COLLAPSED
                )
        except Exception:
            pass

    def _save_state(self):
        if self._prefs is None:
            return
        try:
            self._prefs._set_setting(
                "sidebar_expanded", "true" if self._expanded else "false"
            )
        except Exception:
            pass

    # ── Build ───────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_top_section()
        self._build_scroll_area()
        self._build_bottom_section()

        self.setMouseTracking(True)

    def _build_top_section(self):
        top = QFrame()
        top.setFixedHeight(64)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 0, 12, 0)
        top_layout.setSpacing(8)

        # Monogram circle
        self._monogram = QFrame()
        self._monogram.setFixedSize(32, 32)
        self._monogram.setStyleSheet(
            f"background: {ACCENT}; border-radius: 16px;"
        )
        mono_layout = QHBoxLayout(self._monogram)
        mono_layout.setContentsMargins(0, 0, 0, 0)
        mono_lbl = QLabel("O")
        mono_lbl.setStyleSheet("color: white; font-weight: 700; font-size: 14px;")
        mono_lbl.setAlignment(Qt.AlignCenter)
        mono_layout.addWidget(mono_lbl)
        top_layout.addWidget(self._monogram)

        # App name + subtitle (hidden when collapsed)
        self._app_name_frame = QFrame()
        name_layout = QVBoxLayout(self._app_name_frame)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(0)

        name_lbl = QLabel(t("app.name"))
        name_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-weight: 600; font-size: 13px;"
        )
        name_layout.addWidget(name_lbl)

        sub_lbl = QLabel(t("app.subtitle"))
        sub_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px;"
        )
        name_layout.addWidget(sub_lbl)

        top_layout.addWidget(self._app_name_frame)
        top_layout.addStretch(1)

        self._app_name_frame.hide()

        layout = self.layout()
        layout.addWidget(top)

        # Divider
        divider = QFrame()
        divider.setStyleSheet(f"background: {BORDER_DEFAULT}; max-height: 1px; min-height: 1px;")
        layout.addWidget(divider)

    def _build_scroll_area(self):
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QFrame()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(8, 8, 8, 8)
        self._container_layout.setSpacing(4)
        self._container_layout.setAlignment(Qt.AlignTop)

        self._scroll.setWidget(self._container)
        self.layout().addWidget(self._scroll, 1)

    def _build_bottom_section(self):
        bottom = QFrame()
        bottom.setStyleSheet("background: transparent;")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(8, 0, 8, 8)
        bottom_layout.setSpacing(0)

        divider = QFrame()
        divider.setStyleSheet(f"background: {BORDER_DEFAULT}; max-height: 1px; min-height: 1px;")
        bottom_layout.addWidget(divider)

        self._bottom_layout = bottom_layout
        self.layout().addWidget(bottom)

    # ── Public API ──────────────────────────────────────────────

    def add_group(self, name: str, i18n_key: Optional[str] = None):
        if i18n_key:
            self._group_i18n_keys[name] = i18n_key

        if self._groups:
            spacer = QFrame()
            spacer.setFixedHeight(8)
            self._container_layout.addWidget(spacer)

        text = t(i18n_key).upper() if i18n_key else name.upper()
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 600; "
            f"text-transform: uppercase; letter-spacing: 0.8px; padding-left: 8px;"
        )
        lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._container_layout.addWidget(lbl)
        self._group_labels[name] = lbl

        if not self._expanded:
            lbl.hide()

        self._groups.append(name)

    def add_item(self, key: str, label: str, group: Optional[str] = None,
                 i18n_key: Optional[str] = None):
        if group and group not in self._groups:
            self.add_group(group)
        if i18n_key:
            self._item_i18n_keys[key] = i18n_key

        text = t(i18n_key) if i18n_key else label
        frame = self._create_item_frame(key, text)
        self._container_layout.addWidget(frame)
        self._items[key] = frame

    def add_settings_item(self, key: str, label: str):
        frame = self._create_item_frame(key, label)
        self._bottom_layout.addWidget(frame)
        self._items[key] = frame
        self._settings_item = key

    def select(self, key: str):
        if self._active_key:
            self._deactivate(self._active_key)
        self._active_key = key
        self._activate(key)
        if self._on_select:
            self._on_select(key)

    def highlight(self, key: str):
        if key == self._active_key:
            return
        if self._active_key:
            self._deactivate(self._active_key)
        self._active_key = key
        self._activate(key)

    def get_active_key(self) -> Optional[str]:
        return self._active_key

    def refresh_labels(self, key_label_map: Dict[str, str]):
        for key, text in key_label_map.items():
            if key in self._labels:
                self._labels[key].setText(text)

    # ── Item factory ────────────────────────────────────────────

    def _create_item_frame(self, key: str, label: str) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(ITEM_H)
        frame.setCursor(Qt.PointingHandCursor)
        frame.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 0, 8, 0)
        layout.setSpacing(0)

        # Left accent bar
        accent = QFrame()
        accent.setFixedWidth(3)
        accent.setStyleSheet("background: transparent; border-radius: 2px;")
        layout.addWidget(accent)

        # Icon
        icon_name = NAV_ICONS.get(key, "fa5s.circle")
        icon_lbl = QLabel()
        icon_lbl.setPixmap(_qt_pixmap(icon_name, TEXT_MUTED, 16))
        icon_lbl.setFixedWidth(32)
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        # Text label
        text_lbl = QLabel(label)
        text_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; background: transparent;"
        )
        layout.addWidget(text_lbl, 1)
        if not self._expanded:
            text_lbl.hide()

        frame.mousePressEvent = lambda event, k=key: self.select(k)

        self._labels[key] = text_lbl
        return frame

    def _activate(self, key: str):
        frame = self._items.get(key)
        if frame is None:
            return
        # Update styles directly for active state
        for child in frame.findChildren(QLabel):
            if child.width() == 32 and child.height() == 16:
                # This is the icon label
                icon_name = NAV_ICONS.get(key, "fa5s.circle")
                child.setPixmap(_qt_pixmap(icon_name, ACCENT_TEXT, 16))
            elif child.text() and child != frame.findChildren(QLabel)[0]:
                child.setStyleSheet(
                    f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent;"
                )
        frame.setStyleSheet(
            f"background: {BG_ELEVATED}; border: none; border-left: 3px solid {ACCENT};"
        )

    def _deactivate(self, key: str):
        frame = self._items.get(key)
        if frame is None:
            return
        for child in frame.findChildren(QLabel):
            if child.width() == 32 and child.height() == 16:
                icon_name = NAV_ICONS.get(key, "fa5s.circle")
                child.setPixmap(_qt_pixmap(icon_name, TEXT_MUTED, 16))
            elif child.text() and child != frame.findChildren(QLabel)[0]:
                child.setStyleSheet(
                    f"color: {TEXT_SECONDARY}; font-size: 13px; background: transparent;"
                )
        frame.setStyleSheet("background: transparent; border: none;")

    # ── Expand / collapse ───────────────────────────────────────

    def _set_width_immediate(self, width: int):
        self._expanded = (width == SIDEBAR_EXPANDED)
        self.setFixedWidth(width)
        if self._expanded:
            self._app_name_frame.show()
            for lbl in self._group_labels.values():
                lbl.show()
            for item in self._items.values():
                text_lbl = self._text_label_for_item(item)
                if text_lbl is not None:
                    text_lbl.show()
        else:
            self._app_name_frame.hide()
            for lbl in self._group_labels.values():
                lbl.hide()
            for item in self._items.values():
                text_lbl = self._text_label_for_item(item)
                if text_lbl is not None:
                    text_lbl.hide()

    def _text_label_for_item(self, item: QFrame) -> Optional[QLabel]:
        for child in item.findChildren(QLabel):
            if child.width() != 32 and child.text():
                return child
        return None

    # ── Hover expand / collapse ─────────────────────────────────

    def enterEvent(self, event):
        if not self._expanded:
            self._set_width_immediate(SIDEBAR_EXPANDED)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._expanded:
            top_left = self.mapToGlobal(self.rect().topLeft())
            bottom_right = self.mapToGlobal(self.rect().bottomRight())
            cursor_global = QCursor.pos()
            if not (top_left.x() <= cursor_global.x() <= bottom_right.x() and
                    top_left.y() <= cursor_global.y() <= bottom_right.y()):
                self._set_width_immediate(SIDEBAR_COLLAPSED)
        super().leaveEvent(event)

    # ── Language refresh ───────────────────────────────────────

    def _on_language_changed(self, lang: str):
        try:
            self._refresh_labels()
        except Exception:
            logger.exception("Sidebar language refresh failed")

    def _refresh_labels(self):
        for key, i18n_key in self._item_i18n_keys.items():
            if key in self._labels:
                self._labels[key].setText(t(i18n_key))
        for name, i18n_key in self._group_i18n_keys.items():
            if name in self._group_labels:
                self._group_labels[name].setText(t(i18n_key).upper())

    def destroy(self) -> None:
        unregister_listener(self._language_callback)
        super().deleteLater()
