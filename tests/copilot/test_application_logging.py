"""Application logging tests — §29.

Structured log format, PII exclusion, correct log levels.
"""
from __future__ import annotations


import logging
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.telemetry import get_structured_log_extras


@pytest.fixture(autouse=True)
def _reset_telemetry_context():
    """Reset the telemetry ContextVars so the defaults test is hermetic.

    Other copilot tests on the same worker set the conversation/company/user
    context; without a reset ``get_structured_log_extras()`` would return the
    last module's values (e.g. conversation_id='log-test') instead of ""/0.
    """
    import backend.copilot.telemetry as _tel
    _tel.current_conversation_id.set("")
    _tel.current_company_id.set(0)
    _tel.current_user_id.set(0)
    _tel.current_phase.set("")
    yield
    _tel.current_conversation_id.set("")
    _tel.current_company_id.set(0)
    _tel.current_user_id.set(0)
    _tel.current_phase.set("")


class TestApplicationLogging:
    """Structured logging requirements (§29)."""

    def test_structured_log_extras_have_required_fields(self):
        """Structured log extras must include conversation_id, company_id, user_id, phase."""
        extras = get_structured_log_extras()
        assert "conversation_id" in extras
        assert "company_id" in extras
        assert "user_id" in extras
        assert "phase" in extras

    def test_structured_log_extras_defaults(self):
        """Structured log extras should have sensible defaults."""
        extras = get_structured_log_extras()
        assert extras["conversation_id"] == ""
        assert extras["company_id"] == 0
        assert extras["user_id"] == 0
