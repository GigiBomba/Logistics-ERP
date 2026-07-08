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
