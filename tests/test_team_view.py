"""Tests for QtTeamView — team/user management view."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_user_service():
    us = MagicMock()
    us.list_users.return_value = []
    us.create_user.return_value = None
    return us


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.list_users.return_value = {"items": []}
    client.create_user.return_value = None
    return client


@pytest.fixture
def team_view(qtbot, mock_user_service, mock_api_client):
    """Create QtTeamView with mocked services."""
    patchers = [
        patch("ui.views.team_view.UserService", return_value=mock_user_service),
    ]
    for p in patchers:
        p.start()

    from ui.views.team_view import QtTeamView

    widget = QtTeamView(
        parent=None,
        db=MagicMock(),
        api_client=mock_api_client,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================

class TestQtTeamView:
    """Suite of tests for QtTeamView."""

    def test_initialization(self, team_view):
        """Widget initializes without crashing."""
        assert team_view is not None
        assert hasattr(team_view, "_user_service")

    def test_add_user_form_renders(self, team_view):
        """Add User form has all expected input fields."""
        assert hasattr(team_view, "_email_input")
        assert hasattr(team_view, "_password_input")
        assert hasattr(team_view, "_role_combo")
        assert hasattr(team_view, "_driver_combo")
        assert hasattr(team_view, "_driver_combo_label")

    def test_team_members_table_renders(self, team_view):
        """Team members table exists and has correct columns."""
        assert hasattr(team_view, "_table")
        table = team_view._table
        # Expected columns: email, role, status, created, actions
        assert table.columnCount() >= 4

    def test_add_user_button_exists(self, team_view):
        """Add User button exists and is clickable."""
        assert hasattr(team_view, "_add_btn")
        assert team_view._add_btn is not None
        assert team_view._add_btn.isVisible()

    def test_role_combo_toggles_driver_field_visibility(self, team_view):
        """Selecting 'driver' role shows driver combo; other roles hide it."""
        from services.i18n import t

        # Initially hidden
        assert not team_view._driver_combo_label.isVisible()

        # Select driver role
        driver_role = t("team.role_driver")
        # Find the driver index in the combo
        for i in range(team_view._role_combo.count()):
            if team_view._role_combo.itemText(i) == driver_role:
                team_view._role_combo.setCurrentIndex(i)
                break
        else:
            # If translation key not resolved, set text directly
            team_view._role_combo.setCurrentText(driver_role)
        assert team_view._driver_combo_label.isVisible()

        # Switch back to dispatcher
        dispatcher_role = t("team.role_dispatcher")
        for i in range(team_view._role_combo.count()):
            if team_view._role_combo.itemText(i) == dispatcher_role:
                team_view._role_combo.setCurrentIndex(i)
                break
        else:
            team_view._role_combo.setCurrentText(dispatcher_role)
        assert not team_view._driver_combo_label.isVisible()

    def test_add_user_validates_email(self, team_view):
        """_on_add_user shows warning if email is empty."""
        team_view._email_input.clear()
        team_view._password_input.setText("secret123")
        # Should not crash; warning dialog appears
        team_view._on_add_user()
        # Form should remain intact
        assert team_view._email_input.text() == ""

    def test_add_user_validates_password(self, team_view):
        """_on_add_user shows warning if password is empty."""
        team_view._email_input.setText("user@test.com")
        team_view._password_input.clear()
        team_view._on_add_user()
        assert team_view._email_input.text() == "user@test.com"

    def test_load_users_populates_table(self, team_view, mock_api_client):
        """_load_users fetches data and populates table."""
        mock_api_client.list_users.return_value = {
            "items": [
                {"id": 1, "email": "admin@test.com", "role": "admin", "status": "active",
                 "created_at": "2024-01-01"},
                {"id": 2, "email": "user@test.com", "role": "dispatcher", "status": "active",
                 "created_at": "2024-06-01"},
            ]
        }
        team_view._load_users()
        assert team_view._table.rowCount() == 2

    def test_clear_form_resets_state(self, team_view):
        """_clear_form resets all form fields to initial state."""
        team_view._email_input.setText("test@test.com")
        team_view._password_input.setText("pass")
        team_view._driver_combo_label.setVisible(True)

        team_view._clear_form()

        assert team_view._email_input.text() == ""
        assert team_view._password_input.text() == ""
        assert not team_view._driver_combo_label.isVisible()

    def test_shutdown_cleanup(self, team_view):
        """shutdown() calls base class without crash."""
        team_view.shutdown()

    def test_wakeup_does_not_crash(self, team_view):
        """wakeup() calls super without crash."""
        team_view.wakeup()
