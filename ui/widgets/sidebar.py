"""Collapsible sidebar navigation for Operion ERP.

Replaces ui/widgets/nav_panel.py. Uses qtawesome icons, no emoji.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Callable

import qtawesome as qta
from PySide6.QtCore import QEasingCurve, QEvent, QParallelAnimationGroup, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import register_listener, t, unregister_listener
from ui.design_tokens import (
    ACCENT,
    BG_OVERLAY,
    BORDER_DEFAULT,
    BTN_HEIGHT_SM,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    FONT_SIZE_SM,
    RADIUS_SM,
    SIDEBAR_COLLAPSED,
    SIDEBAR_EXPANDED,
    SPACE_1,
    SPACE_2,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)

ITEM_H = 36
ANIM_DURATION = 200

# ── Icon mapping (qtawesome) ─────────────────────────────────────────
# Nav items MUST use qtawesome icons — no emoji, no colored squares.
# ── Keyboard shortcut hints for the first 9 nav items ──────────────
NAV_SHORTCUTS: dict[str, str] = {
    "overview":      "Ctrl+1",
    "analytics":     "Ctrl+2",
    "route_planner": "Ctrl+3",
    "calculator":    "Ctrl+4",
    "dispatch_board":"Ctrl+5",
    "tracking":      "Ctrl+6",
    "fleet":         "Ctrl+7",
    "driver_manager":"Ctrl+8",
    "clients":       "Ctrl+9",
}

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
        self._shortcut_labels: dict[str, QLabel] = {}
        self._group_labels: dict[str, QLabel] = {}
        self._item_i18n_keys: dict[str, str] = {}
        self._group_i18n_keys: dict[str, str] = {}
        self._settings_item: str | None = None
        self._item_groups: dict[str, str | None] = {}
        self._search_input: QLineEdit | None = None
        self._collapse_btn: QPushButton | None = None

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

        # Monogram circle — click to toggle expand/collapse
        self._monogram = QFrame()
        self._monogram.setFixedSize(32, 32)
        self._monogram.setAccessibleName("Operion home")
        self._monogram.setStyleSheet(
            f"background: {ACCENT}; border-radius: 16px;"
        )
        self._monogram.setProperty("is-monogram", True)
        self._monogram.setCursor(Qt.PointingHandCursor)
        self._monogram.installEventFilter(self)
        mono_layout = QHBoxLayout(self._monogram)
        mono_layout.setContentsMargins(0, 0, 0, 0)
        mono_lbl = QLabel("O")
        mono_lbl.setStyleSheet("color: white; font-weight: 700; font-size: 14px;")
        mono_lbl.setAlignment(Qt.AlignCenter)
        mono_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
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
        divider.setStyleSheet(f"background: {COLOR_BORDER_SUBTLE}; max-height: 1px; min-height: 1px;")
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

        # ── Search input (visible only when expanded) ──
        self._search_input = QLineEdit()
        self._search_input.setAccessibleName("Search navigation")
        self._search_input.setPlaceholderText(t("sidebar.search", default="Search..."))
        self._search_input.addAction(
            qta.icon("fa5s.search", color=COLOR_TEXT_TERTIARY),
            QLineEdit.LeadingPosition,
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setFixedHeight(BTN_HEIGHT_SM)
        self._search_input.textChanged.connect(self._filter_items)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_SM}px;
                color: {COLOR_TEXT_PRIMARY};
                font-size: {FONT_SIZE_SM}px;
                padding: 0 8px;
            }}
            QLineEdit:focus {{
                border-color: {COLOR_ACCENT_PRIMARY};
            }}
            QLineEdit::placeholder {{
                color: {COLOR_TEXT_TERTIARY};
            }}
        """)
        self._search_input.setVisible(self._expanded)
        self._container_layout.addWidget(self._search_input)

        self._scroll.setWidget(self._container)
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        layout.addWidget(self._scroll, 1)

    def _build_bottom_section(self):
        bottom = QFrame()
        bottom.setStyleSheet("background: transparent;")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(8, 0, 8, 8)
        bottom_layout.setSpacing(0)

        divider = QFrame()
        divider.setStyleSheet(f"background: {BORDER_DEFAULT}; max-height: 1px; min-height: 1px;")
        bottom_layout.addWidget(divider)

        # ── Collapse chevron button (visible only when expanded) ──
        self._collapse_btn = QPushButton()
        self._collapse_btn.setIcon(qta.icon("fa5s.chevron-left", color=COLOR_TEXT_TERTIARY))
        self._collapse_btn.setToolTip(t("sidebar.collapse", default="Collapse sidebar"))
        self._collapse_btn.setFixedHeight(28)
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_TERTIARY};
                font-size: {FONT_SIZE_SM}px;
                border-radius: {RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background: {COLOR_BG_HOVER};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        self._collapse_btn.clicked.connect(self._toggle_expand)
        self._collapse_btn.setVisible(self._expanded)
        bottom_layout.addWidget(self._collapse_btn)

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
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; "
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
        self._item_groups[key] = group

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
        accent.setFixedWidth(4)
        accent.setStyleSheet(f"background: transparent; border-radius: {RADIUS_SM}px;")
        layout.addWidget(accent)

        # Icon
        icon_name = NAV_ICONS.get(key, "fa5s.circle")
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color=TEXT_MUTED).pixmap(16, 16))
        icon_lbl.setFixedWidth(32)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon_lbl)

        # Text label
        text_lbl = QLabel(label)
        text_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; background: transparent;"
        )
        text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(text_lbl, 1)
        if not self._expanded:
            text_lbl.hide()

        # Keyboard shortcut hint (visible only when expanded)
        shortcut_text = NAV_SHORTCUTS.get(key)
        if shortcut_text:
            shortcut_lbl = QLabel(shortcut_text)
            shortcut_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_SM}px; background: transparent;"
            )
            shortcut_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            layout.addWidget(shortcut_lbl)
            self._shortcut_labels[key] = shortcut_lbl
            if not self._expanded:
                shortcut_lbl.hide()

        frame.setAccessibleName(label)
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
                child.setPixmap(qta.icon(icon_name, color=COLOR_ACCENT_PRIMARY).pixmap(16, 16))
                break
        # Update text label using stored reference (avoids fragile child detection)
        text_lbl = self._labels.get(key)
        if text_lbl is not None:
            text_lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600; background: transparent;"
            )
        frame.setStyleSheet(
            f"background: {COLOR_BG_HOVER}; border: none; border-left: 4px solid {ACCENT};"
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
        """Handle mouse press on nav-item QFrame or monogram."""
        if event.type() == QEvent.MouseButtonPress:
            if obj.property("is-monogram"):
                self._toggle_expand()
                return True
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
            if self._search_input:
                self._search_input.show()
            if self._collapse_btn:
                self._collapse_btn.show()
            for lbl in self._group_labels.values():
                lbl.show()
            for lbl in self._shortcut_labels.values():
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
            if self._search_input:
                self._search_input.hide()
                self._search_input.clear()
            if self._collapse_btn:
                self._collapse_btn.hide()
            for lbl in self._group_labels.values():
                lbl.hide()
            for lbl in self._shortcut_labels.values():
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

    # ── Click-to-toggle expand / collapse ───────────────────────

    def _toggle_expand(self):
        """Toggle sidebar between expanded and collapsed state."""
        target = SIDEBAR_COLLAPSED if self._expanded else SIDEBAR_EXPANDED
        self._animate_width(target)

    # ── Search / filter items ───────────────────────────────────

    def _filter_items(self, text: str):
        """Show/hide nav items based on search text."""
        query = text.strip().lower()
        if not query:
            # Show all
            for key in self._items:
                frame = self._items[key]
                frame.setVisible(True)
            for name in self._group_labels:
                self._group_labels[name].setVisible(True)
            return

        # Count visible items per group
        visible_in_group: dict[str, int] = {}
        for key, frame in self._items.items():
            label = self._labels.get(key)
            label_text = (label.text() if label else "").lower()
            match = query in label_text
            frame.setVisible(match)
            grp = self._item_groups.get(key)
            if match and grp:
                visible_in_group[grp] = visible_in_group.get(grp, 0) + 1

        # Show/hide group labels
        for name in self._group_labels:
            has_visible = any(
                self._items[k].isVisible()
                for k, g in self._item_groups.items()
                if g == name
            )
            self._group_labels[name].setVisible(has_visible)

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

    def _destroy(self) -> None:
        unregister_listener(self._language_callback)
        self._stop_animation()
        self._items.clear()
        self._labels.clear()
        self._shortcut_labels.clear()
        self._group_labels.clear()
        self._item_i18n_keys.clear()
        self._group_i18n_keys.clear()
        super().deleteLater()
