"""Mobile API router package (Phase 0 scaffolding).

The legacy monolithic module ``backend/api/v1/mobile.py`` is left 100%
untouched, but Python resolves the ``backend.api.v1.mobile`` name to this
package (a directory package wins over a same-named module in CPython).  To
keep every existing caller working, the legacy module is loaded explicitly
here and its full public surface (``router``, ``ensure_mobile_tables``,
``company_export_manifest``, endpoint functions, …) is re-exported.

The new per-entity routers (blueprint §6) are collected into
``mobile_router``, which ``backend/api/v1/router.py`` mounts alongside the
legacy ``router``.  No endpoint handlers exist yet — Phase 0 scaffolding only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter

from . import (
    analytics,
    clients,
    drivers,
    fleet,
    history,
    invoicing,
    maintenance,
    search,
    settings,
    tachograph,
    team,
)

# ── Legacy monolithic mobile.py re-export ──────────────────────────────
# The directory package shadows the ``mobile.py`` module name, so load the
# module explicitly by path and re-export its public namespace.  This keeps
# ``from backend.api.v1.mobile import router/ensure_mobile_tables/…`` and
# ``from backend.api.v1 import mobile`` working exactly as before.
_LEGACY_MODULE_NAME = __name__ + "._legacy_mobile"
_legacy_spec = importlib.util.spec_from_file_location(
    _LEGACY_MODULE_NAME, Path(__file__).resolve().parents[1] / "mobile.py"
)
assert _legacy_spec is not None and _legacy_spec.loader is not None
_legacy_mobile = importlib.util.module_from_spec(_legacy_spec)
sys.modules[_LEGACY_MODULE_NAME] = _legacy_mobile
_legacy_spec.loader.exec_module(_legacy_mobile)

_public_legacy = {
    k: v for k, v in vars(_legacy_mobile).items() if not k.startswith("_")
}
globals().update(_public_legacy)

# Explicit alias so the legacy router stays reachable as ``mobile.router``.
router = _legacy_mobile.router

# ── New per-entity mobile routers (blueprint §6) ──────────────────────
mobile_router = APIRouter(prefix="/mobile", tags=["mobile"])
mobile_router.include_router(fleet.router)
mobile_router.include_router(drivers.router)
mobile_router.include_router(clients.router)
mobile_router.include_router(analytics.router)
mobile_router.include_router(invoicing.router)
mobile_router.include_router(maintenance.router)
mobile_router.include_router(tachograph.router)
mobile_router.include_router(history.router)
mobile_router.include_router(team.router)
mobile_router.include_router(settings.router)
mobile_router.include_router(search.router)
