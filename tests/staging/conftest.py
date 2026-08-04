"""Staging-suite configuration.

Registers the ``staging`` marker (required by the repo's ``--strict-markers``)
and keeps staging tests OUT of the default suite: unless the invocation
explicitly targets ``tests/staging``, items marked ``staging`` are deselected.
This makes the marker the gate the runbook relies on.
"""

from __future__ import annotations

import os

import pytest

# The staging suite never runs against the production environment.  This is a
# belt-and-braces override in case a developer exported OPERION_ENV=production
# in their shell — in-process fallback would otherwise trip the production
# guard-rails (backend/config.py + auth middleware).
if os.environ.get("OPERION_ENV") == "production":
    os.environ["OPERION_ENV"] = "staging"


def pytest_configure(config: "pytest.Config") -> None:
    config.addinivalue_line(
        "markers",
        "staging: staging-harness integration smoke test — run explicitly with `pytest tests/staging/ -v`",
    )


def pytest_collection_modifyitems(config: "pytest.Config", items) -> None:
    """Deselect ``staging``-marked tests unless tests/staging was targeted."""
    args = [str(a).replace("\\", "/") for a in config.invocation_params.args]
    targeted = any(
        a.startswith("tests/staging") or a.rstrip("/") == "tests/staging"
        for a in args
    )
    if targeted:
        return
    items[:] = [item for item in items if "staging" not in item.keywords]
