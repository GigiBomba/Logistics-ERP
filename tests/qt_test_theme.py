"""Tests for the PySide6 theme engine and QSS generation."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ui.theme import COLORS, FONTS, S
from ui.qt_theme import QtTheme
from ui.qt_styles import Theme


class TestThemeTokens:
    """Verify that the existing design-token dictionaries remain intact."""

    def test_color_tokens_exist(self):
        required = [
            "bg_base", "bg_surface", "bg_elevated", "bg_input",
            "border", "border_hover", "border_focus",
            "accent", "accent_hover", "accent_dim", "accent_text",
            "success", "warning", "danger", "info",
            "text_primary", "text_secondary", "text_muted",
        ]
        for key in required:
            assert key in COLORS, f"Missing color token: {key}"
            assert COLORS[key].startswith("#"), f"Color {key} is not a hex value"

    def test_font_tokens_exist(self):
        required = [
            "display", "h1", "h2", "h3", "body", "body_bold",
            "small", "label", "mono", "mono_lg", "mono_xl",
        ]
        for key in required:
            assert key in FONTS, f"Missing font token: {key}"
            assert isinstance(FONTS[key], tuple), f"Font {key} is not a tuple"

    def test_spacing_tokens_exist(self):
        for key in ("1", "2", "3", "4", "5", "6", "8", "10", "12"):
            assert key in S, f"Missing spacing token: {key}"
            assert isinstance(S[key], int), f"Spacing {key} is not an integer"


class TestQssGeneration:
    """Verify that the global QSS string is produced and targets core widgets."""

    def test_qss_is_non_empty(self, qapp):
        qss = QtTheme.qss()
        assert qss
        assert len(qss) > 1000

    def test_qss_contains_base_colors(self, qapp):
        qss = QtTheme.qss()
        assert COLORS["bg_base"] in qss
        assert COLORS["bg_surface"] in qss
        assert COLORS["accent"] in qss
        assert COLORS["text_primary"] in qss
        assert COLORS["border"] in qss

    def test_qss_contains_font_families(self, qapp):
        qss = QtTheme.qss()
        assert "IBM Plex Sans" in qss
        assert "Impact" in qss
        assert "IBM Plex Mono" in qss

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
        assert 'fontRole="hero"' in qss
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
    """Verify the compatibility shim matches the old Theme API."""

    def test_constants_match_colors(self):
        assert Theme.BG == COLORS["bg_base"]
        assert Theme.SURFACE == COLORS["bg_surface"]
        assert Theme.SURFACE2 == COLORS["bg_elevated"]
        assert Theme.INPUT_BG == COLORS["bg_input"]
        assert Theme.TEXT == COLORS["text_primary"]
        assert Theme.MUTED == COLORS["text_secondary"]
        assert Theme.ACCENT == COLORS["accent"]
        assert Theme.ACCENT_HOVER == COLORS["accent_hover"]
        assert Theme.ACCENT_SUCCESS == COLORS["success"]
        assert Theme.BORDER == COLORS["border"]
        assert Theme.BORDER_FOCUS == COLORS["border_focus"]
        assert Theme.DANGER == COLORS["danger"]
        assert Theme.WARNING == COLORS["warning"]
        assert Theme.SUCCESS == COLORS["success"]
        assert Theme.CARD_BG == COLORS["bg_surface"]

    def test_font_strings(self):
        assert "IBM Plex Sans" in Theme.FONT_MAIN
        assert "IBM Plex Sans" in Theme.FONT_BOLD
        assert "IBM Plex Sans" in Theme.FONT_TITLE

    def test_apply_runs(self, qapp):
        Theme.apply()
        assert Theme._applied
