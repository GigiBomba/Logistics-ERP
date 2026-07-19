"""Tests for remote-mode guards in UI views.

Verifies that views correctly use ``guard_local_access`` and ``detect_mode``
to prevent accidental local DB access in remote mode.  Avoids Qt dependencies
by analysing view source code with the ``ast`` module and testing the guard
functions directly.
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ui.mode_guard import ConnectionMode, detect_mode, guard_local_access

# ── Helpers ──────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "ui" / "views"


def _parse_view_source(relative_path: str) -> ast.Module:
    """Parse a view source file into an AST, or skip if file not found."""
    full = (_SRC / relative_path).resolve()
    if not full.is_file():
        raise FileNotFoundError(f"View source not found: {full}")
    return ast.parse(full.read_text(encoding="utf-8"))


def _has_import(node: ast.AST, name: str) -> bool:
    """Check whether an AST node (module-level) imports *name* from
    ``ui.mode_guard``."""
    for child in ast.walk(node):
        if isinstance(child, ast.ImportFrom):
            if child.module == "ui.mode_guard":
                for alias in child.names:
                    if alias.name == name:
                        return True
    return False


def _has_call(node: ast.AST, func_name: str) -> list[ast.Call]:
    """Return all ``Call`` nodes whose function name (unqualified) matches
    *func_name*."""
    calls: list[ast.Call] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id == func_name:
                calls.append(child)
    return calls


# ── Tests ────────────────────────────────────────────────────────────────


class TestModeGuardInMainWindow:
    """Verify that ``detect_mode`` receives the same arguments that
    ``MainWindow.__init__`` receives (regression check)."""

    def test_detect_mode_signature_is_compatible(self):
        """detect_mode(db, api_client) matches the shape of values
        MainWindow passes: self.db and self._api_client."""
        db = MagicMock()
        api = MagicMock()
        mode = detect_mode(db, api)
        assert mode == ConnectionMode.LOCAL  # both provided → LOCAL + warning

    def test_detect_mode_remote_when_no_db(self):
        """Remote mode trigger: db is None, api is present."""
        mode = detect_mode(None, MagicMock())
        assert mode == ConnectionMode.REMOTE

    def test_detect_mode_local_when_no_api(self):
        """Local mode trigger: db is present, api is None."""
        mode = detect_mode(MagicMock(), None)
        assert mode == ConnectionMode.LOCAL


class TestGuardLocalAccessFunction:
    """Direct behavioural tests of ``guard_local_access``."""

    def test_raises_in_remote_mode(self):
        with pytest.raises(RuntimeError, match="requires local database"):
            guard_local_access(ConnectionMode.REMOTE, "TestFeature")

    def test_raises_with_correct_feature_name(self):
        with pytest.raises(RuntimeError, match="My Feature"):
            guard_local_access(ConnectionMode.REMOTE, "My Feature")

    def test_passes_in_local_mode(self):
        guard_local_access(ConnectionMode.LOCAL, "TestFeature")

    def test_passes_in_unknown_mode(self):
        guard_local_access(ConnectionMode.UNKNOWN, "TestFeature")


class TestViewGuardInvocations:
    """Verify that view modules import and call ``guard_local_access`` and
    ``detect_mode`` by parsing their source code with the ``ast`` module.

    This avoids all Qt / PySide6 dependency issues because we never actually
    import the view modules — we only read and analyse their source text.
    """

    # ── import checks ────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("view_rel_path", "expected_imports"),
        [
            ("fleet_tab/fleet_tab.py", {"ConnectionMode", "detect_mode", "guard_local_access"}),
            ("driver_manager.py", {"ConnectionMode", "detect_mode", "guard_local_access"}),
            ("maintenance_analytics_view.py", {"ConnectionMode", "detect_mode", "guard_local_access"}),
            ("dispatch_board/dispatch_board.py", {"ConnectionMode", "detect_mode", "guard_local_access"}),
        ],
        ids=["fleet_tab", "driver_manager", "maintenance_analytics", "dispatch_board"],
    )
    def test_view_imports_guard_functions(self, view_rel_path, expected_imports):
        """Each view imports ``detect_mode``, ``guard_local_access`` and
        ``ConnectionMode`` from ``ui.mode_guard``."""
        try:
            tree = _parse_view_source(view_rel_path)
        except FileNotFoundError:
            pytest.skip(f"View source not found: {view_rel_path}")
        for name in expected_imports:
            assert _has_import(tree, name), (
                f"{view_rel_path} does not import {name!r} from ui.mode_guard"
            )

    # ── call-site checks ─────────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("view_rel_path", "expected_detect_calls", "expected_guard_calls"),
        [
            (
                "fleet_tab/fleet_tab.py",
                1,  # ``detect_mode(db, api_client)`` in __init__
                1,  # ``guard_local_access(self._mode, "Fleet tab")``
            ),
            (
                "driver_manager.py",
                2,  # __init__ + ``mode = detect_mode(self._repo.db, None)``
                2,  # __init__ + ``guard_local_access(mode, "Driver form …")``
            ),
            (
                "maintenance_analytics_view.py",
                1,  # ``detect_mode(db, None)`` in __init__
                1,  # ``guard_local_access(self._mode, "Maintenance analytics")``
            ),
            (
                "dispatch_board/dispatch_board.py",
                1,  # ``detect_mode(db, api_client)`` in __init__
                1,  # ``guard_local_access(self._mode, "Dispatch board")``
            ),
        ],
        ids=["fleet_tab", "driver_manager", "maintenance_analytics", "dispatch_board"],
    )
    def test_view_calls_guard_functions(
        self, view_rel_path, expected_detect_calls, expected_guard_calls
    ):
        """Each view calls ``detect_mode`` and ``guard_local_access`` the
        expected number of times."""
        try:
            tree = _parse_view_source(view_rel_path)
        except FileNotFoundError:
            pytest.skip(f"View source not found: {view_rel_path}")

        detect_calls = _has_call(tree, "detect_mode")
        guard_calls = _has_call(tree, "guard_local_access")

        assert len(detect_calls) == expected_detect_calls, (
            f"{view_rel_path}: expected {expected_detect_calls} detect_mode "
            f"call(s), found {len(detect_calls)}"
        )
        assert len(guard_calls) == expected_guard_calls, (
            f"{view_rel_path}: expected {expected_guard_calls} guard_local_access "
            f"call(s), found {len(guard_calls)}"
        )

    # ── feature-name checks ──────────────────────────────────────────────

    FEATURE_NAMES = {
        "fleet_tab/fleet_tab.py": "Fleet tab",
        "driver_manager.py": "Driver manager",
        "maintenance_analytics_view.py": "Maintenance analytics",
        "dispatch_board/dispatch_board.py": "Dispatch board",
    }

    @pytest.mark.parametrize(
        "view_rel_path",
        list(FEATURE_NAMES.keys()),
        ids=list(FEATURE_NAMES.keys()),
    )
    def test_guard_uses_view_specific_feature_name(self, view_rel_path):
        """The ``guard_local_access`` call in each view passes a
        human-readable feature name appropriate to that view."""
        try:
            tree = _parse_view_source(view_rel_path)
        except FileNotFoundError:
            pytest.skip(f"View source not found: {view_rel_path}")
        expected = self.FEATURE_NAMES[view_rel_path]
        guard_calls = _has_call(tree, "guard_local_access")
        # At least one guard call should contain the expected feature name
        assert any(
            _contains_literal_string(call, expected) for call in guard_calls
        ), (
            f"{view_rel_path}: guard_local_access call does not contain "
            f"feature name {expected!r}"
        )


# ── AST helpers used by TestViewGuardInvocations ─────────────────────────


def _contains_literal_string(call_node: ast.Call, text: str) -> bool:
    """Return True if *text* appears as a string literal inside *call_node*."""
    for child in ast.walk(call_node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if text in child.value:
                return True
    return False


# ── Integration tests ────────────────────────────────────────────────────


class TestRemoteModeGuardIntegration:
    """End-to-end guard pattern: ``detect_mode`` → ``guard_local_access``."""

    def test_local_mode_allows_operations(self):
        """Local mode: guard_local_access is a no-op."""
        mode = detect_mode(MagicMock(), None)
        assert mode == ConnectionMode.LOCAL
        guard_local_access(mode, "local_operation")  # must not raise

    def test_remote_mode_blocks_operations(self):
        """Remote mode: guard_local_access raises RuntimeError."""
        mode = detect_mode(None, MagicMock())
        assert mode == ConnectionMode.REMOTE
        with pytest.raises(RuntimeError, match="requires local database"):
            guard_local_access(mode, "local_operation")

    def test_local_mode_db_only(self):
        """db present, no api_client → LOCAL → guard passes."""
        db = MagicMock()
        mode = detect_mode(db, None)
        assert mode == ConnectionMode.LOCAL
        guard_local_access(mode, "local_operation")

    def test_remote_mode_api_only(self):
        """api_client present, no db → REMOTE → guard blocks."""
        api = MagicMock()
        mode = detect_mode(None, api)
        assert mode == ConnectionMode.REMOTE
        with pytest.raises(RuntimeError):
            guard_local_access(mode, "local_operation")

    def test_both_provided_defaults_to_local(self):
        """Both db and api_client → LOCAL with warning → guard passes."""
        with patch("ui.mode_guard.logger") as mock_logger:
            mode = detect_mode(MagicMock(), MagicMock())
        assert mode == ConnectionMode.LOCAL
        mock_logger.warning.assert_called_once()
        guard_local_access(mode, "test")  # must not raise

    def test_neither_provided_returns_unknown(self):
        """Neither db nor api_client → UNKNOWN → guard passes (fail-open by design)."""
        with patch("ui.mode_guard.logger") as mock_logger:
            mode = detect_mode(None, None)
        assert mode == ConnectionMode.UNKNOWN
        mock_logger.error.assert_called_once()
        guard_local_access(mode, "test")  # must not raise

    def test_guard_uses_feature_name_in_error(self):
        """The error message includes the feature name for easier debugging."""
        with pytest.raises(RuntimeError, match="local_operation"):
            guard_local_access(ConnectionMode.REMOTE, "local_operation")

    def test_main_window_mode_detection_pattern(self):
        """Simulate the exact pattern used in MainWindow.__init__."""
        from ui.main_window import MainWindow  # actually import it
        # We won't instantiate MainWindow (needs Qt), but we can verify
        # the module-level AST import is correct
        main_win_path = Path(__file__).resolve().parent.parent / "ui" / "main_window.py"
        tree = ast.parse(main_win_path.read_text(encoding="utf-8"))
        assert _has_import(tree, "detect_mode"), (
            "MainWindow must import detect_mode from ui.mode_guard"
        )

    def test_guard_pattern_in_driver_manager_dropdown(self):
        """The driver_manager has a second guard call for a dropdown feature."""
        tree = _parse_view_source("driver_manager.py")
        guard_calls = _has_call(tree, "guard_local_access")
        assert len(guard_calls) >= 2, (
            "driver_manager should guard both __init__ and the "
            "truck assignment dropdown"
        )
        # Verify the second call has the dropdown feature name
        dropdown_guard = guard_calls[1] if len(guard_calls) > 1 else guard_calls[0]
        assert _contains_literal_string(dropdown_guard, "truck assignment"), (
            "Second guard in driver_manager should reference "
            "'truck assignment'"
        )
