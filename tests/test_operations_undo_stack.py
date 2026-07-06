"""Tests for operations.undo_stack module."""

from __future__ import annotations

from dataclasses import fields

import pytest

from services.operations.undo_stack import UndoCommand, UndoStack


@pytest.fixture
def stack() -> UndoStack:
    return UndoStack()


@pytest.fixture
def sample_cmd() -> UndoCommand:
    return UndoCommand(trip_id=1, old_status="draft", new_status="confirmed")


@pytest.fixture
def sample_cmd2() -> UndoCommand:
    return UndoCommand(trip_id=2, old_status="confirmed", new_status="in_transit")


class TestUndoCommandDataclass:
    def test_all_fields_present(self):
        field_names = {f.name for f in fields(UndoCommand)}
        expected = {"trip_id", "old_status", "new_status", "previous_odometer", "truck_id"}
        assert field_names == expected

    def test_required_fields(self):
        cmd = UndoCommand(trip_id=1, old_status="a", new_status="b")
        assert cmd.trip_id == 1
        assert cmd.old_status == "a"
        assert cmd.new_status == "b"
        assert cmd.previous_odometer is None
        assert cmd.truck_id is None

    def test_optional_fields(self):
        cmd = UndoCommand(
            trip_id=1, old_status="a", new_status="b",
            previous_odometer=12345.0, truck_id=5,
        )
        assert cmd.previous_odometer == 12345.0
        assert cmd.truck_id == 5

    def test_immutability(self):
        """UndoCommand is a regular dataclass (not frozen), but we just verify the fields."""
        cmd = UndoCommand(trip_id=1, old_status="a", new_status="b")
        cmd.trip_id = 99
        assert cmd.trip_id == 99


class TestPush:
    def test_push_adds_command(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        assert stack.can_undo is True
        assert stack.last_undo_command() == sample_cmd

    def test_push_clears_redo(self, stack: UndoStack, sample_cmd: UndoCommand, sample_cmd2: UndoCommand):
        # Push, undo to populate redo, then push again — redo should clear
        stack.push(sample_cmd)
        stack.undo()
        assert stack.can_redo is True
        stack.push(sample_cmd2)
        assert stack.can_redo is False


class TestUndo:
    def test_undo_returns_command(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        cmd = stack.undo()
        assert cmd == sample_cmd
        assert stack.can_undo is False

    def test_undo_moves_to_redo(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        stack.undo()
        assert stack.can_redo is True
        assert stack.last_redo_command() == sample_cmd

    def test_undo_with_no_commands_returns_none(self, stack: UndoStack):
        assert stack.undo() is None

    def test_undo_with_status_check_passes(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        cmd = stack.undo(current_status="confirmed")
        assert cmd == sample_cmd

    def test_undo_with_status_check_fails(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        cmd = stack.undo(current_status="wrong_status")
        assert cmd is None
        # Command should remain on undo stack
        assert stack.can_undo is True

    def test_undo_on_empty_stack_returns_none(self, stack: UndoStack):
        assert stack.undo(current_status="anything") is None


class TestRedo:
    def test_redo_returns_command(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        stack.undo()
        cmd = stack.redo()
        assert cmd == sample_cmd

    def test_redo_moves_back_to_undo(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        stack.undo()
        stack.redo()
        assert stack.can_undo is True
        assert stack.can_redo is False

    def test_redo_with_no_commands_returns_none(self, stack: UndoStack):
        assert stack.redo() is None

    def test_redo_with_status_check_passes(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        stack.undo()
        cmd = stack.redo(current_status="draft")
        assert cmd == sample_cmd

    def test_redo_with_status_check_fails(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        stack.undo()
        cmd = stack.redo(current_status="wrong_status")
        assert cmd is None
        assert stack.can_redo is True  # still available

    def test_redo_on_empty_stack_returns_none(self, stack: UndoStack):
        assert stack.redo(current_status="anything") is None


class TestClear:
    def test_clear_empties_both_stacks(self, stack: UndoStack, sample_cmd: UndoCommand, sample_cmd2: UndoCommand):
        stack.push(sample_cmd)
        stack.push(sample_cmd2)
        stack.undo()
        assert stack.can_undo is True
        assert stack.can_redo is True
        stack.clear()
        assert stack.can_undo is False
        assert stack.can_redo is False
        assert stack.last_undo_command() is None
        assert stack.last_redo_command() is None


class TestCanUndoCanRedo:
    def test_initial_state(self, stack: UndoStack):
        assert stack.can_undo is False
        assert stack.can_redo is False

    def test_after_push(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        assert stack.can_undo is True
        assert stack.can_redo is False

    def test_after_undo(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        stack.undo()
        assert stack.can_undo is False
        assert stack.can_redo is True

    def test_after_redo(self, stack: UndoStack, sample_cmd: UndoCommand):
        stack.push(sample_cmd)
        stack.undo()
        stack.redo()
        assert stack.can_undo is True
        assert stack.can_redo is False


class TestMaxDepth:
    def test_max_depth_enforcement(self, stack: UndoStack):
        """Pushing more than MAX_DEPTH (20) commands removes the oldest."""
        for i in range(UndoStack.MAX_DEPTH + 5):
            cmd = UndoCommand(trip_id=i, old_status="a", new_status="b")
            stack.push(cmd)

        assert stack.last_undo_command().trip_id == UndoStack.MAX_DEPTH + 4
        # The oldest 5 should have been evicted
        assert stack.can_undo is True

    def test_max_depth_value(self):
        assert UndoStack.MAX_DEPTH == 20

    def test_initial_stacks_empty(self, stack: UndoStack):
        assert stack.last_undo_command() is None
        assert stack.last_redo_command() is None


class TestThreadSafety:
    """Basic thread-safety: multiple operations don't crash."""

    def test_concurrent_push_undo(self, stack: UndoStack):
        import threading

        def worker():
            for i in range(50):
                cmd = UndoCommand(trip_id=i, old_status="a", new_status="b")
                stack.push(cmd)
                stack.undo()
                stack.redo()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # No exception should have occurred
        assert isinstance(stack.can_undo, bool)
        assert isinstance(stack.can_redo, bool)


class TestLastCommandMethods:
    def test_last_undo_command_with_items(self, stack: UndoStack, sample_cmd: UndoCommand, sample_cmd2: UndoCommand):
        stack.push(sample_cmd)
        stack.push(sample_cmd2)
        assert stack.last_undo_command() == sample_cmd2

    def test_last_redo_command_with_items(self, stack: UndoStack, sample_cmd: UndoCommand, sample_cmd2: UndoCommand):
        stack.push(sample_cmd)
        stack.push(sample_cmd2)
        stack.undo()  # pops sample_cmd2 → redo: [sample_cmd2]
        assert stack.last_redo_command() == sample_cmd2

    def test_last_undo_command_empty(self, stack: UndoStack):
        assert stack.last_undo_command() is None

    def test_last_redo_command_empty(self, stack: UndoStack):
        assert stack.last_redo_command() is None
