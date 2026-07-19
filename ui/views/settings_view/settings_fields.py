"""PySide6 settings view — field creation helpers and form sections.

Split from ``settings_view.py``.  Provides ``SettingsFieldsMixin`` used by
``QtSettingsView``.
"""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from services.invoicing.config_manager import load_company_config
from services.operations.event_bus import TOUR_REPLAY_REQUESTED, EventBus
from ui.components import Btn, Card, Divider, FieldLabel, Label, SectionTitle
from ui.design_tokens import SP
from ui.widgets import StyledComboBox, StyledLineEdit

logger = logging.getLogger(__name__)

DEFAULT_BRAND_COLOR = "#6366f1"


class SettingsFieldsMixin:
    """Mixin providing section card helpers and all ``_build_section_*`` methods.

    Intended for use alongside ``QtSettingsView``; relies on ``self`` having
    the instance attributes set up in ``QtSettingsView.__init__``.
    """

    # ──────────────────────────────────────────────────────────────────────────
    #  Section card helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _section_card(self, title_key: str) -> QFrame:
        """Build a Card with a SectionTitle and a dedicated content area.

        Returns the card; its content layout is stored at ``card._content_layout``
        so callers can ``.addWidget()`` field rows into it.
        """
        card = Card(self._scroll)

        title_lbl = SectionTitle(card, t(title_key))
        card.layout().addWidget(title_lbl)
        self._section_headings[title_key] = title_lbl

        div = Divider(card)
        card.layout().addWidget(div)

        card._content_layout = card.layout()
        card._content_widget = card
        return card

    def _add_labeled_field(
        self,
        card: QFrame,
        label_key: str,
        widget: QWidget,
        helper_text: str = "",
    ) -> QWidget:
        """Append a label + widget row inside a section card.

        Uses FieldLabel() from the design system and wires i18n tracking.
        Returns the container widget.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SP["1"])

        label = FieldLabel(container, t(label_key))
        layout.addWidget(label)
        self._i18n_labels.append((label, label_key))

        layout.addWidget(widget)

        if helper_text:
            helper = Label(container, helper_text, role="muted")
            layout.addWidget(helper)

        card._content_layout.addWidget(container)
        return container

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: Company
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_company(self) -> None:
        card = self._section_card("settings.section_company")
        self._scroll.add_widget(card)

        conf = load_company_config()

        fields_cfg: list[tuple[str, str]] = [
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
            vlyt.setSpacing(SP["1"])

            lbl = FieldLabel(container, t(label_key))
            vlyt.addWidget(lbl)
            self._i18n_labels.append((lbl, label_key))

            row = QWidget()
            hlyt = QHBoxLayout(row)
            hlyt.setContentsMargins(0, 0, 0, 0)
            hlyt.setSpacing(SP["2"])

            entry = StyledLineEdit(text=value)
            hlyt.addWidget(entry, 1)

            browse_btn = Btn(row, "...", variant="ghost", command=lambda: on_browse(entry))
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
        colour_vlyt.setSpacing(SP["1"])

        colour_lbl = FieldLabel(colour_container, t("settings.field_color"))
        colour_vlyt.addWidget(colour_lbl)
        self._i18n_labels.append((colour_lbl, "settings.field_color"))

        colour_row = QWidget()
        colour_hlyt = QHBoxLayout(colour_row)
        colour_hlyt.setContentsMargins(0, 0, 0, 0)
        colour_hlyt.setSpacing(SP["2"])

        e_colour = StyledLineEdit(text=conf.get("company_color", DEFAULT_BRAND_COLOR))
        colour_hlyt.addWidget(e_colour, 1)

        swatch = QFrame()
        swatch.setFixedSize(24, 24)
        swatch.setProperty("role", "colour-swatch")
        swatch.setStyleSheet(
            f"QFrame[role=\"colour-swatch\"] {{"
            f"  background-color: {conf.get('company_color', DEFAULT_BRAND_COLOR)};"
            f"  border-radius: 4px;"
            f"}}"
        )
        colour_hlyt.addWidget(swatch)

        pick_btn = Btn(
            colour_row,
            t("invoice_editor.pick_color"),
            variant="ghost",
            command=lambda: self._pick_brand_color(e_colour, swatch),
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

    def _build_lang_display_list(self) -> list[str]:
        return [
            f"{self.prefs.get_language_display_name(c)} ({c})"
            for c in self._lang_codes
        ]

    def _rebuild_preference_menus(self) -> None:
        """Re-populate language and currency dropdowns after language change."""
        if self._lang_combo is not None:
            blocked = self._lang_combo.blockSignals(True)
            self._lang_codes = self.prefs.get_available_languages()
            lang_display = self._build_lang_display_list()
            self._lang_combo.clear()
            self._lang_combo.addItems(lang_display)
            current_lang = self.prefs.get_language()
            current_idx = next(
                (i for i, c in enumerate(self._lang_codes) if c == current_lang), 0
            )
            self._lang_combo.setCurrentIndex(current_idx)
            self._lang_combo.blockSignals(blocked)

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
        """Handle theme dropdown selection — re-apply global QSS."""
        from PySide6.QtWidgets import QApplication
        from ui.theme_engine import QtTheme

        app = QApplication.instance()
        if app is not None:
            QtTheme.refresh(app)
        logger.debug("Theme refreshed (selected: %s)", text)

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
        btn_hlyt.setSpacing(SP["2"])

        test_btn = Btn(
            btn_row, t("settings.test_connection"),
            command=self._test_smtp,
            variant="secondary",
        )
        btn_hlyt.addWidget(test_btn)
        self._i18n_buttons.append((test_btn, "settings.test_connection"))

        logs_btn = Btn(
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
        card.setObjectName("settings_section_tracking")
        self._scroll.add_widget(card)

        # Hint label
        hint = Label(card, t("tracking.setup_hint"), role="muted")
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
        tracking_defs: list[tuple[str, str, bool]] = [
            ("token", "tracking.token", False),
            ("host", "tracking.host", False),
            ("username", "tracking.username", False),
            ("password", "tracking.password", True),
        ]
        for key, _label_key, is_password in tracking_defs:
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
            container = QWidget()
            vlyt = QVBoxLayout(container)
            vlyt.setContentsMargins(0, 0, 0, 0)
            vlyt.setSpacing(SP["1"])
            lbl = FieldLabel(container, t(label_key))
            vlyt.addWidget(lbl)
            self._i18n_labels.append((lbl, label_key))
            vlyt.addWidget(row_widget)
            card._content_layout.addWidget(container)

        # Test button row
        test_row = QWidget()
        test_hlyt = QHBoxLayout(test_row)
        test_hlyt.setContentsMargins(0, 0, 0, 0)
        test_hlyt.setSpacing(SP["2"])

        test_btn = Btn(
            test_row, t("tracking.btn_test"),
            command=self._test_tracking_connection,
            variant="secondary",
        )
        test_hlyt.addWidget(test_btn)
        self._i18n_buttons.append((test_btn, "tracking.btn_test"))

        self._tracking_test_label = Label(test_row, "", role="muted")
        test_hlyt.addWidget(self._tracking_test_label)

        card._content_layout.addWidget(test_row)

        # Initial visibility
        self._on_tracking_platform_changed(self._tracking_platform_combo.currentText())

    def _build_tracking_platform_values(self) -> list[str]:
        return [
            t("tracking.platform_not_configured"),
            t("tracking.platform_wialon", default="Wialon / GPS-Trace (Gurtam)"),
            t("tracking.platform_frotcom", default="Frotcom"),
            t("tracking.platform_navixy", default="Navixy"),
            t("tracking.platform_traccar", default="Traccar (self-hosted)"),
            t("tracking.platform_generic_rest", default="Generic REST API"),
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
            visible = dict.fromkeys(self._tracking_rows, False)
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
            visible = dict.fromkeys(self._tracking_rows, False)

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
        for _key, (row_widget, entry) in self._tracking_rows.items():
            if row_widget.isVisible() and not entry.text().strip():
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
        for key, (_row_widget, entry) in self._tracking_rows.items():
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

        entries: list[tuple[str, str, str]] = [
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
    #  Section: Automation / OCR / Email Importer / Folder Watcher
    # ──────────────────────────────────────────────────────────────────────────

    def _build_section_automation(self) -> None:
        card = self._section_card("settings.section_automation")
        self._scroll.add_widget(card)

        # Company name used as the email signature.
        company_entry = StyledLineEdit(
            text=(self.prefs.get_setting("automation_company_name", "Operion ERP")
                  if self.prefs else "Operion ERP")
        )
        self._add_labeled_field(card, "settings.field_automation_company", company_entry)
        self._automation_company_entry = company_entry

        # Subject template.
        from services.document_automation.email_template import DEFAULT_SUBJECT
        subject_entry = StyledLineEdit(
            text=(self.prefs.get_setting("automation_email_subject_template", DEFAULT_SUBJECT)
                  if self.prefs else DEFAULT_SUBJECT)
        )
        self._add_labeled_field(card, "settings.field_automation_subject", subject_entry)
        self._automation_subject_entry = subject_entry

        # Body template.
        from services.document_automation.email_template import DEFAULT_BODY
        body_widget = QPlainTextEdit()
        body_widget.setPlainText(
            self.prefs.get_setting("automation_email_body_template", DEFAULT_BODY)
             if self.prefs else DEFAULT_BODY
        )
        body_widget.setMinimumHeight(180)
        body_label = QLabel(t("settings.field_automation_body", default="Body template:"))
        body_label.setProperty("fontRole", "muted")
        card.layout().addWidget(body_label)
        card.layout().addWidget(body_widget)
        self._automation_body_edit = body_widget

        # ── Cloud OCR credentials ────────────────────────────────────
        ocr_label = QLabel(t("settings.field_ocr_credentials", default="Cloud OCR credentials:"))
        ocr_label.setProperty("fontRole", "muted")
        card.layout().addWidget(ocr_label)
        card.layout().addSpacing(4)

        self._ocr_google_key = self._add_ocr_field(
            card, "Google Vision API key",
            self.prefs.get_setting("ocr_google_key", "") if self.prefs else "",
        )
        self._ocr_google_project = self._add_ocr_field(
            card, "Google Project ID",
            self.prefs.get_setting("ocr_google_project_id", "") if self.prefs else "",
        )
        self._ocr_azure_endpoint = self._add_ocr_field(
            card, "Azure endpoint",
            self.prefs.get_setting("ocr_azure_endpoint", "") if self.prefs else "",
        )
        self._ocr_azure_key = self._add_ocr_field(
            card, "Azure key",
            self.prefs.get_setting("ocr_azure_key", "") if self.prefs else "",
        )
        self._ocr_language_hints = self._add_ocr_field(
            card, "Language hints (comma-separated)",
            self.prefs.get_setting("ocr_language_hints", "") if self.prefs else "",
        )

        hint = QLabel(t("settings.field_ocr_help", default="Set at least one provider's credentials to enable handwriting recognition."))
        hint.setProperty("fontRole", "muted")
        hint.setWordWrap(True)
        card.layout().addWidget(hint)

        # ── PaddleOCR GPU toggle ──────────────────────────────────────
        from ui.widgets import StyledCheckBox
        gpu_enabled = self.prefs.get_setting("ocr_use_gpu", "0") if self.prefs else "0"
        self._ocr_gpu_check = StyledCheckBox(
            card,
            text=t("settings.field_ocr_gpu", default="Use GPU for OCR (requires CUDA + PaddlePaddle GPU)"),
        )
        self._ocr_gpu_check.setChecked(gpu_enabled in ("1", "true", "yes"))
        card.layout().addWidget(self._ocr_gpu_check)

        # ── PaddleOCR advanced config ─────────────────────────────────
        ocr_config_label = QLabel(t("settings.field_ocr_config", default="PaddleOCR advanced settings:"))
        ocr_config_label.setProperty("fontRole", "muted")
        card.layout().addWidget(ocr_config_label)

        det_len = self.prefs.get_setting("ocr_det_limit_side_len", "960") if self.prefs else "960"
        self._ocr_det_len = StyledLineEdit(text=det_len)
        self._add_labeled_field(card, "Detection limit side length (px)", self._ocr_det_len)

        rec_batch = self.prefs.get_setting("ocr_rec_batch_num", "6") if self.prefs else "6"
        self._ocr_rec_batch = StyledLineEdit(text=rec_batch)
        self._add_labeled_field(card, "Recognition batch count", self._ocr_rec_batch)

        # ── AI Vision fallback (Gemma 3) ──────────────────────────────
        ai_label = QLabel(t("settings.field_ai_vision", default="AI Vision fallback (Gemma 3, local):"))
        ai_label.setProperty("fontRole", "muted")
        card.layout().addWidget(ai_label)
        card.layout().addSpacing(4)

        from ui.widgets import StyledComboBox
        self._ai_api_mode = StyledComboBox(
            values=["ollama", "openai"],
            state="readonly",
        )
        api_mode = self.prefs.get_setting("qwen_api_mode", "ollama") if self.prefs else "ollama"
        self._ai_api_mode.setCurrentText(api_mode)
        self._add_labeled_field(card, "API mode (ollama / openai-compat)", self._ai_api_mode)

        self._ai_endpoint = StyledLineEdit(
            text=self.prefs.get_setting("qwen_endpoint", "https://ocr.operionerp.xyz") if self.prefs else "https://ocr.operionerp.xyz",
        )
        self._add_labeled_field(card, "Endpoint URL", self._ai_endpoint)

        self._ai_model = StyledLineEdit(
            text=self.prefs.get_setting("qwen_model", "gemma3:4b") if self.prefs else "gemma3:4b",
        )
        self._add_labeled_field(card, "Model name", self._ai_model)

        self._ai_max_pages = StyledLineEdit(
            text=self.prefs.get_setting("qwen_max_pages", "3") if self.prefs else "3",
        )
        self._add_labeled_field(card, "Max pages per document", self._ai_max_pages)

        self._ai_rpm = StyledLineEdit(
            text=self.prefs.get_setting("qwen_rpm_limit", "10") if self.prefs else "10",
        )
        self._add_labeled_field(card, "Rate limit (requests/min)", self._ai_rpm)

        # AI request timeout (seconds)
        self._ai_timeout = QSpinBox()
        self._ai_timeout.setRange(30, 600)
        self._ai_timeout.setSuffix(" seconds")
        self._ai_timeout.setSingleStep(10)
        current_timeout = int(self.prefs.get_setting("qwen_timeout_s", "300")) if self.prefs else 300
        self._ai_timeout.setValue(current_timeout)
        self._add_labeled_field(card, "AI request timeout", self._ai_timeout)

        # Confidence threshold for PaddleOCR → AI fallback
        self._ai_threshold = StyledLineEdit(
            text=self.prefs.get_setting("ai_confidence_threshold", "75") if self.prefs else "75",
        )
        self._add_labeled_field(card, "PaddleOCR confidence threshold (%)", self._ai_threshold)

        # ── Email Importer ─────────────────────────────────────────────
        email_label = QLabel(t("settings.field_email_importer", default="Email importer (IMAP):"))
        email_label.setProperty("fontRole", "muted")
        card.layout().addWidget(email_label)
        card.layout().addSpacing(4)

        from ui.widgets import StyledCheckBox
        self._email_importer_enabled = StyledCheckBox(card, text="Enable email import")
        if self.prefs:
            self._email_importer_enabled.setChecked(self.prefs.get_setting("email_importer_enabled", "0") in ("1", "true"))
        card.layout().addWidget(self._email_importer_enabled)

        self._email_importer_host = StyledLineEdit(
            text=self.prefs.get_setting("email_importer_host", "") if self.prefs else "",
        )
        self._add_labeled_field(card, "IMAP server", self._email_importer_host)

        self._email_importer_port = StyledLineEdit(
            text=self.prefs.get_setting("email_importer_port", "993") if self.prefs else "993",
        )
        self._add_labeled_field(card, "IMAP port", self._email_importer_port)

        self._email_importer_user = StyledLineEdit(
            text=self.prefs.get_setting("email_importer_user", "") if self.prefs else "",
        )
        self._add_labeled_field(card, "IMAP username", self._email_importer_user)

        self._email_importer_password = StyledLineEdit(
            text=self.prefs.get_setting("email_importer_password", "") if self.prefs else "",
        )
        self._email_importer_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_labeled_field(card, "IMAP password", self._email_importer_password)

        self._email_importer_interval = StyledLineEdit(
            text=self.prefs.get_setting("email_importer_interval", "60") if self.prefs else "60",
        )
        self._add_labeled_field(card, "Poll interval (seconds)", self._email_importer_interval)

        self._email_importer_whitelist = StyledLineEdit(
            text=self.prefs.get_setting("email_importer_whitelist", "") if self.prefs else "",
        )
        self._add_labeled_field(card, "Sender whitelist (comma-separated)", self._email_importer_whitelist)

        self._email_importer_delete = StyledCheckBox(card, text="Delete processed emails after import")
        if self.prefs:
            self._email_importer_delete.setChecked(
                self.prefs.get_setting("email_importer_delete", "0") in ("1", "true")
            )
        card.layout().addWidget(self._email_importer_delete)

        # ── Folder Watcher ─────────────────────────────────────────────
        fw_label = QLabel(t("settings.field_folder_watcher", default="Folder watcher (hot folder):"))
        fw_label.setProperty("fontRole", "muted")
        card.layout().addWidget(fw_label)
        card.layout().addSpacing(4)

        self._fw_enabled = StyledCheckBox(card, text="Enable folder watcher")
        if self.prefs:
            self._fw_enabled.setChecked(self.prefs.get_setting("folder_watcher_enabled", "0") in ("1", "true"))
        card.layout().addWidget(self._fw_enabled)

        self._fw_path = StyledLineEdit(
            text=self.prefs.get_setting("folder_watcher_path", "") if self.prefs else "",
        )
        self._add_labeled_field(card, "Watch folder path", self._fw_path)

        self._fw_interval = StyledLineEdit(
            text=self.prefs.get_setting("folder_watcher_interval", "10") if self.prefs else "10",
        )
        self._add_labeled_field(card, "Poll interval (seconds)", self._fw_interval)

        self._fw_recursive = StyledCheckBox(card, text="Watch subdirectories recursively")
        if self.prefs:
            self._fw_recursive.setChecked(self.prefs.get_setting("folder_watcher_recursive", "0") in ("1", "true"))
        card.layout().addWidget(self._fw_recursive)

        self._fw_delete = StyledCheckBox(card, text="Delete files after import")
        if self.prefs:
            self._fw_delete.setChecked(self.prefs.get_setting("folder_watcher_delete", "0") in ("1", "true"))
        card.layout().addWidget(self._fw_delete)

    # ──────────────────────────────────────────────────────────────────────────
    #  Section: Autonomous Mode  (Enterprise-tier per-workflow AI toggles)
    # ──────────────────────────────────────────────────────────────────────────

    def _get_subscription_tier(self) -> str:
        """Return the current company's subscription tier from the DB.

        Returns ``"starter"`` when the database is unavailable (remote mode
        or offline without a configured company).
        """
        if not self.db:
            return "starter"
        try:
            cursor = self.db.execute(
                "SELECT subscription_tier FROM companies LIMIT 1",
            )
            row = cursor.fetchone()
            return str(row[0]) if row else "starter"
        except Exception:
            return "starter"

    def _build_section_autonomous_mode(self) -> None:
        """Build settings card for AI Autonomous Mode (Enterprise feature).

        Non-Enterprise tiers see an upgrade prompt.  Enterprise users get
        per-workflow toggle switches and a circuit-breaker status stub.
        """
        card = self._section_card("settings.section_autonomous_mode")
        self._scroll.add_widget(card)

        tier = self._get_subscription_tier()
        is_enterprise = tier == "enterprise"

        if not is_enterprise:
            upgrade_label = Label(
                card,
                t("settings.autonomous.upgrade_needed"),
                role="muted",
            )
            upgrade_label.setWordWrap(True)
            card._content_layout.addWidget(upgrade_label)
            return

        from ui.widgets import StyledCheckBox

        # ── Auto-Dispatch ─────────────────────────────────────────────────
        dispatch_cb = StyledCheckBox(
            card, text=t("settings.autonomous.dispatch"),
        )
        if self.prefs:
            dispatch_cb.setChecked(
                self.prefs.get_setting("copilot.auto_dispatch", "0")
                in ("1", "true"),
            )
        card._content_layout.addWidget(dispatch_cb)
        self._auto_dispatch = dispatch_cb

        dispatch_help = Label(
            card, t("settings.autonomous.dispatch_help"), role="muted",
        )
        dispatch_help.setWordWrap(True)
        card._content_layout.addWidget(dispatch_help)

        # ── Auto-Invoice ─────────────────────────────────────────────────
        invoice_cb = StyledCheckBox(
            card, text=t("settings.autonomous.invoice"),
        )
        if self.prefs:
            invoice_cb.setChecked(
                self.prefs.get_setting("copilot.auto_invoice", "0")
                in ("1", "true"),
            )
        card._content_layout.addWidget(invoice_cb)
        self._auto_invoice = invoice_cb

        invoice_help = Label(
            card, t("settings.autonomous.invoice_help"), role="muted",
        )
        invoice_help.setWordWrap(True)
        card._content_layout.addWidget(invoice_help)

        # ── Auto-Email ────────────────────────────────────────────────────
        email_cb = StyledCheckBox(
            card, text=t("settings.autonomous.email"),
        )
        if self.prefs:
            email_cb.setChecked(
                self.prefs.get_setting("copilot.auto_email", "0")
                in ("1", "true"),
            )
        card._content_layout.addWidget(email_cb)
        self._auto_email = email_cb

        email_help = Label(
            card, t("settings.autonomous.email_help"), role="muted",
        )
        email_help.setWordWrap(True)
        card._content_layout.addWidget(email_help)

        # ── Circuit breaker status (stub) ────────────────────────────────
        divider = Divider(card)
        card._content_layout.addWidget(divider)

        cb_header = Label(
            card,
            t("settings.autonomous.circuit_breaker_status"),
            role="muted",
        )
        card._content_layout.addWidget(cb_header)

        cb_status = Label(
            card,
            t("settings.autonomous.circuit_breaker_active"),
            role="success",
        )
        card._content_layout.addWidget(cb_status)
        self._circuit_breaker_status = cb_status

    # ── Tutorial Section (§34.7) ──────────────────────────────────────────

    def _build_section_tutorial(self) -> None:
        """Build settings card for replaying the onboarding tour."""
        card = self._section_card("settings.section_tutorial")
        self._scroll.add_widget(card)

        desc = Label(
            card,
            t("settings.tutorial.description"),
            role="muted",
        )
        desc.setWordWrap(True)
        card._content_layout.addWidget(desc)

        # Check if tour has been completed before
        from ui.copilot import tour_tracker
        tour_completed = tour_tracker.is_tour_completed("app_overview")
        status_key = "settings.tutorial.completed" if tour_completed else "settings.tutorial.not_completed"
        status_label = Label(card, t(status_key), role="success" if tour_completed else "muted")
        card._content_layout.addWidget(status_label)

        # Replay button
        replay_btn = Btn(
            card,
            t("settings.tutorial.replay_button"),
            command=self._on_replay_tour,
            variant="primary",
        )
        replay_btn.setFixedWidth(240)
        card._content_layout.addWidget(replay_btn)

        # Reset all tours button
        reset_btn = Btn(
            card,
            t("settings.tutorial.reset_all_button"),
            command=self._on_reset_all_tours,
            variant="secondary",
        )
        reset_btn.setFixedWidth(240)
        card._content_layout.addWidget(reset_btn)

        self._i18n_buttons.append((replay_btn, "settings.tutorial.replay_button"))
        self._i18n_buttons.append((reset_btn, "settings.tutorial.reset_all_button"))

    def _on_replay_tour(self) -> None:
        """Handle replay tour button click."""
        from ui.copilot import tour_tracker
        tour_tracker.clear_tour_completed("app_overview")
        # Publish event so MainWindow picks it up
        EventBus.publish(TOUR_REPLAY_REQUESTED, {"workflow_id": "app_overview"})
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            t("settings.tutorial.replay_title"),
            t("settings.tutorial.replay_message"),
        )

    def _on_reset_all_tours(self) -> None:
        """Handle reset all tours button."""
        from ui.copilot import tour_tracker
        tour_tracker.clear_all_tours()
        EventBus.publish(TOUR_REPLAY_REQUESTED, {"workflow_id": "all"})
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            t("settings.tutorial.reset_title"),
            t("settings.tutorial.reset_message"),
        )

    def _add_ocr_field(self, card, label: str, value: str):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SP["2"])
        lbl = QLabel(label)
        lbl.setProperty("fontRole", "small")
        lbl.setFixedWidth(200)
        entry = StyledLineEdit(text=value)
        entry.setEchoMode(QLineEdit.EchoMode.Password)
        row_layout.addWidget(lbl)
        row_layout.addWidget(entry, 1)
        card.layout().addWidget(row)
        return entry
