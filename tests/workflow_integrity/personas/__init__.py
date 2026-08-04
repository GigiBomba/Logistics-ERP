"""Persona fixtures — pre-seeded test data for workflow scenarios.

Each module exports a ``build_X_persona(db)`` function that seeds
the in-memory database with a representative company + fleet + user
configuration and returns a dict of entity IDs.

Usage::

    from tests.workflow_integrity.personas import build_ionut_persona

    def test_driver_submits_status(workflow_env):
        ids = build_ionut_persona(workflow_env.db)
        ...
"""

from __future__ import annotations

from .ana_dispatcher import build_ana_persona
from .andrei_operations_manager import build_andrei_persona
from .elena_accountant import build_elena_persona
from .ionut_driver import build_ionut_persona
from .marius_argo_power_user import build_marius_persona
from .mihai_owner_operator import build_mihai_persona

__all__ = [
    "build_mihai_persona",
    "build_ana_persona",
    "build_andrei_persona",
    "build_ionut_persona",
    "build_elena_persona",
    "build_marius_persona",
]
