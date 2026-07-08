"""QWebEngine Chromium flags for ghost-window suppression.

When PySide6 loads ``QWebEngineWidgets``, it starts a child Chromium
process (``QtWebEngineProcess.exe``) for GPU compositing, crash
reporting, and network services.  On Windows this process creates
transient top-level windows that flash in the corner of the screen
at startup.

These environment variables must be set **before** any PySide6 import
that transitively triggers ``from PySide6.QtWebEngineWidgets import
QWebEngineView``, otherwise the Qt WebEngine bootstrap already
consumed the default (empty) flags and the Chromium child process
launches with its own default GPU/renderer configuration.

Usage
-----
    from utils.webengine_flags import apply_webengine_flags
    apply_webengine_flags()          # call at the very top of main.py
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger(__name__)

# Chromium flags that suppress every known source of transient top-level
# windows on Windows.  These mirror the flags we add to the chart_export
# Chrome instance via ``_SilentChromium.get_cli()``.
#
# NOTE: ``--disable-gpu`` is intentionally absent — it conflicts with
# ``--headless=new`` / QtWebEngine's modern rendering path and causes
# Chromium to fall back to a software-rendered window that appears as
# a visible gray box on the desktop.  We use the more targeted
# ``--disable-gpu-compositing`` + ``--disable-software-rasterizer``
# instead, which suppress GPU window artefacts without breaking the
# entire GPU pipeline.
_SILENT_FLAGS: list[str] = [
    "--disable-gpu-compositing",
    "--disable-software-rasterizer",
    "--no-sandbox",
    "--disable-breakpad",
    "--disable-features=VizDisplayCompositor",
    "--disable-crashpad-for-testing",
    "--disable-background-networking",
    "--disable-component-extensions-with-background-pages",
    "--disable-extensions",
    "--disable-sync",
    "--no-first-run",
    "--no-default-browser-check",
]

_FLAG_VAR = "QTWEBENGINE_CHROMIUM_FLAGS"


def apply_webengine_flags() -> None:
    """Set ``QTWEBENGINE_CHROMIUM_FLAGS`` if not already configured.

    This function is idempotent — calling it multiple times does not
    duplicate flags.  If the variable is already set (e.g. from a
    previous test run), the existing flags are preserved and the
    silent flags are only appended if missing.
    """
    existing = os.environ.get(_FLAG_VAR, "").strip()
    # Collect all flags already present.
    existing_set = set(existing.split())
    missing = [f for f in _SILENT_FLAGS if f not in existing_set]

    if not missing:
        _log.debug("QWebEngine flags already up to date")
        return

    combined = (existing + " " + " ".join(missing)).strip()
    os.environ[_FLAG_VAR] = combined
    _log.info(
        "QWebEngine flags set (%d added, %d total): %s",
        len(missing),
        len(combined.split()),
        combined,
    )
