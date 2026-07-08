"""Tests for _SilentChromium, _browser_kwargs, and window_suppressor.

Verifies:
1. get_cli() strips old --headless and adds all required new flags
2. get_popen_args() includes CREATE_NO_WINDOW on Windows
3. _browser_kwargs() provides a persistent tmp_dir
4. configure_choreographer_export / shutdown_browser_sync
   start and stop the window suppressor cleanly
"""

from __future__ import annotations

import os
import platform
import tempfile
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

import utils.chart_export as ce


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_engine():
    """Replace the real engine singleton with a mock after each test.

    We set a MagicMock rather than ``None`` so that async QThreadPool
    render workers that outlive the test boundary never see
    ``_ENGINE is None`` and attempt to start real Chrome.
    """
    mock = MagicMock(spec=ce._RenderEngine)
    mock.submit.return_value = b"<svg>mock</svg>"
    with ce._ENGINE_LOCK:
        saved = ce._ENGINE
        ce._ENGINE = mock
    yield
    with ce._ENGINE_LOCK:
        ce._ENGINE = saved


@pytest.fixture
def mock_engine():
    """Mock _RenderEngine singleton."""
    engine = MagicMock(spec=ce._RenderEngine)
    engine.submit.return_value = b"<svg>mock</svg>"
    with ce._ENGINE_LOCK:
        ce._ENGINE = engine
    yield engine


# ── _SilentChromium.get_cli() tests ───────────────────────────────────

class TestGetCli:
    """Verify the Chrome CLI flags produced by _SilentChromium."""

    def test_removes_old_headless_flag(self):
        """The old --headless must be stripped to avoid flag conflict."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        # Choreographer always adds --headless (default True)
        mock_wrapped.get_cli.return_value = [
            "/path/to/chrome",
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
        ]
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()

        assert "--headless" not in cli, (
            "Old --headless flag must be stripped to prevent "
            "conflict with --headless=new"
        )

    def test_includes_headless_new(self):
        """--headless=new must be present."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_cli.return_value = ["/path/to/chrome"]
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()

        assert "--headless=new" in cli

    def test_includes_crashpad_disabled(self):
        """--disable-crashpad-for-testing must be present."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_cli.return_value = ["/path/to/chrome"]
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()

        assert "--disable-crashpad-for-testing" in cli, (
            "Crashpad reporter must be disabled to prevent "
            "crashpad_handler.exe creating windows"
        )

    def test_includes_disable_software_rasterizer(self):
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_cli.return_value = ["/path/to/chrome"]
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()
        assert "--disable-software-rasterizer" in cli

    def test_includes_all_protective_flags(self):
        """Verify the full set of ghost-window protective flags."""
        required_exact = {
            "--headless=new",
            "--disable-software-rasterizer",
            "--disable-crashpad-for-testing",
            "--disable-gpu-compositing",
            "--disable-background-networking",
            "--no-default-browser-check",
            "--no-first-run",
        }
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_cli.return_value = ["/path/to/chrome"]
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()
        cli_flags = set(cli)

        missing = required_exact - cli_flags
        assert not missing, f"Missing required CLI flags: {missing}"

        # --user-data-dir is special (value includes a temp path); check prefix
        assert any(
            f.startswith("--user-data-dir=") and "operion_chrome_profile" in f
            for f in cli
        ), "A --user-data-dir pointing to operion_chrome_profile must be present"

    def test_does_not_duplicate_existing_flags(self):
        """Flags that the base Chromium class already emits must not be
        duplicated by _SilentChromium's extra flag list."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        # Simulate base Chromium already providing some of these
        base = [
            "/path/to/chrome",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-breakpad",
            "--no-first-run",  # Choreographer already adds this
        ]
        mock_wrapped.get_cli.return_value = list(base)
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()
        # Should only appear once
        assert cli.count("--no-first-run") == 1, (
            "--no-first-run should not be duplicated"
        )
        # --disable-gpu is intentionally stripped (conflicts with
        # --headless=new).  We keep the more targeted
        # --disable-gpu-compositing instead.
        assert "--disable-gpu" not in cli, (
            "--disable-gpu must be stripped to avoid conflict with"
            " --headless=new (new headless mode requires GPU)"
        )

    def test_strips_disable_gpu_keeps_gpu_compositing(self):
        """--disable-gpu from the base class must be stripped, but
        --disable-gpu-compositing must be present (new headless mode
        needs GPU, so we use the targeted compositing disable instead)."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_cli.return_value = [
            "/path/to/chrome",
            "--disable-gpu",
            "--headless",
        ]
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()
        assert "--disable-gpu" not in cli, (
            "--disable-gpu must be stripped to avoid conflict with new headless"
        )
        assert "--disable-gpu-compositing" in cli, (
            "--disable-gpu-compositing must be present as the safer alternative"
        )

    def test_strips_base_user_data_dir(self):
        """The --user-data-dir from the base Chromium class must be
        stripped and replaced with our persistent dir."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_cli.return_value = [
            "/path/to/chrome",
            "--user-data-dir=C:\\temp\\choreo_tmp_xxx",
            "--disable-gpu",
        ]
        wrapper._wrapped = mock_wrapped

        cli = wrapper.get_cli()
        # Old temp-based user-data-dir must be removed
        old = [f for f in cli if f == "--user-data-dir=C:\\temp\\choreo_tmp_xxx"]
        assert not old, "Old temp user-data-dir must be stripped"

        # Our persistent dir must be present
        our = [f for f in cli if f.startswith("--user-data-dir=") and "operion_chrome_profile" in f]
        assert our, "Persistent operion_chrome_profile --user-data-dir must be present"
        assert len(our) == 1, "--user-data-dir must appear exactly once"

    def test_all_flags_are_strings(self):
        """Every CLI argument must be a string (subprocess safety)."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_cli.return_value = ["/path/to/chrome"]
        wrapper._wrapped = mock_wrapped

        for arg in wrapper.get_cli():
            assert isinstance(arg, str), f"CLI arg is not a string: {arg!r}"


# ── _SilentChromium.get_popen_args() tests ────────────────────────────

class TestGetPopenArgs:
    """Subprocess creation flags must prevent console windows on Windows."""

    def test_includes_create_no_window_on_windows(self):
        """On Windows, CREATE_NO_WINDOW flag must be present."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_popen_args.return_value = {
            "creationflags": 0x00000200,  # CREATE_NEW_PROCESS_GROUP
            "close_fds": False,
        }
        wrapper._wrapped = mock_wrapped

        args = wrapper.get_popen_args()

        if platform.system() == "Windows":
            import subprocess
            assert args.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW, (
                "CREATE_NO_WINDOW must be set in creationflags on Windows"
            )
        # On non-Windows, the method should not modify args
        else:
            assert "creationflags" in args

    def test_includes_startupinfo_sw_hide_on_windows(self):
        """On Windows, STARTUPINFO with SW_HIDE must be present."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_popen_args.return_value = {
            "creationflags": 0x00000200,
            "close_fds": False,
        }
        wrapper._wrapped = mock_wrapped

        args = wrapper.get_popen_args()

        if platform.system() == "Windows":
            import subprocess
            si = args.get("startupinfo")
            assert si is not None, "startupinfo must be set on Windows"
            assert si.dwFlags & subprocess.STARTF_USESHOWWINDOW, (
                "STARTF_USESHOWWINDOW must be set in startupinfo.dwFlags"
            )
            assert si.wShowWindow == subprocess.SW_HIDE, (
                "wShowWindow must be SW_HIDE (0)"
            )

    def test_preserves_existing_creationflags(self):
        """Existing creationflags must not be overwritten, only extended."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        existing = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        mock_wrapped.get_popen_args.return_value = {
            "creationflags": existing,
            "close_fds": False,
        }
        wrapper._wrapped = mock_wrapped

        args = wrapper.get_popen_args()

        if platform.system() == "Windows":
            # The original flag must still be set
            assert args["creationflags"] & existing, (
                "Original CREATE_NEW_PROCESS_GROUP must be preserved"
            )

    def test_graceful_when_no_creationflags(self):
        """When the wrapped class returns no creationflags, it must not crash."""
        wrapper = ce._SilentChromium.__new__(ce._SilentChromium)
        mock_wrapped = MagicMock()
        mock_wrapped.get_popen_args.return_value = {}
        wrapper._wrapped = mock_wrapped

        args = wrapper.get_popen_args()
        assert isinstance(args, dict)


# ── _browser_kwargs() tests ───────────────────────────────────────────

class TestBrowserKwargs:
    """Verify the kwargs passed to Choreographer's Browser."""

    def test_uses_persistent_tmp_dir(self):
        """tmp_dir must point to a persistent (not temporary) directory."""
        kwargs = ce._browser_kwargs()
        tmp_dir = kwargs.get("tmp_dir", "")
        assert tmp_dir, "tmp_dir must be set"
        assert os.path.exists(tmp_dir), f"tmp_dir {tmp_dir} must exist"
        assert "operion_chrome_profile" in tmp_dir, (
            "tmp_dir name must contain the application profile identifier"
        )

    def test_tmp_dir_is_persistent_across_calls(self):
        """Calling _browser_kwargs() multiple times returns the same dir."""
        dir1 = ce._browser_kwargs()["tmp_dir"]
        dir2 = ce._browser_kwargs()["tmp_dir"]
        assert dir1 == dir2, "tmp_dir must be consistent across calls"

    def test_uses_silent_chromium(self):
        """browser_cls must be _SilentChromium."""
        kwargs = ce._browser_kwargs()
        assert kwargs.get("browser_cls") is ce._SilentChromium, (
            "browser_cls must be _SilentChromium"
        )

    def test_gpu_and_sandbox_disabled(self):
        """GPU and sandbox must be explicitly disabled."""
        kwargs = ce._browser_kwargs()
        assert kwargs.get("enable_gpu") is False
        assert kwargs.get("enable_sandbox") is False

    def test_includes_chrome_path_when_set(self):
        """When _CHROME_PATH is set, the 'path' kwarg must be included."""
        saved = ce._CHROME_PATH
        ce._CHROME_PATH = "/custom/chrome/path"
        try:
            kwargs = ce._browser_kwargs()
            assert kwargs.get("path") == "/custom/chrome/path"
        finally:
            ce._CHROME_PATH = saved

    def test_omits_chrome_path_when_not_set(self):
        """When _CHROME_PATH is None, 'path' must not be in kwargs
        (Choreographer will auto-discover the browser)."""
        saved = ce._CHROME_PATH
        ce._CHROME_PATH = None
        try:
            kwargs = ce._browser_kwargs()
            assert "path" not in kwargs
        finally:
            ce._CHROME_PATH = saved


# ── configure / shutdown integration tests ────────────────────────────

class TestConfigureChoreographerExport:
    """Integration tests for configure_choreographer_export."""

    @patch("utils.chart_export._get_engine")
    def test_starts_engine(self, mock_get_engine):
        """configure_choreographer_export must start the Chrome engine."""
        engine = MagicMock()
        mock_get_engine.return_value = engine
        ce.configure_choreographer_export()
        engine.start.assert_called_once_with(block=True)


class TestShutdownBrowserSync:
    """Verify shutdown_browser_sync."""

    @patch("utils.chart_export._get_engine")
    def test_shutdown_delegates_to_engine(self, mock_get_engine):
        """shutdown_browser_sync must shut down the engine."""
        engine = MagicMock()
        mock_get_engine.return_value = engine
        ce.shutdown_browser_sync()
        engine.shutdown.assert_called_once()


# ── Persistent profile directory test ─────────────────────────────────

class TestPersistentProfileDir:
    """The default persistent profile directory must exist and be writable."""

    def test_suppressor_default_profile_dir_exists(self):
        profile_dir = ce._PERSISTENT_PROFILE_DIR
        assert os.path.exists(profile_dir), (
            f"Profile directory {profile_dir} must be created by _ensure_profile_dir"
        )
        assert os.access(profile_dir, os.W_OK), (
            f"Profile directory {profile_dir} must be writable"
        )
