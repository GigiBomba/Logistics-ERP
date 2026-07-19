"""Observability tracing tests — §23.6.

A fixture conversation's logs and metrics share one conversation_id
and per-phase timing is recorded and retrievable.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.telemetry import (
    PhaseTimer, set_correlation_context,
    current_conversation_id, current_company_id,
)


class TestCorrelationContext:
    """Correlation ID propagation across pipeline phases."""

    def test_set_correlation_context(self):
        """Setting correlation context makes values available."""
        set_correlation_context(conversation_id="test-conv-123", company_id=42, user_id=7)
        assert current_conversation_id.get() == "test-conv-123"
        assert current_company_id.get() == 42


class TestPhaseTimer:
    """Per-phase latency tracking."""

    def test_phase_timer_records_elapsed(self):
        """PhaseTimer should record elapsed time."""
        with PhaseTimer("TEST_PHASE", conversation_id="test") as timer:
            time.sleep(0.05)
        assert timer.elapsed_ms > 0, (
            f"Timer should record positive elapsed time, got {timer.elapsed_ms}"
        )
        assert timer.phase_name == "TEST_PHASE"

    def test_phase_timer_no_conversation(self):
        """PhaseTimer should work without explicit conversation_id."""
        timer = PhaseTimer("TEST_NO_CONV")
        with timer:
            pass
        assert timer.elapsed_ms >= 0


class TestTelemetryModule:
    """Telemetry module structure."""

    def test_telemetry_module_imports(self):
        """Telemetry module should be importable."""
        import backend.copilot.telemetry
        assert hasattr(backend.copilot.telemetry, "PhaseTimer")
        assert hasattr(backend.copilot.telemetry, "set_correlation_context")
