"""Tests for the style definitions (canonical sources).

``ui/styles.py`` (the legacy ``ui.styles.Theme`` compatibility shim) was deleted.
These tests verify the canonical sources that replaced it:
``ui.theme_engine`` (QSS theme manager) and ``ui.design_tokens`` (color tokens).
"""
from __future__ import annotations
import pytest

class TestStyles:
    def test_theme_class_exists(self):
        from ui.theme_engine import QtTheme
        assert hasattr(QtTheme, 'qss')

    def test_theme_colors_are_strings(self):
        from ui.design_tokens import COLOR_ACCENT_PRIMARY
        assert isinstance(COLOR_ACCENT_PRIMARY, str)

    def test_theme_importable(self):
        from ui.theme_engine import QtTheme
        assert QtTheme is not None