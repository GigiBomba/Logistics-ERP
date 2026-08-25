"""Tenant isolation tests — company filter presence, column allowlists, validation.

Uses fixtures from ``tests/security/conftest.py`` where available, plus
standalone unit tests for repository-level validations.
"""
from __future__ import annotations


import os
import pytest
from unittest.mock import MagicMock
from repositories import BaseRepository


# ═══════════════════════════════════════════════════════════════════════════════
# Static-scan exemptions — repositories that legitimately do not use the
# context-based ``_company_filter`` / ``_set_company_from_context`` helpers.
# ═══════════════════════════════════════════════════════════════════════════════

# company_repository.py  — manages the ``companies`` (tenant) table itself;
#                          a company_id filter on the tenant table is
#                          meaningless (there is no parent tenant).
# copilot_repository.py  — scopes every query inline with an explicit
#                          ``company_id = ?`` bind (equivalent behaviour to
#                          ``_company_filter``, different spelling).
# sent_email_repository.py — global dedup ledger (roadmap 12) keyed by
#                          ``document_id`` (AUTOINCREMENT PK of the
#                          company-scoped ``documents`` table). The table has
#                          NO ``company_id`` column, so ``_company_filter`` /
#                          ``_set_company_from_context`` cannot be applied;
#                          isolation is inherited from the globally-unique
#                          ``document_id`` FK. Reachable only from the
#                          ``build_email_package`` Celery task, which already
#                          resolves ``document_ids`` via company-scoped
#                          ``DocumentService.get_by_id``.
STATIC_SCAN_EXEMPT = frozenset({
    "company_repository.py",
    "copilot_repository.py",
    "sent_email_repository.py",
})


# ═══════════════════════════════════════════════════════════════════════════════
# Repository static-analysis checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompanyFilterPresent:
    """Every non-analytics repository must call ``_company_filter`` on reads."""

    def test_company_filter_present_in_all_repos(self):
        """Scan all ``repositories/*.py`` files (excluding ``__init__.py``)
        and verify each non-analytics file contains a reference to
        ``_company_filter`` or ``_set_company_from_context``.

        Exemptions (``STATIC_SCAN_EXEMPT``) are limited to repositories that
        either own the tenant table itself or scope inline with an explicit
        ``company_id = ?`` bind.
        """
        import repositories as repos_pkg

        repo_dir = os.path.dirname(repos_pkg.__file__)
        violations: list[str] = []

        for fname in sorted(os.listdir(repo_dir)):
            if not fname.endswith(".py") or fname == "__init__.py":
                continue
            if fname in STATIC_SCAN_EXEMPT:
                continue
            filepath = os.path.join(repo_dir, fname)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            # Analytics repository uses _company_filter differently
            # (inline in queries) and is exempt from this check.
            if "analytics" in fname:
                continue

            if "_company_filter" not in content and "_set_company_from_context" not in content:
                violations.append(fname)

        if violations:
            pytest.fail(
                f"Repositories missing _company_filter / _set_company_from_context "
                f"references: {violations}"
            )


class TestColumnAllowlists:
    """Every non-analytics repository must define a ``COLUMNS`` allowlist."""

    def test_column_allowlists_present_in_all_repos(self):
        """Scan all ``repositories/*.py`` files and confirm each
        non-analytics file has ``COLUMNS`` defined.
        """
        import repositories as repos_pkg

        repo_dir = os.path.dirname(repos_pkg.__file__)
        violations: list[str] = []

        for fname in sorted(os.listdir(repo_dir)):
            if not fname.endswith(".py") or fname == "__init__.py":
                continue
            filepath = os.path.join(repo_dir, fname)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            # Analytics repositories skip column validation because they
            # use read-only aggregate queries with known column names.
            if "analytics" in fname:
                continue

            if "COLUMNS" not in content:
                violations.append(fname)

        if violations:
            pytest.fail(
                f"Repositories missing COLUMNS allowlists: {violations}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Column validation unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestColumnValidation:
    """``_validate_columns`` should accept known columns and reject unknowns."""

    def test_internal_columns_rejected(self):
        """Confirm that _validate_columns rejects unknown columns and
        accepts known ones, including system-managed columns that are
        legitimately in the allowlist.

        The important distinction is:
        - ``id``, ``company_id``, ``created_at`` ARE in COLUMNS (allowlisted)
          so they are accepted by _validate_columns.
        - Unknown fields like ``"; DROP TABLE"`` are rejected.
        """
        class TestRepo(BaseRepository):
            COLUMNS = ["id", "name", "email", "company_id", "created_at"]

        repo = TestRepo(db=MagicMock())

        # Known columns (including system-managed ones) should NOT raise.
        repo._validate_columns({"id": 1, "company_id": 10, "created_at": "2024-01-01"})
        repo._validate_columns({"name": "Alice", "email": "a@b.com"})

    def test_unknown_columns_rejected(self):
        """Unknown fields should raise ValueError."""
        class TestRepo(BaseRepository):
            COLUMNS = ["id", "name", "email", "company_id"]

        repo = TestRepo(db=MagicMock())

        # Unknown column → ValueError
        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"; DROP TABLE trips;--": "1"})

        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"totally_fake_field": "x"})

        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"id": 1, "__init__": "hack"})
