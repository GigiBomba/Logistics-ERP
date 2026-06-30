"""Resource path resolution for development and PyInstaller-packaged mode.

Usage::

    from utils.resource_path import resource_path, data_path

    # Read-only bundled asset (translations, configs)
    path = resource_path("data/translations/en.json")

    # User-data path (writable — database, logs, exports)
    db_path = data_path("data/cashflow.db")
"""

from __future__ import annotations

import os
import sys
from typing import Optional


def _is_packaged() -> bool:
    """Return ``True`` when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _bundle_dir() -> str:
    """Return the directory where bundled data files live.

    Development: project root (parent of ``utils/``).
    Packaged:    PyInstaller's ``sys._MEIPASS`` temp directory.
    """
    if _is_packaged():
        return str(sys._MEIPASS)
    # Project root is parent of utils/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _app_dir() -> str:
    """Return the directory where the application (or executable) lives.

    Development: project root.
    Packaged:    directory containing the ``.exe``.
    """
    if _is_packaged():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path: str) -> str:
    """Return the absolute path to a **read-only** bundled resource.

    Translations, default config files, ICC profiles, QWebChannel JS,
    and any other file that is shipped with the application.
    """
    return os.path.join(_bundle_dir(), relative_path)


def data_path(relative_path: str) -> str:
    """Return the absolute path to a **writable** user-data file.

    The database, logs, exports, cached fuel prices, and any other file
    that the application modifies at runtime.

    In a packaged build these files live *beside* the executable so they
    survive upgrades and do not vanish when the MEIPASS temp dir is
    cleaned up.
    """
    return os.path.join(_app_dir(), relative_path)


def ensure_data_dirs(*subdirs: str) -> None:
    """Create writable data subdirectories next to the executable."""
    for sub in subdirs:
        os.makedirs(data_path(sub), exist_ok=True)
