"""Application logging tests — §29.

Structured log format, PII exclusion, correct log levels.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.telemetry import get_structured_log_extras


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
