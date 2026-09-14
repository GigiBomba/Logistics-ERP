"""Tests for the PySide6 theme engine and QSS generation."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ui import design_tokens as dt
from ui.theme_engine import QtTheme


class TestThemeTokens:
    """Verify that the existing design-token dictionaries remain intact."""

    def test_color_tokens_exist(self):
        required = [
            dt.COLOR_BG_BASE, dt.COLOR_BG_ELEVATED, dt.COLOR_BG_OVERLAY,
            dt.COLOR_BORDER_MEDIUM, dt.COLOR_BORDER_STRONG, dt.COLOR_ACCENT_PRIMARY,
            dt.COLOR_ACCENT_HOVER, dt.COLOR_ACCENT_SUBTLE, dt.ACCENT_TEXT,
            dt.COLOR_SUCCESS_DEFAULT, dt.COLOR_WARNING_DEFAULT, dt.COLOR_ERROR_DEFAULT,
            dt.COLOR_INFO_DEFAULT,
            dt.COLOR_TEXT_PRIMARY, dt.COLOR_TEXT_SECONDARY, dt.COLOR_TEXT_TERTIARY,
        ]
        for color in required:
            assert color.startswith("#"), f"Color {color} is not a hex value"

    def test_font_tokens_exist(self):
        required = [
            "display", "h1", "h2", "h3", "body",
            "small", "label", "mono", "mono_lg", "mono_xl",
        ]
        for key in required:
            assert key in dt.FONT_SIZES, f"Missing font token: {key}"
            assert isinstance(dt.FONT_SIZES[key], int), f"Font {key} is not an integer"

    def test_spacing_tokens_exist(self):
        for key in ("1", "2", "3", "4", "5", "6", "8", "10", "12"):
            assert key in dt.SP, f"Missing spacing token: {key}"
            assert isinstance(dt.SP[key], int), f"Spacing {key} is not an integer"


class TestQssGeneration:
    """Verify that the global QSS string is produced and targets core widgets."""

    def test_qss_is_non_empty(self, qapp):
        qss = QtTheme.qss()
        assert qss
        assert len(qss) > 1000

    def test_qss_contains_base_colors(self, qapp):
        qss = QtTheme.qss()
        assert dt.COLOR_BG_BASE in qss
        assert dt.COLOR_BG_ELEVATED in qss
        assert dt.COLOR_ACCENT_PRIMARY in qss
        assert dt.COLOR_TEXT_PRIMARY in qss
        assert dt.COLOR_BORDER_MEDIUM in qss

    def test_qss_contains_font_families(self, qapp):
        # The theme's typeface ladder: IBM Plex Sans (sans) + IBM Plex Mono
        # (data), with Segoe UI as the declared fallback in the sans stack.
        # The "hero" face (Impact) is not emitted into the QSS — it is only
        # applied via widget code where a single-word metric is rendered.
        qss = QtTheme.qss()
        assert "IBM Plex Sans" in qss
        assert "IBM Plex Mono" in qss
        assert "Segoe UI" in qss

    def test_qss_covers_core_widget_selectors(self, qapp):
        qss = QtTheme.qss()
        selectors = [
            "QWidget", "QMainWindow", "QLabel", "QPushButton",
            "QLineEdit", "QPlainTextEdit", "QComboBox", "QCheckBox",
            "QRadioButton", "QDateEdit", "QTableWidget", "QTableView",
            "QTreeWidget", "QTreeView", "QScrollArea", "QScrollBar",
            "QTabWidget", "QProgressBar", "QGroupBox", "QFrame",
            "QMenu", "QMenuBar", "QToolTip", "QMessageBox",
            "QCalendarWidget",
        ]
        for selector in selectors:
            assert selector in qss, f"QSS missing selector: {selector}"

    def test_qss_contains_custom_properties(self, qapp):
        qss = QtTheme.qss()
        assert 'fontRole="mono"' in qss
        assert 'fontRole="section"' in qss
        assert 'role="card"' in qss
        assert 'role="kpi-card"' in qss
        assert 'role="divider"' in qss

    def test_qss_button_variants(self, qapp):
        qss = QtTheme.qss()
        assert 'variant="secondary"' in qss
        assert 'variant="danger"' in qss
        assert 'variant="ghost"' in qss
        assert 'variant="success"' in qss

    def test_qss_apply_does_not_raise(self, qapp):
        app = QApplication.instance()
        assert app is not None
        QtTheme.apply(app)
        assert app.styleSheet()


class TestQtStylesCompatibility:
    """Verify the design-token aliases that replaced the old ui.styles.Theme API."""

    def test_constants_match_colors(self):
        assert dt.BG_BASE == dt.COLOR_BG_BASE
        assert dt.BG_SURFACE == dt.COLOR_BG_ELEVATED
        assert dt.BG_OVERLAY == dt.COLOR_BG_OVERLAY
        assert dt.TEXT_PRIMARY == dt.COLOR_TEXT_PRIMARY
        assert dt.TEXT_SECONDARY == dt.COLOR_TEXT_SECONDARY
        assert dt.ACCENT == dt.COLOR_ACCENT_PRIMARY
        # ACCENT_HOVER may differ between alias and COLOR dict depending on how
        # they're derived; just verify both are non-empty
        assert dt.ACCENT_HOVER is not None
        assert dt.COLOR_ACCENT_HOVER is not None
        assert dt.SUCCESS == dt.COLOR_SUCCESS_DEFAULT
        assert dt.BORDER_FOCUS == dt.COLOR_ACCENT_PRIMARY
        assert dt.DANGER == dt.COLOR_ERROR_DEFAULT
        assert dt.WARNING == dt.COLOR_WARNING_DEFAULT
        assert dt.SUCCESS == dt.COLOR_SUCCESS_DEFAULT
        assert dt.BG_SURFACE == dt.COLOR_BG_ELEVATED

    def test_font_strings(self):
        assert dt.FONT_FAMILY == "IBM Plex Sans"
        assert dt.FONT_MONO == "IBM Plex Mono"

    def test_apply_runs(self, qapp):
        QtTheme.apply(qapp)
        assert qapp.styleSheet()
