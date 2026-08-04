"""Tests for ui/mode_guard.py — ConnectionMode detection and enforcement."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from ui.mode_guard import ConnectionMode, detect_mode, guard_local_access


class TestConnectionMode:
    """ConnectionMode enum values."""

    def test_local_value(self):
        assert ConnectionMode.LOCAL.value == "local"

    def test_remote_value(self):
        assert ConnectionMode.REMOTE.value == "remote"

    def test_unknown_value(self):
        assert ConnectionMode.UNKNOWN.value == "unknown"

    def test_enum_membership(self):
        assert ConnectionMode.LOCAL in ConnectionMode
        assert ConnectionMode.REMOTE in ConnectionMode
        assert ConnectionMode.UNKNOWN in ConnectionMode


class TestDetectMode:
    """detect_mode(db, api_client) -> ConnectionMode"""

    def test_db_only_returns_local(self):
        db = MagicMock()
        assert detect_mode(db, None) == ConnectionMode.LOCAL

    def test_api_only_returns_remote(self):
        api = MagicMock()
        assert detect_mode(None, api) == ConnectionMode.REMOTE

    def test_both_provided_logs_warning_and_returns_local(self, caplog):
        db = MagicMock()
        api = MagicMock()
        with caplog.at_level(logging.WARNING):
            mode = detect_mode(db, api)
        assert mode == ConnectionMode.LOCAL
        assert "Both db and api_client" in caplog.text
        assert "data leakage" in caplog.text

    def test_neither_logs_warning_and_returns_unknown(self, caplog):
        with caplog.at_level(logging.WARNING):
            mode = detect_mode(None, None)
        assert mode == ConnectionMode.UNKNOWN
        assert "Neither db nor api_client" in caplog.text
        assert "degraded mode" in caplog.text

    def test_db_is_none_with_api_returns_remote(self):
        api = MagicMock()
        assert detect_mode(None, api) == ConnectionMode.REMOTE

    def test_api_is_none_with_db_returns_local(self):
        db = MagicMock()
        assert detect_mode(db, None) == ConnectionMode.LOCAL


class TestGuardLocalAccess:
    """guard_local_access(mode, feature_name) — raises on REMOTE only."""

    def test_remote_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="requires local database"):
            guard_local_access(ConnectionMode.REMOTE)

    def test_remote_raises_with_feature_name(self):
        with pytest.raises(RuntimeError, match="My Feature"):
            guard_local_access(ConnectionMode.REMOTE, "My Feature")

    def test_local_does_nothing(self):
        guard_local_access(ConnectionMode.LOCAL)

    def test_unknown_does_nothing(self):
        guard_local_access(ConnectionMode.UNKNOWN)

    def test_default_feature_name_in_message(self):
        with pytest.raises(RuntimeError, match="this feature"):
            guard_local_access(ConnectionMode.REMOTE)

    def test_remote_feature_name_appears_in_no_db_message(self):
        with pytest.raises(RuntimeError, match="Calculator"):
            guard_local_access(ConnectionMode.REMOTE, "Calculator")

    def test_local_with_feature_name_no_error(self):
        guard_local_access(ConnectionMode.LOCAL, "Any Feature")
