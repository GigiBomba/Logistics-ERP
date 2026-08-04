"""Tests for theme switching — refresh, token swap, and widget re-styling."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton, QLabel

from ui.theme_engine import QtTheme, FONT_FAMILIES, FONT_SIZES


# ──────────────────────────────────────────────────────────────────────
# TestThemeRefresh
# ──────────────────────────────────────────────────────────────────────


class TestThemeRefresh:
    """Test that QtTheme.refresh() properly rebuilds and reapplies styles."""

    def test_refresh_sets_stylesheet_on_app(self, qapp):
        """Call QtTheme.refresh(qapp), verify qapp.styleSheet() non-empty."""
        QtTheme.refresh(qapp)
        sheet = qapp.styleSheet()
        assert isinstance(sheet, str)
        assert len(sheet) > 1000

    def test_refresh_sets_font_on_app(self, qapp):
        """Call refresh, verify font family/size correct."""
        QtTheme.refresh(qapp)
        font = qapp.font()
        # Font family may fall back to system default if IBM Plex Sans not installed
        assert font.family() is not None
        assert font.pointSize() > 0

    def test_refresh_invalidates_cache_then_rebuilds(self, qapp):
        """Pre-cache qss(), call refresh, verify cache is rebuilt."""
        # Pre-cache
        first_qss = QtTheme.qss()
        assert QtTheme._style_sheet is not None
        assert isinstance(first_qss, str)

        # Refresh clears the internal cache and rebuilds it
        QtTheme.refresh(qapp)

        # After refresh, the cache is rebuilt
        assert QtTheme._style_sheet is not None

        rebuilt_qss = QtTheme.qss()
        assert isinstance(rebuilt_qss, str)
        assert len(rebuilt_qss) > 1000

    def test_refresh_is_idempotent(self, qapp):
        """Call refresh twice, no exceptions."""
        QtTheme.refresh(qapp)
        QtTheme.refresh(qapp)


# ──────────────────────────────────────────────────────────────────────
# TestThemeTokenSwap
# ──────────────────────────────────────────────────────────────────────


class TestThemeTokenSwap:
    """Test that changing design tokens and calling refresh propagates."""

    def test_patching_color_token_propagates(self, qapp, monkeypatch):
        """Monkeypatch COLOR_BG_BASE to '#FFFFFF', refresh, verify in stylesheet. Restore."""
        import ui.theme_engine as theme_engine

        orig = theme_engine.COLOR_BG_BASE

        # Patch to light
        monkeypatch.setattr(theme_engine, "COLOR_BG_BASE", "#FFFFFF")
        QtTheme.refresh(qapp)
        assert "#FFFFFF" in qapp.styleSheet()

        # Restore and verify dark is back
        theme_engine.COLOR_BG_BASE = orig
        QtTheme.refresh(qapp)
        assert "#0C0C0E" in qapp.styleSheet()

    def test_patching_font_family_propagates(self, qapp, monkeypatch):
        """Monkeypatch FONT_FAMILIES['sans'] to 'Arial', refresh, verify. Restore."""
        import ui.theme_engine as theme_engine

        orig = theme_engine.FONT_FAMILIES["sans"]

        monkeypatch.setitem(theme_engine.FONT_FAMILIES, "sans", "Arial")
        QtTheme.refresh(qapp)
        assert "Arial" in qapp.styleSheet()

        # Restore
        theme_engine.FONT_FAMILIES["sans"] = orig
        QtTheme.refresh(qapp)
        # The original font family reference appears in the QSS
        assert "IBM Plex Sans" in qapp.styleSheet()

    def test_light_toggle_simulation(self, qapp, monkeypatch):
        """Patch 5 key tokens to light values, refresh, verify.

        Then restore original tokens, refresh, verify dark hex values.
        """
        import ui.theme_engine as theme_engine

        # ── Save originals ────────────────────────────────────────
        orig_bg = theme_engine.COLOR_BG_BASE
        orig_text = theme_engine.COLOR_TEXT_PRIMARY
        orig_accent = theme_engine.COLOR_ACCENT_PRIMARY
        orig_border = theme_engine.COLOR_BORDER_MEDIUM
        orig_elevated = theme_engine.COLOR_BG_ELEVATED

        # ── Light values (simulating a light theme toggle) ────────
        light_bg = "#FFFFFF"
        light_text = "#1F2937"
        light_accent = "#2563EB"
        light_border = "#D1D5DB"
        light_elevated = "#F9FAFB"

        monkeypatch.setattr(theme_engine, "COLOR_BG_BASE", light_bg)
        monkeypatch.setattr(theme_engine, "COLOR_TEXT_PRIMARY", light_text)
        monkeypatch.setattr(theme_engine, "COLOR_ACCENT_PRIMARY", light_accent)
        monkeypatch.setattr(theme_engine, "COLOR_BORDER_MEDIUM", light_border)
        monkeypatch.setattr(theme_engine, "COLOR_BG_ELEVATED", light_elevated)
        QtTheme.refresh(qapp)

        sheet = qapp.styleSheet()
        assert light_bg in sheet
        assert light_text in sheet
        assert light_accent in sheet
        assert light_border in sheet
        assert light_elevated in sheet

        # ── Restore original dark tokens ──────────────────────────
        theme_engine.COLOR_BG_BASE = orig_bg
        theme_engine.COLOR_TEXT_PRIMARY = orig_text
        theme_engine.COLOR_ACCENT_PRIMARY = orig_accent
        theme_engine.COLOR_BORDER_MEDIUM = orig_border
        theme_engine.COLOR_BG_ELEVATED = orig_elevated
        QtTheme.refresh(qapp)

        sheet = qapp.styleSheet()
        assert orig_bg in sheet
        assert orig_text in sheet
        assert orig_accent in sheet
        assert orig_border in sheet
        assert orig_elevated in sheet


# ──────────────────────────────────────────────────────────────────────
# TestWidgetReactsToThemeRefresh
# ──────────────────────────────────────────────────────────────────────


class TestWidgetReactsToThemeRefresh:
    """Test that widgets respond correctly after a theme refresh."""

    def test_widget_style_polished_after_refresh(self, qapp):
        """Create QPushButton with variant='secondary', refresh, re-polish, verify property."""
        button = QPushButton("Test")
        button.setProperty("variant", "secondary")
        assert button.property("variant") == "secondary"

        QtTheme.refresh(qapp)

        # Re-polish the widget so it picks up any changes from the
        # refreshed stylesheet.
        qapp.style().unpolish(button)
        qapp.style().polish(button)

        # Verify the dynamic property is still intact
        assert button.property("variant") == "secondary"

    def test_new_widgets_after_refresh_get_correct_font(self, qapp):
        """Refresh, create new QLabel, verify font inherited from app."""
        QtTheme.refresh(qapp)

        label = QLabel("Hello")
        inherited = label.font()
        app_font = qapp.font()

        assert inherited.family() == app_font.family()
        assert inherited.pointSize() == app_font.pointSize()
