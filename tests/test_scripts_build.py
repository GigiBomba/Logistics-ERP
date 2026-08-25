"""Tests for scripts/build_client.py — PyInstaller build configuration."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_pyinstaller_imports():
    """Prevent any actual PyInstaller import during tests."""
    with (
        patch("scripts.build_client.subprocess") as mock_sp,
        patch("scripts.build_client.shutil") as mock_sh,
    ):
        mock_sp.run.return_value = MagicMock(returncode=0)
        yield


# ── Module-level constants ─────────────────────────────────────────────────


class TestModuleConstants:
    def test_project_root_is_path(self):
        import scripts.build_client

        assert isinstance(scripts.build_client.PROJECT_ROOT, Path)

    def test_project_root_points_to_parent_of_scripts(self):
        import scripts.build_client

        assert (scripts.build_client.PROJECT_ROOT / "scripts").resolve() == Path(
            __file__
        ).resolve().parent.parent / "scripts"

    def test_dist_dir_is_correct(self):
        import scripts.build_client

        expected = scripts.build_client.PROJECT_ROOT / "dist" / "operion-client"
        assert scripts.build_client.DIST_DIR == expected

    def test_work_dir_is_correct(self):
        import scripts.build_client

        expected = scripts.build_client.PROJECT_ROOT / "build" / "client"
        assert scripts.build_client.WORK_DIR == expected

    def test_client_assets_contains_expected_paths(self):
        import scripts.build_client

        root = scripts.build_client.PROJECT_ROOT
        assert str(root / "ui") in scripts.build_client.CLIENT_ASSETS
        assert str(root / "client") in scripts.build_client.CLIENT_ASSETS
        assert str(root / "config.py") in scripts.build_client.CLIENT_ASSETS
        assert str(root / "main.py") in scripts.build_client.CLIENT_ASSETS

    def test_exclude_modules_excludes_backend(self):
        """Server-only + test tooling stay excluded from the desktop binary."""
        import scripts.build_client

        assert "backend" in scripts.build_client.EXCLUDE_MODULES
        assert "backend.api.v1" in scripts.build_client.EXCLUDE_MODULES
        assert "tests" in scripts.build_client.EXCLUDE_MODULES
        assert "celery" in scripts.build_client.EXCLUDE_MODULES

    def test_exclude_modules_keeps_local_first_stack(self):
        """Phase F: the local-first build must NOT exclude the sync stack —
        the old remote-only build excluded these; the new one includes them."""
        import scripts.build_client

        excluded = set(scripts.build_client.EXCLUDE_MODULES)
        assert "database" not in excluded
        assert "database.db_manager" not in excluded
        assert "database.schema" not in excluded
        assert "repositories" not in excluded
        assert "services" not in excluded
        assert "services.sync_engine" not in excluded
        assert "services.operations" not in excluded
        assert "services.document" not in excluded

    def test_exclude_modules_excludes_test_frameworks(self):
        import scripts.build_client

        assert "unittest" in scripts.build_client.EXCLUDE_MODULES
        assert "pytest" in scripts.build_client.EXCLUDE_MODULES

    def test_hidden_imports_contains_qt(self):
        import scripts.build_client

        assert "PySide6.QtCore" in scripts.build_client.HIDDEN_IMPORTS
        assert "PySide6.QtWidgets" in scripts.build_client.HIDDEN_IMPORTS

    def test_hidden_imports_contains_client_modules(self):
        import scripts.build_client

        assert "client.config" in scripts.build_client.HIDDEN_IMPORTS
        assert "client.api_client" in scripts.build_client.HIDDEN_IMPORTS


# ── _clean_dist ────────────────────────────────────────────────────────────


class TestCleanDist:
    def test_removes_dist_and_work_dirs(self):
        with patch("scripts.build_client.DIST_DIR") as mock_dist, \
             patch("scripts.build_client.WORK_DIR") as mock_work, \
             patch("scripts.build_client.shutil") as mock_sh:

            mock_dist.exists.return_value = True
            mock_work.exists.return_value = True

            import scripts.build_client
            scripts.build_client._clean_dist()

            assert mock_sh.rmtree.call_count == 2

    def test_does_not_fail_if_dirs_missing(self):
        with patch("scripts.build_client.DIST_DIR") as mock_dist, \
             patch("scripts.build_client.WORK_DIR") as mock_work, \
             patch("scripts.build_client.shutil") as mock_sh:

            mock_dist.exists.return_value = False
            mock_work.exists.return_value = False

            import scripts.build_client
            scripts.build_client._clean_dist()

            mock_sh.rmtree.assert_not_called()


# ── _run_pyinstaller ───────────────────────────────────────────────────────


class TestRunPyinstaller:
    def test_builds_command_with_entry_point(self):
        with patch("scripts.build_client.subprocess") as mock_sp, \
             patch("scripts.build_client.sys.executable", "python"):
            mock_sp.run.return_value = MagicMock(returncode=0)

            import scripts.build_client
            rc = scripts.build_client._run_pyinstaller("main_remote.py")

            assert rc == 0
            mock_sp.run.assert_called_once()

    def test_excludes_specified_modules(self):
        with patch("scripts.build_client.subprocess") as mock_sp, \
             patch("scripts.build_client.sys.executable", "python"):
            mock_sp.run.return_value = MagicMock(returncode=0)

            import scripts.build_client
            scripts.build_client._run_pyinstaller("main.py", extra_excludes=["extra_mod"])

            call_args = mock_sp.run.call_args[0][0]
            assert "--exclude-module" in call_args
            assert "extra_mod" in call_args

    def test_hidden_imports_included(self):
        with patch("scripts.build_client.subprocess") as mock_sp, \
             patch("scripts.build_client.sys.executable", "python"):
            mock_sp.run.return_value = MagicMock(returncode=0)

            import scripts.build_client
            scripts.build_client._run_pyinstaller("main.py")

            call_args = mock_sp.run.call_args[0][0]
            assert "--hidden-import" in call_args
            # At least one hidden import should be present
            hidden_idx = call_args.index("--hidden-import")
            assert hidden_idx >= 0


# ── _report_size ──────────────────────────────────────────────────────────


class TestReportSize:
    def test_reports_size_for_small_build(self, capsys):
        import scripts.build_client

        base = Path(__file__).parent  # use test dir as a small directory
        scripts.build_client._report_size(base)
        captured = capsys.readouterr()
        assert "Build size:" in captured.out
        assert "MB" in captured.out

    def test_no_warning_for_small_build(self, capsys):
        import scripts.build_client

        base = Path(__file__).parent
        scripts.build_client._report_size(base)
        captured = capsys.readouterr()
        # Should NOT contain the 100 MB warning
        assert "WARNING" not in captured.out


# ── main() ─────────────────────────────────────────────────────────────────


class TestMain:
    def test_main_production_build(self):
        with (
            patch("scripts.build_client.sys.argv", ["build_client.py"]),
            patch("scripts.build_client._clean_dist") as mock_clean,
            patch("scripts.build_client._run_pyinstaller", return_value=0) as mock_run,
        ):
            import scripts.build_client
            rc = scripts.build_client.main()

            assert rc == 0
            mock_clean.assert_called_once()
            # Phase F: production mode → entry is main.py (local-first),
            # NOT the deprecated main_remote.py.
            entry_arg = mock_run.call_args[0][0]
            assert "main.py" in entry_arg
            assert "main_remote.py" not in entry_arg

    def test_main_dev_build(self):
        with (
            patch("scripts.build_client.sys.argv", ["build_client.py", "--dev"]),
            patch("scripts.build_client._clean_dist") as mock_clean,
            patch("scripts.build_client._run_pyinstaller", return_value=0) as mock_run,
        ):
            import scripts.build_client
            rc = scripts.build_client.main()

            assert rc == 0
            mock_clean.assert_called_once()
            # Dev mode → entry is main.py
            entry_arg = mock_run.call_args[0][0]
            assert "main.py" in entry_arg

    def test_main_returns_nonzero_on_pyinstaller_failure(self):
        with (
            patch("scripts.build_client.sys.argv", ["build_client.py"]),
            patch("scripts.build_client._clean_dist"),
            patch("scripts.build_client._run_pyinstaller", return_value=1),
        ):
            import scripts.build_client
            rc = scripts.build_client.main()
            assert rc == 1

    def test_main_production_extra_excludes(self):
        """Phase F: the production build no longer passes any extra excludes —
        the local-first app needs services.document / services.invoicing / etc."""
        with (
            patch("scripts.build_client.sys.argv", ["build_client.py"]),
            patch("scripts.build_client._clean_dist"),
            patch("scripts.build_client._run_pyinstaller") as mock_run,
        ):
            import scripts.build_client
            scripts.build_client.main()

            _args, kwargs = mock_run.call_args
            extra = kwargs.get("extra_excludes")
            assert extra is None, f"local-first build passed stale excludes: {extra}"

    def test_main_dev_no_extra_excludes(self):
        with (
            patch("scripts.build_client.sys.argv", ["build_client.py", "--dev"]),
            patch("scripts.build_client._clean_dist"),
            patch("scripts.build_client._run_pyinstaller") as mock_run,
        ):
            import scripts.build_client
            scripts.build_client.main()

            _args, kwargs = mock_run.call_args
            extra = kwargs.get("extra_excludes")
            assert extra is None or extra == []


# ── Importability ──────────────────────────────────────────────────────────


class TestModuleImportability:
    def test_module_can_be_imported(self):
        """scripts.build_client can be imported without SyntaxError or ImportError
        (with subprocess/shutil mocked)."""
        with patch("scripts.build_client.subprocess"), \
             patch("scripts.build_client.shutil"):
            import scripts.build_client  # noqa: F811
            assert hasattr(scripts.build_client, "main")
            assert hasattr(scripts.build_client, "_clean_dist")
            assert hasattr(scripts.build_client, "_run_pyinstaller")
            assert hasattr(scripts.build_client, "_report_size")
