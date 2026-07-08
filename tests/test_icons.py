"""Tests for icon mappings."""
from __future__ import annotations
import pytest

class TestIcons:
    def test_module_importable(self):
        from ui import icons
        assert icons is not None

    def test_has_icon_mappings(self):
        from ui.icons import ICONS
        assert ICONS is not None

    def test_icons_is_iterable(self):
        from ui.icons import ICONS
        count = len(ICONS) if hasattr(ICONS, "__len__") else len(list(ICONS))
        assert count >= 0
