"""Tests for the design token definitions."""
from __future__ import annotations
import pytest

class TestDesignTokens:
    def test_colors_are_strings(self):
        from ui import design_tokens as dt
        assert isinstance(dt.COLOR_BG_BASE, str)
        assert isinstance(dt.COLOR_ACCENT_PRIMARY, str)
        assert isinstance(dt.COLOR_SUCCESS_TEXT, str)
        assert isinstance(dt.COLOR_ERROR_TEXT, str)
        assert len(dt.COLOR_BG_BASE) == 7  # #RRGGBB

    def test_spacing_values_are_positive(self):
        from ui import design_tokens as dt
        assert dt.SPACE_1 > 0
        assert dt.SPACE_4 > 0
        assert dt.SPACE_16 > 0

    def test_font_sizes_are_positive(self):
        from ui import design_tokens as dt
        assert dt.FONT_SIZE_XS > 0
        assert dt.FONT_SIZE_XL > dt.FONT_SIZE_BASE
        assert dt.FONT_SIZE_2XL > dt.FONT_SIZE_XL

    def test_radius_values_are_positive(self):
        from ui import design_tokens as dt
        assert dt.RADIUS_SM > 0
        assert dt.RADIUS_LG > dt.RADIUS_SM
        assert dt.RADIUS_PILL >= 100

    def test_status_styles_have_required_keys(self):
        from ui import design_tokens as dt
        required = ["delivered", "planned", "in_progress", "cancelled", "invoiced", "paid"]
        for key in required:
            assert key in dt.STATUS_STYLES, f"Missing status style: {key}"
            label, text_color, bg_color = dt.STATUS_STYLES[key]
            assert isinstance(label, str) and len(label) > 0
            assert isinstance(text_color, str) and text_color.startswith("#")
            assert isinstance(bg_color, str) and bg_color.startswith("#")

    def test_backward_compatibility_aliases(self):
        from ui import design_tokens as dt
        assert dt.BG_BASE == dt.COLOR_BG_BASE
        assert dt.ACCENT == dt.COLOR_ACCENT_PRIMARY
        assert dt.DANGER == dt.COLOR_ERROR_DEFAULT
        assert dt.SUCCESS == dt.COLOR_SUCCESS_DEFAULT

    def test_legacy_status_dict_has_keys(self):
        from ui import design_tokens as dt
        assert "delivered" in dt.STATUS
        assert "planned" in dt.STATUS
        assert "cancelled" in dt.STATUS

    def test_sp_dictionary_matches_space_constants(self):
        from ui import design_tokens as dt
        assert dt.SP["1"] == dt.SPACE_1
        assert dt.SP["4"] == dt.SPACE_4
        assert dt.SP["16"] == dt.SPACE_16

    def test_legacy_radius_dict(self):
        from ui import design_tokens as dt
        assert dt.RADIUS["sm"] == dt.RADIUS_SM
        assert dt.RADIUS["lg"] == dt.RADIUS_LG

    def test_sidebar_dimensions(self):
        from ui import design_tokens as dt
        assert dt.SIDEBAR_EXPANDED > dt.SIDEBAR_COLLAPSED
        assert dt.SIDEBAR_COLLAPSED >= 40

    def test_dimension_constants(self):
        from ui import design_tokens as dt
        assert dt.TOPBAR_HEIGHT > 0
        assert dt.ROW_HEIGHT > 0
        assert dt.INPUT_HEIGHT > 0
        assert dt.BTN_HEIGHT > 0
