"""Tests for ``utils.editor_toolkit`` — debounced tasks, shortcuts, field
validation, and JSON export — all Qt dependencies are mocked so these
tests run without a display server or a running QApplication.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

# ── Module-level autouse fixture to mock QTimer ──────────────────────────


@pytest.fixture(autouse=True)
def _mock_all_qt():
    """Mock all Qt classes used by editor_toolkit so no real Qt objects are
    instantiated during any test in this module."""
    with (
        patch("utils.editor_toolkit.QTimer") as mock_timer_cls,
        patch("utils.editor_toolkit.QShortcut") as mock_shortcut_cls,
        patch("utils.editor_toolkit.QKeySequence") as mock_keyseq_cls,
        patch("utils.editor_toolkit.QFileDialog") as mock_fd_cls,
        patch("utils.editor_toolkit.QMessageBox") as mock_mb_cls,
        patch("utils.editor_toolkit.logger", MagicMock()),
    ):
        mock_timer_cls.side_effect = lambda *a, **kw: MagicMock()
        mock_shortcut_cls.side_effect = lambda *a: MagicMock()
        mock_keyseq_cls.side_effect = lambda *a: MagicMock()
        yield


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_widget() -> MagicMock:
    """Return a QWidget stand-in whose ``style()`` returns a mock."""
    w = MagicMock()
    w.style.return_value = MagicMock()
    return w


# ── DebouncedTask ────────────────────────────────────────────────────────


class TestDebouncedTask:
    """Tests for the DebouncedTask wrapper."""

    def test_constructor_creates_singleshot_timer(self):
        """The internal QTimer is set to single-shot mode."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            DebouncedTask(lambda: None)
            mock_timer_instance.setSingleShot.assert_called_once_with(True)

    def test_constructor_connects_timeout_to_callback(self):
        """The callback is wired to the timer's timeout signal."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            callback = MagicMock()
            task = DebouncedTask(callback)
            mock_timer_instance.timeout.connect.assert_called_once_with(callback)
            # Also verify the default interval
            assert task._interval == 300

    def test_schedule_starts_timer(self):
        """schedule() starts the timer with the default interval."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            callback = MagicMock()
            task = DebouncedTask(callback)
            task.schedule()
            mock_timer_instance.start.assert_called_once_with(300)

    def test_schedule_restarts_timer_when_called_multiple_times(self):
        """Calling schedule() again restarts the timer (stop + start)."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            task = DebouncedTask(lambda: None)
            task.schedule()
            task.schedule()
            # start is called each time schedule() is called
            assert mock_timer_instance.start.call_count == 2
            assert mock_timer_instance.start.call_args_list == [call(300), call(300)]

    def test_cancel_stops_timer(self):
        """cancel() stops the running timer."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            task = DebouncedTask(lambda: None)
            task.cancel()
            mock_timer_instance.stop.assert_called_once()

    def test_is_active_returns_true_when_timer_active(self):
        """is_active reflects the active state of the underlying timer."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            mock_timer_instance.isActive.return_value = True
            task = DebouncedTask(lambda: None)
            assert task.is_active is True

    def test_is_active_returns_false_when_timer_inactive(self):
        """is_active is False when the underlying timer is not active."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            mock_timer_instance.isActive.return_value = False
            task = DebouncedTask(lambda: None)
            assert task.is_active is False

    def test_custom_interval(self):
        """A custom interval (ms) can be passed to the constructor."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            task = DebouncedTask(lambda: None, interval_ms=500)
            task.schedule()
            mock_timer_instance.start.assert_called_once_with(500)

    def test_cancel_does_not_raise_when_timer_not_started(self):
        """cancel() is safe to call even if the timer was never started."""
        from utils.editor_toolkit import DebouncedTask

        with patch("utils.editor_toolkit.QTimer") as MockTimer:
            mock_timer_instance = MockTimer.return_value
            task = DebouncedTask(lambda: None)
            # Should not raise
            task.cancel()
            mock_timer_instance.stop.assert_called_once()


# ── SHORTCUT_KEYS ───────────────────────────────────────────────────────


class TestShortcutKeys:
    """Tests for the SHORTCUT_KEYS mapping."""

    def test_is_dict(self):
        """SHORTCUT_KEYS is a dict."""
        from utils.editor_toolkit import SHORTCUT_KEYS

        assert isinstance(SHORTCUT_KEYS, dict)

    def test_contains_expected_keys(self):
        """All expected action keys are present."""
        from utils.editor_toolkit import SHORTCUT_KEYS

        expected = {"generate", "save_draft", "load_draft",
                    "duplicate", "export_json", "print"}
        assert set(SHORTCUT_KEYS.keys()) == expected

    def test_values_are_nonempty_strings(self):
        """Every shortcut value is a non-empty string."""
        from utils.editor_toolkit import SHORTCUT_KEYS

        for key, value in SHORTCUT_KEYS.items():
            assert isinstance(value, str), f"{key!r} value is not a string"
            assert len(value) > 0, f"{key!r} value is empty"

    def test_all_shortcuts_start_with_ctrl(self):
        """All standard shortcuts start with Ctrl (convention check)."""
        from utils.editor_toolkit import SHORTCUT_KEYS

        for key, value in SHORTCUT_KEYS.items():
            assert value.startswith("Ctrl"), f"{key!r} shortcut {value!r} does not start with Ctrl"

    def test_immutability_does_not_raise(self):
        """SHORTCUT_KEYS is a plain dict, not required to be frozen —
        just verify it can be accessed without error."""
        from utils.editor_toolkit import SHORTCUT_KEYS

        assert SHORTCUT_KEYS["generate"] == "Ctrl+G"


# ── register_shortcuts ──────────────────────────────────────────────────


class TestRegisterShortcuts:
    """Tests for the register_shortcuts function."""

    def test_creates_shortcuts_for_valid_keys(self):
        """QShortcut is created for each valid action key."""
        from utils.editor_toolkit import register_shortcuts

        with (
            patch("utils.editor_toolkit.QShortcut") as MockShortcut,
            patch("utils.editor_toolkit.QKeySequence") as MockKeySeq,
        ):
            mock_shortcut_instance = MockShortcut.return_value
            parent = MagicMock()
            actions = {
                "generate": MagicMock(),
                "save_draft": MagicMock(),
                "load_draft": MagicMock(),
            }
            result = register_shortcuts(parent, actions)
            assert len(result) == 3
            assert MockShortcut.call_count == 3
            # Each entry in result is the mock shortcut instance
            assert all(s is mock_shortcut_instance for s in result)

    def test_returns_shortcuts_list(self):
        """The returned list contains the created QShortcut objects."""
        from utils.editor_toolkit import register_shortcuts

        with (
            patch("utils.editor_toolkit.QShortcut") as MockShortcut,
            patch("utils.editor_toolkit.QKeySequence") as MockKeySeq,
        ):
            parent = MagicMock()
            actions = {"generate": MagicMock(), "export_json": MagicMock()}
            result = register_shortcuts(parent, actions)
            assert isinstance(result, list)
            assert len(result) == 2

    def test_skips_unknown_key_with_warning(self):
        """An unknown action key is skipped and a warning is logged."""
        from utils.editor_toolkit import register_shortcuts

        with (
            patch("utils.editor_toolkit.QShortcut"),
            patch("utils.editor_toolkit.QKeySequence"),
            patch("utils.editor_toolkit.logger") as mock_logger,
        ):
            parent = MagicMock()
            actions = {"unknown_action": MagicMock()}
            result = register_shortcuts(parent, actions)
            assert len(result) == 0
            mock_logger.warning.assert_called_once_with(
                "register_shortcuts: unknown action key %r", "unknown_action"
            )

    def test_mixed_valid_and_invalid_keys(self):
        """Valid keys create shortcuts; invalid keys are skipped."""
        from utils.editor_toolkit import register_shortcuts

        with (
            patch("utils.editor_toolkit.QShortcut") as MockShortcut,
            patch("utils.editor_toolkit.QKeySequence"),
            patch("utils.editor_toolkit.logger"),
        ):
            parent = MagicMock()
            actions = {
                "generate": MagicMock(),
                "bogus": MagicMock(),
                "print": MagicMock(),
            }
            result = register_shortcuts(parent, actions)
            assert len(result) == 2
            assert MockShortcut.call_count == 2

    def test_empty_actions_returns_empty_list(self):
        """An empty actions dict produces an empty list and no shortcuts."""
        from utils.editor_toolkit import register_shortcuts

        with (
            patch("utils.editor_toolkit.QShortcut") as MockShortcut,
            patch("utils.editor_toolkit.QKeySequence"),
        ):
            parent = MagicMock()
            result = register_shortcuts(parent, {})
            assert result == []
            MockShortcut.assert_not_called()


# ── highlight_invalid_fields ────────────────────────────────────────────


class TestHighlightInvalidFields:
    """Tests for highlight_invalid_fields."""

    def test_clears_invalid_property_on_all_widgets(self):
        """Every widget gets invalid set to 'false'."""
        from utils.editor_toolkit import highlight_invalid_fields

        widgets = [_make_widget() for _ in range(3)]
        highlight_invalid_fields(widgets)
        for w in widgets:
            w.setProperty.assert_any_call("invalid", "false")

    def test_calls_unpolish_and_polish_on_each_widget(self):
        """Each widget's style is unpolished then polished."""
        from utils.editor_toolkit import highlight_invalid_fields

        widgets = [_make_widget() for _ in range(2)]
        highlight_invalid_fields(widgets)
        for w in widgets:
            w.style.return_value.unpolish.assert_called_with(w)
            w.style.return_value.polish.assert_called_with(w)

    def test_empty_widgets_list_does_nothing(self):
        """An empty sequence does not raise and produces no calls."""
        from utils.editor_toolkit import highlight_invalid_fields

        highlight_invalid_fields([])  # should not raise

    def test_single_widget(self):
        """A single widget is handled correctly."""
        from utils.editor_toolkit import highlight_invalid_fields

        w = _make_widget()
        highlight_invalid_fields([w])
        w.setProperty.assert_called_once_with("invalid", "false")
        w.style.return_value.unpolish.assert_called_once_with(w)
        w.style.return_value.polish.assert_called_once_with(w)


# ── mark_field_invalid ──────────────────────────────────────────────────


class TestMarkFieldInvalid:
    """Tests for mark_field_invalid."""

    def test_sets_invalid_property_to_true(self):
        """The widget's invalid property is set to 'true'."""
        from utils.editor_toolkit import mark_field_invalid

        w = _make_widget()
        mark_field_invalid(w)
        w.setProperty.assert_called_once_with("invalid", "true")

    def test_calls_unpolish_and_polish(self):
        """The widget's style is unpolished then polished."""
        from utils.editor_toolkit import mark_field_invalid

        w = _make_widget()
        mark_field_invalid(w)
        w.style.return_value.unpolish.assert_called_once_with(w)
        w.style.return_value.polish.assert_called_once_with(w)

    def test_can_be_called_twice(self):
        """Calling mark_field_invalid twice is idempotent (no crash)."""
        from utils.editor_toolkit import mark_field_invalid

        w = _make_widget()
        mark_field_invalid(w)
        mark_field_invalid(w)
        assert w.setProperty.call_count == 2


# ── validate_and_highlight ──────────────────────────────────────────────


class TestValidateAndHighlight:
    """Tests for validate_and_highlight (convenience combo)."""

    def test_clears_all_then_marks_invalid_widgets(self):
        """All widgets are cleared, then only invalid ones are marked."""
        from utils.editor_toolkit import validate_and_highlight

        widgets = [_make_widget() for _ in range(4)]
        invalid = [widgets[0], widgets[2]]

        validate_and_highlight(widgets, invalid)

        # All widgets must have been cleared
        for w in widgets:
            assert w.setProperty.call_args_list[0] == call("invalid", "false")

        # Invalid widgets also get marked
        for w in invalid:
            assert w.setProperty.call_args_list[1] == call("invalid", "true")

    def test_invalid_only_contains_subset(self):
        """Only widgets in invalid_widgets get the second mark."""
        from utils.editor_toolkit import validate_and_highlight

        widgets = [_make_widget() for _ in range(3)]
        invalid = [widgets[0]]

        validate_and_highlight(widgets, invalid)

        # widget[0] was cleared then marked invalid
        assert widgets[0].setProperty.call_count == 2
        # widgets[1] and [2] were only cleared
        assert widgets[1].setProperty.call_count == 1
        assert widgets[2].setProperty.call_count == 1

    def test_empty_invalid_list_only_clears(self):
        """When invalid_widgets is empty, all widgets are just cleared."""
        from utils.editor_toolkit import validate_and_highlight

        widgets = [_make_widget() for _ in range(2)]
        validate_and_highlight(widgets, [])
        for w in widgets:
            w.setProperty.assert_called_once_with("invalid", "false")

    def test_delegates_to_sub_functions(self):
        """The function delegates to highlight_invalid_fields and
        mark_field_invalid."""
        from utils.editor_toolkit import validate_and_highlight

        with (
            patch("utils.editor_toolkit.highlight_invalid_fields") as mock_clear,
            patch("utils.editor_toolkit.mark_field_invalid") as mock_mark,
        ):
            widgets = [_make_widget() for _ in range(2)]
            invalid = [widgets[1]]
            validate_and_highlight(widgets, invalid)

            mock_clear.assert_called_once_with(widgets)
            mock_mark.assert_called_once_with(widgets[1])


# ── export_editor_data ──────────────────────────────────────────────────


class TestExportEditorData:
    """Tests for export_editor_data."""

    def test_returns_early_when_dialog_cancelled(self):
        """When the file dialog returns an empty path, the function returns
        without writing or showing any message box."""
        from utils.editor_toolkit import export_editor_data

        with (
            patch("utils.editor_toolkit.QFileDialog.getSaveFileName", return_value=("", "")),
            patch("utils.editor_toolkit.QMessageBox") as MockMsgBox,
            patch("builtins.open") as mock_open,
        ):
            parent = MagicMock()
            export_editor_data(parent, {"key": "value"}, "Export Title", "default.json")

            mock_open.assert_not_called()
            MockMsgBox.information.assert_not_called()
            MockMsgBox.critical.assert_not_called()

    def test_opens_file_dialog_with_correct_arguments(self):
        """The file save dialog is opened with the expected title, default
        filename, and JSON filter."""
        from utils.editor_toolkit import export_editor_data

        with (
            patch("utils.editor_toolkit.QFileDialog.getSaveFileName",
                  return_value=("/path/out.json", "JSON (*.json)")) as mock_dialog,
            patch("builtins.open") as mock_open,
            patch("utils.editor_toolkit.json.dump"),
        ):
            parent = MagicMock()
            export_editor_data(parent, {"a": 1}, "My Dialog", "my_data.json")

            mock_dialog.assert_called_once_with(
                parent, "My Dialog", "my_data.json", "JSON (*.json)"
            )

    def test_writes_json_with_indent_and_ensure_ascii(self):
        """json.dump is called with indent=2 and ensure_ascii=False."""
        from utils.editor_toolkit import export_editor_data

        test_data = {"name": "test", "value": 42}
        filepath = "C:/tmp/export.json"

        with (
            patch("utils.editor_toolkit.QFileDialog.getSaveFileName",
                  return_value=(filepath, "JSON (*.json)")),
            patch("builtins.open") as mock_open,
            patch("utils.editor_toolkit.json.dump") as mock_json_dump,
            patch("utils.editor_toolkit.QMessageBox"),
        ):
            parent = MagicMock()
            export_editor_data(parent, test_data, "Export", "data.json")

            mock_json_dump.assert_called_once_with(
                test_data, mock_open.return_value.__enter__.return_value,
                indent=2, ensure_ascii=False
            )

    def test_shows_success_message_on_completion(self):
        """QMessageBox.information is shown after a successful export."""
        from utils.editor_toolkit import export_editor_data

        filepath = "C:/tmp/export.json"

        with (
            patch("utils.editor_toolkit.QFileDialog.getSaveFileName",
                  return_value=(filepath, "JSON (*.json)")),
            patch("builtins.open"),
            patch("utils.editor_toolkit.json.dump"),
            patch("utils.editor_toolkit.QMessageBox") as MockMsgBox,
        ):
            parent = MagicMock()
            export_editor_data(parent, {"k": "v"}, "Export OK", "data.json")

            MockMsgBox.information.assert_called_once_with(
                parent, "Export OK", f"Data exported to:\n{filepath}"
            )
            MockMsgBox.critical.assert_not_called()

    def test_shows_error_message_on_write_failure(self):
        """QMessageBox.critical is shown when writing raises an exception."""
        from utils.editor_toolkit import export_editor_data

        filepath = "C:/tmp/export.json"

        with (
            patch("utils.editor_toolkit.QFileDialog.getSaveFileName",
                  return_value=(filepath, "JSON (*.json)")),
            patch("builtins.open", side_effect=IOError("Permission denied")),
            patch("utils.editor_toolkit.json.dump"),
            patch("utils.editor_toolkit.QMessageBox") as MockMsgBox,
        ):
            parent = MagicMock()
            export_editor_data(parent, {"k": "v"}, "Export Fail", "data.json")

            MockMsgBox.critical.assert_called_once_with(
                parent, "Export Fail", "Export failed:\nPermission denied"
            )
            MockMsgBox.information.assert_not_called()

    def test_logs_exception_on_failure(self):
        """logger.exception is called when the write operation fails."""
        from utils.editor_toolkit import export_editor_data

        filepath = "C:/tmp/export.json"

        with (
            patch("utils.editor_toolkit.QFileDialog.getSaveFileName",
                  return_value=(filepath, "JSON (*.json)")),
            patch("builtins.open", side_effect=OSError("Disk full")),
            patch("utils.editor_toolkit.json.dump"),
            patch("utils.editor_toolkit.QMessageBox"),
            patch("utils.editor_toolkit.logger") as mock_logger,
        ):
            parent = MagicMock()
            export_editor_data(parent, {"k": "v"}, "Export", "data.json")

            mock_logger.exception.assert_called_once_with("JSON export failed")

    def test_file_opened_with_correct_encoding(self):
        """The output file is opened in write mode with utf-8 encoding."""
        from utils.editor_toolkit import export_editor_data

        filepath = "C:/tmp/export.json"

        with (
            patch("utils.editor_toolkit.QFileDialog.getSaveFileName",
                  return_value=(filepath, "JSON (*.json)")),
            patch("builtins.open") as mock_open,
            patch("utils.editor_toolkit.json.dump"),
            patch("utils.editor_toolkit.QMessageBox"),
        ):
            parent = MagicMock()
            export_editor_data(parent, {"k": "v"}, "Export", "data.json")

            mock_open.assert_called_once_with(filepath, "w", encoding="utf-8")
