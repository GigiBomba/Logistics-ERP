"""Tests for tour_tracker module — tour completion state persisted to JSON.

Blueprint: §34.7 — Onboarding Tour (first launch tracking).
"""

from __future__ import annotations

import json
import os
import builtins
from unittest.mock import MagicMock
from pathlib import Path

import pytest
from ui.copilot.tour_tracker import (
    mark_tour_completed,
    is_tour_completed,
    clear_tour_completed,
    clear_all_tours,
    get_completed_tours,
    get_completion_count,
    increment_completion_count,
)


# ── Fixture ──────────────────────────────────────────────────────────

@pytest.fixture
def tour_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect TOUR_COMPLETED_FILE to a temp path so tests don't touch
    the real ~/.operion/.tour_completed.json on disk."""
    fake_path = tmp_path / ".tour_completed.json"
    monkeypatch.setattr(
        "ui.copilot.tour_tracker.TOUR_COMPLETED_FILE", str(fake_path)
    )
    return fake_path


# ── TestMarkTourCompleted ────────────────────────────────────────────

class TestMarkTourCompleted:
    """Tests for mark_tour_completed()."""

    def test_mark_then_is_completed(self, tour_file: Path) -> None:
        mark_tour_completed("add_driver")
        assert is_tour_completed("add_driver") is True

    def test_mark_allows_other_uncompleted(self, tour_file: Path) -> None:
        mark_tour_completed("add_driver")
        assert is_tour_completed("add_driver") is True
        assert is_tour_completed("create_trip") is False


# ── TestIsTourCompleted ──────────────────────────────────────────────

class TestIsTourCompleted:
    """Tests for is_tour_completed()."""

    def test_default_not_completed(self, tour_file: Path) -> None:
        assert is_tour_completed("anything") is False

    def test_default_param_app_overview(self, tour_file: Path) -> None:
        """is_tour_completed() with no argument checks 'app_overview'."""
        assert is_tour_completed() is False  # no arg → "app_overview"
        mark_tour_completed("other_thing")
        assert is_tour_completed() is False  # "app_overview" still not done
        mark_tour_completed()  # marks "app_overview" (default arg)
        assert is_tour_completed() is True

    def test_initially_missing_file(self, tour_file: Path) -> None:
        """When the file does not exist, is_tour_completed returns False."""
        assert not tour_file.exists()
        assert is_tour_completed("any_id") is False

    def test_corrupt_json_recovers(self, tour_file: Path) -> None:
        """Invalid JSON content → no crash, returns False."""
        tour_file.write_text("{invalid json content!!!", encoding="utf-8")
        assert is_tour_completed("anything") is False

    def test_non_dict_root_recovers(self, tour_file: Path) -> None:
        """Root JSON value is not a dict → safe defaults."""
        tour_file.write_text('["not", "a", "dict"]', encoding="utf-8")
        assert is_tour_completed("anything") is False


# ── TestClearTourCompleted ───────────────────────────────────────────

class TestClearTourCompleted:
    """Tests for clear_tour_completed() and clear_all_tours()."""

    def test_clear_single_tour(self, tour_file: Path) -> None:
        mark_tour_completed("a")
        mark_tour_completed("b")
        assert is_tour_completed("a") is True
        assert is_tour_completed("b") is True

        clear_tour_completed("a")

        assert is_tour_completed("a") is False
        assert is_tour_completed("b") is True

    def test_clear_all_tours(self, tour_file: Path) -> None:
        mark_tour_completed("alpha")
        mark_tour_completed("beta")
        mark_tour_completed("gamma")
        assert len(get_completed_tours()) == 3

        clear_all_tours()

        assert get_completed_tours() == []

    def test_clear_tour_completed(self, tour_file: Path) -> None:
        """clear_tour_completed('x') → is_tour_completed('x') is False."""
        mark_tour_completed("x")
        assert is_tour_completed("x") is True
        clear_tour_completed("x")
        assert is_tour_completed("x") is False


# ── TestGetCompletedTours ────────────────────────────────────────────

class TestGetCompletedTours:
    """Tests for get_completed_tours()."""

    def test_get_completed_tours_empty(self, tour_file: Path) -> None:
        assert get_completed_tours() == []

    def test_get_completed_tours_multiple(self, tour_file: Path) -> None:
        mark_tour_completed("A")
        mark_tour_completed("B")
        mark_tour_completed("C")
        completed = get_completed_tours()
        assert "A" in completed
        assert "B" in completed
        assert "C" in completed
        assert len(completed) == 3


# ── TestCompletionCount ──────────────────────────────────────────────

class TestCompletionCount:
    """Tests for get_completion_count() and increment_completion_count()."""

    def test_completion_count_default(self, tour_file: Path) -> None:
        """Never-completed workflow → count is 0."""
        assert get_completion_count("never_touched") == 0

    def test_completion_count_after_mark(self, tour_file: Path) -> None:
        """mark_tour_completed sets implicit count to 1."""
        mark_tour_completed("cnt")
        assert get_completion_count("cnt") == 1

    def test_increment_count(self, tour_file: Path) -> None:
        """increment_completion_count increases the count (1→2)."""
        increment_completion_count("inc")
        assert get_completion_count("inc") == 1
        increment_completion_count("inc")
        assert get_completion_count("inc") == 2

    def test_increment_also_sets_completed(self, tour_file: Path) -> None:
        """After increment_completion_count, is_tour_completed is True."""
        increment_completion_count("x")
        assert is_tour_completed("x") is True


# ── TestFileIOErrors ─────────────────────────────────────────────────

class TestFileIOErrors:
    """Tests that file I/O errors are handled gracefully (no propagation)."""

    def test_write_error_handled(self, tour_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock open(..., 'w') to raise OSError → mark_tour_completed does
        not propagate the exception."""

        original_open = builtins.open

        def _mock_open(*args, **kwargs):
            if len(args) >= 2 and "w" in args[1]:
                raise OSError("Mock write error")
            if "mode" in kwargs and "w" in kwargs["mode"]:
                raise OSError("Mock write error")
            return original_open(*args, **kwargs)

        monkeypatch.setattr("builtins.open", _mock_open)

        # Should not raise
        mark_tour_completed("should_not_crash")

    def test_oserror_during_read(self, tour_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock open(..., 'r') to raise OSError → is_tour_completed returns
        False without crashing."""

        # Create the file so _read_tour_data tries to read it
        tour_file.write_text(
            json.dumps({"_version": "1.0", "tours": {"existing": {"completed": True}}}),
            encoding="utf-8",
        )

        original_open = builtins.open

        def _mock_open(*args, **kwargs):
            if len(args) >= 2 and "r" in args[1]:
                raise OSError("Mock read error")
            if "mode" in kwargs and "r" in kwargs["mode"]:
                raise OSError("Mock read error")
            return original_open(*args, **kwargs)

        monkeypatch.setattr("builtins.open", _mock_open)

        # Should not crash, returns default False
        assert is_tour_completed("existing") is False
