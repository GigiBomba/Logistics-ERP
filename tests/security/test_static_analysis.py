"""Static analysis tests that scan the codebase for security issues.

These tests parse source files in ``backend/``, ``repositories/``, and
``services/`` looking for hardcoded secrets, unsafe calls, and weak
cryptographic practices.
"""

import ast
import os
import pathlib
from typing import Optional

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SOURCE_DIRS = ["backend", "repositories", "services"]
EXCLUDE_PATTERNS = ["__pycache__", ".venv", ".git"]


def _iter_source_files():
    """Yield all .py files in SOURCE_DIRS, skipping excluded dirs."""
    for d in SOURCE_DIRS:
        base = PROJECT_ROOT / d
        if not base.is_dir():
            continue
        for pyfile in base.rglob("*.py"):
            skip = any(patt in str(pyfile) for patt in EXCLUDE_PATTERNS)
            if not skip:
                yield pyfile


class TestHardcodedSecrets:
    """Scan for secrets or credentials hardcoded in source code."""

    def test_no_hardcoded_secrets_in_source(self):
        """Scan for variables named like password/secret/api_key assigned string literals.

        Excludes config.py (contains only empty defaults) and test files.
        """
        secret_keywords = {"password", "secret", "api_key", "api_secret", "token_key", "jwt_secret"}
        violations: list[str] = []

        for pyfile in _iter_source_files():
            # Skip config files (contain only empty/example defaults)
            if pyfile.name in ("config.py", "conftest.py"):
                continue
            try:
                tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue

            # Skip enum class bodies — enum member names like API_KEY_EXPIRED are
            # not real secrets, they are enum keys with arbitrary string values.
            enum_lines: set[int] = set()
            if isinstance(tree, ast.Module):
                for stmt in tree.body:
                    if isinstance(stmt, ast.ClassDef):
                        for base in stmt.bases:
                            if isinstance(base, ast.Name) and base.id == "Enum":
                                # This is an enum — skip all assignments in the body
                                end_ln = stmt.end_lineno or stmt.lineno
                                enum_lines = set(range(stmt.lineno, end_ln + 1))
                                break
                        else:
                            continue
                        break

            for node in ast.walk(tree):
                # Skip nodes that belong to an enum class body
                node_lineno = getattr(node, 'lineno', None)
                if node_lineno is not None and node_lineno in enum_lines:
                    continue

                # Plain assignment: x = "value"
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self._check_assignment(target.id, node.value, pyfile, node.lineno, violations)

                # Annotated assignment: x: str = "value"
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        self._check_assignment(node.target.id, node.value, pyfile, node.lineno, violations)

        if violations:
            pytest.fail(
                f"Potential hardcoded secrets found ({len(violations)} occurrence(s)):\n"
                + "\n".join(violations[:30])
            )

    @staticmethod
    def _check_assignment(
        var_name: str,
        value: Optional[ast.AST],
        pyfile: pathlib.Path,
        lineno: int,
        violations: list[str],
    ) -> None:
        """Append to *violations* if *var_name* looks like a secret with a non-empty string value."""
        name_lower = var_name.lower()
        # Settings-table key NAME constants: the identifier used to look up a
        # secret inside the settings store, NOT the secret itself.  They are
        # referenced by name (e.g. ``prefs.get_setting(TRACKING_API_KEY_KEY)``)
        # and their value is a dotted settings path, not a credential.
        SETTINGS_KEY_NAME_CONSTANTS = {
            "tracking_api_key_key",  # = "tracking.token" (backend/schemas/mobile.py)
        }
        if name_lower in SETTINGS_KEY_NAME_CONSTANTS:
            return
        secret_keywords = {"password", "secret", "api_key", "api_secret", "token_key", "jwt_secret"}
        if not any(kw in name_lower for kw in secret_keywords):
            return
        if value is None:
            return
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value:
            # Skip masked values (all asterisks) — those are placeholders, not real secrets
            if set(value.value.strip()) == {"*"}:
                return
            violations.append(f"{pyfile}:{lineno}: {var_name} = '***' (hardcoded string)")
        elif isinstance(value, ast.JoinedStr) and any(
            isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value
            for v in value.values
        ):
            violations.append(f"{pyfile}:{lineno}: {var_name} = f'...' (hardcoded f-string)")


class TestUnsafeCalls:
    """Scan for eval, exec, compile, unsafe subprocess, and pickle usage."""

    def test_no_unsafe_eval_or_exec(self):
        """Scan for eval(), exec(), compile() calls in source code (exclude test files)."""
        violations: list[str] = []

        for pyfile in _iter_source_files():
            # Skip test files
            if pyfile.name.startswith("test_") or pyfile.name == "conftest.py":
                continue
            try:
                tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "compile"):
                        violations.append(f"{pyfile}:{node.lineno}: {node.func.id}()")

        if violations:
            pytest.fail(
                f"Unsafe eval/exec/compile calls found ({len(violations)}):\n"
                + "\n".join(violations)
            )

    def test_no_unsafe_subprocess_shell(self):
        """Scan for shell=True in subprocess calls."""
        violations: list[pathlib.Path] = []

        for pyfile in _iter_source_files():
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
            if "shell=True" in content:
                violations.append(pyfile)

        if violations:
            pytest.fail(
                f"Files using shell=True in subprocess ({len(violations)}):\n"
                + "\n".join(str(v) for v in violations)
            )

    def test_no_unsafe_pickle(self):
        """Scan for pickle.loads or pickle.load in source code."""
        violations: list[pathlib.Path] = []

        for pyfile in _iter_source_files():
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
            if "pickle.load" in content:
                violations.append(pyfile)

        if violations:
            pytest.fail(
                f"Files using pickle.load ({len(violations)}):\n"
                + "\n".join(str(v) for v in violations)
            )

    def test_no_weak_randomness_for_crypto(self):
        """Scan for random module usage in source files (should use secrets).
        Skips files where random is used for non-crypto purposes (rate limiting, etc.).
        """
        violations: list[str] = []
        # Files where random is legitimately used for non-crypto purposes.
        # rate_limiter.py         — exponential-backoff jitter.
        # fleet_tracking_service.py — GPS poll backoff jitter
        #   (random.uniform(0, POLL_JITTER_MAX_SECONDS) to avoid stampeding a
        #   recovering partner; never used for tokens/keys/crypto).
        ALLOWED_RANDOM_USERS = {"rate_limiter.py", "fleet_tracking_service.py"}

        for pyfile in _iter_source_files():
            if pyfile.name in ALLOWED_RANDOM_USERS:
                continue
            try:
                tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "random":
                            violations.append(f"{pyfile}:{node.lineno}: import random")
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "random":
                        violations.append(f"{pyfile}:{node.lineno}: from random import ...")

        if violations:
            pytest.fail(
                f"Files using random module instead of secrets ({len(violations)}):\n"
                + "\n".join(violations)
            )


class TestInsecureProtocols:
    """Scan for imports of deprecated/insecure protocol libraries."""

    INSECURE_MODULES = ["telnetlib", "ftplib", "poplib"]

    def test_no_insecure_imports(self):
        """Scan for import telnetlib, import ftplib, import poplib (insecure protocols)."""
        violations: list[str] = []

        for pyfile in _iter_source_files():
            try:
                tree = ast.parse(pyfile.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.INSECURE_MODULES:
                            violations.append(
                                f"{pyfile}:{node.lineno}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module in self.INSECURE_MODULES:
                        violations.append(
                            f"{pyfile}:{node.lineno}: from {node.module} import ..."
                        )

        if violations:
            pytest.fail(
                f"Files importing insecure protocol modules ({len(violations)}):\n"
                + "\n".join(violations)
            )
