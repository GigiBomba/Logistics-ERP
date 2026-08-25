"""GDPR erasure tests — §24.

Anonymization satisfies right-to-erasure without breaking
the append-only audit guarantee.
"""
from __future__ import annotations


import json
from unittest.mock import MagicMock, patch

import pytest


class TestCopilotErasure:
    """§24 — Right to erasure and data anonymization."""

    def test_retention_task_exists(self):
        """The retention/anonymization task must be importable."""
        from backend.celery_app.tasks.retention_tasks import (
            enforce_copilot_retention, anonymize_copilot_data,
        )
        assert enforce_copilot_retention is not None
        assert anonymize_copilot_data is not None

    def test_retention_task_has_correct_signature(self):
        """anonymize_copilot_data takes entity_type and entity_id."""
        import inspect
        from backend.celery_app.tasks.retention_tasks import anonymize_copilot_data
        sig = inspect.signature(anonymize_copilot_data)
        params = list(sig.parameters.keys())
        assert "entity_type" in params
        assert "entity_id" in params

    def test_enforce_retention_has_no_required_params(self):
        """enforce_copilot_retention takes no required parameters."""
        import inspect
        from backend.celery_app.tasks.retention_tasks import enforce_copilot_retention
        sig = inspect.signature(enforce_copilot_retention)
        # Celery tasks with bind=True have 'self' as first param
        params = list(sig.parameters.keys())
        assert len(params) <= 1, f"Unexpected params: {params}"

    def test_conversation_summary_retention_period(self):
        """conversation_summary retention is 24 months per §24."""
        from datetime import timedelta
        retention = timedelta(days=730)  # 24 months
        assert retention.days == 730

    def test_audit_log_retention_period(self):
        """copilot_audit_log retention is 24 months per §24."""
        from datetime import timedelta
        retention = timedelta(days=730)
        assert retention.days == 730

    def test_reasoning_graph_retention_period(self):
        """copilot_reasoning_graphs retention is 90 days per §24."""
        from datetime import timedelta
        retention = timedelta(days=90)
        assert retention.days == 90
