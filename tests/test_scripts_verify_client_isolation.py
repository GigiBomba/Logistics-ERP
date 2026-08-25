"""Tests for scripts/verify_client_isolation.py — local-first build verifier.

Phase F: the desktop app is no longer a remote-only shell (main_remote.py is
deprecated); the production build targets main.py and MUST include the local
SQLite DB, repositories and the offline-first sync stack.  The script now
verifies the build configuration rather than scanning for forbidden imports.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestRequiredModules:
    def test_sync_stack_modules_are_declared(self):
        import scripts.verify_client_isolation as v

        assert "services.sync_engine" in v.REQUIRED_MODULES
        assert "services.sync_outbox_service" in v.REQUIRED_MODULES
        assert "services.sync_pull_service" in v.REQUIRED_MODULES
        assert "services.device_identity" in v.REQUIRED_MODULES
        assert "database.schema" in v.REQUIRED_MODULES

    def test_sync_related_excludes_never_allowed(self):
        import scripts.verify_client_isolation as v

        # These were excluded by the OLD remote-only build and would break
        # the local-first app if excluded again.
        assert "database" in v.SYNC_RELATED_EXCLUDES_NEVER_ALLOWED
        assert "repositories" in v.SYNC_RELATED_EXCLUDES_NEVER_ALLOWED
        assert "services" in v.SYNC_RELATED_EXCLUDES_NEVER_ALLOWED
        assert "services.operations" in v.SYNC_RELATED_EXCLUDES_NEVER_ALLOWED


class TestMain:
    def test_returns_zero_on_clean_local_first_config(self):
        from scripts.verify_client_isolation import main

        rc = main()
        assert rc == 0

    def test_fails_when_build_excludes_database(self):
        import scripts.verify_client_isolation as v

        with patch.object(
            v, "EXCLUDE_MODULES", ["backend", "tests", "database"]
        ):
            rc = v.main()
            assert rc == 1

    def test_fails_when_build_excludes_services(self):
        import scripts.verify_client_isolation as v

        with patch.object(
            v, "EXCLUDE_MODULES", ["backend", "tests", "services"]
        ):
            rc = v.main()
            assert rc == 1

    def test_fails_when_sync_module_missing_on_disk(self, tmp_path):
        import scripts.verify_client_isolation as v

        fake_root = tmp_path
        (fake_root / "main.py").write_text("")
        (fake_root / "database").mkdir()
        (fake_root / "repositories").mkdir()
        (fake_root / "services").mkdir()
        with (
            patch.object(v, "PROJECT_ROOT", fake_root),
            patch.object(v, "EXCLUDE_MODULES", ["backend", "tests"]),
        ):
            rc = v.main()
            # services/sync_engine.py etc. do not exist in the fake tree.
            assert rc == 1

    def test_remote_entry_is_not_the_build_entry(self):
        """main_remote.py may still exist as a deprecated file, but the build
        must target main.py — the verifier only requires main.py to exist."""
        import scripts.verify_client_isolation as v

        assert (v.PROJECT_ROOT / "main.py").is_file()


class TestImportClosureScan:
    """The restored import-closure scan: a shipped module must never import an
    excluded module (backend/celery/redis/...) UNGUARDED at top level."""

    def _make_tree(self, tmp_path, files):
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    def test_clean_tree_no_violations(self, tmp_path):
        import scripts.verify_client_isolation as v

        self._make_tree(tmp_path, {
            "main.py": "import os\nfrom utils.security import hash_password\n",
            "ui/view.py": "import httpx\n",
        })
        with (
            patch.object(v, "PROJECT_ROOT", tmp_path),
            patch.object(v, "DESKTOP_CLOSURE_ROOTS", ["main.py", "ui"]),
        ):
            assert v.scan_import_closure() == []

    def test_unguarded_import_fails(self, tmp_path):
        import scripts.verify_client_isolation as v

        self._make_tree(tmp_path, {
            "main.py": "from backend.security import hash_password\n",
        })
        with (
            patch.object(v, "PROJECT_ROOT", tmp_path),
            patch.object(v, "DESKTOP_CLOSURE_ROOTS", ["main.py"]),
        ):
            violations = v.scan_import_closure()
            assert len(violations) == 1
            rel, lineno, code = violations[0]
            assert "backend" in code
            assert lineno == 1

    def test_guarded_import_passes(self, tmp_path):
        """try/except ImportError is the accepted guarded pattern."""
        import scripts.verify_client_isolation as v

        self._make_tree(tmp_path, {
            "main.py": (
                "try:\n"
                "    from backend.middleware.correlation_middleware import get_correlation_id\n"
                "except ImportError:\n"
                "    def get_correlation_id() -> str:\n"
                "        return ''\n"
            ),
        })
        with (
            patch.object(v, "PROJECT_ROOT", tmp_path),
            patch.object(v, "DESKTOP_CLOSURE_ROOTS", ["main.py"]),
        ):
            assert v.scan_import_closure() == []

    def test_function_level_import_passes(self, tmp_path):
        """Imports inside functions are lazy — allowed."""
        import scripts.verify_client_isolation as v

        self._make_tree(tmp_path, {
            "main.py": (
                "def f():\n"
                "    from backend.cache import get_cache\n"
                "    return get_cache()\n"
            ),
        })
        with (
            patch.object(v, "PROJECT_ROOT", tmp_path),
            patch.object(v, "DESKTOP_CLOSURE_ROOTS", ["main.py"]),
        ):
            assert v.scan_import_closure() == []

    def test_main_fails_on_unguarded_import(self, tmp_path):
        import scripts.verify_client_isolation as v

        self._make_tree(tmp_path, {
            "main.py": "import os\n",
            "ui/bad.py": "from backend.config import BackendSettings\n",
        })
        with (
            patch.object(v, "PROJECT_ROOT", tmp_path),
            patch.object(v, "DESKTOP_CLOSURE_ROOTS", ["main.py", "ui"]),
            patch.object(v, "EXCLUDE_MODULES", ["backend", "tests"]),
        ):
            rc = v.main()
            assert rc == 1

    def test_real_tree_is_clean(self):
        """The current desktop closure must have zero unguarded imports."""
        import scripts.verify_client_isolation as v

        assert v.scan_import_closure() == []


@pytest.fixture(autouse=True)
def _module_importable():
    """The rewritten script must import cleanly (no leftover scan symbols)."""
    import scripts.verify_client_isolation
    assert hasattr(scripts.verify_client_isolation, "main")
    assert hasattr(scripts.verify_client_isolation, "REQUIRED_MODULES")
    assert hasattr(scripts.verify_client_isolation, "scan_import_closure")
    assert not hasattr(scripts.verify_client_isolation, "FORBIDDEN_IMPORTS")
