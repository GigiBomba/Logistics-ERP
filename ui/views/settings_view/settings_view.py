"""PySide6 settings view — main class.

Split from ``settings_view.py``.  The form section builders live in
``settings_fields.py``.
"""

from __future__ import annotations

import contextlib
import logging

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from repositories.automail_repository import AutoMailRepository
from client.auth_manager import is_admin
from services.i18n import t
from ui.base_view import BaseView
from services.invoicing.config_manager import load_company_config, save_company_config
from services.operations.event_bus import SETTINGS_UPDATED, EventBus
from services.operations.notification_center import NotificationCenter
from services.preferences import PreferencesManager
from ui.components import Btn, Divider, Label, PageTitle, SectionTitle
from ui.design_tokens import SP
from ui.theme import S
from ui.widgets import (
    ActionButton,
    ScrollableFormContainer,
    StyledComboBox,
    StyledLineEdit,
)

from ui.views.settings_view.settings_fields import DEFAULT_BRAND_COLOR, SettingsFieldsMixin

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  QtSettingsView
# ══════════════════════════════════════════════════════════════════════════════


class QtSettingsView(SettingsFieldsMixin, BaseView):
    """Settings page with form fields organized in section cards.

    Designed for embedded use in a QStackedWidget.  Provides company
    configuration, branding, user preferences (language/currency/theme),
    SMTP e-mail setup, fleet tracking, and maintenance threshold fields.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs: PreferencesManager | None = None,
        ops=None,
        automail_repo=None,
        api_client=None,
    ):
        super().__init__(parent)
        self.db = db
        self._api_client = api_client
        self.prefs = prefs or PreferencesManager(db)
        self.ops = ops
        if self._api_client is not None:
            self._automail_repo = None
        else:
            self._automail_repo = automail_repo if automail_repo is not None else AutoMailRepository(db)
        # ── i18n tracking ────────────────────────────────────────────────
        self._i18n_labels: list[tuple[QLabel, str]] = []
        self._i18n_buttons: list[tuple[ActionButton, str]] = []
        self._section_headings: dict[str, QLabel] = {}
        self._language_callback = self._on_language_changed

        # ── Brand colour swatch reference ────────────────────────────────
        self._brand_color_swatch: QFrame | None = None

        # ── Input maps ───────────────────────────────────────────────────
        self.company_inputs: dict[str, StyledLineEdit] = {}
        self.branding_inputs: dict[str, StyledLineEdit] = {}
        self.smtp_inputs: dict[str, StyledLineEdit] = {}
        self._tracking_rows: dict[str, tuple[QWidget, StyledLineEdit]] = {}

        # ── Preference controls ──────────────────────────────────────────
        self._lang_codes: list[str] = []
        self._lang_combo: StyledComboBox | None = None
        self._currency_combo: StyledComboBox | None = None
        self._theme_combo: StyledComboBox | None = None
        self._tracking_platform_combo: StyledComboBox | None = None
        self._tracking_test_label: QLabel | None = None

        # ── Maintenance entries ──────────────────────────────────────────
        self._alert_days_ahead_entry: StyledLineEdit | None = None
        self._tacho_warning_entry: StyledLineEdit | None = None
        self._tacho_critical_entry: StyledLineEdit | None = None

        # ── Build UI ─────────────────────────────────────────────────────
        self._build_ui()
        self._register_i18n(self._language_callback)

    # ──────────────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    def wakeup(self) -> None:
        """Called when the view becomes visible (e.g. tab switch)."""
        pass

    def handle_nav_data(self, data: dict) -> None:
        """Accept deep-link data, e.g. ``{"scroll_to": "tracking"}``."""
        section = data.get("scroll_to")
        if section == "tracking" and hasattr(self, "_scroll"):
            self._scroll_to_section("tracking")

    def _scroll_to_section(self, section: str) -> None:
        """Scroll the form to *section*, deferred to after layout."""
        object_names = {
            "tracking": "settings_section_tracking",
        }
        obj_name = object_names.get(section)
        if obj_name is None:
            return

        def _do_scroll() -> None:
            widget = getattr(self, "_scroll", None)
            if widget is None:
                return
            target = widget.findChild(QFrame, obj_name)
            if target is not None:
                widget.ensureWidgetVisible(target, xMargin=0, yMargin=20)

        QTimer.singleShot(50, _do_scroll)

    def shutdown(self) -> None:
        """Clean up resources when the view is destroyed / hidden."""
        super().shutdown()

    # ──────────────────────────────────────────────────────────────────────────
    #  i18n
    # ──────────────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        self.refresh_translations()

    def refresh_translations(self) -> None:
        """Update all visible text to the current language."""
        for label, key in self._i18n_labels:
            with contextlib.suppress(Exception):
                label.setText(t(key))
        for button, key in self._i18n_buttons:
            with contextlib.suppress(Exception):
                button.setText(t(key))
        for text_key, lbl in self._section_headings.items():
            with contextlib.suppress(Exception):
                lbl.setText(t(text_key))
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
        if is_admin():
            self._build_section_automation()

        # Bottom save bar
        self._build_save_bar(layout)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setObjectName("card")
        header.setFixedHeight(72)
        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(SP["10"], SP["4"], SP["10"], SP["4"])

        title = PageTitle(header, t("settings.title"))
        hdr_layout.addWidget(title)

        subtitle = Label(header, t("settings.subtitle"), role="secondary")
        hdr_layout.addWidget(subtitle)

        parent_layout.addWidget(header)

    # ──────────────────────────────────────────────────────────────────────────
    #  Save bar
    # ──────────────────────────────────────────────────────────────────────────

    def _build_save_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setObjectName("card")
        bar.setFixedHeight(64)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(SP["10"], SP["3"], SP["10"], SP["3"])

        reset_btn = Btn(
            bar, t("settings.reset"),
            command=self._reset,
            variant="secondary",
        )
        bar_layout.addWidget(reset_btn)
        self._i18n_buttons.append((reset_btn, "settings.reset"))

        bar_layout.addStretch(1)

        save_btn = Btn(
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
        company_data: dict[str, str] = {
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

        # ── Cloud OCR ────────────────────────────────────────────────────
        for key, attr in [
            ("ocr_google_key", "_ocr_google_key"),
            ("ocr_google_project_id", "_ocr_google_project"),
            ("ocr_azure_endpoint", "_ocr_azure_endpoint"),
            ("ocr_azure_key", "_ocr_azure_key"),
            ("ocr_language_hints", "_ocr_language_hints"),
        ]:
            entry = getattr(self, attr, None)
            if entry is not None:
                self.prefs.save_setting(key, entry.text().strip())
        # Save PaddleOCR settings.
        if getattr(self, "_ocr_gpu_check", None) is not None:
            self.prefs.save_setting(
                "ocr_use_gpu", "1" if self._ocr_gpu_check.isChecked() else "0",
            )
        for key, attr in [
            ("ocr_det_limit_side_len", "_ocr_det_len"),
            ("ocr_rec_batch_num", "_ocr_rec_batch"),
        ]:
            entry = getattr(self, attr, None)
            if entry is not None:
                self.prefs.save_setting(key, entry.text().strip())
        # ── AI Vision (Gemma 3) ────────────────────────────────────────
        for key, attr in [
            ("qwen_api_mode", "_ai_api_mode"),
            ("qwen_endpoint", "_ai_endpoint"),
            ("qwen_model", "_ai_model"),
            ("qwen_max_pages", "_ai_max_pages"),
            ("qwen_rpm_limit", "_ai_rpm"),
            ("ai_confidence_threshold", "_ai_threshold"),
            ("qwen_timeout_s", "_ai_timeout"),
        ]:
            obj = getattr(self, attr, None)
            if obj is not None:
                if hasattr(obj, "currentText"):
                    val = obj.currentText()
                elif hasattr(obj, "value"):
                    val = str(obj.value())
                else:
                    val = obj.text().strip()
                self.prefs.save_setting(key, val)
        # Also update the runtime threshold in ocr_extractor.
        try:
            thresh_text = getattr(self, "_ai_threshold", None)
            if thresh_text is not None:
                val = float(thresh_text.text().strip())
                from services.document_automation.ocr_extractor import OcrExtractor
                OcrExtractor.LOCAL_CONFIDENCE_THRESHOLD = val
        except Exception:
            pass
        try:
            from services.document_automation.ai_fallback import init_from_db as ai_init
            ai_init(self.db)
        except Exception:
            pass

        # ── Email Importer ─────────────────────────────────────────────
        for key, attr in [
            ("email_importer_enabled", "_email_importer_enabled"),
            ("email_importer_host", "_email_importer_host"),
            ("email_importer_port", "_email_importer_port"),
            ("email_importer_user", "_email_importer_user"),
            ("email_importer_password", "_email_importer_password"),
            ("email_importer_interval", "_email_importer_interval"),
            ("email_importer_whitelist", "_email_importer_whitelist"),
            ("email_importer_delete", "_email_importer_delete"),
        ]:
            obj = getattr(self, attr, None)
            if obj is not None:
                val = obj.isChecked() if hasattr(obj, "isChecked") else obj.text().strip()
                val = "1" if val is True else ("0" if val is False else val)
                self.prefs.save_setting(key, str(val))

        # ── Folder Watcher ─────────────────────────────────────────────
        for key, attr in [
            ("folder_watcher_enabled", "_fw_enabled"),
            ("folder_watcher_path", "_fw_path"),
            ("folder_watcher_interval", "_fw_interval"),
            ("folder_watcher_recursive", "_fw_recursive"),
            ("folder_watcher_delete", "_fw_delete"),
        ]:
            obj = getattr(self, attr, None)
            if obj is not None:
                val = obj.isChecked() if hasattr(obj, "isChecked") else obj.text().strip()
                val = "1" if val is True else ("0" if val is False else val)
                self.prefs.save_setting(key, str(val))

        # Reload cloud OCR credentials from DB so they take effect immediately.
        try:
            from services.document_automation.cloud_ocr import init_from_db
            init_from_db(self.db)
        except Exception:
            pass

        # ── Document automation ──────────────────────────────────────
        if getattr(self, "_automation_company_entry", None) is not None:
            self.prefs.save_setting(
                "automation_company_name",
                self._automation_company_entry.text().strip(),
            )
        if getattr(self, "_automation_subject_entry", None) is not None:
            self.prefs.save_setting(
                "automation_email_subject_template",
                self._automation_subject_entry.text().strip(),
            )
        if getattr(self, "_automation_body_edit", None) is not None:
            self.prefs.save_setting(
                "automation_email_body_template",
                self._automation_body_edit.toPlainText().strip(),
            )

        # ── Ops refresh ─────────────────────────────────────────────────
        if self.ops is not None:
            with contextlib.suppress(Exception):
                self.ops._configure_smtp_from_db()

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
            t("signature.filter_images", default="Image files (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*.*)"),
        )
        if path:
            entry.setText(path)

    def _pick_brand_color(self, entry: StyledLineEdit, swatch: QFrame) -> None:
        initial = QColor(entry.text()) if entry.text() else QColor(DEFAULT_BRAND_COLOR)
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
        smtp_data: dict[str, str] = {
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
            rows = self._automail_repo.get_recent_email_logs(200)
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
