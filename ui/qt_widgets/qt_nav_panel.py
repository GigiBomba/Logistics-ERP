"""Animated sidebar navigation panel for the PySide6 main window.

Replaces ``ui/widgets/nav_panel.py``. Provides grouped nav items, a pinned
settings item, smooth expand/collapse animation, hover auto-expand, and live
i18n label refresh.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve
from PySide6.QtGui import QCursor
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

from ui.theme import S
from services.i18n import t, register_listener, unregister_listener

logger = logging.getLogger(__name__)

W_EXPANDED = 220
W_COLLAPSED = 52
ITEM_H = 36
ANIMATION_DURATION_MS = 200


class NavPanel(QFrame):
    """Collapsible animated sidebar navigation panel."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_select: Optional[Callable[[str], None]] = None,
        prefs=None,
    ):
        super().__init__(parent)
        self.setProperty("role", "nav-panel")
        self.setFixedWidth(W_COLLAPSED)
        self._on_select = on_select
        self._prefs = prefs

        self._expanded = False
        self._active_key: Optional[str] = None
        self._animation_group: Optional[QParallelAnimationGroup] = None

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

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load_state(self):
        if self._prefs is None:
            return
        try:
            raw = self._prefs._get_setting("sidebar_expanded")
            if raw is not None:
                self._expanded = raw.lower() == "true"
                self._set_width_immediate(W_EXPANDED if self._expanded else W_COLLAPSED)
        except Exception:
            pass

    def _save_state(self):
        if self._prefs is None:
            return
        try:
            self._prefs._set_setting("sidebar_expanded", "true" if self._expanded else "false")
        except Exception:
            pass

    # ── Build ──────────────────────────────────────────────────────────────────

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
        top.setProperty("role", "nav-top-section")
        top.setFixedHeight(56)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 0, 4, 0)
        top_layout.setSpacing(8)

        # Monogram icon
        icon_frame = QFrame()
        icon_frame.setProperty("role", "nav-monogram")
        icon_frame.setFixedSize(28, 28)
        icon_layout = QHBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel("O")
        icon_lbl.setProperty("role", "nav-monogram-text")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_lbl)
        top_layout.addWidget(icon_frame)

        # App name / subtitle
        self._app_name_frame = QFrame()
        self._app_name_frame.setProperty("role", "nav-top-section")
        name_layout = QVBoxLayout(self._app_name_frame)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(0)

        name_lbl = QLabel(t("app.name"))
        name_lbl.setProperty("role", "nav-app-name")
        name_layout.addWidget(name_lbl)

        sub_lbl = QLabel(t("app.subtitle"))
        sub_lbl.setProperty("role", "nav-app-subtitle")
        name_layout.addWidget(sub_lbl)

        top_layout.addWidget(self._app_name_frame)
        top_layout.addStretch(1)

        # Toggle button
        self._toggle_btn = QPushButton("\u00bb")  # »
        self._toggle_btn.setProperty("role", "nav-toggle")
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.clicked.connect(self._toggle_expand)
        top_layout.addWidget(self._toggle_btn)

        self._app_name_frame.hide()

        layout = self.layout()
        layout.addWidget(top)

        divider = QFrame()
        divider.setProperty("role", "nav-divider")
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Plain)
        layout.addWidget(divider)

    def _build_scroll_area(self):
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QFrame()
        self._container.setProperty("role", "nav-panel")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(8, 8, 8, 8)
        self._container_layout.setSpacing(4)
        self._container_layout.setAlignment(Qt.AlignTop)

        self._scroll.setWidget(self._container)
        self.layout().addWidget(self._scroll, 1)

    def _build_bottom_section(self):
        bottom = QFrame()
        bottom.setProperty("role", "nav-panel")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(8, 0, 8, 8)
        bottom_layout.setSpacing(0)

        divider = QFrame()
        divider.setProperty("role", "nav-divider")
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Plain)
        bottom_layout.addWidget(divider)

        self._bottom_layout = bottom_layout
        self.layout().addWidget(bottom)

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_group(self, name: str, i18n_key: Optional[str] = None):
        if i18n_key:
            self._group_i18n_keys[name] = i18n_key

        if self._groups:
            spacer = QFrame()
            spacer.setFixedHeight(8)
            self._container_layout.addWidget(spacer)

        text = t(i18n_key).upper() if i18n_key else name.upper()
        lbl = QLabel(text)
        lbl.setProperty("role", "nav-group-label")
        lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._container_layout.addWidget(lbl)
        self._group_labels[name] = lbl

        if not self._expanded:
            lbl.hide()

        self._groups.append(name)

    def add_item(self, key: str, icon: str, label: str, group: Optional[str] = None, i18n_key: Optional[str] = None):
        if group and group not in self._groups:
            self.add_group(group)
        if i18n_key:
            self._item_i18n_keys[key] = i18n_key

        text = t(i18n_key) if i18n_key else label
        frame = self._create_item_frame(key, icon, text)
        self._container_layout.addWidget(frame)
        self._items[key] = frame

    def add_settings_item(self, key: str, icon: str, label: str):
        frame = self._create_item_frame(key, icon, label)
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

    # ── Item factory ───────────────────────────────────────────────────────────

    def _create_item_frame(self, key: str, icon: str, label: str) -> QFrame:
        frame = QFrame()
        frame.setProperty("role", "nav-item")
        frame.setFixedHeight(ITEM_H)
        frame.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 0, 8, 0)
        layout.setSpacing(0)

        accent = QFrame()
        accent.setProperty("role", "nav-accent")
        layout.addWidget(accent)

        icon_lbl = QLabel(icon)
        icon_lbl.setProperty("role", "nav-icon")
        icon_lbl.setFixedWidth(32)
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        text_lbl = QLabel(label)
        text_lbl.setProperty("role", "nav-label")
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
        frame.setProperty("state", "active")
        frame.style().unpolish(frame)
        frame.style().polish(frame)

    def _deactivate(self, key: str):
        frame = self._items.get(key)
        if frame is None:
            return
        frame.setProperty("state", "")
        frame.style().unpolish(frame)
        frame.style().polish(frame)

    # ── Expand / collapse animation ────────────────────────────────────────────

    def _toggle_expand(self):
        self._set_width(W_EXPANDED if not self._expanded else W_COLLAPSED)

    def _set_width(self, width: int):
        should_expand = (width == W_EXPANDED)
        if should_expand == self._expanded and self.width() == width:
            return

        self._expanded = should_expand
        self._save_state()
        self._toggle_btn.setText("\u00ab" if self._expanded else "\u00bb")  # « / »

        self._stop_animation()
        group = QParallelAnimationGroup(self)

        for prop in (b"minimumWidth", b"maximumWidth"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(ANIMATION_DURATION_MS)
            anim.setStartValue(self.width())
            anim.setEndValue(width)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            group.addAnimation(anim)

        group.finished.connect(self._on_animation_finished)
        self._animation_group = group
        group.start()

    def _set_width_immediate(self, width: int):
        self._expanded = (width == W_EXPANDED)
        self.setFixedWidth(width)
        self._toggle_btn.setText("\u00ab" if self._expanded else "\u00bb")
        self._on_animation_finished()

    def _stop_animation(self):
        if self._animation_group is not None:
            self._animation_group.stop()
            self._animation_group.deleteLater()
            self._animation_group = None

    def _text_label_for_item(self, item: QFrame) -> Optional[QLabel]:
        for child in item.findChildren(QLabel):
            if child.property("role") == "nav-label":
                return child
        return None

    def _on_animation_finished(self):
        if self._expanded:
            self.setMaximumWidth(16777215)
            self.setMinimumWidth(W_EXPANDED)
            self.setFixedWidth(W_EXPANDED)
            self._app_name_frame.show()
            for lbl in self._group_labels.values():
                lbl.show()
            for item in self._items.values():
                text_lbl = self._text_label_for_item(item)
                if text_lbl is not None:
                    text_lbl.show()
        else:
            self.setFixedWidth(W_COLLAPSED)
            self.setMinimumWidth(W_COLLAPSED)
            self.setMaximumWidth(W_COLLAPSED)
            self._app_name_frame.hide()
            for lbl in self._group_labels.values():
                lbl.hide()
            for item in self._items.values():
                text_lbl = self._text_label_for_item(item)
                if text_lbl is not None:
                    text_lbl.hide()

    # ── Hover expand / collapse ────────────────────────────────────────────────

    def enterEvent(self, event):
        if not self._expanded:
            self._set_width(W_EXPANDED)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._expanded:
            top_left = self.mapToGlobal(self.rect().topLeft())
            bottom_right = self.mapToGlobal(self.rect().bottomRight())
            cursor_global = QCursor.pos()
            if not (top_left.x() <= cursor_global.x() <= bottom_right.x() and
                    top_left.y() <= cursor_global.y() <= bottom_right.y()):
                self._set_width(W_COLLAPSED)
        super().leaveEvent(event)

    # ── Language refresh ───────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str):
        try:
            self._refresh_labels()
        except Exception:
            logger.exception("NavPanel language refresh failed")

    def _refresh_labels(self):
        for key, i18n_key in self._item_i18n_keys.items():
            if key in self._labels:
                self._labels[key].setText(t(i18n_key))
        for name, i18n_key in self._group_i18n_keys.items():
            if name in self._group_labels:
                self._group_labels[name].setText(t(i18n_key).upper())

    def destroy(self) -> None:
        unregister_listener(self._language_callback)
        self._stop_animation()
        super().deleteLater()
