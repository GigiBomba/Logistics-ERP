"""Tests for the SettingsFieldsMixin — form section builders.

Since SettingsFieldsMixin is intended as a mixin for QtSettingsView, we
construct a minimal QWidget subclass that inherits the mixin and provides
the attributes it expects (``_scroll``, ``prefs``, ``db``, etc.).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.widgets import ScrollableFormContainer, StyledComboBox, StyledLineEdit


# =========================================================================
#  Test helper — MixinHost
# =========================================================================


class _SettingsFieldsHostBase(QWidget):
    """Base that provides the attributes SettingsFieldsMixin expects.

    Subclassed below with the mixin mixed in so that the MRO resolves
    correctly: ``_SettingsFieldsHost -> SettingsFieldsMixin -> QWidget -> object``.
    """

    def __init__(self, prefs=None, db=None):
        super().__init__()
        self.db = db or MagicMock()
        self.prefs = prefs or MagicMock()
        self._api_client = MagicMock()

        # Attributes the mixin relies on
        self._scroll = ScrollableFormContainer(self)
        self._section_headings: dict[str, QLabel] = {}
        self._i18n_labels: list[tuple[QLabel, str]] = []
        self._i18n_buttons: list[tuple] = []
        self.company_inputs: dict[str, StyledLineEdit] = {}
        self.branding_inputs: dict[str, StyledLineEdit] = {}
        self.smtp_inputs: dict[str, StyledLineEdit] = {}
        self._tracking_rows: dict[str, tuple[QWidget, StyledLineEdit]] = {}
        self._lang_codes: list[str] = []
        self._lang_combo: StyledComboBox | None = None
        self._currency_combo: StyledComboBox | None = None
        self._theme_combo: StyledComboBox | None = None
        self._tracking_platform_combo: StyledComboBox | None = None
        self._tracking_test_label: QLabel | None = None
        self._brand_color_swatch: QFrame | None = None

        # Build the host layout
        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll)


# Build the final host class with the mixin mixed in.
# We do this at module level so MRO is clean.
from ui.views.settings_view.settings_fields import SettingsFieldsMixin  # noqa: E402


class _SettingsFieldsHost(SettingsFieldsMixin, _SettingsFieldsHostBase):
    """Minimal QWidget that inherits SettingsFieldsMixin for testing."""

    def __init__(self, prefs=None, db=None):
        super().__init__(prefs=prefs, db=db)
        # The mixin methods are now available via MRO.
        # Override _browse_file / _pick_brand_color so they are no-ops.
        self._browse_file = MagicMock()
        self._pick_brand_color = MagicMock()

        # Stub methods required by section builders that reference
        # QtSettingsView methods not defined on the mixin itself.
        self._test_smtp = MagicMock()
        self._view_email_logs = MagicMock()


# =========================================================================
#  Fixtures
# =========================================================================


@pytest.fixture
def prefs():
    """Return a MagicMock simulating PreferencesManager."""
    p = MagicMock()
    p.get_available_languages.return_value = ["en", "ro", "de"]
    p.get_language.return_value = "en"
    p.get_language_display_name.return_value = "English"
    p.get_supported_currencies.return_value = ["EUR", "RON", "USD"]
    p.get_currency.return_value = "EUR"
    # Return the default when provided, else empty string
    p.get_setting.side_effect = lambda *args: args[1] if len(args) > 1 else ""
    p.get_settings.return_value = {}
    return p


@pytest.fixture
def settings_host(qtbot, prefs):
    """Create a _SettingsFieldsHost with mocked prefs."""
    host = _SettingsFieldsHost(prefs=prefs)
    qtbot.addWidget(host)
    yield host


# =========================================================================
#  Tests — Section card helpers
# =========================================================================


class TestSettingsFieldsHelpers:
    """Tests for _section_card and _add_labeled_field."""

    def test_section_card_returns_qframe(self, settings_host):
        """_section_card builds a Card/QFrame with content layout."""
        card = settings_host._section_card("settings.section_company")
        assert isinstance(card, QFrame)
        assert hasattr(card, "_content_layout")
        assert hasattr(card, "_content_widget")

    def test_section_card_stores_heading(self, settings_host):
        """Section heading is tracked in _section_headings."""
        settings_host._section_card("settings.section_company")
        assert "settings.section_company" in settings_host._section_headings
        assert settings_host._section_headings["settings.section_company"] is not None

    def test_add_labeled_field_adds_widget(self, settings_host):
        """_add_labeled_field appends a container to the card."""
        card = settings_host._section_card("settings.section_company")
        entry = StyledLineEdit()
        container = settings_host._add_labeled_field(card, "settings.field_company_name", entry)
        assert isinstance(container, QWidget)

    def test_add_labeled_field_tracks_i18n(self, settings_host):
        """_add_labeled_field registers the label for i18n updates."""
        card = settings_host._section_card("settings.section_company")
        entry = StyledLineEdit()
        settings_host._add_labeled_field(card, "settings.field_company_name", entry)
        assert len(settings_host._i18n_labels) >= 1
        label, key = settings_host._i18n_labels[-1]
        assert key == "settings.field_company_name"

    def test_add_labeled_field_with_helper_text(self, settings_host):
        """Helper text appears when provided."""
        card = settings_host._section_card("settings.section_company")
        entry = StyledLineEdit()
        container = settings_host._add_labeled_field(
            card, "settings.field_company_name", entry, "Helps",
        )
        # Find the helper label inside the container
        labels = container.findChildren(QLabel)
        helper_found = any("Helps" in lbl.text() for lbl in labels)
        assert helper_found

    def test_section_card_added_to_scroll(self, settings_host):
        """Card widget is added to the scroll container."""
        card = settings_host._section_card("settings.section_company")
        # The card should be in the scroll's content layout
        assert card.parent() is not None


# =========================================================================
#  Tests — Section: Company
# =========================================================================


class TestSettingsSectionCompany:
    """Tests for _build_section_company."""

    def test_company_section_builds(self, settings_host):
        """_build_section_company creates company inputs."""
        settings_host._build_section_company()
        assert len(settings_host.company_inputs) >= 6
        for key in ("company_name", "cui", "reg_number", "address", "phone", "email"):
            assert key in settings_host.company_inputs

    def test_company_inputs_are_styledlineedit(self, settings_host):
        """Each company input is a StyledLineEdit."""
        settings_host._build_section_company()
        for key, entry in settings_host.company_inputs.items():
            assert isinstance(entry, StyledLineEdit), f"{key} is not StyledLineEdit"


# =========================================================================
#  Tests — Section: Branding
# =========================================================================


class TestSettingsSectionBranding:
    """Tests for _build_section_branding."""

    def test_branding_section_builds(self, settings_host):
        """_build_section_branding creates branding inputs."""
        settings_host._build_section_branding()
        assert "logo_path" in settings_host.branding_inputs
        assert "company_color" in settings_host.branding_inputs
        assert "signature_path" in settings_host.branding_inputs
        assert "stamp_path" in settings_host.branding_inputs

    def test_branding_color_swatch_created(self, settings_host):
        """Brand colour swatch QFrame is stored."""
        settings_host._build_section_branding()
        assert settings_host._brand_color_swatch is not None
        assert isinstance(settings_host._brand_color_swatch, QFrame)

    def test_branding_inputs_are_styledlineedit(self, settings_host):
        """Each branding input is a StyledLineEdit."""
        settings_host._build_section_branding()
        for key, entry in settings_host.branding_inputs.items():
            assert isinstance(entry, StyledLineEdit), f"{key} is not StyledLineEdit"


# =========================================================================
#  Tests — Section: Preferences
# =========================================================================


class TestSettingsSectionPreferences:
    """Tests for _build_section_preferences."""

    def test_preferences_section_builds(self, settings_host):
        """_build_section_preferences creates combos."""
        settings_host._build_section_preferences()
        assert settings_host._lang_combo is not None
        assert settings_host._currency_combo is not None
        assert settings_host._theme_combo is not None

    def test_language_combo_populated(self, settings_host, prefs):
        """Language combo is populated from prefs."""
        settings_host._build_section_preferences()
        assert settings_host._lang_combo.count() >= 3

    def test_currency_combo_populated(self, settings_host, prefs):
        """Currency combo is populated from prefs."""
        settings_host._build_section_preferences()
        assert settings_host._currency_combo.count() >= 3

    def test_language_change_handler(self, settings_host, prefs):
        """_on_lang_combo_changed calls prefs.set_language when index valid."""
        settings_host._build_section_preferences()
        settings_host._lang_combo.setCurrentIndex(0)
        settings_host._on_lang_combo_changed(settings_host._lang_combo.currentText())
        assert prefs.set_language.called

    def test_currency_change_handler(self, settings_host, prefs):
        """_on_currency_combo_changed calls prefs.set_currency."""
        settings_host._build_section_preferences()
        settings_host._currency_combo.setCurrentIndex(0)
        settings_host._on_currency_combo_changed(settings_host._currency_combo.currentText())
        prefs.set_currency.assert_called()

    def test_build_lang_display_list(self, settings_host, prefs):
        """_build_lang_display_list returns formatted language strings."""
        settings_host._build_section_preferences()
        display = settings_host._build_lang_display_list()
        assert len(display) >= 3
        assert all("(" in d for d in display)

    def test_rebuild_preference_menus(self, settings_host, prefs):
        """_rebuild_preference_menus refreshes combos without crash."""
        settings_host._build_section_preferences()
        settings_host._rebuild_preference_menus()
        assert settings_host._lang_combo.count() >= 3


# =========================================================================
#  Tests — Section: E-mail
# =========================================================================


class TestSettingsSectionEmail:
    """Tests for _build_section_email."""

    def test_email_section_builds(self, settings_host):
        """_build_section_email creates SMTP inputs."""
        settings_host._build_section_email()
        assert len(settings_host.smtp_inputs) >= 5
        for key in ("smtp_server", "smtp_port", "smtp_user", "smtp_password",
                     "alert_email_recipients"):
            assert key in settings_host.smtp_inputs

    def test_smtp_password_masked(self, settings_host):
        """Password field uses EchoMode.Password."""
        from PySide6.QtWidgets import QLineEdit

        settings_host._build_section_email()
        pwd_entry = settings_host.smtp_inputs["smtp_password"]
        assert pwd_entry.echoMode() == QLineEdit.EchoMode.Password

    def test_smtp_test_and_logs_buttons(self, settings_host):
        """Email section has test and logs buttons."""
        settings_host._build_section_email()
        btn_keys = [key for _, key in settings_host._i18n_buttons]
        assert "settings.test_connection" in btn_keys
        assert "settings.email_logs" in btn_keys


# =========================================================================
#  Tests — Section: Tracking
# =========================================================================


class TestSettingsSectionTracking:
    """Tests for _build_section_tracking."""

    def test_tracking_section_builds(self, settings_host):
        """_build_section_tracking creates platform combo and field rows."""
        settings_host._build_section_tracking()
        assert settings_host._tracking_platform_combo is not None
        assert settings_host._tracking_test_label is not None
        assert len(settings_host._tracking_rows) == 4

    def test_tracking_platform_combo_populated(self, settings_host):
        """Platform combo has multiple entries."""
        settings_host._build_section_tracking()
        assert settings_host._tracking_platform_combo.count() >= 4

    def test_tracking_platform_change_hides_fields(self, settings_host):
        """Selecting 'not configured' hides all tracking fields."""
        settings_host._build_section_tracking()
        settings_host._tracking_platform_combo.setCurrentIndex(0)
        text = settings_host._tracking_platform_combo.currentText()
        settings_host._on_tracking_platform_changed(text)
        for key, (row_widget, _) in settings_host._tracking_rows.items():
            assert row_widget.isVisible() is False, f"{key} should be hidden"

    def test_tracking_test_not_configured(self, settings_host):
        """_test_tracking_connection shows incomplete when not configured."""
        settings_host._build_section_tracking()
        settings_host._tracking_platform_combo.setCurrentIndex(0)
        settings_host._test_tracking_connection()
        label = settings_host._tracking_test_label
        assert label is not None
        assert "incomplete" in label.text() or "\u2717" in label.text()

    def test_build_tracking_platform_values(self, settings_host):
        """_build_tracking_platform_values returns expected list."""
        values = settings_host._build_tracking_platform_values()
        assert len(values) >= 5
        for name in ("Frotcom", "Traccar", "Wialon", "Navixy", "Generic"):
            assert any(name in v for v in values), f"{name} not in platform values"


# =========================================================================
#  Tests — Section: Maintenance
# =========================================================================


class TestSettingsSectionMaintenance:
    """Tests for _build_section_maintenance."""

    def test_maintenance_section_builds(self, settings_host):
        """_build_section_maintenance creates threshold entries."""
        settings_host._build_section_maintenance()
        assert settings_host._alert_days_ahead_entry is not None
        assert settings_host._tacho_warning_entry is not None
        assert settings_host._tacho_critical_entry is not None

    def test_maintenance_entries_are_styledlineedit(self, settings_host):
        """Each maintenance entry is a StyledLineEdit."""
        settings_host._build_section_maintenance()
        for attr in ("_alert_days_ahead_entry", "_tacho_warning_entry", "_tacho_critical_entry"):
            entry = getattr(settings_host, attr, None)
            assert isinstance(entry, StyledLineEdit), f"{attr} is not StyledLineEdit"


# =========================================================================
#  Tests — Section: Automation
# =========================================================================


class TestSettingsSectionAutomation:
    """Tests for _build_section_automation."""

    def test_automation_section_builds(self, settings_host):
        """_build_section_automation creates automation inputs."""
        settings_host._build_section_automation()
        assert settings_host._automation_company_entry is not None
        assert settings_host._automation_subject_entry is not None
        assert settings_host._automation_body_edit is not None

    def test_automation_ocr_fields_exist(self, settings_host):
        """OCR credential inputs are created."""
        settings_host._build_section_automation()
        assert hasattr(settings_host, "_ocr_google_key")
        assert hasattr(settings_host, "_ocr_azure_endpoint")
        assert hasattr(settings_host, "_ocr_azure_key")

    def test_automation_has_gpu_checkbox(self, settings_host):
        """GPU toggle checkbox is created."""
        settings_host._build_section_automation()
        assert hasattr(settings_host, "_ocr_gpu_check")

    def test_automation_has_ai_section(self, settings_host):
        """AI Vision fallback fields are created."""
        settings_host._build_section_automation()
        assert hasattr(settings_host, "_ai_api_mode")
        assert hasattr(settings_host, "_ai_endpoint")
        assert hasattr(settings_host, "_ai_model")
        assert hasattr(settings_host, "_ai_timeout")

    def test_automation_email_importer_fields(self, settings_host):
        """Email importer fields are created."""
        settings_host._build_section_automation()
        assert hasattr(settings_host, "_email_importer_enabled")
        assert hasattr(settings_host, "_email_importer_host")
        assert hasattr(settings_host, "_email_importer_port")
        assert hasattr(settings_host, "_email_importer_user")

    def test_automation_folder_watcher_fields(self, settings_host):
        """Folder watcher fields are created."""
        settings_host._build_section_automation()
        assert hasattr(settings_host, "_fw_enabled")
        assert hasattr(settings_host, "_fw_path")
        assert hasattr(settings_host, "_fw_interval")
        assert hasattr(settings_host, "_fw_recursive")
        assert hasattr(settings_host, "_fw_delete")

    def test_add_ocr_field_returns_entry(self, settings_host):
        """_add_ocr_field returns a StyledLineEdit with Password echo."""
        from PySide6.QtWidgets import QLineEdit

        settings_host._build_section_automation()
        card = settings_host._section_card("settings.section_automation")
        entry = settings_host._add_ocr_field(card, "Test Field", "test_value")
        assert isinstance(entry, StyledLineEdit)
        assert entry.echoMode() == QLineEdit.EchoMode.Password
        assert entry.text() == "test_value"


# =========================================================================
#  Tests — Rebuild helpers
# =========================================================================


class TestSettingsRebuild:
    """Tests for _rebuild_preference_menus and _rebuild_tracking_platform_menu."""

    def test_rebuild_tracking_platform_menu(self, settings_host):
        """_rebuild_tracking_platform_menu refreshes without crash."""
        settings_host._build_section_tracking()
        settings_host._rebuild_tracking_platform_menu()
        assert settings_host._tracking_platform_combo.count() >= 4

    def test_rebuild_preferences_after_language_change(self, settings_host, prefs):
        """Both preference menus rebuild after language change."""
        settings_host._build_section_preferences()
        settings_host._build_section_tracking()
        settings_host._rebuild_preference_menus()
        settings_host._rebuild_tracking_platform_menu()
        assert settings_host._lang_combo.count() >= 3
        assert settings_host._tracking_platform_combo.count() >= 4


# =========================================================================
#  Tests — Preference change handlers
# =========================================================================


class TestSettingsHandlers:
    """Tests for theme change handler."""

    def test_theme_combo_change_with_app(self, settings_host):
        """_on_theme_combo_changed does not crash when QApp exists."""
        from PySide6.QtWidgets import QApplication

        settings_host._build_section_preferences()
        app = QApplication.instance()
        if app is not None:
            settings_host._theme_combo.setCurrentIndex(0)
            settings_host._on_theme_combo_changed(settings_host._theme_combo.currentText())
            # Should not crash

    def test_theme_combo_change_no_app(self, settings_host, monkeypatch):
        """_on_theme_combo_changed handles missing QApplication gracefully."""
        import PySide6.QtWidgets as qtw

        settings_host._build_section_preferences()

        monkeypatch.setattr(qtw.QApplication, "instance", lambda: None)
        settings_host._theme_combo.setCurrentIndex(0)
        settings_host._on_theme_combo_changed(settings_host._theme_combo.currentText())
        # Should not crash
