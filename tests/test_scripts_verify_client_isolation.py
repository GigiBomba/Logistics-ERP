"""Tests for scripts/verify_client_isolation.py — tenant isolation verification."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────


def _write_file(path: str, lines: list[str]) -> str:
    """Write a temporary Python file and return its path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return path


# ── _should_skip ───────────────────────────────────────────────────────────


class TestShouldSkip:
    @staticmethod
    def _skip(path: str) -> bool:
        from scripts.verify_client_isolation import _should_skip
        return _should_skip(path, "/root")

    def test_skip_cache_dirs(self):
        assert self._skip("/root/client/__pycache__/foo.py")

    def test_skip_init_py(self):
        assert self._skip("/root/client/__init__.py")

    def test_skip_allowlisted_file(self):
        assert self._skip("/root/client/cache.py")

    def test_skip_allowlisted_config(self):
        assert self._skip("/root/client/config.py")

    def test_do_not_skip_normal_file(self):
        assert not self._skip("/root/client/network.py")

    def test_do_not_skip_ui_file(self):
        assert not self._skip("/root/ui/main_view.py")


# ── _collect_python_files ──────────────────────────────────────────────────


class TestCollectPythonFiles:
    def test_collects_from_directory(self, tmp_path):
        from scripts.verify_client_isolation import _collect_python_files

        src = tmp_path / "ui"
        src.mkdir()
        (src / "main_view.py").write_text("")
        (src / "helper.py").write_text("")
        (src / "ignored.txt").write_text("")

        files = _collect_python_files(["ui"], str(tmp_path))
        assert len(files) == 2
        assert all(f.endswith(".py") for f in files)

    def test_collects_single_file(self, tmp_path):
        from scripts.verify_client_isolation import _collect_python_files

        main_py = tmp_path / "main.py"
        main_py.write_text("")

        files = _collect_python_files(["main.py"], str(tmp_path))
        assert files == [str(main_py)]

    def test_skips_nonexistent_root(self, tmp_path):
        from scripts.verify_client_isolation import _collect_python_files

        files = _collect_python_files(["nonexistent"], str(tmp_path))
        assert files == []

    def test_returns_sorted(self, tmp_path):
        from scripts.verify_client_isolation import _collect_python_files

        ui = tmp_path / "ui"
        ui.mkdir()
        (ui / "z_view.py").write_text("")
        (ui / "a_view.py").write_text("")

        files = _collect_python_files(["ui"], str(tmp_path))
        assert files[0].endswith("a_view.py")
        assert files[1].endswith("z_view.py")


# ── scan_file ──────────────────────────────────────────────────────────────


class TestScanFile:
    def test_detects_sqlite3_import(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "bad.py"), [
            "import sqlite3\n",
            "def foo(): pass\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert len(violations) == 1
        lineno, label, _ = violations[0]
        assert lineno == 1
        assert "sqlite3" in label

    def test_detects_database_import(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "bad.py"), [
            "from database import db_manager\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert len(violations) == 1
        assert "database" in violations[0][1]

    def test_detects_repositories_import(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "bad.py"), [
            "import repositories\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert len(violations) == 1
        assert "repositories" in violations[0][1]

    def test_detects_base_reference(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "bad.py"), [
            "x = BaseRepository()\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert len(violations) == 1
        assert "BaseRepository" in violations[0][1]

    def test_detects_db_path_string(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "bad.py"), [
            "DB_PATH = 'data/cashflow.db'\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert len(violations) == 1
        assert ".db" in violations[0][1]

    def test_clean_file_no_violations(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "clean.py"), [
            "import httpx\n",
            "from PySide6 import QtWidgets\n",
            "def render(): pass\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert violations == []

    def test_comment_lines_are_ignored(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "comment.py"), [
            "# import sqlite3\n",
            "# from database import something\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert violations == []

    def test_empty_file_no_violations(self, tmp_path):
        from scripts.verify_client_isolation import scan_file
        path = _write_file(os.path.join(tmp_path, "ui", "empty.py"), [])
        violations = scan_file(path, str(tmp_path))
        assert violations == []

    def test_skipped_file_returns_empty(self, tmp_path):
        from scripts.verify_client_isolation import scan_file
        path = _write_file(os.path.join(tmp_path, "client", "cache.py"), [
            "import sqlite3\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert violations == []

    def test_violation_snippet_truncated(self, tmp_path):
        """Snippet is capped at ~120 characters."""
        from scripts.verify_client_isolation import scan_file

        # Use .db pattern (matches anywhere on line) with a long prefix
        long_prefix = "x = " + "A" * 150
        path = _write_file(os.path.join(tmp_path, "ui", "long.py"), [
            long_prefix + "test.db\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert len(violations) == 1
        assert len(violations[0][2]) <= 120


# ── scan_file: multiple violations per file ────────────────────────────────


class TestScanFileMultipleViolations:
    def test_multiple_violations_reported(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "multi.py"), [
            "import sqlite3\n",
            "from database import db\n",
            "import repositories\n",
        ])
        violations = scan_file(path, str(tmp_path))
        assert len(violations) == 3

    def test_first_match_only_per_line(self, tmp_path):
        from scripts.verify_client_isolation import scan_file

        path = _write_file(os.path.join(tmp_path, "ui", "overlap.py"), [
            "import sqlite3; from database import db\n",
        ])
        violations = scan_file(path, str(tmp_path))
        # Only the first pattern match per line is reported (break after match)
        assert len(violations) == 1


# ── main() ─────────────────────────────────────────────────────────────────


class TestMain:
    def test_returns_zero_when_clean(self, tmp_path):
        from scripts.verify_client_isolation import main

        # Create a realistic project structure
        ui = tmp_path / "ui"
        ui.mkdir()
        (ui / "clean.py").write_text("import httpx\n")
        (ui / "__init__.py").write_text("")

        # Point __file__ into tmp_path so base_dir = tmp_path
        fake_file = str(tmp_path / "scripts" / "verify_client_isolation.py")
        with (
            patch("scripts.verify_client_isolation.SCAN_ROOTS", ["ui"]),
            patch("scripts.verify_client_isolation.__file__", fake_file),
        ):
            rc = main()
            assert rc == 0

    def test_returns_one_when_violations_found(self, tmp_path):
        from scripts.verify_client_isolation import main

        ui = tmp_path / "ui"
        ui.mkdir()
        (ui / "bad.py").write_text("import sqlite3\n")

        fake_file = str(tmp_path / "scripts" / "verify_client_isolation.py")
        with (
            patch("scripts.verify_client_isolation.SCAN_ROOTS", ["ui"]),
            patch("scripts.verify_client_isolation.__file__", fake_file),
        ):
            rc = main()
            assert rc == 1

    def test_remote_mode_scans_main_remote(self, tmp_path):
        from scripts.verify_client_isolation import main

        client = tmp_path / "client"
        client.mkdir()
        (client / "remote_handler.py").write_text("import httpx\n")
        main_remote = tmp_path / "main_remote.py"
        main_remote.write_text("import sys\n")

        fake_file = str(tmp_path / "scripts" / "verify_client_isolation.py")
        with (
            patch("scripts.verify_client_isolation.sys.argv", ["script.py", "--remote"]),
            patch("scripts.verify_client_isolation.SCAN_ROOTS", ["main_remote.py", "client"]),
            patch("scripts.verify_client_isolation.__file__", fake_file),
        ):
            rc = main()
            assert rc == 0

    def test_main_with_mixed_roots(self, tmp_path):
        """Some roots are files, some are directories."""
        from scripts.verify_client_isolation import main

        ui = tmp_path / "ui"
        ui.mkdir()
        (ui / "view.py").write_text("import httpx\n")
        main_py = tmp_path / "main.py"
        main_py.write_text("import sys\n")

        fake_file = str(tmp_path / "scripts" / "verify_client_isolation.py")
        with (
            patch("scripts.verify_client_isolation.SCAN_ROOTS", ["ui", "main.py"]),
            patch("scripts.verify_client_isolation.__file__", fake_file),
        ):
            rc = main()
            assert rc == 0
