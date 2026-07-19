"""Operation integration tests for telemetry, kill switch, and executor.

Tests cover:
- Telemetry: correlation context propagation, PhaseTimer logging, set_phase
- Kill switch: Redis integration, plan cancellation, endpoint blocking
- Executor: circuit breaker feedback, guardrail enforcement, execute_with_fallback
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.telemetry import (
    PhaseTimer,
    set_correlation_context,
    set_phase,
    get_structured_log_extras,
    current_conversation_id,
    current_phase,
)


class TestTelemetryOperations:
    """Telemetry correlation and phase tracking must work end-to-end."""

    def test_set_correlation_context_propagates(self):
        """set_correlation_context must make values available via ContextVars."""
        set_correlation_context(conversation_id="ops-test-conv", company_id=99, user_id=5)
        assert current_conversation_id.get() == "ops-test-conv"

    def test_set_phase_tracking(self):
        """set_phase must update the current_phase ContextVar."""
        set_phase("TESTING")
        assert current_phase.get() == "TESTING"

    def test_phase_timer_enter_sets_phase(self):
        """PhaseTimer.__enter__ must set the phase via set_phase."""
        timer = PhaseTimer("OPS_TEST", conversation_id="test")
        with timer:
            assert current_phase.get() == "OPS_TEST"

    def test_phase_timer_exit_restores_previous_phase(self):
        """PhaseTimer.__exit__ must restore the previous phase."""
        set_phase("BEFORE")
        with PhaseTimer("INSIDE", conversation_id="test"):
            pass
        assert current_phase.get() == "BEFORE", "Phase should be restored after exit"

    def test_phase_timer_measures_elapsed_time(self):
        """PhaseTimer must record positive elapsed time."""
        with PhaseTimer("TIMING_TEST", conversation_id="test") as timer:
            time.sleep(0.05)
        assert timer.elapsed_ms > 0, f"Expected positive elapsed, got {timer.elapsed_ms}"

    def test_phase_timer_no_conversation_id(self):
        """PhaseTimer should work without an explicit conversation_id."""
        timer = PhaseTimer("NO_CONV")
        with timer:
            pass
        assert timer.elapsed_ms >= 0

    def test_get_structured_log_extras_reflects_context(self):
        """get_structured_log_extras must return current correlation values."""
        set_correlation_context(conversation_id="log-ctx", company_id=42, user_id=7)
        set_phase("LOGGING")
        extras = get_structured_log_extras()
        assert extras["conversation_id"] == "log-ctx"
        assert extras["company_id"] == 42
        assert extras["user_id"] == 7
        assert extras["phase"] == "LOGGING"

    def test_get_structured_log_extras_defaults(self):
        """get_structured_log_extras must have sensible defaults when no context set."""
        extras = get_structured_log_extras()
        # These are the default values from ContextVar
        assert isinstance(extras["conversation_id"], str)
        assert isinstance(extras["company_id"], int)
        assert isinstance(extras["user_id"], int)


class TestKillSwitchOperations:
    """Kill switch must block endpoints and cancel plans via Redis."""

    def test_check_kill_switch_called_on_chat(self):
        """The _check_kill_switch function must be callable."""
        from backend.api.v1.copilot_router import _check_kill_switch
        assert callable(_check_kill_switch)

    def test_set_kill_switch_exists(self):
        """The _set_kill_switch management helper must exist."""
        from backend.api.v1.copilot_router import _set_kill_switch
        assert callable(_set_kill_switch)

    def test_cancel_inflight_plans_exists(self):
        """The _cancel_inflight_plans helper must exist."""
        from backend.api.v1.copilot_router import _cancel_inflight_plans
        assert callable(_cancel_inflight_plans)

    @patch('backend.cache.get_cache')
    def test_check_kill_switch_platform_blocks(self, mock_get_cache):
        """Platform-wide kill switch must raise 503."""
        from backend.api.v1.copilot_router import _check_kill_switch
        from fastapi import HTTPException
        
        mock_cache = MagicMock()
        mock_cache.get.return_value = True  # Kill switch engaged
        mock_get_cache.return_value = mock_cache
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_check_kill_switch(company_id=1))
        assert exc_info.value.status_code == 503

    @patch('backend.cache.get_cache')
    def test_check_kill_switch_company_blocks(self, mock_get_cache):
        """Per-company kill switch must raise 503 for that company."""
        from backend.api.v1.copilot_router import _check_kill_switch
        from fastapi import HTTPException
        
        mock_cache = MagicMock()
        # Platform returns False, company returns True
        mock_cache.get.side_effect = lambda key: True if "company:42" in key else False
        mock_get_cache.return_value = mock_cache
        
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_check_kill_switch(company_id=42))
        assert exc_info.value.status_code == 503

    @patch('backend.cache.get_cache')
    def test_check_kill_switch_allows_when_off(self, mock_get_cache):
        """Kill switch must not block when neither platform nor company is killed."""
        from backend.api.v1.copilot_router import _check_kill_switch
        
        mock_cache = MagicMock()
        mock_cache.get.return_value = False  # Kill switch off
        mock_get_cache.return_value = mock_cache
        
        # Should not raise
        asyncio.run(_check_kill_switch(company_id=1))


class TestExecutorOperations:
    """Executor guardrails and circuit breaker integration."""

    def test_execute_with_fallback_timeout(self):
        """execute_with_fallback must return fallback on timeout."""
        from backend.copilot.executor import execute_with_fallback

        async def slow_operation():
            await asyncio.sleep(10)
            return "done"

        result = asyncio.run(execute_with_fallback(
            slow_operation(),
            fallback_response="timeout_fallback",
            timeout_seconds=1,
        ))
        assert result == "timeout_fallback"

    def test_execute_with_fallback_cancelled_propagates(self):
        """execute_with_fallback must re-raise CancelledError."""
        from backend.copilot.executor import execute_with_fallback

        async def cancelled_op():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(execute_with_fallback(cancelled_op()))

    def test_execute_with_fallback_success(self):
        """execute_with_fallback must return the result on success."""
        from backend.copilot.executor import execute_with_fallback

        async def good_op():
            return "success_result"

        result = asyncio.run(execute_with_fallback(good_op()))
        assert result == "success_result"

    def test_validate_guardrails_checks_max_steps(self):
        """validate_guardrails must reject plans exceeding max steps."""
        from backend.copilot.executor import validate_guardrails, MAX_TOOL_CALLS_PER_PLAN
        from backend.copilot.schemas import (ConfirmationLevel, ExecutionPlan,
                                              ExecutionStep, Intent)
        
        steps = [ExecutionStep(
            step_id=f"s{i}", tool_name="test", tool_version="1.0.0",
            parameters={}, depends_on=[],
            confirmation_level=ConfirmationLevel.SAFE, status="pending",
        ) for i in range(MAX_TOOL_CALLS_PER_PLAN + 5)]
        
        plan = ExecutionPlan(
            plan_id="grd-test", conversation_id="test", reasoning_graph_id="test",
            intent=Intent(name="test", raw_utterance="test"),
            steps=steps, overall_confidence=1.0, requires_confirmation=False,
        )
        errors = validate_guardrails(plan)
        assert any("too_many_steps" in e for e in errors)

    def test_validate_guardrails_passes_normal(self):
        """validate_guardrails must pass normal-sized plans."""
        from backend.copilot.executor import validate_guardrails
        from backend.copilot.schemas import (ConfirmationLevel, ExecutionPlan,
                                              ExecutionStep, Intent)
        
        steps = [ExecutionStep(
            step_id=f"s{i}", tool_name="test", tool_version="1.0.0",
            parameters={}, depends_on=[],
            confirmation_level=ConfirmationLevel.SAFE, status="pending",
        ) for i in range(5)]
        
        plan = ExecutionPlan(
            plan_id="grd-pass", conversation_id="test", reasoning_graph_id="test",
            intent=Intent(name="test", raw_utterance="test"),
            steps=steps, overall_confidence=1.0, requires_confirmation=False,
        )
        errors = validate_guardrails(plan)
        assert len(errors) == 0, f"Normal plan should pass guardrails: {errors}"


class TestCircuitBreakerOperations:
    """Circuit breaker must trip on repeated failures and recover."""

    @pytest.fixture(autouse=True)
    def _reset_cb(self):
        from backend.copilot.circuit_breaker import get_circuit_breaker
        get_circuit_breaker()._states.clear()

    def test_breaker_starts_open(self):
        """Circuit breaker must start as allowed (not tripped)."""
        from backend.copilot.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.is_allowed(1) is True

    def test_breaker_trips_on_max_failures(self):
        """Circuit breaker must trip after max consecutive failures."""
        from backend.copilot.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        max_fails = cb._config.max_consecutive_failures
        for i in range(max_fails):
            cb.record_failure(1, "test.tool", f"error {i}")
        assert cb.is_allowed(1) is False

    def test_breaker_records_success_resets_failures(self):
        """A success after failures must reset the consecutive failure count."""
        from backend.copilot.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_failure(1, "test.tool", "error")
        cb.record_failure(1, "test.tool", "error")
        cb.record_success(1, "test.tool")
        state = cb.get_state(1)
        assert state.consecutive_failures == 0

    def test_breaker_per_company_isolation(self):
        """One company's failures must not affect another's state."""
        from backend.copilot.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        max_fails = cb._config.max_consecutive_failures
        for i in range(max_fails):
            cb.record_failure(1, "test.tool", "error")
        assert cb.is_allowed(1) is False
        assert cb.is_allowed(2) is True, "Company 2 should be unaffected"

    def test_breaker_admin_reset(self):
        """Admin reset must clear the tripped state."""
        from backend.copilot.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        max_fails = cb._config.max_consecutive_failures
        for i in range(max_fails):
            cb.record_failure(1, "test.tool", "error")
        assert cb.is_allowed(1) is False
        cb.reset(1)
        assert cb.is_allowed(1) is True
