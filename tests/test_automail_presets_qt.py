"""Qt-integrated tests for automail PRESETS data structure."""
from __future__ import annotations

import pytest

from ui.views.automail.presets import PRESETS, get_preset, get_preset_names

PRESET_KEYS = ["Friendly", "Professional", "Strict"]


class TestPresetsStructure:
    """Verify the PRESETS dict is well-formed."""

    def test_presets_not_empty(self):
        assert len(PRESETS) > 0

    def test_expected_presets_present(self):
        for name in PRESET_KEYS:
            assert name in PRESETS, f"Missing preset: {name}"

    def test_each_preset_has_description(self):
        for name, preset in PRESETS.items():
            assert "description" in preset, f"{name}: missing description"
            assert isinstance(preset["description"], str)
            assert len(preset["description"]) > 0

    def test_each_preset_has_schedules(self):
        for name, preset in PRESETS.items():
            assert "schedules" in preset, f"{name}: missing schedules"
            assert isinstance(preset["schedules"], list)
            assert len(preset["schedules"]) > 0

    def test_each_preset_has_template(self):
        for name, preset in PRESETS.items():
            assert "template" in preset, f"{name}: missing template"
            assert isinstance(preset["template"], dict)

    def test_no_extra_keys(self):
        allowed = {"description", "schedules", "template"}
        for name, preset in PRESETS.items():
            extra = set(preset.keys()) - allowed
            assert not extra, f"{name}: unexpected keys: {extra}"


class TestPresetsScheduleValidation:
    """Verify schedule entries are well-formed."""

    def test_schedule_has_required_fields(self):
        required = {"name", "trigger_type", "days_offset", "is_active", "sort_order"}
        for pname, preset in PRESETS.items():
            for i, s in enumerate(preset["schedules"]):
                missing = required - set(s.keys())
                assert not missing, f"{pname} schedule[{i}]: missing {missing}"

    def test_trigger_type_valid(self):
        valid = {"days_before_due", "on_due_date", "days_after_due"}
        for pname, preset in PRESETS.items():
            for i, s in enumerate(preset["schedules"]):
                assert s["trigger_type"] in valid, \
                    f"{pname} schedule[{i}]: invalid trigger_type={s['trigger_type']}"

    def test_days_offset_non_negative(self):
        for pname, preset in PRESETS.items():
            for i, s in enumerate(preset["schedules"]):
                assert s["days_offset"] >= 0, \
                    f"{pname} schedule[{i}]: negative days_offset"

    def test_is_active_0_or_1(self):
        for pname, preset in PRESETS.items():
            for i, s in enumerate(preset["schedules"]):
                assert s["is_active"] in (0, 1), \
                    f"{pname} schedule[{i}]: invalid is_active={s['is_active']}"

    def test_sort_order_unique(self):
        for pname, preset in PRESETS.items():
            orders = [s["sort_order"] for s in preset["schedules"]]
            assert len(orders) == len(set(orders)), \
                f"{pname}: duplicate sort_order values"


class TestPresetsTemplateValidation:
    """Verify template entries are well-formed."""

    def test_template_has_required_fields(self):
        required = {"name", "subject", "body_text", "body_html"}
        for pname, preset in PRESETS.items():
            tpl = preset["template"]
            missing = required - set(tpl.keys())
            assert not missing, f"{pname}: template missing {missing}"

    def test_subject_contains_variables(self):
        for pname, preset in PRESETS.items():
            subj = preset["template"]["subject"]
            assert "{" in subj and "}" in subj, \
                f"{pname}: subject has no template variables"

    def test_body_text_non_empty(self):
        for pname, preset in PRESETS.items():
            assert len(preset["template"]["body_text"]) > 0, \
                f"{pname}: body_text is empty"

    def test_body_html_non_empty(self):
        for pname, preset in PRESETS.items():
            assert len(preset["template"]["body_html"]) > 0, \
                f"{pname}: body_html is empty"


class TestPresetsGetFunctions:
    """Test get_preset_names() and get_preset()."""

    def test_get_preset_names(self):
        names = get_preset_names()
        assert isinstance(names, list)
        assert all(name in PRESETS for name in names)

    def test_get_preset_valid(self):
        for name in PRESET_KEYS:
            preset = get_preset(name)
            assert preset == PRESETS[name]
            assert "description" in preset
            assert "schedules" in preset
            assert "template" in preset

    def test_get_preset_invalid(self):
        preset = get_preset("NonExistent")
        assert preset == {}

    def test_get_preset_empty_string(self):
        preset = get_preset("")
        assert preset == {}


class TestPresetsPresetOrder:
    """Verify schedules are in correct logical order (before → on → after due)."""

    def test_friendly_order(self):
        schedules = PRESETS["Friendly"]["schedules"]
        assert schedules[0]["trigger_type"] == "days_before_due"
        assert schedules[1]["trigger_type"] == "on_due_date"
        assert schedules[2]["trigger_type"] == "days_after_due"

    def test_professional_order(self):
        schedules = PRESETS["Professional"]["schedules"]
        assert schedules[0]["trigger_type"] == "days_before_due"
        assert schedules[1]["trigger_type"] == "on_due_date"
        assert schedules[2]["trigger_type"] == "days_after_due"

    def test_strict_starts_on_due_date(self):
        schedules = PRESETS["Strict"]["schedules"]
        assert schedules[0]["trigger_type"] == "on_due_date"
        assert schedules[1]["trigger_type"] == "days_after_due"
