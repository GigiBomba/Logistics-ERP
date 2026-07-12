"""Tests for QtMigrationCenterView — migration/import-export hub."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_prefs():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    return ops


@pytest.fixture
def migration_center(qtbot, mock_db, mock_prefs, mock_ops):
    """Create QtMigrationCenterView with mocked dependencies."""
    # Mock the three tab classes so they don't require real imports
    tab_patchers = [
        patch("ui.views.migration_center.migration_center_view.ImmigrateSoftwareTab",
              return_value=MagicMock()),
        patch("ui.views.migration_center.migration_center_view.ImmigratePhysicalTab",
              return_value=MagicMock()),
        patch("ui.views.migration_center.migration_center_view.EmigrateTab",
              return_value=MagicMock()),
        patch("ui.views.migration_center.migration_center_view.QtDispatchTabs",
              return_value=MagicMock()),
    ]
    for p in tab_patchers:
        p.start()

    from ui.views.migration_center.migration_center_view import QtMigrationCenterView

    widget = QtMigrationCenterView(
        parent=None,
        db=mock_db,
        prefs=mock_prefs,
        ops=mock_ops,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()
    for p in tab_patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================

class TestQtMigrationCenterView:
    """Suite of tests for QtMigrationCenterView."""

    def test_initialization(self, migration_center):
        """Widget initializes without crashing."""
        assert migration_center is not None
        assert migration_center.db is not None

    def test_three_tabs_rendered(self, migration_center):
        """Three tabs are registered in the dispatch tabs widget."""
        assert hasattr(migration_center, "_tabs")
        # Verify tabs were added (we mocked _tabs to return a MagicMock)
        # The add_tab method should have been called 3 times
        assert migration_center._tabs.add_tab.call_count == 3

    def test_tab_names_match(self, migration_center):
        """Tabs use expected keys: software, physical, emigrate."""
        call_args_list = migration_center._tabs.add_tab.call_args_list
        tab_keys = [call[0][0] for call in call_args_list]
        assert "software" in tab_keys
        assert "physical" in tab_keys
        assert "emigrate" in tab_keys

    def test_header_renders(self, migration_center):
        """Header contains PageTitle widget."""
        from ui.components import PageTitle
        titles = migration_center.findChildren(PageTitle)
        # At minimum the PageTitle should exist
        assert len(titles) >= 1

    def test_subtitle_renders(self, migration_center):
        """Subtitle label exists."""
        from ui.components import Label
        labels = migration_center.findChildren(Label)
        # Should have at least the subtitle label
        assert len(labels) >= 1

    def test_wakeup_does_not_crash(self, migration_center):
        """wakeup() is a no-op but should not crash."""
        migration_center.wakeup()

    def test_shutdown_does_not_crash(self, migration_center):
        """shutdown() cleans up without error."""
        migration_center.shutdown()

    def test_db_stored(self, migration_center, mock_db):
        """DB reference is stored correctly."""
        assert migration_center.db is mock_db

    def test_prefs_stored(self, migration_center, mock_prefs):
        """Prefs reference is stored correctly."""
        assert migration_center.prefs is mock_prefs

    def test_ops_stored(self, migration_center, mock_ops):
        """Ops reference is stored correctly."""
        assert migration_center.ops is mock_ops
