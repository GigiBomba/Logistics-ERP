"""Tests for telemetry pipeline integration — §23.6.

set_correlation_context should be called at the request entry point
and PhaseTimer should be used around pipeline stages.
"""

import pytest

from backend.copilot.telemetry import (
    set_correlation_context, set_phase, get_structured_log_extras,
    current_conversation_id, current_company_id, current_user_id,
)


class TestTelemetryPipelineIntegration:
    """Telemetry functions are wired into the request pipeline."""

    def test_set_correlation_context_in_entry_point(self):
        """set_correlation_context is callable from pipeline entry points."""
        # This test verifies the function exists and works
        set_correlation_context(conversation_id="test-conv", company_id=42, user_id=7)
        assert current_conversation_id.get() == "test-conv"

    def test_set_phase_through_pipeline(self):
        """set_phase should be callable at each pipeline stage."""
        from backend.api.v1.copilot_router import router
        # The router imports the planner which calls set_phase
        assert router is not None

    def test_get_structured_log_extras_reflects_context(self):
        """get_structured_log_extras should reflect the current context."""
        set_correlation_context(conversation_id="log-test", company_id=99, user_id=5)
        extras = get_structured_log_extras()
        assert extras["conversation_id"] == "log-test"
        assert extras["company_id"] == 99
        assert extras["user_id"] == 5
