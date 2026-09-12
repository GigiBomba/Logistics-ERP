"""Platform parity — Mobile feature inventory.

Mobile-side companion to :mod:`.desktop_features`.  Re-exports the shared
§4 matrix types/data (defined in ``desktop_features.py`` so desktop is the
single source of truth for :data:`~.desktop_features.PARITY_MATRIX`) and adds
the mobile-only inventory:

* :data:`MOBILE_STATES` — the four driver-facing statuses the mobile app can
  set (matrix row "Status Transitions", §4 "Basic (4 states)").
* :data:`MOBILE_PROBES` — feature -> probe ``Callable[..., bool]`` mirroring
  the *actual* mobile fixture API (``tests/workflow_integrity/fixtures/
  multi_platform_client.py`` → ``MobileClient``).  Each probe receives either
  a ``MobileClient``-like object or a services dict holding one under the
  ``"mobile_client"`` key, and returns ``True`` only when the method the
  feature needs is exposed.  Probes never import UI and never raise.

Only the features the ``MobileClient`` fixture actually models are given
probes (trip view, status updates with offline queueing, document upload,
expense submission) — the fixture deliberately exposes a *driver-scoped*
subset of the matrix's mobile surface.
"""

from __future__ import annotations

from typing import Callable

from .desktop_features import FeatureRow, PARITY_MATRIX  # noqa: F401

__all__ = [
    "FeatureRow",
    "PARITY_MATRIX",
    "MOBILE_STATES",
    "MOBILE_PROBES",
]

#: The four driver-facing statuses reachable from the mobile app.  Mirrors
#: the status vocabulary used by the multi-platform client fixture and the
#: trip status engine (§4 row "Status Transitions": "Basic (4 states)").
MOBILE_STATES: list[str] = ["Planned", "Loading", "In Transit", "Delivered"]


def _resolve_mobile(mobile) -> object:
    """Accept either a MobileClient-like object or a services dict."""
    if isinstance(mobile, dict):
        return mobile.get("mobile_client")
    return mobile


def _mobile_has(mobile, *methods: str) -> bool:
    """True when the mobile client object exposes every named callable."""
    client = _resolve_mobile(mobile)
    if client is None:
        return False
    return all(callable(getattr(client, method, None)) for method in methods)


#: feature -> probe.  Each probe checks the MobileClient fixture API that
#: implements the feature's mobile coverage in the §4 matrix.
MOBILE_PROBES: dict[str, Callable[..., bool]] = {
    # Matrix coverage: driver "View only", dispatcher "View + status mgmt".
    "Trip CRUD": lambda m: _mobile_has(m, "get_trip"),
    # Matrix coverage: driver + dispatcher "Basic (4 states)".  update_status
    # carries the offline/idempotency path; sync_queue/pending_actions replay
    # queued transitions on reconnect (§4 offline behaviour).
    "Status Transitions": lambda m: _mobile_has(
        m, "update_status", "sync_queue", "pending_actions"),
    # Matrix coverage: driver "Photo upload", dispatcher "Document center".
    "Document Upload": lambda m: _mobile_has(m, "queue_document_upload"),
    # Matrix coverage: driver "Enter + receipt photo".
    "Expense Submission": lambda m: _mobile_has(m, "queue_expense"),
}
