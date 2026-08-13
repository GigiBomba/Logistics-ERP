"""Ensure ``import alembic`` resolves to the installed pip package.

The repository ships a local ``alembic/`` directory (migration scripts, no
``__init__.py``).  When pytest prepends the repo root (or the ``tests/``
package root) to ``sys.path``, Python's import machinery can resolve
``alembic`` to that directory-as-a-namespace-package instead of the installed
package — breaking ``from alembic import command`` and
``from alembic.script import ScriptDirectory`` with
``ImportError: cannot import name 'command' from 'alembic' (unknown location)``.

The previous probe-and-fix version failed under the FULL test suite: some
other conftest/module imported the shadowed ``alembic`` namespace package
into ``sys.modules`` before this conftest ran (so the probe saw it as
importable, or the conditional purge was skipped).  This version therefore
runs unconditionally at import time:

  (a) locates the REAL alembic package in site-packages and puts its parent
      directory at the FRONT of ``sys.path`` (never a no-op);
  (b) purges ``alembic`` and every ``alembic.*`` module from ``sys.modules``
      so the re-import cannot reuse a shadowed namespace package;
  (c) re-imports ``alembic`` and asserts ``command`` is importable, raising a
      clear, actionable error instead of the cryptic "unknown location"
      ImportError when the real package truly cannot be found (e.g. not
      installed — alembic is only declared in ``pyproject.toml``, so CI must
      install it explicitly).
"""
from __future__ import annotations

import importlib
import os
import site
import sys


def _find_real_alembic_paths() -> list[str]:
    """Return sys.path roots that contain a real (regular) ``alembic``.

    The shadowed repo-local ``alembic/`` namespace directory has no
    ``__init__.py``; the installed package does.  Scanning the known
    site-packages locations (plus the parent of an already-imported real
    package, if any) locates it without depending on the current
    ``sys.path`` order.
    """
    candidates: list[str] = []
    for root in site.getsitepackages() + [site.getusersitepackages()]:
        if root and os.path.isdir(os.path.join(root, "alembic")) and os.path.isfile(
            os.path.join(root, "alembic", "__init__.py")
        ):
            candidates.append(root)

    # If an already-imported alembic is a regular package, its real location
    # is the safest candidate of all.
    mod = sys.modules.get("alembic")
    if mod is not None and getattr(mod, "__file__", None):
        root = os.path.dirname(os.path.dirname(mod.__file__))
        if root and root not in candidates:
            candidates.append(root)

    return candidates


def _alembic_unavailable() -> RuntimeError:
    return RuntimeError(
        "alembic is not importable from site-packages: the repo-local "
        "`alembic/` namespace directory shadows it and the installed "
        "package could not be located. Install alembic (it is declared "
        "only in pyproject.toml [project.dependencies], so CI must "
        "`pip install alembic` explicitly) or run the migrations suite "
        "from an environment that has it."
    )


def _ensure_real_alembic() -> None:
    # (a) Always put a real alembic on the front of sys.path — even when an
    # earlier import already succeeded — because the shadowed namespace
    # package may have been imported by another conftest before this one.
    for root in _find_real_alembic_paths():
        if root not in sys.path:
            sys.path.insert(0, root)

    # (b) Purge any partially/fully imported ``alembic`` modules so the
    # re-import below is rebuilt from the real package rather than reusing a
    # shadowed namespace package or its stale submodules.
    for mod in list(sys.modules):
        if mod == "alembic" or mod.startswith("alembic."):
            del sys.modules[mod]

    # (c) Re-import and assert the real package is in place.  If alembic is
    # not installed at all, ``import alembic`` silently succeeds on the
    # repo-local namespace package, so the failure surfaces on the submodule
    # import — catch it and turn it into the clear, actionable message.
    try:
        importlib.import_module("alembic")
        importlib.import_module("alembic.command")
    except ImportError:
        raise _alembic_unavailable() from None
    alembic = sys.modules["alembic"]
    if not hasattr(alembic, "command"):
        raise _alembic_unavailable()


_ensure_real_alembic()
