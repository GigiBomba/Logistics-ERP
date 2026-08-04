"""S1-S5: Soft friction rule tests.

S1-S4 are UI-layer concerns requiring browser/device test infrastructure.
S5 (auto-save) is partially testable at service layer.
"""
from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.friction


class TestMaxClicksForCommonOps:
    """S1: Max 3 clicks for common operations — UI-layer concern."""

    def test_max_clicks_common_ops(self):
        """S1: Would need Playwright/browser to verify click counts."""
        pass  # Documented gap — requires UI testing


class TestWorkflowCompletionVisibility:
    """S2: Workflow completion visibility — UI-layer concern."""

    def test_workflow_completion_visibility(self):
        """S2: Would need Playwright/browser to verify UX."""
        pass  # Documented gap


class TestConfirmationOnDestructiveActions:
    """S3: Confirmation on destructive actions — partially testable."""

    def test_confirmation_on_destructive_actions(self):
        """S3: Would need Playwright/browser to verify UX confirmation dialogs."""
        pass  # Documented gap — requires UI testing


class TestUndoForMultiEdit:
    """S4: Undo support for multi-edit operations."""

    def test_undo_for_multi_edit(self):
        """S4: Would need Playwright/browser to verify undo UX."""
        pass  # Documented gap — requires UI testing


class TestAutoSaveOfInProgress:
    """S5: Auto-save of in-progress work."""

    def test_invoice_draft_persisted_immediately(
        self, workflow_env, invoice_service, db
    ):
        """Invoice draft is persisted immediately after create()."""
        from tests.workflow_integrity.personas import build_elena_persona
        from models.invoice_models import InvoiceCreate

        ids = build_elena_persona(db)
        result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                trip_id=ids["trip_ids"]["delivered"][0],
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
            ),
        )
        assert result.success, f"Invoice creation failed: {result.errors}"
        row = db.conn.execute(
            "SELECT id, status FROM invoices WHERE id = ?",
            (result.data.id,),
        ).fetchone()
        assert row is not None, "Invoice should be persisted immediately"
        assert row["status"] == "draft"
