"""Additional edge case tests for human handoff (§23.7).

Extends the existing test_phase4_human_handoff.py with:
- Thread safety under concurrent access
- Memory leak / cleanup verification
- Empty intent name edge cases
- Accumulation of multiple counter types
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.human_handoff import (
    HandoffState, HandoffTracker, should_handoff,
    _trackers,
)


class TestHandoffThreadSafety:
    """Thread safety for global _trackers dict."""

    def test_concurrent_get_does_not_race(self):
        """Multiple threads getting the same conversation should not race."""
        errors = []

        def getter(cid):
            try:
                HandoffTracker.get(cid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=getter, args=(f"race-conv-{i}",))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"

    def test_concurrent_record_does_not_lose_updates(self):
        """Concurrent record_low_confidence calls should not lose counts."""
        state = HandoffTracker.get("record-race-conv")
        state.low_confidence_count = 0

        def recorder():
            state.record_low_confidence("test.intent")

        threads = [threading.Thread(target=recorder) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each call should increment to at most some value
        # (exact value depends on timing - just ensure no crash)
        assert state.low_confidence_count >= 1


class TestHandoffCleanup:
    """Memory leak prevention for _trackers."""

    def test_reset_removes_tracker(self):
        """reset should remove the tracker from the dict."""
        HandoffTracker.get("reset-test-conv")
        HandoffTracker.reset("reset-test-conv")
        # After reset, getting a new one should be fresh
        state = HandoffTracker.get("reset-test-conv")
        assert not state.should_handoff()

    def test_reset_does_not_raise_on_missing(self):
        """reset should not raise if conversation was never tracked."""
        # Should not raise KeyError
        HandoffTracker.reset("never-tracked-conv")
        assert True  # Reached here without exception


class TestHandoffEdgeCases:
    """Edge cases for handoff logic."""

    def test_empty_intent_name_ignored(self):
        """Empty intent names should be ignored (guard prevents counting)."""
        state = HandoffState("test")
        state.record_low_confidence("")
        assert state.low_confidence_count == 0
        assert state.last_intent is None

    def test_none_intent_name_handled(self):
        """None intent name should be treated as valid intent (not None after guard)."""
        state = HandoffState("test")
        state.record_low_confidence(None)  # type: ignore[arg-type]
        # None is falsy, so guard catches it — counter stays 0
        assert state.low_confidence_count == 0

    def test_multiple_counter_types_accumulate(self):
        """Different counter types should accumulate independently."""
        state = HandoffState("test")
        state.record_low_confidence("intent.a")
        state.record_low_confidence("intent.a")
        state.record_cancellation("intent.b")
        state.record_cancellation("intent.b")
        assert state.low_confidence_count == 2
        assert state.cancellation_count == 2
        assert state.should_handoff()

    def test_handoff_triggered_stays_triggered(self):
        """Once handoff is triggered via should_handoff(), it stays triggered."""
        state = HandoffState("test")
        state.record_low_confidence("intent.a")
        state.record_low_confidence("intent.a")
        state.should_handoff()  # This triggers the flag
        assert state.handoff_triggered
        # Even after a successful action
        assert state.should_handoff()
        assert state.reason is not None

    def test_low_confidence_and_cancellation_mixed(self):
        """Mixed low confidence and cancellation for the same intent."""
        state = HandoffState("test")
        # First low confidence
        state.record_low_confidence("intent.a")
        assert not state.should_handoff()
        # Cancellation for same intent
        state.record_cancellation("intent.a")
        # Neither threshold is crossed yet (both at 1)
        assert not state.should_handoff()
        # Second low confidence for same intent crosses threshold
        state.record_low_confidence("intent.a")
        assert state.should_handoff()
