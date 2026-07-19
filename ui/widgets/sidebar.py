"""Collapsible sidebar navigation for Operion ERP.

Replaces ui/widgets/nav_panel.py. Uses qtawesome icons, no emoji.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Callable

import qtawesome as qta
from PySide6.QtCore import QEasingCurve, QEvent, QParallelAnimationGroup, QPropertyAnimation, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import register_listener, t, unregister_listener
from ui.design_tokens import (
    ACCENT,
    ACCENT_TEXT,
    BG_OVERLAY,
    BORDER_DEFAULT,
    SIDEBAR_COLLAPSED,
    SIDEBAR_EXPANDED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)

ITEM_H = 36
ANIM_DURATION = 200

# ── Icon mapping (qtawesome) ─────────────────────────────────────────
# Nav items MUST use qtawesome icons — no emoji, no colored squares.
NAV_ICONS = {
    "overview":           "fa5s.home",
    "analytics":          "fa5s.chart-line",
    "route_planner":      "fa5s.map-marked-alt",
    "calculator":         "fa5s.calculator",
    "dispatch_board":     "fa5s.truck-loading",
    "tracking":           "fa5s.map-marker-alt",
    "freight_exchange":   "fa5s.search",
    "fleet":              "fa5s.truck-moving",
    "driver_manager":     "fa5s.user",
    "clients":            "fa5s.users",
    "documents":          "fa5s.folder-open",
    "maintenance":        "fa5s.wrench",
    "maintenance_control": "fa5s.tools",
    "tachograph":         "fa5s.hdd",
    "invoices":           "fa5s.file-invoice-dollar",
    "history":            "fa5s.clipboard-list",
    "route_history":       "fa5s.archive",
    "copilot":             "fa5s.robot",
    "migration_center":    "fa5s.exchange-alt",
    "team":                "fa5s.user-cog",
    "settings":            "fa5s.cog",
}


class Sidebar(QFrame):
    """Collapsible sidebar navigation panel."""

    def __init__(
        self,
        parent: QWidget | None = None,
        on_select: Callable | None = None,
        prefs=None,
    ):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_COLLAPSED)
        self._on_select = on_select
        self._prefs = prefs

        self._expanded = False
        self._active_key: str | None = None
        self._anim_group: QParallelAnimationGroup | None = None

        self._groups: list[str] = []
        self._items: dict[str, QFrame] = {}
        self._labels: dict[str, QLabel] = {}
        self._group_labels: dict[str, QLabel] = {}
        self._item_i18n_keys: dict[str, str] = {}
        self._group_i18n_keys: dict[str, str] = {}
        self._settings_item: str | None = None

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
        with contextlib.suppress(Exception):
            self._prefs._set_setting(
                "sidebar_expanded", "true" if self._expanded else "false"
            )

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

    def add_group(self, name: str, i18n_key: str | None = None):
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

    def add_item(self, key: str, label: str, group: str | None = None,
                 i18n_key: str | None = None):
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
            self._on_select(key, None)

    def highlight(self, key: str):
        if key == self._active_key:
            return
        if self._active_key:
            self._deactivate(self._active_key)
        self._active_key = key
        self._activate(key)

    def get_active_key(self) -> str | None:
        return self._active_key

    def refresh_labels(self, key_label_map: dict[str, str]):
        for key, text in key_label_map.items():
            if key in self._labels:
                self._labels[key].setText(text)
            if key in self._items:
                self._items[key].setToolTip(text)

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
        icon_lbl.setPixmap(qta.icon(icon_name, color=TEXT_MUTED).pixmap(16, 16))
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

        frame.setToolTip(label)
        # Store the nav key so the event filter can dispatch to
        # ``self.select(key)`` without shadowing the virtual method.
        frame.setProperty("nav-key", key)
        # Install an event filter instead of shadowing mousePressEvent
        # to avoid overriding the QFrame virtual method.
        frame.installEventFilter(self)

        self._labels[key] = text_lbl
        return frame

    def _activate(self, key: str):
        frame = self._items.get(key)
        if frame is None:
            return
        # Update icon to accent color
        icon_name = NAV_ICONS.get(key, "fa5s.circle")
        for child in frame.findChildren(QLabel):
            if child.width() == 32:  # icon label has fixedWidth(32)
                child.setPixmap(qta.icon(icon_name, color=ACCENT_TEXT).pixmap(16, 16))
                break
        # Update text label using stored reference (avoids fragile child detection)
        text_lbl = self._labels.get(key)
        if text_lbl is not None:
            text_lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent;"
            )
        frame.setStyleSheet(
            f"background: {BG_OVERLAY}; border: none; border-left: 3px solid {ACCENT};"
        )

    def _deactivate(self, key: str):
        frame = self._items.get(key)
        if frame is None:
            return
        icon_name = NAV_ICONS.get(key, "fa5s.circle")
        for child in frame.findChildren(QLabel):
            if child.width() == 32:  # icon label has fixedWidth(32)
                child.setPixmap(qta.icon(icon_name, color=TEXT_MUTED).pixmap(16, 16))
                break
        text_lbl = self._labels.get(key)
        if text_lbl is not None:
            text_lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 13px; background: transparent;"
            )
        frame.setStyleSheet("background: transparent; border: none;")

    # ── Event filter — nav item clicks ──────────────────────────

    def eventFilter(self, obj, event) -> bool:
        """Handle mouse press on nav-item QFrame without shadowing the virtual."""
        if event.type() == QEvent.MouseButtonPress:
            key = obj.property("nav-key")
            if key is not None:
                self.select(key)
                return True
        return super().eventFilter(obj, event)

    # ── Expand / collapse ───────────────────────────────────────

    def _stop_animation(self):
        if self._anim_group is not None:
            self._anim_group.stop()
            self._anim_group.deleteLater()
            self._anim_group = None

    def _animate_width(self, target_width: int):
        self._expanded = (target_width == SIDEBAR_EXPANDED)
        self._save_state()
        self._stop_animation()

        group = QParallelAnimationGroup(self)
        for prop in (b"minimumWidth", b"maximumWidth"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(ANIM_DURATION)
            anim.setStartValue(self.width())
            anim.setEndValue(target_width)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            group.addAnimation(anim)

        group.finished.connect(self._on_animation_finished)
        self._anim_group = group
        group.start()

    def _on_animation_finished(self):
        if self._expanded:
            self.setFixedWidth(SIDEBAR_EXPANDED)
            self.setMinimumWidth(SIDEBAR_EXPANDED)
            self.setMaximumWidth(16777215)
            self._app_name_frame.show()
            for lbl in self._group_labels.values():
                lbl.show()
            for item in self._items.values():
                text_lbl = self._text_label_for_item(item)
                if text_lbl is not None:
                    text_lbl.show()
        else:
            self.setFixedWidth(SIDEBAR_COLLAPSED)
            self.setMinimumWidth(SIDEBAR_COLLAPSED)
            self.setMaximumWidth(SIDEBAR_COLLAPSED)
            self._app_name_frame.hide()
            for lbl in self._group_labels.values():
                lbl.hide()
            for item in self._items.values():
                text_lbl = self._text_label_for_item(item)
                if text_lbl is not None:
                    text_lbl.hide()
        self._anim_group = None

    def _set_width_immediate(self, width: int):
        self._expanded = (width == SIDEBAR_EXPANDED)
        self.setFixedWidth(width)
        self._on_animation_finished()

    def _text_label_for_item(self, item: QFrame) -> QLabel | None:
        for child in item.findChildren(QLabel):
            if child.width() != 32 and child.text():
                return child
        return None

    # ── Hover expand / collapse ─────────────────────────────────

    def enterEvent(self, event):
        if not self._expanded:
            self._animate_width(SIDEBAR_EXPANDED)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._expanded:
            top_left = self.mapToGlobal(self.rect().topLeft())
            bottom_right = self.mapToGlobal(self.rect().bottomRight())
            cursor_global = QCursor.pos()
            if not (top_left.x() <= cursor_global.x() <= bottom_right.x() and
                    top_left.y() <= cursor_global.y() <= bottom_right.y()):
                self._animate_width(SIDEBAR_COLLAPSED)
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
        self._stop_animation()
        self._items.clear()
        self._labels.clear()
        self._group_labels.clear()
        self._item_i18n_keys.clear()
        self._group_i18n_keys.clear()
        super().deleteLater()
