"""Tests for the style definitions."""
from __future__ import annotations
import pytest

class TestStyles:
    def test_theme_class_exists(self):
        from ui.styles import Theme
        assert hasattr(Theme, 'ACCENT_SUCCESS') or hasattr(Theme, 'ACCENT')

    def test_theme_colors_are_strings(self):
        from ui.styles import Theme
        if hasattr(Theme, 'ACCENT'):
            assert isinstance(Theme.ACCENT, str)

    def test_theme_importable(self):
        from ui.styles import Theme
        assert Theme is not None
