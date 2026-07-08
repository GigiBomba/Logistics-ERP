"""Secrets-management security tests.

Verify that secret files are gitignored, not tracked, that
constant-time comparison is used, and that the ``jose`` JWT
library is not imported anywhere in source.
"""

import os
import subprocess
import pathlib


# ═══════════════════════════════════════════════════════════════════════
# Git / .gitignore checks
# ═══════════════════════════════════════════════════════════════════════

class TestGitSecretFiles:
    """Sensitive env files must be excluded from version control."""

    PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"
    EXPECTED_ENTRIES = ("admin.env", "securityprompt.env", ".env")

    def test_env_files_gitignored(self):
        """Read .gitignore and confirm the expected entries are present."""
        assert self.GITIGNORE_PATH.is_file(), ".gitignore not found"
        content = self.GITIGNORE_PATH.read_text(encoding="utf-8")

        for entry in self.EXPECTED_ENTRIES:
            assert entry in content, (
                f"'{entry}' not found in .gitignore — "
                f"it may be accidentally tracked"
            )

    def test_admin_env_not_tracked(self):
        """git ls-files must report admin.env as untracked (non-zero exit)."""
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "admin.env"],
            cwd=self.PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        # Non-zero exit code means the file is NOT tracked (expected)
        assert result.returncode != 0, (
            f"admin.env is tracked in git!\n{result.stdout}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Cryptographic practices
# ═══════════════════════════════════════════════════════════════════════

class TestCryptoPractices:
    """Verify constant-time comparison and banned JWT library usage."""

    AUTH_MIDDLEWARE_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / \
        "backend" / "middleware" / "auth_middleware.py"
    SOURCE_DIRS = (
        pathlib.Path(__file__).resolve().parent.parent.parent / "backend",
        pathlib.Path(__file__).resolve().parent.parent.parent / "repositories",
    )

    def test_hmac_compare_digest_used(self):
        """auth_middleware.py must use hmac.compare_digest."""
        assert self.AUTH_MIDDLEWARE_PATH.is_file(), (
            f"auth_middleware.py not found at {self.AUTH_MIDDLEWARE_PATH}"
        )
        source = self.AUTH_MIDDLEWARE_PATH.read_text(encoding="utf-8")
        assert "hmac.compare_digest" in source, (
            "auth_middleware.py does not use hmac.compare_digest — "
            "may be vulnerable to timing attacks"
        )

    def test_no_jose_imports_in_source(self):
        """No .py file in backend/ or repositories/ should import ``jose``.

        The ``python-jose`` library has known vulnerabilities and should
        not be used.  Use ``PyJWT`` instead.
        """
        banned_patterns = ("from jose import", "import jose")
        offending: list[str] = []

        for source_dir in self.SOURCE_DIRS:
            if not source_dir.is_dir():
                continue
            for py_file in source_dir.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                for pattern in banned_patterns:
                    if pattern in content:
                        offending.append(f"{py_file} contains '{pattern}'")

        assert not offending, (
            "Found banned jose imports:\n" + "\n".join(offending)
        )
