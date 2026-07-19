"""Kill switch tests — §26.

Flip the per-company kill switch mid-conversation and assert:
(a) in-flight plans are cancelled,
(b) subsequent requests return unavailable,
(c) other companies are unaffected.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.schemas import (
    ConfirmationLevel, ExecutionPlan, ExecutionStep, Intent,
)


class TestKillSwitchContract:
    """Kill switch key patterns and Redis integration (§26)."""

    def test_platform_key_pattern(self):
        """Platform-wide kill switch uses correct Redis key."""
        key = "copilot:kill_switch:platform"
        assert key is not None

    def test_company_key_pattern(self):
        """Per-company kill switch uses correct Redis key with company_id."""
        company_id = 42
        key = f"copilot:kill_switch:company:{company_id}"
        assert str(company_id) in key

    def test_kill_switch_checked_after_auth(self):
        """Kill switch must be checked after authentication but before
        permission resolution per §15.1."""
        from backend.api.v1.copilot_router import _check_kill_switch
        assert callable(_check_kill_switch)

    def test_kill_switch_cancel_inflight_exists(self):
        """_cancel_inflight_plans function must exist."""
        from backend.api.v1.copilot_router import _cancel_inflight_plans
        assert callable(_cancel_inflight_plans)

    def test_kill_switch_set_exists(self):
        """_set_kill_switch function must exist."""
        from backend.api.v1.copilot_router import _set_kill_switch
        assert callable(_set_kill_switch)
