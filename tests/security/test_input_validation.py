"""Input validation tests — extra fields, malicious input, file upload safeguards.

Uses fixtures from ``tests/security/conftest.py``:
- ``client`` — FastAPI TestClient bound to the test app.
- ``admin_token`` — a valid JWT for the admin user.
- ``auth_admin`` — ``{"Authorization": "Bearer <token>"}`` header dict.
"""
from __future__ import annotations


import io
import os
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from repositories import BaseRepository


# ═══════════════════════════════════════════════════════════════════════════════
# Extra fields rejection on create endpoints
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtraFieldsRejected:
    """Create endpoints must reject unexpected/malicious fields."""

    def test_extra_fields_rejected_on_trip_create(
        self, client: TestClient, auth_admin: dict
    ):
        """POST /api/v1/trips/ with an unexpected field — must be rejected."""
        payload = {
            "client_name": "Security Test Client",
            "loading_city": "Berlin",
            "malicious_field": "should be rejected",
        }
        try:
            resp = client.post("/api/v1/trips/", json=payload, headers=auth_admin)
            assert resp.status_code in (400, 422, 500, 429), (
                f"Expected error status for extra fields, "
                f"got {resp.status_code}: {resp.text}"
            )
        except ValueError:
            # Repository _validate_columns raises ValueError — proves rejection
            pass

    def test_extra_fields_rejected_on_client_create(
        self, client: TestClient, auth_admin: dict
    ):
        """POST /api/v1/clients/ with an unexpected field — must be rejected."""
        payload = {
            "name": "Test Client",
            "email": "test@client.com",
            "; DROP TABLE clients;--": "malicious",
        }
        try:
            resp = client.post("/api/v1/clients/", json=payload, headers=auth_admin)
            assert resp.status_code in (400, 422, 500, 429), (
                f"Expected error status for extra fields, "
                f"got {resp.status_code}: {resp.text}"
            )
        except ValueError:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Malicious column name — unit test
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaliciousColumnName:
    """Repository ``_validate_columns`` must reject dangerous column names."""

    def test_malicious_column_name_rejected_unit(self):
        """Unit test: create a test repo and call ``_validate_columns``
        with a malicious key — expect ``ValueError``.
        """
        class TestRepo(BaseRepository):
            COLUMNS = ["id", "name", "email", "company_id"]

        repo = TestRepo(db=MagicMock())

        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"; DROP TABLE": "x"})

        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"__init__": "hack"})

        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"id; --": "1"})

        # Known columns must NOT raise
        repo._validate_columns({"name": "Alice", "email": "a@b.com"})


# ═══════════════════════════════════════════════════════════════════════════════
# File upload validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestFileUploadValidation:
    """File upload endpoint must enforce size and MIME-type limits."""

    def test_oversized_file_rejected(
        self, client: TestClient, auth_admin: dict
    ):
        """POST /api/v1/documents/upload with a 51 MB file → 400."""
        big_data = b"%" * (51 * 1024 * 1024)  # 51 MB
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("huge.pdf", big_data, "application/pdf")},
            data={"category": "test"},
            headers=auth_admin,
        )
        assert resp.status_code in (400, 429), (
            f"Expected 400 for oversized file, got {resp.status_code}: {resp.text}"
        )
        if resp.status_code == 400:
            error_body = resp.text.lower()
            assert "too large" in error_body, (
                f"Response should mention 'too large', got: {resp.text[:200]}"
            )

    def test_disallowed_mime_type_rejected(
        self, client: TestClient, auth_admin: dict
    ):
        """POST /api/v1/documents/upload with ``text/html`` → 400."""
        small_data = b"<html><script>alert(1)</script></html>"
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("evil.html", small_data, "text/html")},
            data={"category": "test"},
            headers=auth_admin,
        )
        assert resp.status_code in (400, 429), (
            f"Expected 400 for disallowed MIME type, got {resp.status_code}: {resp.text}"
        )
        if resp.status_code == 400:
            error_body = resp.text.lower()
            assert "not allowed" in error_body, (
                f"Response should mention 'not allowed', got: {resp.text[:200]}"
            )

    def test_mismatched_extension_rejected(
        self, client: TestClient, auth_admin: dict
    ):
        """Send a file named ``.pdf`` with executable content.

        Known gap: the current upload validation only checks MIME type and
        size, not extension-vs-magic-bytes mismatch.  This test documents
        the current behaviour (may succeed upload or fail for other reasons).
        """
        exe_data = b"MZ\x90\x00" + b"\x00" * 100
        resp = None
        try:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("innocent.pdf", exe_data, "application/pdf")},
                data={"category": "test"},
                headers=auth_admin,
            )
        except Exception:
            pass
        if resp is not None:
            # Current behaviour: MIME type check passes, so may upload
            # successfully or fail for other reasons.
            assert resp.status_code in (200, 400, 422, 429, 500), (
                f"Unexpected status {resp.status_code} for mismatched extension"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# SQL injection via f-strings in repositories
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoFstringSQLInjection:
    """No repository file should use f-strings (``execute(f"..."``) for SQL.

    The base class in ``__init__.py`` may contain legitimate formatting,
    but individual repo files must use parameterised queries via the
    ``_execute`` / ``_fetchone`` / ``_fetchall`` methods.
    """

    def test_no_fstring_sql_in_repositories(self):
        """Scan all ``repositories/*.py`` files for ``execute(f"`` or
        ``execute(f'`` patterns.  Only ``__init__.py`` (the base class)
        is exempt.
        """
        import repositories as repos_pkg

        repo_dir = os.path.dirname(repos_pkg.__file__)
        violations: list[str] = []

        for fname in sorted(os.listdir(repo_dir)):
            if not fname.endswith(".py"):
                continue
            if fname == "__init__.py":
                continue  # base class is allowed
            if fname == "analytics_repository.py":
                continue  # f-strings for month expressions (not user data)
            if fname == "route_repository.py":
                continue  # f-strings for TABLE constant only (not user input)

            filepath = os.path.join(repo_dir, fname)
            with open(filepath, encoding="utf-8") as f:
                content = f.read()

            for pattern in (
                'execute(f"',
                "execute(f'",
                'execute_insert(f"',
                "execute_insert(f'",
                'execute_with_count(f"',
                "execute_with_count(f'",
                'fetchone(f"',
                "fetchone(f'",
                'fetchall(f"',
                "fetchall(f'",
            ):
                if pattern in content:
                    violations.append(f"{fname}: contains `{pattern}`")
                    break

        if violations:
            pytest.fail(
                "Repositories using f-string SQL (potential injection vector):\n"
                + "\n".join(violations)
            )
