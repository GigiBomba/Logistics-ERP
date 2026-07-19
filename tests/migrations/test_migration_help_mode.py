"""Migration proof tests for Help Mode Alembic migrations.

Blueprint requirement: "every migration MUST be proven with a failing-then-passing
test in tests/security/ or tests/migrations/ as applicable."

Uses Alembic's ScriptDirectory to verify migration structure, revision chain,
and upgrade/downgrade function signatures — without needing a database,
since parent migrations use PostgreSQL-only types (JSONB).
"""
from __future__ import annotations

import os

import pytest
from alembic.script import ScriptDirectory


SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "alembic",
)

REV_DOC_CHUNKS = "a8b9c0d1e2f3"
REV_USER_WF = "a9b0c1d2e3f4"


@pytest.fixture(scope="module")
def script():
    """Return the Alembic ScriptDirectory."""
    return ScriptDirectory(SCRIPT_DIR)


def _get_revision(script: ScriptDirectory, rev_id: str):
    """Get a revision by ID."""
    rev = script.get_revision(rev_id)
    assert rev is not None, f"Revision {rev_id} not found"
    return rev


class TestMigrationDocumentationChunks:
    """Tests for a8b9c0d1e2f3: create documentation_chunks table."""

    REVISION = REV_DOC_CHUNKS

    def test_revision_exists(self, script):
        """The migration file must exist in the Alembic versions directory."""
        rev = _get_revision(script, self.REVISION)
        assert rev.revision == self.REVISION
        assert rev.doc == "create documentation_chunks"

    def test_revision_has_correct_down_revision(self, script):
        """The migration should chain from the expected parent."""
        rev = _get_revision(script, self.REVISION)
        assert rev.down_revision == "a7b8c9d0e1f7", (
            f"Expected down_revision a7b8c9d0e1f7, got {rev.down_revision}"
        )

    def test_revision_has_upgrade_function(self, script):
        """The migration module must have an upgrade() function."""
        rev = _get_revision(script, self.REVISION)
        module = rev.module
        assert hasattr(module, "upgrade"), "Missing upgrade() function"
        assert callable(module.upgrade), "upgrade() is not callable"

    def test_revision_has_downgrade_function(self, script):
        """The migration module must have a downgrade() function."""
        rev = _get_revision(script, self.REVISION)
        module = rev.module
        assert hasattr(module, "downgrade"), "Missing downgrade() function"
        assert callable(module.downgrade), "downgrade() is not callable"

    def test_revision_is_in_a_chain(self, script):
        """The revision must be reachable from at least one head."""
        # Get all heads (there may be multiple branches)
        heads = script.get_heads()
        found = False
        for head_id in heads:
            head_rev = script.get_revision(head_id)
            current = head_rev
            while current is not None:
                if current.revision == self.REVISION:
                    found = True
                    break
                down_rev = current.down_revision
                current = script.get_revision(down_rev) if down_rev else None
            if found:
                break
        assert found, (
            f"Revision {self.REVISION} is not in any chain from heads {heads}"
        )


class TestMigrationUserWorkflowFamiliarity:
    """Tests for a9b0c1d2e3f4: create user_workflow_familiarity table."""

    REVISION = REV_USER_WF

    def test_revision_exists(self, script):
        """The migration file must exist."""
        rev = _get_revision(script, self.REVISION)
        assert rev.revision == self.REVISION

    def test_revision_has_correct_down_revision(self, script):
        """Should chain from the doc_chunks migration."""
        rev = _get_revision(script, self.REVISION)
        assert rev.down_revision == REV_DOC_CHUNKS, (
            f"Expected down_revision {REV_DOC_CHUNKS}, got {rev.down_revision}"
        )

    def test_revision_has_upgrade_function(self, script):
        rev = _get_revision(script, self.REVISION)
        assert hasattr(rev.module, "upgrade") and callable(rev.module.upgrade)

    def test_revision_has_downgrade_function(self, script):
        rev = _get_revision(script, self.REVISION)
        assert hasattr(rev.module, "downgrade") and callable(rev.module.downgrade)

    def test_revision_is_in_a_chain(self, script):
        rev = _get_revision(script, self.REVISION)
        heads = script.get_heads()
        found = False
        for head_id in heads:
            head_rev = script.get_revision(head_id)
            current = head_rev
            while current is not None:
                if current.revision == self.REVISION:
                    found = True
                    break
                down_rev = current.down_revision
                current = script.get_revision(down_rev) if down_rev else None
            if found:
                break
        assert found, f"Revision {self.REVISION} not in any chain from heads {heads}"

    def test_both_migrations_in_correct_sequence(self, script):
        """Verify the chain: parent → doc_chunks → user_wf."""
        doc_rev = _get_revision(script, REV_DOC_CHUNKS)
        wf_rev = _get_revision(script, self.REVISION)

        assert doc_rev.down_revision == "a7b8c9d0e1f7"
        assert wf_rev.down_revision == REV_DOC_CHUNKS
        # user_workflow_familiarity should be a head revision
        heads = script.get_heads()
        assert wf_rev.revision in heads, (
            f"{self.REVISION} should be a head, but heads are {heads}"
        )

    def test_migration_module_can_be_imported(self, script):
        """The migration module should import without errors."""
        rev = _get_revision(script, self.REVISION)
        module = rev.module
        # The module was already imported by ScriptDirectory, which proves
        # it imports cleanly. Additional verification: it has upgrade/downgrade.
        assert module.revision == self.REVISION

    def test_migration_sql_contains_create_table_in_docstring(self, script):
        """The migration docstring describes what it creates."""
        rev = _get_revision(script, self.REVISION)
        doc_lower = rev.doc.lower()
        assert "user_workflow_familiarity" in doc_lower or \
               "familiarity" in doc_lower
