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
    QGraphicsOpacityEffect,
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
from ui.components import Badge
from ui.design_tokens import (
    ACCENT,
    BTN_HEIGHT_SM,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_HOVER,
    COLOR_TEXT_TERTIARY,
    RADIUS_PILL,
    SIDEBAR_COLLAPSED,
    SIDEBAR_EXPANDED,
    SP,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)

ITEM_H = 36
ANIM_DURATION = 200

# Monogram app-mark size. KEPT fixed on purpose: the mark is a perfect circle
# (border-radius 16 = half of 32) and the top section pins it to a 64px band;
# a pure minimums conversion would let it deform in the header row. Intentional
# decorative geometry (Phase 2).
MONOGRAM_SIZE = 32

# ── Icon mapping (qtawesome) ─────────────────────────────────────────
# Nav items MUST use qtawesome icons — no emoji, no colored squares.
# ── Keyboard shortcut hints for nav items ────────────────────────
# Display-only hints. The Ctrl+1..9 bindings exist in main_window;
# the extended set (Ctrl+0, Ctrl+Shift+1..4, Ctrl+Shift+S/T) is added
# by the main_window Phase 6 lane and mirrored here for display.
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
    "freight_exchange": "Ctrl+0",
    "maintenance":   "Ctrl+Shift+1",
    "invoices":      "Ctrl+Shift+2",
    "route_history": "Ctrl+Shift+4",
    "settings":      "Ctrl+Shift+S",
    "team":          "Ctrl+Shift+T",
    "history":       "Ctrl+H",  # final table also lists Ctrl+Shift+3 for history; Ctrl+H wins as the single display hint
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
"maintenance": "fa5s.wrench",
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
        self._badge_keys: dict[str, str] = {}
        self._badges: dict[str, Badge] = {}
        self._badge_counts: dict[str, int] = {}
        self._recent_section: QFrame | None = None
        self._recent_label: QLabel | None = None
        self._recent_items_layout: QVBoxLayout | None = None
        self._recent_items: list[tuple[str, str]] = []
        self._recent_frames: list[QFrame] = []
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
        top_layout.setContentsMargins(SP["3"], 0, SP["3"], 0)
        top_layout.setSpacing(SP["2"])

        # Monogram circle — click to toggle expand/collapse
        self._monogram = QFrame()
        self._monogram.setFixedSize(MONOGRAM_SIZE, MONOGRAM_SIZE)
        self._monogram.setAccessibleName("Operion home")
        self._monogram.setStyleSheet(
            f"background: {ACCENT}; border-radius: {RADIUS_PILL}px;"
        )
        self._monogram.setProperty("is-monogram", True)
        self._monogram.setCursor(Qt.PointingHandCursor)
        self._monogram.installEventFilter(self)
        mono_layout = QHBoxLayout(self._monogram)
        mono_layout.setContentsMargins(0, 0, 0, 0)
        mono_lbl = QLabel("O")
        mono_lbl.setProperty("role", "nav-monogram-text")
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
        name_lbl.setProperty("role", "nav-app-name")
        name_layout.addWidget(name_lbl)

        sub_lbl = QLabel(t("app.subtitle"))
        sub_lbl.setProperty("role", "nav-app-subtitle")
        name_layout.addWidget(sub_lbl)

        top_layout.addWidget(self._app_name_frame)
        top_layout.addStretch(1)

        self._app_name_frame.hide()

        layout = self.layout()
        layout.addWidget(top)

        # Divider
        divider = QFrame()
        divider.setProperty("role", "nav-divider")
        layout.addWidget(divider)

    def _build_scroll_area(self):
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QFrame()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(SP["2"], SP["2"], SP["2"], SP["2"])
        self._container_layout.setSpacing(SP["1"])
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
        # Compact search field — global QLineEdit[compact="true"] theme rule
        # covers the SUBTLE border / small radius / tight padding look.
        self._search_input.setProperty("compact", "true")
        self._search_input.textChanged.connect(self._filter_items)
        self._search_input.setVisible(self._expanded)
        self._container_layout.addWidget(self._search_input)

        # ── Recent items section (top of the scroll area, above groups) ──
        self._build_recent_section()

        self._scroll.setWidget(self._container)
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        layout.addWidget(self._scroll, 1)

    def _build_bottom_section(self):
        bottom = QFrame()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(SP["2"], 0, SP["2"], SP["2"])
        bottom_layout.setSpacing(0)

        divider = QFrame()
        divider.setProperty("role", "nav-divider")
        bottom_layout.addWidget(divider)

        # ── Collapse chevron button (visible only when expanded) ──
        self._collapse_btn = QPushButton()
        self._collapse_btn.setIcon(qta.icon("fa5s.chevron-left", color=COLOR_TEXT_TERTIARY))
        self._collapse_btn.setToolTip(t("sidebar.collapse", default="Collapse sidebar"))
        self._collapse_btn.setFixedHeight(28)
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setProperty("role", "nav-toggle")
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
        lbl.setProperty("role", "nav-group-label")
        lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._container_layout.addWidget(lbl)
        self._group_labels[name] = lbl

        if not self._expanded:
            lbl.hide()

        self._groups.append(name)

    def add_item(self, key: str, label: str, group: str | None = None,
                 i18n_key: str | None = None, badge_key: str | None = None):
        if group and group not in self._groups:
            self.add_group(group)
        if i18n_key:
            self._item_i18n_keys[key] = i18n_key
        if badge_key:
            self._badge_keys[key] = badge_key

        text = t(i18n_key) if i18n_key else label
        frame = self._create_item_frame(key, text, badge_key=badge_key)
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

    def set_badge(self, key: str, count: int):
        """Set the count badge for a nav item (hides at <=0 and when collapsed)."""
        badge = self._badges.get(key)
        if badge is None:
            return
        self._badge_counts[key] = count
        if not self._expanded:
            badge.hide()
            return
        badge.set_count(count)

    def set_recent_items(self, items: list[tuple[str, str]]):
        """Rebuild the recent-items section (up to 3, most recent last).

        Items are ``(nav_key, label)`` pairs. The section is hidden when the
        list is empty. Clicking a recent item navigates through the normal
        select path but never activates/highlights it.
        """
        recent = list(items[-3:])
        self._recent_items = recent

        # Remove previous frames from the layout before deleting them.
        if self._recent_items_layout is not None:
            while self._recent_items_layout.count():
                item = self._recent_items_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._recent_frames.clear()

        if self._recent_items_layout is not None:
            for key, label in recent:
                frame = self._create_recent_item_frame(key, label)
                self._recent_items_layout.addWidget(frame)
                self._recent_frames.append(frame)

        if self._recent_section is not None:
            self._recent_section.setVisible(bool(recent))
            if not self._expanded and self._recent_label is not None:
                self._recent_label.hide()

    # ── Item factory ────────────────────────────────────────────

    def _create_item_frame(self, key: str, label: str, badge_key: str | None = None) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(ITEM_H)
        frame.setCursor(Qt.PointingHandCursor)
        frame.setProperty("role", "nav-item")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(SP["1"], 0, SP["2"], 0)
        layout.setSpacing(0)

        # Left accent bar (coloured by the nav-accent role when active)
        accent = QFrame()
        accent.setFixedWidth(4)
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
        text_lbl.setProperty("role", "nav-label")
        text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(text_lbl, 1)
        if not self._expanded:
            text_lbl.hide()

        # Count badge (hidden at 0 and when collapsed; shown via set_badge)
        if badge_key:
            badge = Badge()
            badge.setAttribute(Qt.WA_TransparentForMouseEvents)
            layout.addWidget(badge)
            self._badges[key] = badge
            if not self._expanded:
                badge.hide()

        # Keyboard shortcut hint (visible only when expanded)
        shortcut_text = NAV_SHORTCUTS.get(key)
        if shortcut_text:
            shortcut_lbl = QLabel(shortcut_text)
            shortcut_lbl.setProperty("fontRole", "helper")
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

    # ── Recent items section ───────────────────────────────────

    def _build_recent_section(self):
        """Build the (initially hidden) recent-items section at the very top
        of the scroll area — directly above the first group."""
        section = QFrame()
        section.setProperty("role", "nav-group")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        self._recent_label = QLabel(t("nav.group_recent").upper())
        self._recent_label.setProperty("role", "nav-group-label")
        self._recent_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        section_layout.addWidget(self._recent_label)
        if not self._expanded:
            self._recent_label.hide()

        self._recent_items_layout = QVBoxLayout()
        self._recent_items_layout.setSpacing(0)
        section_layout.addLayout(self._recent_items_layout)

        # Separator below the recent section, above the first group.
        spacer = QFrame()
        spacer.setFixedHeight(8)
        section_layout.addWidget(spacer)

        # Insert below the search input (index 1) — above every group.
        self._container_layout.insertWidget(1, section)
        self._recent_section = section
        self._recent_section.hide()

    def _create_recent_item_frame(self, key: str, label: str) -> QFrame:
        """Subdued nav-item frame for recent entries: tertiary text, dimmed
        icon (60% opacity), no active accent. Never activated/highlighted."""
        frame = QFrame()
        frame.setFixedHeight(ITEM_H)
        frame.setCursor(Qt.PointingHandCursor)
        frame.setProperty("role", "nav-item")
        frame.setProperty("is-recent", True)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(SP["1"], 0, SP["2"], 0)
        layout.setSpacing(0)

        # Left accent bar — kept structurally, stays uncoloured (no active state)
        accent = QFrame()
        accent.setFixedWidth(4)
        layout.addWidget(accent)

        # Icon — dimmed to 60% opacity
        icon_name = NAV_ICONS.get(key, "fa5s.circle")
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color=TEXT_MUTED).pixmap(16, 16))
        icon_lbl.setFixedWidth(32)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        effect = QGraphicsOpacityEffect(icon_lbl)
        effect.setOpacity(0.6)
        icon_lbl.setGraphicsEffect(effect)
        layout.addWidget(icon_lbl)

        # Text label — tertiary color, subdued
        text_lbl = QLabel(label)
        text_lbl.setProperty("role", "nav-label")
        text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 13px; background: transparent;"
        )
        layout.addWidget(text_lbl, 1)
        if not self._expanded:
            text_lbl.hide()

        frame.setAccessibleName(label)
        frame.setToolTip(label)
        frame.setProperty("nav-key", key)
        frame.installEventFilter(self)
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
                if obj.property("is-recent"):
                    # Recent items navigate through the select path but are
                    # deliberately never shown as active/highlighted.
                    if self._on_select:
                        self._on_select(key, None)
                else:
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
            # Badges: restore visibility from stored counts (hidden at <=0)
            for key, badge in self._badges.items():
                badge.set_count(self._badge_counts.get(key, 0))
            # Recent section: show label + item texts when populated
            if self._recent_label is not None:
                self._recent_label.show()
            for frame in self._recent_frames:
                text_lbl = self._text_label_for_item(frame)
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
            # Badges and recent labels are hidden in the collapsed rail.
            for badge in self._badges.values():
                badge.hide()
            if self._recent_label is not None:
                self._recent_label.hide()
            for frame in self._recent_frames:
                text_lbl = self._text_label_for_item(frame)
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
        if self._recent_label is not None:
            self._recent_label.setText(t("nav.group_recent").upper())

    def _destroy(self) -> None:
        unregister_listener(self._language_callback)
        self._stop_animation()
        self._items.clear()
        self._labels.clear()
        self._shortcut_labels.clear()
        self._group_labels.clear()
        self._item_i18n_keys.clear()
        self._group_i18n_keys.clear()
        self._badge_keys.clear()
        self._badges.clear()
        self._badge_counts.clear()
        for frame in self._recent_frames:
            frame.deleteLater()
        self._recent_frames.clear()
        self._recent_items.clear()
        super().deleteLater()
