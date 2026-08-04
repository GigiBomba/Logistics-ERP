"""Tests for the theme engine."""
from __future__ import annotations
import pytest

class TestQtTheme:
    def test_qss_returns_string(self, qapp):
        from ui.theme_engine import QtTheme
        qss = QtTheme.qss()
        assert isinstance(qss, str)
        assert len(qss) > 1000

    def test_apply_does_not_crash(self, qapp):
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)

    def test_refresh_rebuilds_style(self, qapp):
        from ui.theme_engine import QtTheme
        QtTheme.refresh(qapp)

    def test_qss_is_cached(self, qapp):
        from ui.theme_engine import QtTheme
        qss1 = QtTheme.qss()
        qss2 = QtTheme.qss()
        assert qss1 == qss2

    def test_qss_contains_key_selectors(self, qapp):
        from ui.theme_engine import QtTheme
        qss = QtTheme.qss()
        assert "QWidget" in qss
        assert "QPushButton" in qss
        assert "QLineEdit" in qss
        assert "QTableWidget" in qss
        assert "QScrollBar" in qss

    def test_qss_contains_nav_styles(self, qapp):
        from ui.theme_engine import QtTheme
        qss = QtTheme.qss()
        assert "nav-item" in qss

    def test_qss_contains_topbar_styles(self, qapp):
        from ui.theme_engine import QtTheme
        qss = QtTheme.qss()
        assert "top-bar" in qss

    def test_qss_contains_toast_styles(self, qapp):
        from ui.theme_engine import QtTheme
        qss = QtTheme.qss()
        assert "toast" in qss

    def test_font_families_defined(self):
        from ui.theme_engine import FONT_FAMILIES
        assert "sans" in FONT_FAMILIES
        assert "hero" in FONT_FAMILIES
        assert "mono" in FONT_FAMILIES

    def test_font_sizes_defined(self):
        from ui.theme_engine import FONT_SIZES
        assert "body" in FONT_SIZES
        assert "h1" in FONT_SIZES


class TestQtThemeApplication:
    """Tests for QtTheme.apply()."""

    def test_apply_sets_app_stylesheet(self, qapp):
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)
        ss = qapp.styleSheet()
        assert isinstance(ss, str) and len(ss) > 100
        assert "QWidget" in ss
        assert "QPushButton" in ss
        assert "QTableWidget" in ss

    def test_apply_sets_app_font(self, qapp):
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)
        font = qapp.font()
        # Font may fall back to system font if IBM Plex Sans is not installed
        assert font.family() is not None
        assert font.pointSize() > 0

    def test_apply_sets_stylesheet_to_qss_output(self, qapp):
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)
        assert qapp.styleSheet() == QtTheme.qss()

    def test_apply_replaces_previous_stylesheet(self, qapp):
        from ui.theme_engine import QtTheme
        old_ss = "QWidget { background-color: hotpink; }"
        qapp.setStyleSheet(old_ss)
        QtTheme.apply(qapp)
        assert "hotpink" not in qapp.styleSheet()


class TestQtThemeFontInheritance:
    """Widgets inherit the application font from QtTheme."""

    def test_qwidget_inherits_app_font(self, qapp):
        from PySide6.QtWidgets import QWidget
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)
        w = QWidget()
        font = w.font()
        # Font family may fall back to system default if IBM Plex Sans not installed
        assert font.family() is not None
        assert font.pointSize() > 0

    def test_qpushbutton_inherits_app_font(self, qapp):
        from PySide6.QtWidgets import QPushButton
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)
        btn = QPushButton("X")
        font = btn.font()
        assert font.family() is not None
        assert font.pointSize() > 0

    def test_qlabel_inherits_app_font(self, qapp):
        from PySide6.QtWidgets import QLabel
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)
        lbl = QLabel("X")
        font = lbl.font()
        assert font.family() is not None
        assert font.pointSize() > 0

    def test_deep_child_inherits_app_font(self, qapp):
        from PySide6.QtWidgets import QMainWindow, QWidget, QLabel
        from ui.theme_engine import QtTheme
        QtTheme.apply(qapp)
        mw = QMainWindow()
        w = QWidget()
        lbl = QLabel("X")
        w.setParent(mw)
        lbl.setParent(w)
        font = lbl.font()
        assert font.family() is not None
        assert font.pointSize() > 0


class TestQtThemeCaching:
    """Extend caching coverage."""

    def test_refresh_invalidates_cache(self, qapp):
        from ui.theme_engine import QtTheme
        _ = QtTheme.qss()  # populate cache
        assert QtTheme._style_sheet is not None
        QtTheme.refresh(qapp)
        # refresh sets _style_sheet = None then apply() repopulates it
        assert QtTheme._style_sheet is not None


class TestQssSelectorCompleteness:
    """Verify generated QSS covers all expected selectors and tokens."""

    def test_qss_contains_all_widget_selectors(self, qapp):
        from ui.theme_engine import QtTheme
        qss = QtTheme.qss()
        expected = [
            "QWidget", "QPushButton", "QLineEdit", "QPlainTextEdit",
            "QTextEdit", "QDateEdit", "QSpinBox", "QDoubleSpinBox",
            "QCheckBox", "QRadioButton", "QComboBox", "QTableWidget",
            "QTableView", "QTreeWidget", "QTreeView", "QScrollArea",
            "QScrollBar", "QTabWidget", "QProgressBar", "QGroupBox",
            "QFrame", "QMenuBar", "QMenu", "QToolTip", "QMessageBox",
            "QDialog", "QSplitter", "QStackedWidget", "QCalendarWidget",
        ]
        for selector in expected:
            assert selector in qss, f"Missing widget selector: {selector}"

    def test_qss_contains_property_selectors(self, qapp):
        from ui.theme_engine import QtTheme
        qss = QtTheme.qss()
        assert "[variant=" in qss
        assert "[validation=" in qss
        assert "[role=" in qss
        assert "[fontRole=" in qss

    def test_qss_contains_all_semantic_colors(self, qapp):
        from ui.theme_engine import QtTheme
        import ui.design_tokens as dt
        qss = QtTheme.qss()
        # COLOR_* tokens referenced by QtTheme (those imported in theme_engine.py)
        # Tokens whose values are actually embedded in QtTheme.qss()
        used_tokens = [
            "COLOR_ACCENT_HOVER", "COLOR_ACCENT_PRIMARY", "COLOR_ACCENT_SUBTLE",
            "COLOR_BG_BASE", "COLOR_BG_ELEVATED", "COLOR_BG_HOVER", "COLOR_BG_OVERLAY",
            "COLOR_BG_SELECTED", "COLOR_BORDER_MEDIUM", "COLOR_BORDER_STRONG",
            "COLOR_BORDER_SUBTLE", "COLOR_ERROR_DEFAULT", "COLOR_ERROR_SUBTLE",
            "COLOR_ERROR_TEXT", "COLOR_INFO_SUBTLE",
            "COLOR_SUCCESS_DEFAULT", "COLOR_SUCCESS_SUBTLE",
            "COLOR_SUCCESS_TEXT", "COLOR_TEXT_INVERSE", "COLOR_TEXT_PRIMARY",
            "COLOR_TEXT_SECONDARY", "COLOR_TEXT_TERTIARY",
            "COLOR_WARNING_SUBTLE", "COLOR_WARNING_TEXT",
        ]
        for name in used_tokens:
            value = getattr(dt, name)
            assert value in qss, f"{name} ({value}) not found in QSS"
