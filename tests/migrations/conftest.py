"""Ensure ``import alembic`` resolves to the installed pip package.

The repository ships a local ``alembic/`` directory (migration scripts, no
``__init__.py``).  When pytest prepends the repo root (or the ``tests/``
package root) to ``sys.path``, Python 3.10's import machinery can resolve
``alembic`` to that directory-as-a-namespace-package instead of the installed
package — breaking ``from alembic import command`` and
``from alembic.script import ScriptDirectory`` with
``ImportError: cannot import name 'command' from 'alembic' (unknown location)``.

This conftest detects the shadowing at collection time and re-imports the real
package from ``site-packages`` (pushed to the front of ``sys.path``) before
any test module imports it.  On interpreters where the regular package already
wins (e.g. 3.11+) this is a no-op.
"""
from __future__ import annotations

import importlib
import sys


def _ensure_real_alembic() -> None:
    # ``alembic/__init__.py`` does not import ``command``/``script`` at the
    # top, so the reliable probe is whether the submodules import.  The
    # shadowed namespace package has neither, raising ImportError.
    try:
        import alembic.command  # noqa: F401
        import alembic.script  # noqa: F401
        return
    except ImportError:
        pass  # Shadowed by the repo-local ``alembic/`` namespace package.

    import site

    site_packages = [p for p in site.getsitepackages() if p not in sys.path]
    sys.path[:0] = site_packages

    # Drop any partially-imported ``alembic`` modules so the re-import is
    # rebuilt from site-packages rather than reusing the namespace package.
    for mod in list(sys.modules):
        if mod == "alembic" or mod.startswith("alembic."):
            del sys.modules[mod]

    importlib.import_module("alembic")


_ensure_real_alembic()
