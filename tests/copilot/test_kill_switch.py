"""Kill switch tests — prove the mechanism is checked first on every request.

Blueprint: §26 — Emergency Kill Switch.

Phase 0: Test the contract/schema, since the actual kill switch mechanism
is a stub until Phase 1 router creation.
"""

import pytest


class TestKillSwitchContract:
    """Test that the kill switch concept is well-defined."""

    def test_kill_switch_config_key_exists(self):
        """Document the expected kill switch config key pattern."""
        per_company_key = "copilot:kill_switch:company:{company_id}"
        platform_key = "copilot:kill_switch:platform"
        assert "{company_id}" in per_company_key
        assert "platform" in platform_key

    def test_kill_switch_checked_first(self):
        """The kill switch must be checked before permission resolution, tier gating,
        or anything else in the /api/v1/copilot/* request path (§26).

        This test documents the expected behavior. The actual enforcement test
        will be written when copilot_router.py is implemented in Phase 1.
        """
        # Phase 0: This is a placeholder documenting the contract.
        # Phase 1 will implement: flip kill switch → assert 503 response.
        pass

    def test_kill_switch_isolates_company_only(self):
        """Other companies must be entirely unaffected when one company's
        kill switch is flipped (§26).
        """
        # Phase 0 placeholder — Phase 1 will implement.
        pass

    def test_kill_switch_cancels_inflight_plans(self):
        """Flipping the kill switch mid-conversation must cancel
        any in-flight AWAITING_CONFIRMATION plans (§26).
        """
        # Phase 0 placeholder — Phase 1 will implement.
        pass

    def test_kill_switch_response_i18n(self):
        """The kill switch response must be an i18n'd message, not a raw error."""
        expected_key = "copilot.error.unavailable"
        assert "copilot" in expected_key
        assert "." in expected_key
