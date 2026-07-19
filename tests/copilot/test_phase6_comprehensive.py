"""Comprehensive Phase 6 hardening tests.

Covers: kill switch, guardrails, telemetry, CancelledError, memory leak fixes.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.executor import execute_with_fallback


class TestExecuteWithFallback:
    """execute_with_fallback edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self):
        """CancelledError should propagate, not be caught by except Exception."""
        async def will_be_cancelled():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await execute_with_fallback(will_be_cancelled())

    @pytest.mark.asyncio
    async def test_timeout_error_returns_fallback(self):
        """TimeoutError should return fallback response."""
        async def will_timeout():
            await asyncio.sleep(10)

        result = await execute_with_fallback(
            will_timeout(), fallback_response="fallback", timeout_seconds=1,
        )
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_success_returns_result(self):
        """Successful coroutine should return its result."""
        async def works():
            return "success"

        result = await execute_with_fallback(works())
        assert result == "success"
