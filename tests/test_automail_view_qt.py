"""Tests for QtAutoMailView — three-panel automation center."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QFrame, QWidget


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def automail_view(qt_widget, qtbot, monkeypatch):
    """Create QtAutoMailView with mocked panel imports returning None
    (so placeholders remain until wakeup tries to wire them)."""
    from ui.views.automail_view import QtAutoMailView

    monkeypatch.setattr(
        "ui.views.automail_view._import_config_panel",
        lambda: None,
    )
    monkeypatch.setattr(
        "ui.views.automail_view._import_timeline_panel",
        lambda: None,
    )
    monkeypatch.setattr(
        "ui.views.automail_view._import_editor_panel",
        lambda: None,
    )

    view = QtAutoMailView(
        parent=qt_widget,
        db=MagicMock(),
        prefs=MagicMock(),
        ops=MagicMock(),
        api_client=MagicMock(),
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


# =========================================================================
# Tests
# =========================================================================


class TestQtAutoMailViewInit:
    """Construction and basic attributes."""

    def test_creation(self, automail_view):
        assert automail_view is not None
        assert automail_view.db is not None
        assert automail_view.prefs is not None
        assert automail_view.ops is not None
        assert automail_view._api_client is not None

    def test_panels_default_to_none(self, automail_view):
        """Real panels are None until wired."""
        assert automail_view._config_panel is None
        assert automail_view._timeline_panel is None
        assert automail_view._editor_panel is None

    def test_wired_false_initially(self, automail_view):
        assert not automail_view._wired


class TestQtAutoMailViewUiElements:
    """Verify UI structure."""

    def test_splitter_exists(self, automail_view):
        assert hasattr(automail_view, "_splitter")
        assert isinstance(automail_view._splitter, QSplitter)

    def test_splitter_has_three_placeholders(self, automail_view):
        assert automail_view._splitter.count() == 3

    def test_config_placeholder_exists(self, automail_view):
        assert automail_view._config_placeholder is not None
        assert isinstance(automail_view._config_placeholder, QFrame)

    def test_timeline_placeholder_exists(self, automail_view):
        assert automail_view._timeline_placeholder is not None
        assert isinstance(automail_view._timeline_placeholder, QFrame)

    def test_editor_placeholder_exists(self, automail_view):
        assert automail_view._editor_placeholder is not None
        assert isinstance(automail_view._editor_placeholder, QFrame)

    def test_placeholders_have_role_property(self, automail_view):
        assert automail_view._config_placeholder.property("role") == "automail-placeholder"
        assert automail_view._timeline_placeholder.property("role") == "automail-placeholder"
        assert automail_view._editor_placeholder.property("role") == "automail-placeholder"

    def test_splitter_orientation(self, automail_view):
        assert automail_view._splitter.orientation() == Qt.Horizontal

    def test_splitter_handle_width(self, automail_view):
        assert automail_view._splitter.handleWidth() == 4


class TestQtAutoMailViewLifecycle:
    """Lifecycle methods."""

    def test_wakeup_does_not_crash(self, automail_view):
        automail_view.wakeup()

    def test_shutdown_does_not_crash(self, automail_view):
        automail_view.shutdown()

    def test_wakeup_does_not_wire_without_panels(self, automail_view):
        """wakeup calls _ensure_wired — since imports return None, nothing wires."""
        automail_view.wakeup()
        assert not automail_view._wired
        assert automail_view._config_panel is None

    def test_wakeup_reentrant(self, automail_view):
        """Multiple wakeup calls are safe."""
        automail_view.wakeup()
        automail_view.wakeup()
        automail_view.wakeup()
        assert not automail_view._wired  # still no panels

    def test_ensure_wired_all_panels_load(self, qt_widget, qtbot):
        """When all panel imports succeed, placeholders are replaced after wakeup."""
        from ui.views.automail_view import QtAutoMailView

        # Use a real QWidget subclass so it works with splitter.insertWidget
        class FakePanel(QFrame):
            pass

        mock_panel_cls = MagicMock()
        mock_panel_cls.side_effect = lambda *a, **kw: FakePanel()
        mock_panel_cls.return_value = None  # side_effect overrides this

        with patch("ui.views.automail_view._import_config_panel", return_value=mock_panel_cls):
            with patch("ui.views.automail_view._import_timeline_panel", return_value=mock_panel_cls):
                with patch("ui.views.automail_view._import_editor_panel", return_value=mock_panel_cls):
                    view = QtAutoMailView(
                        parent=qt_widget,
                        db=MagicMock(),
                        prefs=MagicMock(),
                        ops=MagicMock(),
                    )
                    qtbot.addWidget(view)

                    # Panels are wired lazily via wakeup()
                    assert view._config_panel is None  # not yet wired
                    view.wakeup()

                    assert view._config_panel is not None
                    assert view._timeline_panel is not None
                    assert view._editor_panel is not None
                    assert view._config_placeholder is None
                    assert view._timeline_placeholder is None
                    assert view._editor_placeholder is None
                    assert view._wired

                    view.shutdown()

    def test_ensure_wired_partial_panels(self, qt_widget, qtbot):
        """When only some panels load, others keep placeholders after wakeup."""
        from ui.views.automail_view import QtAutoMailView

        class FakePanel(QFrame):
            pass

        mock_panel_cls = MagicMock()
        mock_panel_cls.side_effect = lambda *a, **kw: FakePanel()
        mock_panel_cls.return_value = None

        with patch("ui.views.automail_view._import_config_panel", return_value=mock_panel_cls):
            with patch("ui.views.automail_view._import_timeline_panel", return_value=None):
                with patch("ui.views.automail_view._import_editor_panel", return_value=mock_panel_cls):
                    view = QtAutoMailView(
                        parent=qt_widget,
                        db=MagicMock(),
                        prefs=MagicMock(),
                        ops=MagicMock(),
                    )
                    qtbot.addWidget(view)

                    view.wakeup()  # trigger lazy wiring

                    assert view._config_panel is not None
                    assert view._timeline_panel is None  # not available
                    assert view._editor_panel is not None
                    assert view._timeline_placeholder is not None  # still there
                    assert not view._wired  # not all 3

                    view.shutdown()


class TestQtAutoMailViewPlaceholderPanel:
    """Tests for the internal _PlaceholderPanel."""

    def test_placeholder_creation(self, qt_widget, qtbot):
        from ui.views.automail_view import _PlaceholderPanel

        panel = _PlaceholderPanel(qt_widget, "Test Label")
        qtbot.addWidget(panel)

        assert panel.property("role") == "automail-placeholder"
        assert len(panel.styleSheet()) > 0
        panel.close()
