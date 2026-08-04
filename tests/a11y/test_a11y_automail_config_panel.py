"""Accessibility tests for ConfigPanel (AutoMail config panel).

Gap: ConfigPanel does not set accessibleName or accessibleDescription.
Child controls (checkboxes, spinboxes, time edits, buttons) also lack
accessibleName — tests will FAIL documenting the gap.

NOTE: ConfigPanel.__init__ triggers SectionHeader creation in ui.widgets
which references an undefined SP variable (source bug). We apply the
SP workaround at module level so ConfigPanel can be created and tested.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
    collect_focusable_children,
)

# SP workaround: ConfigPanel / SectionHeader access ui.widgets.SP which
# is imported internally as 'S'.  Without this the whole module can't
# even be imported.



def _create_panel(parent, **kwargs):
    """Create ConfigPanel for testing."""
    from ui.views.automail.config_panel import ConfigPanel

    return ConfigPanel(parent=parent, **kwargs)


class TestConfigPanelA11y:
    """ConfigPanel — left configuration panel for AutoMail."""

    def test_panel_accessible_name(self, qt_widget, qtbot):
        """ConfigPanel should expose an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel)

    def test_panel_accessible_description(self, qt_widget, qtbot):
        """ConfigPanel should expose an accessibleDescription (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_description_not_empty(panel)

    def test_master_toggle_accessible_name(self, qt_widget, qtbot):
        """Master enable/disable toggle should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._master_toggle)

    def test_add_reminder_button_accessible_name(self, qt_widget, qtbot):
        """Add Reminder button should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._add_btn)

    def test_business_hours_checkbox_accessible_name(self, qt_widget, qtbot):
        """Business hours checkbox should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._biz_hours_cb)

    def test_skip_weekends_checkbox_accessible_name(self, qt_widget, qtbot):
        """Skip weekends checkbox should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._skip_weekends_cb)

    def test_max_reminders_spin_accessible_name(self, qt_widget, qtbot):
        """Max reminders spinbox should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._max_reminders_spin)

    def test_retry_spin_accessible_name(self, qt_widget, qtbot):
        """Retry attempts spinbox should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._retry_spin)

    def test_start_time_accessible_name(self, qt_widget, qtbot):
        """Start time picker should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._start_time)

    def test_end_time_accessible_name(self, qt_widget, qtbot):
        """End time picker should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._end_time)

    def test_preset_combo_accessible_name(self, qt_widget, qtbot):
        """Preset dropdown should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._preset_combo)

    def test_apply_preset_button_accessible_name(self, qt_widget, qtbot):
        """Apply Preset button should have an accessibleName (gap)."""
        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        assert_accessible_name_not_empty(panel._apply_preset_btn)

    def test_section_headers_have_accessible_names(self, qt_widget, qtbot):
        """Each SectionHeader should have an accessibleName (gap)."""
        from ui.widgets import SectionHeader

        panel = _create_panel(qt_widget)
        qtbot.addWidget(panel)
        headers = panel.findChildren(SectionHeader)
        assert len(headers) >= 1, "Expected at least one SectionHeader"
        for header in headers:
            assert_accessible_name_not_empty(header)
