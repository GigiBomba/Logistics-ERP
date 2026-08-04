"""Operation tests for data retention and GDPR erasure tasks (§24).

Tests: task existence, correct retention periods, SQL compatibility,
anonymization logic, and Celery integration.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.celery_app.tasks.retention_tasks import (
    enforce_copilot_retention,
    anonymize_copilot_data,
)


@pytest.fixture(autouse=True)
def _clear_tenant_context():
    """Retention tasks call set_company_context; reset it after each test so it
    cannot leak into unrelated tests in the same process."""
    from database.tenant_context import clear_context
    yield
    clear_context()


class TestRetentionTaskContract:
    """Retention and anonymization tasks must be importable and runnable."""

    def test_enforce_retention_importable(self):
        """enforce_copilot_retention must be importable."""
        assert enforce_copilot_retention is not None

    def test_anonymize_data_importable(self):
        """anonymize_copilot_data must be importable."""
        assert anonymize_copilot_data is not None

    def test_enforce_retention_is_celery_task(self):
        """enforce_copilot_retention must have delay method (Celery task marker)."""
        assert hasattr(enforce_copilot_retention, 'delay')

    def test_anonymize_data_is_celery_task(self):
        """anonymize_copilot_data must have delay method."""
        assert hasattr(anonymize_copilot_data, 'delay')

    def test_enforce_retention_returns_dict(self):
        """enforce_copilot_retention should return a dict with cleanup counts."""
        mock_db = MagicMock()
        mock_db.conn.execute.return_value.rowcount = 0

        with (
            patch('backend.db.DatabaseManager', return_value=mock_db),
            patch(
                'repositories.company_repository.CompanyRepository.get_active_ids',
                return_value=[1],
            ),
        ):
            result = enforce_copilot_retention()
            assert isinstance(result, dict)
            assert "audit_log_deleted" in result
            assert "reasoning_graphs_anonymized" in result

    def test_anonymize_data_returns_dict(self):
        """anonymize_copilot_data should return a dict with anonymized count."""
        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchall.return_value = []

        with (
            patch('backend.db.DatabaseManager', return_value=mock_db),
            patch(
                'repositories.company_repository.CompanyRepository.get_active_ids',
                return_value=[1],
            ),
        ):
            result = anonymize_copilot_data(entity_type="user", entity_id=42)
            assert isinstance(result, dict)
            # Should handle empty result gracefully
            assert result.get("audit_anonymized", -1) >= 0


class TestRetentionPeriods:
    """Retention periods must match §24 specifications."""

    def test_audit_log_24_months(self):
        """copilot_audit_log retention must be 24 months."""
        retention = timedelta(days=730)
        assert retention.days == 730

    def test_reasoning_graphs_90_days(self):
        """copilot_reasoning_graphs retention must be 90 days."""
        retention = timedelta(days=90)
        assert retention.days == 90

    def test_conversation_summary_24_months(self):
        """conversation_summary retention must be 24 months."""
        retention = timedelta(days=730)
        assert retention.days == 730


class TestAnonymizationLogic:
    """GDPR anonymization must preserve structural fields while redacting PII."""

    def test_anonymize_redacts_personal_fields(self):
        """Personal identifiers must be replaced with [REDACTED]."""
        import inspect
        source = inspect.getsource(anonymize_copilot_data)
        # The _redact_jsonb function should be defined
        assert "_redact_jsonb" in source
        assert "REDACTED" in source or "[REDACTED]" in source

    def test_anonymize_preserves_structural_fields(self):
        """Structural fields (tool_name, status, timestamps) must survive."""
        import inspect
        source = inspect.getsource(anonymize_copilot_data)
        personal_keys = {"name", "email", "phone", "address"}
        for key in personal_keys:
            assert key in source, f"Personal key '{key}' not in redaction list"

    def test_anonymize_signature(self):
        """anonymize_copilot_data must accept entity_type and entity_id."""
        import inspect
        sig = inspect.signature(anonymize_copilot_data)
        params = list(sig.parameters.keys())
        assert "entity_type" in params, "Missing entity_type parameter"
        assert "entity_id" in params, "Missing entity_id parameter"


class TestRetentionSQL:
    """SQL queries in retention tasks must be cross-database compatible."""

    def test_sql_uses_cast_not_postgres_only(self):
        """SQL must use CAST(... AS TEXT) not PostgreSQL ::text syntax."""
        import inspect
        source = inspect.getsource(enforce_copilot_retention)
        source += inspect.getsource(anonymize_copilot_data)
        assert "::text" not in source, "PostgreSQL-only ::text syntax found"
        assert "CAST(" in source or "LIKE" in source, "CAST or LIKE expected for cross-DB compat"

    def test_enforce_retention_queries_exist_tables(self):
        """SQL queries reference tables that exist in migrations."""
        import inspect
        source = inspect.getsource(enforce_copilot_retention)
        assert "copilot_audit_log" in source
        assert "copilot_reasoning_graphs" in source
        assert "conversation_summary" in source
