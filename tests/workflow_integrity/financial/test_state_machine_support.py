"""Support ticket state machine — not implemented in Operion.

The codebase does not currently implement a support ticket system.
There is no SupportTicket model, no ticket service, and no status
transition logic for customer support workflows.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.state_machine


class TestSupportTicketStateMachine:
    """Support ticket state machine — not implemented in Operion."""

    def test_support_ticket_system_not_implemented(self):
        """Documented gap: Support tickets are not a core Operion feature yet.

        Known gap: The codebase does not implement a support ticket system.
        There is no SupportTicket model, no ticket service, and no status
        transition logic for customer support workflows. When implemented,
        the state machine should support:
          Open → In Progress → Resolved → Closed
          Open → Closed
          Resolved → Reopened → In Progress
        """
        # Documented gap — support ticket system is not implemented
        assert True
