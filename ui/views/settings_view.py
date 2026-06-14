"""PySide6 settings view.

Replaces ``ui/settings_view.py``.  Embedded as a QWidget for use in
QStackedWidget.  All form fields are organised in section cards inside a
scrollable container.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QDateEdit,
    QFileDialog,
    QColorDialog,
    QMessageBox,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from ui.theme import COLORS, S
from ui.styles import Theme
from ui.widgets import (
    StyledLineEdit,
    StyledComboBox,
    ActionButton,
    SectionHeader,
    ScrollableFormContainer,
    field,
)
from services.i18n import t, register_listener, unregister_listener
from services.preferences import PreferencesManager
from services.invoicing.config_manager import load_company_config, save_company_config
from services.operations.notification_center import NotificationCenter
from services.operations.event_bus import EventBus, SETTINGS_UPDATED

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  QtSettingsView
# ══════════════════════════════════════════════════════════════════════════════


class QtSettingsView(QWidget):
    """Settings page with form fields organized in section cards.

    Designed for embedded use in a QStackedWidget.  Provides company
    configuration, branding, user preferences (language/currency/theme),
    SMTP e-mail setup, fleet tracking, and maintenance threshold fields.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db=None,
        prefs: Optional[PreferencesManager] = None,
        ops=None,
    ):
        super().__init__(parent)
        self.db = db
        self.prefs = prefs or PreferencesManager(db)
        self.ops = ops
        self._event_bus = EventBus()

        # ── i18n tracking ────────────────────────────────────────────────
        self._i18n_labels: List[Tuple[QLabel, str]] = []
        self._i18n_buttons: List[Tuple[ActionButton, str]] = []
        self._section_headings: Dict[str, QLabel] = {}
        self._language_callback = self._on_language_changed

        # ── Brand colour swatch reference ────────────────────────────────
        self._brand_color_swatch: Optional[QFrame] = None

        # ── Input maps ───────────────────────────────────────────────────
        self.company_inputs: Dict[str, StyledLineEdit] = {}
        self.branding_inputs: Dict[str, StyledLineEdit] = {}
        self.smtp_inputs: Dict[str, StyledLineEdit] = {}
        self._tracking_rows: Dict[str, Tuple[QWidget, StyledLineEdit]] = {}

        # ── Preference controls ──────────────────────────────────────────
        self._lang_codes: List[str] = []
        self._lang_combo: Optional[StyledComboBox] = None
        self._currency_combo: Optional[StyledComboBox] = None
        self._theme_combo: Optional[StyledComboBox] = None
        self._tracking_platform_combo: Optional[StyledComboBox] = None
        self._tracking_test_label: Optional[QLabel] = None

        # ── Maintenance entries ──────────────────────────────────────────
        self._alert_days_ahead_entry: Optional[StyledLineEdit] = None
        self._tacho_warning_entry: Optional[StyledLineEdit] = None
        self._tacho_critical_entry: Optional[StyledLineEdit] = None

        # ── Build UI ─────────────────────────────────────────────────────
        self._build_ui()
        register_listener(self._language_callback)

    # ──────────────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Called when the view becomes visible (e.g. tab switch)."""
        pass

    def shutdown(self) -> None:
        """Clean up resources when the view is destroyed / hidden."""
        unregister_listener(self._language_callback)

    # ──────────────────────────────────────────────────────────────────────────
    #  i18n
    # ──────────────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        self.refresh_translations()

    def refresh_translations(self) -> None:
        """Update all visible text to the current language."""
        for label, key in self._i18n_labels:
            try:
                label.setText(t(key))
            except Exception:
                pass
        for button, key in self._i18n_buttons:
            try:
                button.setText(t(key))
            except Exception:
                pass
        for text_key, lbl in self._section_headings.items():
            try:
                lbl.setText(t(text_key))
            except Exception:
                pass
        # Rebuild preference menus whose items are language-dependent
        self._rebuild_preference_menus()
        # Rebuild tracking platform menu which contains translated items
        self._rebuild_tracking_platform_menu()

    # ──────────────────────────────────────────────────────────────────────────
    #  UI Build – top-level structure
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Page header
        self._build_header(layout)

        # Scrollable form body
        self._scroll = ScrollableFormContainer(self)
        layout.addWidget(self._scroll, 1)

        self._build_section_company()
        self._build_section_branding()
        self._build_section_preferences()
        self._build_section_email()
        self._build_section_tracking()
        self._build_section_maintenance()

        # Bottom save bar
        self._build_save_bar(layout)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setProperty("role", "card")
        header.setFixedHeight(72)
        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(S["5"], S["4"], S["5"], S["4"])

        title = QLabel(t("settings.title"))
        title.setProperty("fontRole", "h1")
        hdr_layout.addWidget(title)

        subtitle = QLabel(t("settings.subtitle"))
        subtitle.setProperty("fontRole", "muted")
        hdr_layout.addWidget(subtitle)

        parent_layout.addWidget(header)

    # ──────────────────────────────────────────────────────────────────────────
    #  Section card helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _section_card(self, title_key: str) -> QFrame:
        """Build a QFrame card with a SectionHeader and a dedicated content area.

        Returns the card; its content layout is stored at ``card._content_layout``
        so callers can ``.addWidget()`` field rows into it.
        """
        card = QFrame()
        card.setProperty("role", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = SectionHeader(card, t(title_key))
        self._section_headings[title_key] = header.label
        card_layout.addWidget(header)

        content = QWidget(card)
        content.setProperty("role", "card-content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(S["5"], S["3"], S["5"], S["5"])
        content_layout.setSpacing(S["3"])
        card_layout.addWidget(content)

        card._content_layout = content_layout
        card._content_widget = content  # keep a reference for cleanup
        return card

    def _add_labeled_field(
        self,
        card: QFrame,
        label_key: str,
        widget: QWidget,
        helper_text: str = "",
    ) -> QWidget:
        """Append a label + widget row inside a section card.

        Uses the global ``field()`` helper and wires i18n tracking.
        Returns the container widget.
        """
        container = field(card._content_widget, t(label_key), widget, helper_text)
        # The first (and only) QLabel child is the field label
        lbl = container.findChild(QLabel)
        if lbl is not None:
            self._i18n_labels.append((lbl, label_key))
        card._content_layout.addWidget(container)
        return container

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: Company
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_company(self) -> None:
        card = self._section_card("settings.section_company")
        self._scroll.add_widget(card)

        conf = load_company_config()

        fields_cfg: List[Tuple[str, str]] = [
            ("company_name", "settings.field_company_name"),
            ("cui", "settings.field_cui"),
            ("reg_number", "settings.field_reg_number"),
            ("address", "settings.field_address"),
            ("phone", "settings.field_phone"),
            ("email", "settings.field_email"),
        ]
        for key, label_key in fields_cfg:
            entry = StyledLineEdit(text=conf.get(key, ""))
            self._add_labeled_field(card, label_key, entry)
            self.company_inputs[key] = entry

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: Branding  (logo, colour, signature, stamp with file browsers)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_branding(self) -> None:
        card = self._section_card("settings.section_branding")
        self._scroll.add_widget(card)

        conf = load_company_config()

        # Helper to build an input row with an inline browse button
        def _browse_row(
            label_key: str,
            value: str,
            on_browse: Callable[[StyledLineEdit], None],
        ) -> StyledLineEdit:
            container = QWidget()
            vlyt = QVBoxLayout(container)
            vlyt.setContentsMargins(0, 0, 0, 0)
            vlyt.setSpacing(S["1"])

            lbl = QLabel(t(label_key))
            lbl.setProperty("fontRole", "label")
            vlyt.addWidget(lbl)
            self._i18n_labels.append((lbl, label_key))

            row = QWidget()
            hlyt = QHBoxLayout(row)
            hlyt.setContentsMargins(0, 0, 0, 0)
            hlyt.setSpacing(S["2"])

            entry = StyledLineEdit(text=value)
            hlyt.addWidget(entry, 1)

            browse_btn = ActionButton(row, "...", command=lambda: on_browse(entry), variant="ghost")
            browse_btn.setFixedWidth(32)
            hlyt.addWidget(browse_btn)

            vlyt.addWidget(row)
            card._content_layout.addWidget(container)
            return entry

        # ── Logo ────────────────────────────────────────────────────────
        self.branding_inputs["logo_path"] = _browse_row(
            "settings.field_logo",
            conf.get("logo_path", ""),
            self._browse_file,
        )

        # ── Company colour ──────────────────────────────────────────────
        colour_container = QWidget()
        colour_vlyt = QVBoxLayout(colour_container)
        colour_vlyt.setContentsMargins(0, 0, 0, 0)
        colour_vlyt.setSpacing(S["1"])

        colour_lbl = QLabel(t("settings.field_color"))
        colour_lbl.setProperty("fontRole", "label")
        colour_vlyt.addWidget(colour_lbl)
        self._i18n_labels.append((colour_lbl, "settings.field_color"))

        colour_row = QWidget()
        colour_hlyt = QHBoxLayout(colour_row)
        colour_hlyt.setContentsMargins(0, 0, 0, 0)
        colour_hlyt.setSpacing(S["2"])

        e_colour = StyledLineEdit(text=conf.get("company_color", "#6366f1"))
        colour_hlyt.addWidget(e_colour, 1)

        swatch = QFrame()
        swatch.setFixedSize(24, 24)
        swatch.setProperty("role", "colour-swatch")
        swatch.setStyleSheet(
            f"QFrame[role=\"colour-swatch\"] {{"
            f"  background-color: {conf.get('company_color', '#6366f1')};"
            f"  border-radius: 4px;"
            f"}}"
        )
        colour_hlyt.addWidget(swatch)

        pick_btn = ActionButton(
            colour_row,
            t("invoice_editor.pick_color"),
            command=lambda: self._pick_brand_color(e_colour, swatch),
            variant="ghost",
        )
        colour_hlyt.addWidget(pick_btn)

        colour_vlyt.addWidget(colour_row)
        card._content_layout.addWidget(colour_container)
        self.branding_inputs["company_color"] = e_colour
        self._brand_color_swatch = swatch

        # ── Signature ───────────────────────────────────────────────────
        self.branding_inputs["signature_path"] = _browse_row(
            "settings.field_signature",
            conf.get("signature_path", ""),
            self._browse_file,
        )

        # ── Stamp ───────────────────────────────────────────────────────
        self.branding_inputs["stamp_path"] = _browse_row(
            "settings.field_stamp",
            conf.get("stamp_path", ""),
            self._browse_file,
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: Preferences  (language / currency / theme)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_preferences(self) -> None:
        card = self._section_card("settings.section_preferences")
        self._scroll.add_widget(card)

        # ── Language ────────────────────────────────────────────────────
        self._lang_codes = self.prefs.get_available_languages()
        lang_display = self._build_lang_display_list()
        self._lang_combo = StyledComboBox(
            values=lang_display,
            state="readonly",
        )
        current_lang = self.prefs.get_language()
        current_idx = next(
            (i for i, c in enumerate(self._lang_codes) if c == current_lang), 0
        )
        self._lang_combo.setCurrentIndex(current_idx)
        self._lang_combo.currentTextChanged.connect(self._on_lang_combo_changed)
        self._add_labeled_field(card, "settings.language_label", self._lang_combo)

        # ── Currency ────────────────────────────────────────────────────
        currencies = self.prefs.get_supported_currencies()
        self._currency_combo = StyledComboBox(
            values=currencies,
            state="readonly",
        )
        current_currency = self.prefs.get_currency()
        currency_idx = currencies.index(current_currency) if current_currency in currencies else 0
        self._currency_combo.setCurrentIndex(currency_idx)
        self._currency_combo.currentTextChanged.connect(self._on_currency_combo_changed)
        self._add_labeled_field(card, "settings.currency_label", self._currency_combo)

        # ── Theme ───────────────────────────────────────────────────────
        self._theme_combo = StyledComboBox(
            values=[t("settings.theme_dark"), t("settings.theme_light")],
            state="readonly",
        )
        self._theme_combo.setCurrentIndex(0)
        self._theme_combo.currentTextChanged.connect(self._on_theme_combo_changed)
        self._add_labeled_field(card, "settings.theme_label", self._theme_combo)
        self._i18n_buttons.append((self._theme_combo, "settings.theme_label"))

    def _build_lang_display_list(self) -> List[str]:
        return [
            f"{self.prefs.get_language_display_name(c)} ({c})"
            for c in self._lang_codes
        ]

    def _rebuild_preference_menus(self) -> None:
        """Re-populate language and currency dropdowns after language change."""
        if self._lang_combo is not None:
            self._lang_codes = self.prefs.get_available_languages()
            lang_display = self._build_lang_display_list()
            self._lang_combo.clear()
            self._lang_combo.addItems(lang_display)
            current_lang = self.prefs.get_language()
            current_idx = next(
                (i for i, c in enumerate(self._lang_codes) if c == current_lang), 0
            )
            self._lang_combo.setCurrentIndex(current_idx)

        if self._theme_combo is not None:
            blocked = self._theme_combo.blockSignals(True)
            self._theme_combo.clear()
            self._theme_combo.addItems(
                [t("settings.theme_dark"), t("settings.theme_light")]
            )
            self._theme_combo.blockSignals(blocked)

    # ── Preference change handlers ──────────────────────────────────────

    def _on_lang_combo_changed(self, text: str) -> None:
        """Handle language dropdown selection."""
        try:
            idx = self._lang_combo.currentIndex()
            if 0 <= idx < len(self._lang_codes):
                self.prefs.set_language(self._lang_codes[idx])
        except Exception:
            pass

    def _on_currency_combo_changed(self, text: str) -> None:
        """Handle currency dropdown selection."""
        self.prefs.set_currency(text)

    def _on_theme_combo_changed(self, text: str) -> None:
        """Handle theme dropdown selection (stub — applies global QSS)."""
        # Theme switching would call QtTheme.apply(mode) here
        pass

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: E-mail / SMTP
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_email(self) -> None:
        card = self._section_card("settings.section_email")
        self._scroll.add_widget(card)

        smtp_keys = [
            "smtp_server", "smtp_port", "smtp_user", "smtp_password",
            "alert_email_recipients",
        ]
        smtp_labels = [
            "settings.field_smtp_server", "settings.field_smtp_port",
            "settings.field_smtp_user", "settings.field_smtp_password",
            "settings.field_alert_recipients",
        ]
        smtp_cfg = self.prefs.get_settings(smtp_keys) if self.prefs else {}

        for key, label_key in zip(smtp_keys, smtp_labels):
            entry = StyledLineEdit(text=smtp_cfg.get(key, ""))
            if key == "smtp_password":
                entry.setEchoMode(QLineEdit.EchoMode.Password)
            self._add_labeled_field(card, label_key, entry)
            self.smtp_inputs[key] = entry

        # Action buttons row
        btn_row = QWidget()
        btn_hlyt = QHBoxLayout(btn_row)
        btn_hlyt.setContentsMargins(0, 0, 0, 0)
        btn_hlyt.setSpacing(S["2"])

        test_btn = ActionButton(
            btn_row, t("settings.test_connection"),
            command=self._test_smtp,
            variant="secondary",
        )
        btn_hlyt.addWidget(test_btn)
        self._i18n_buttons.append((test_btn, "settings.test_connection"))

        logs_btn = ActionButton(
            btn_row, t("settings.email_logs"),
            command=self._view_email_logs,
            variant="secondary",
        )
        btn_hlyt.addWidget(logs_btn)
        self._i18n_buttons.append((logs_btn, "settings.email_logs"))

        card._content_layout.addWidget(btn_row)

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: Fleet Tracking
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_tracking(self) -> None:
        card = self._section_card("tracking.section_title")
        self._scroll.add_widget(card)

        # Hint label
        hint = QLabel(t("tracking.setup_hint"))
        hint.setProperty("fontRole", "muted")
        hint.setWordWrap(True)
        card._content_layout.addWidget(hint)

        # Platform dropdown
        platform_vals = self._build_tracking_platform_values()
        self._tracking_platform_combo = StyledComboBox(
            values=platform_vals,
            state="readonly",
        )
        saved_platform = (
            self.prefs.get_setting("tracking.platform") or ""
            if self.db else ""
        )
        display_val = saved_platform if saved_platform else platform_vals[0]
        idx = platform_vals.index(display_val) if display_val in platform_vals else 0
        self._tracking_platform_combo.setCurrentIndex(idx)
        self._tracking_platform_combo.currentTextChanged.connect(
            self._on_tracking_platform_changed
        )
        self._add_labeled_field(card, "tracking.platform", self._tracking_platform_combo)

        # Dynamic fields
        tracking_defs: List[Tuple[str, str, bool]] = [
            ("token", "tracking.token", False),
            ("host", "tracking.host", False),
            ("username", "tracking.username", False),
            ("password", "tracking.password", True),
        ]
        for key, label_key, is_password in tracking_defs:
            row_widget = QWidget()
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            # We store a reference to the input for later value access
            entry = StyledLineEdit(
                text=(
                    self.prefs.get_setting(f"tracking.{key}") or ""
                    if self.db else ""
                ),
            )
            if is_password:
                entry.setEchoMode(QLineEdit.EchoMode.Password)
            row_layout.addWidget(entry)
            # The field label is added via _add_labeled_field, but we track
            # field rows separately so _on_tracking_platform_changed can
            # show/hide them.
            self._tracking_rows[key] = (row_widget, entry)

        # Add each tracked field row to the card
        for key, label_key, _ in tracking_defs:
            row_widget, entry = self._tracking_rows[key]
            container = field(card._content_widget, t(label_key), row_widget)
            lbl = container.findChild(QLabel)
            if lbl is not None:
                self._i18n_labels.append((lbl, label_key))
            card._content_layout.addWidget(container)

        # Test button row
        test_row = QWidget()
        test_hlyt = QHBoxLayout(test_row)
        test_hlyt.setContentsMargins(0, 0, 0, 0)
        test_hlyt.setSpacing(S["2"])

        test_btn = ActionButton(
            test_row, t("tracking.btn_test"),
            command=self._test_tracking_connection,
            variant="secondary",
        )
        test_hlyt.addWidget(test_btn)
        self._i18n_buttons.append((test_btn, "tracking.btn_test"))

        self._tracking_test_label = QLabel("")
        self._tracking_test_label.setProperty("fontRole", "small")
        test_hlyt.addWidget(self._tracking_test_label)

        card._content_layout.addWidget(test_row)

        # Initial visibility
        self._on_tracking_platform_changed(self._tracking_platform_combo.currentText())

    def _build_tracking_platform_values(self) -> List[str]:
        return [
            t("tracking.platform_not_configured"),
            "Wialon / GPS-Trace (Gurtam)",
            "Frotcom",
            "Navixy",
            "Traccar (self-hosted)",
            "Generic REST API",
        ]

    def _rebuild_tracking_platform_menu(self) -> None:
        if self._tracking_platform_combo is None:
            return
        current_text = self._tracking_platform_combo.currentText()
        values = self._build_tracking_platform_values()
        self._tracking_platform_combo.clear()
        self._tracking_platform_combo.addItems(values)
        idx = values.index(current_text) if current_text in values else 0
        self._tracking_platform_combo.setCurrentIndex(idx)

    def _on_tracking_platform_changed(self, text: str) -> None:
        p = text.lower()
        not_cfg = t("tracking.platform_not_configured").lower()

        if not_cfg in p or "not configured" in p:
            visible = {k: False for k in self._tracking_rows}
        elif "wialon" in p or "gps-trace" in p or "gurtam" in p:
            visible = {"token": True, "host": True, "username": False, "password": False}
        elif "frotcom" in p:
            visible = {"token": False, "host": False, "username": True, "password": True}
        elif "navixy" in p:
            visible = {"token": True, "host": True, "username": False, "password": False}
        elif "traccar" in p:
            visible = {"token": False, "host": True, "username": True, "password": True}
        elif "generic" in p or "rest" in p:
            visible = {"token": True, "host": True, "username": False, "password": False}
        else:
            visible = {k: False for k in self._tracking_rows}

        for key, (row_widget, _entry) in self._tracking_rows.items():
            row_widget.setVisible(visible.get(key, False))

    def _test_tracking_connection(self) -> None:
        from services.fleet_tracking_service import FleetTrackingService

        platform = self._tracking_platform_combo.currentText() if self._tracking_platform_combo else ""
        if t("tracking.platform_not_configured").lower() in platform.lower():
            self._tracking_test_label.setText(
                f"\u2717 {t('tracking.test_incomplete')}"
            )
            self._tracking_test_label.setProperty("fontRole", "danger")
            # force style refresh
            self._tracking_test_label.style().unpolish(self._tracking_test_label)
            self._tracking_test_label.style().polish(self._tracking_test_label)
            return

        all_filled = True
        for key, (row_widget, entry) in self._tracking_rows.items():
            if row_widget.isVisible():
                if not entry.text().strip():
                    all_filled = False
                    break

        if not all_filled:
            self._tracking_test_label.setText(
                f"\u2717 {t('tracking.test_incomplete')}"
            )
            self._tracking_test_label.setProperty("fontRole", "danger")
            self._tracking_test_label.style().unpolish(self._tracking_test_label)
            self._tracking_test_label.style().polish(self._tracking_test_label)
            return

        settings_map = {"tracking.platform": platform}
        for key, (row_widget, entry) in self._tracking_rows.items():
            settings_map[f"tracking.{key}"] = entry.text().strip()
        if self.prefs:
            for k, v in settings_map.items():
                self.prefs.save_setting(k, v)

        svc = FleetTrackingService()
        svc.initialize(self.db)
        ok, msg = svc.test_connection()

        if not ok:
            logger.error("Tracking connection test failed: %s", msg)
            self._tracking_test_label.setText(
                f"\u2717 {t('tracking.test_incorrect')}"
            )
            self._tracking_test_label.setProperty("fontRole", "danger")
        else:
            self._tracking_test_label.setText(f"\u2713 {msg}")
            self._tracking_test_label.setProperty("fontRole", "success")
        self._tracking_test_label.style().unpolish(self._tracking_test_label)
        self._tracking_test_label.style().polish(self._tracking_test_label)

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: Maintenance Thresholds
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_maintenance(self) -> None:
        card = self._section_card("settings.section_maintenance")
        self._scroll.add_widget(card)

        entries: List[Tuple[str, str, str]] = [
            ("alert_days_ahead", "settings.field_alert_days_ahead", "_alert_days_ahead_entry"),
            ("tacho_warning", "settings.field_tacho_warning", "_tacho_warning_entry"),
            ("tacho_critical", "settings.field_tacho_critical", "_tacho_critical_entry"),
        ]
        for key, label_key, attr_name in entries:
            val = self.prefs.get_setting(key) if self.prefs else ""
            entry = StyledLineEdit(text=val or "")
            self._add_labeled_field(card, label_key, entry)
            setattr(self, attr_name, entry)

    # ──────────────────────────────────────────────────────────────────────────
    #  Save bar
    # ──────────────────────────────────────────────────────────────────────────

    def _build_save_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setProperty("role", "card")
        bar.setFixedHeight(64)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(S["5"], S["3"], S["5"], S["3"])

        reset_btn = ActionButton(
            bar, t("settings.reset"),
            command=self._reset,
            variant="secondary",
        )
        bar_layout.addWidget(reset_btn)
        self._i18n_buttons.append((reset_btn, "settings.reset"))

        bar_layout.addStretch(1)

        save_btn = ActionButton(
            bar, t("settings.save"),
            command=self._save_all,
            variant="primary",
        )
        save_btn.setFixedWidth(160)
        bar_layout.addWidget(save_btn)
        self._i18n_buttons.append((save_btn, "settings.save"))

        parent_layout.addWidget(bar)

    # ──────────────────────────────────────────────────────────────────────────
    #  Actions
    # ──────────────────────────────────────────────────────────────────────────

    def _save_all(self) -> None:
        """Collect all field values and persist to config / settings DB."""
        # ── Company + Branding ──────────────────────────────────────────
        company_data: Dict[str, str] = {
            k: v.text() for k, v in self.company_inputs.items()
        }
        for k, e in self.branding_inputs.items():
            company_data[k] = e.text()
        save_company_config(company_data)

        # ── Preferences ─────────────────────────────────────────────────
        if self._lang_combo is not None:
            self._on_lang_combo_changed(self._lang_combo.currentText())
        if self._currency_combo is not None:
            self._on_currency_combo_changed(self._currency_combo.currentText())

        # ── SMTP ────────────────────────────────────────────────────────
        smtp_keys = [
            "smtp_server", "smtp_port", "smtp_user", "smtp_password",
            "alert_email_recipients",
        ]
        for key in smtp_keys:
            entry = self.smtp_inputs.get(key)
            if entry is not None:
                self.prefs.save_setting(key, entry.text().strip())

        # ── Tracking ────────────────────────────────────────────────────
        if self.prefs is not None and self._tracking_platform_combo is not None:
            platform = self._tracking_platform_combo.currentText()
            self.prefs.save_setting("tracking.platform", platform)
            for key, (_row, entry) in self._tracking_rows.items():
                self.prefs.save_setting(f"tracking.{key}", entry.text().strip())

        # ── Maintenance ─────────────────────────────────────────────────
        for key, attr_name in [
            ("alert_days_ahead", "_alert_days_ahead_entry"),
            ("tacho_warning", "_tacho_warning_entry"),
            ("tacho_critical", "_tacho_critical_entry"),
        ]:
            entry = getattr(self, attr_name, None)
            if entry is not None:
                self.prefs.save_setting(key, entry.text().strip())

        # ── Ops refresh ─────────────────────────────────────────────────
        if self.ops is not None:
            try:
                self.ops._configure_smtp_from_db()
            except Exception:
                pass

        # ── Publish event ───────────────────────────────────────────────
        self._event_bus.publish(SETTINGS_UPDATED, {})

        QMessageBox.information(
            self,
            t("settings.success_save"),
            t("settings.success_save"),
        )

    def _reset(self) -> None:
        """Reload all field values from persisted config (discard edits)."""
        # Company
        conf = load_company_config()
        for key, entry in self.company_inputs.items():
            entry.setText(conf.get(key, ""))

        # Branding
        for k, entry in self.branding_inputs.items():
            entry.setText(conf.get(k, ""))

        # SMTP
        smtp_keys = [
            "smtp_server", "smtp_port", "smtp_user", "smtp_password",
            "alert_email_recipients",
        ]
        smtp_cfg = self.prefs.get_settings(smtp_keys) if self.prefs else {}
        for key, entry in self.smtp_inputs.items():
            entry.setText(smtp_cfg.get(key, ""))

        # Tracking
        if self.prefs is not None:
            for key, (_row, entry) in self._tracking_rows.items():
                entry.setText(self.prefs.get_setting(f"tracking.{key}") or "")

        # Maintenance
        for key, attr_name in [
            ("alert_days_ahead", "_alert_days_ahead_entry"),
            ("tacho_warning", "_tacho_warning_entry"),
            ("tacho_critical", "_tacho_critical_entry"),
        ]:
            entry = getattr(self, attr_name, None)
            if entry is not None:
                entry.setText(self.prefs.get_setting(key) or "")

    # ── File / colour pickers ───────────────────────────────────────────

    def _browse_file(self, entry: StyledLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("invoice_editor.select_logo"),
            "",
            "Image files (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*.*)",
        )
        if path:
            entry.setText(path)

    def _pick_brand_color(self, entry: StyledLineEdit, swatch: QFrame) -> None:
        initial = QColor(entry.text()) if entry.text() else QColor("#6366f1")
        color = QColorDialog.getColor(initial, self, t("invoice_editor.pick_color_title"))
        if color.isValid():
            hex_color = color.name()
            entry.setText(hex_color)
            swatch.setStyleSheet(
                f"QFrame[role=\"colour-swatch\"] {{"
                f"  background-color: {hex_color};"
                f"  border-radius: 4px;"
                f"}}"
            )

    # ── SMTP helpers ────────────────────────────────────────────────────

    def _test_smtp(self) -> None:
        nc = NotificationCenter()
        smtp_data: Dict[str, str] = {
            k: v.text().strip() for k, v in self.smtp_inputs.items()
        }
        try:
            port = int(smtp_data.get("smtp_port", "587"))
        except ValueError:
            QMessageBox.warning(
                self,
                t("settings.title"),
                t("settings.test_failed").format("Invalid port"),
            )
            return

        nc.configure_smtp(
            smtp_data.get("smtp_server", ""),
            port,
            smtp_data.get("smtp_user", ""),
            smtp_data.get("smtp_password", ""),
        )
        recipients_raw = smtp_data.get("alert_email_recipients", "")
        first_recipient = (
            recipients_raw.split(",")[0].strip()
            if recipients_raw
            else smtp_data.get("smtp_user", "")
        )
        if nc.send_test_email(first_recipient):
            QMessageBox.information(
                self,
                t("settings.test_connection"),
                t("settings.test_success"),
            )
        else:
            QMessageBox.critical(
                self,
                t("settings.test_connection"),
                t("settings.test_failed").format("SMTP error"),
            )

    def _view_email_logs(self) -> None:
        """Open a dialog showing recent e-mail log entries."""
        dialog = QDialog(self)
        dialog.setWindowTitle(t("settings.email_logs"))
        dialog.resize(700, 400)
        dialog.setProperty("role", "dialog")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(S["4"], S["4"], S["4"], S["4"])

        table = QTableWidget(dialog)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            t("email_logs.col_id"),
            t("email_logs.col_recipient"),
            t("email_logs.col_subject"),
            t("email_logs.col_sent"),
            t("email_logs.col_status"),
        ])
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(table.SelectRows)
        table.setEditTriggers(table.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setColumnWidth(0, 40)
        table.setColumnWidth(1, 200)
        table.setColumnWidth(2, 200)
        table.setColumnWidth(3, 150)
        table.setColumnWidth(4, 60)

        try:
            rows = self.db.conn.execute(
                "SELECT id, recipient, subject, timestamp, status "
                "FROM email_logs ORDER BY id DESC LIMIT 200"
            ).fetchall()
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    item = QTableWidgetItem(str(val) if val is not None else "")
                    table.setItem(r, c, item)
        except Exception:
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem(""))
            table.setItem(0, 1, QTableWidgetItem(t("email_logs.no_logs")))
            table.setItem(0, 2, QTableWidgetItem(""))
            table.setItem(0, 3, QTableWidgetItem(""))
            table.setItem(0, 4, QTableWidgetItem(""))

        layout.addWidget(table)
        dialog.exec()
