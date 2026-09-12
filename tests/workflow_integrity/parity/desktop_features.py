"""Platform parity — Desktop feature inventory.

Encoding of §4 "Desktop + Mobile Parity Matrix" from
``docs/blueprints/workflow_integrity_test_suite_architecture.md`` (the Product
Constitution).  Every row of the matrix appears exactly once in
:data:`PARITY_MATRIX` with the blueprint's coverage / sync / offline values.

Coverage legend (columns ``desktop`` / ``mobile_driver`` / ``mobile_dispatcher``):

* ``True``  — the platform ships an interactive implementation of the feature
  (create / edit / act).  The desktop column is ``True`` for every row the
  blueprint marks "✅ Full" (everything except Route Navigation).
* ``"view"`` — the platform can only *consume* the feature read-only
  (e.g. "View only", "View docs", "Profile only", "Driver list", "Browse").
* ``False`` — the feature is not available on that platform ("❌").

Sync vocabulary (column ``sync_requirement``) is one of:
``"real-time" | "≤30s" | "≤60s" | "≤5min" | "n/a"``.

:data:`DESKTOP_PROBES` maps each matrix feature to a probe
``Callable[[dict], bool]`` that verifies the *service-layer* callable(s) which
back the desktop implementation are reachable from the test services dict.
Probes are pure capability checks over the supplied dict — they never import
or construct UI, and they return ``False`` (never raise) when a service or
callable is absent, so they are safe to call against any dict.

Canonical services-dict keys the probes understand (tests assemble the dict
from the workflow-integrity conftest fixtures and, where needed, wire in extra
service instances under these exact keys)::

    db, trip_service, invoice_service, fleet_repo, driver_repo,
    conflict_service, dispatch_service, event_bus, alert_manager,
    operations_engine, workflow_env,                      # conftest fixtures
    permission_service, analytics_service, route_service, document_service,
    ocr_extractor, cmr_generator, receipt_generator, fleet_service,
    maintenance_engine, search_engine_service, client_service, user_service,
    preferences_manager, copilot_planner, tacho_service   # extended services
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Union

# Coverage of a single platform column: interactive (True),
# read-only access ("view"), or absent (False).
Coverage = Union[bool, Literal["view"]]

# Allowed sync requirement vocabulary (spec-locked).
SyncRequirement = Literal["real-time", "≤30s", "≤60s", "≤5min", "n/a"]

SYNC_REQUIREMENTS: frozenset[str] = frozenset(
    {"real-time", "≤30s", "≤60s", "≤5min", "n/a"}
)

# Driver-facing statuses the mobile app can set (matrix row "Status
# Transitions").  Keep in sync with the mobile fixture / status engine.
MOBILE_STATUSES = ("Planned", "Loading", "In Transit", "Delivered")


@dataclass(frozen=True)
class FeatureRow:
    """One row of the §4 platform-parity matrix."""

    feature: str
    desktop: Coverage
    mobile_driver: Coverage
    mobile_dispatcher: Coverage
    sync_requirement: str
    offline_behavior: str


# ── §4 Feature Parity Matrix (30 rows — one per blueprint table row) ───────
PARITY_MATRIX: list[FeatureRow] = [
    FeatureRow("Login/Auth", True, True, True, "real-time",
               "Login requires connectivity"),
    FeatureRow("Dashboard", True, True, True, "real-time",
               "Shows cached data with staleness indicator"),
    FeatureRow("Dispatch Board", True, False, True, "real-time",
               "Queue updates, sync on reconnect"),
    FeatureRow("Trip CRUD", True, "view", True, "real-time",
               "Queue status changes"),
    FeatureRow("Status Transitions", True, True, True, "real-time",
               "Queue with idempotency, sync on reconnect"),
    FeatureRow("Route Planning", True, "view", True, "≤30s",
               "Offline navigation (Google Maps)"),
    FeatureRow("Route Navigation", False, True, False, "n/a",
               "Full offline (Google Maps)"),
    FeatureRow("Fleet Tracking", True, False, True, "real-time",
               "Shows last known positions"),
    FeatureRow("Driver Management", True, "view", "view", "≤60s",
               "Read cached data"),
    FeatureRow("Vehicle/Fleet", True, False, False, "≤60s",
               "Read cached data"),
    FeatureRow("Maintenance", True, True, False, "real-time",
               "Queue fault report"),
    FeatureRow("Document Upload", True, True, True, "≤30s",
               "Queue uploads"),
    FeatureRow("Document View", True, "view", "view", "≤60s",
               "Cached documents"),
    FeatureRow("OCR Processing", True, False, True, "≤30s", "N/A"),
    FeatureRow("CMR Generation", True, False, False, "≤30s", "N/A"),
    FeatureRow("Invoicing", True, False, False, "≤30s", "N/A"),
    FeatureRow("Invoice View", True, False, "view", "≤60s",
               "Cached data"),
    FeatureRow("Receipt Generation", True, False, False, "≤30s", "N/A"),
    FeatureRow("Expense Submission", True, True, False, "≤30s",
               "Queue with photo"),
    FeatureRow("Expense Approval", True, False, True, "≤30s",
               "Queue actions"),
    FeatureRow("Messaging", True, True, True, "real-time",
               "Queue messages"),
    FeatureRow("Notifications", True, True, True, "real-time",
               "Queue offline"),
    FeatureRow("Analytics", True, False, True, "≤5min",
               "Cached snapshots"),
    FeatureRow("Freight Exchange", True, False, "view", "≤60s",
               "Read cached"),
    FeatureRow("Client Management", True, False, False, "≤60s",
               "Read cached"),
    FeatureRow("User/Team Admin", True, False, False, "≤30s",
               "Read cached"),
    FeatureRow("Settings", True, True, True, "≤5min", "Local storage"),
    FeatureRow("ARGO Chat/Actions", True, True, True, "real-time",
               "Offline not supported"),
    FeatureRow("Tachograph", True, False, False, "≤60s", "Read cached"),
    FeatureRow("Migration", True, False, False, "n/a", "N/A"),
]


# ── Desktop probes ─────────────────────────────────────────────────────────

def _resolve(svc: dict, key: str):
    """Return the object stored under ``key`` (dict lookup only, never raises)."""
    if isinstance(svc, dict):
        return svc.get(key)
    return getattr(svc, key, None)


def _svc_has(svc: dict, key: str, *methods: str) -> bool:
    """True when the service under ``key`` exposes every named callable."""
    obj = _resolve(svc, key)
    if obj is None:
        return False
    return all(callable(getattr(obj, method, None)) for method in methods)


def _svc_attr(svc: dict, key: str, *attrs: str) -> bool:
    """True when the service under ``key`` exposes every named attribute.

    Attribute (not callable) check — used for property-exposed subsystems such
    as ``DocumentService.ocr`` whose value is an object, not a method.
    """
    obj = _resolve(svc, key)
    if obj is None:
        return False
    return all(getattr(obj, attr, None) is not None for attr in attrs)


#: feature -> probe.  Each probe receives the conftest services dict and
#: returns True only when the service layer backing that desktop feature is
#: reachable.  Route Navigation is intentionally absent: the matrix marks it
#: ``False`` on desktop (it is a mobile-only feature).
DESKTOP_PROBES: dict[str, Callable[[dict], bool]] = {
    "Login/Auth": lambda svc: _svc_has(svc, "permission_service",
                                       "is_authenticated", "can_create_trip"),
    "Dashboard": lambda svc: _svc_has(svc, "analytics_service", "get_data"),
    "Dispatch Board": lambda svc: _svc_has(
        svc, "dispatch_service", "get_dispatch_board_data"),
    "Trip CRUD": lambda svc: _svc_has(
        svc, "trip_service", "create", "update", "get_by_id"),
    "Status Transitions": lambda svc: _svc_has(
        svc, "operations_engine", "force_trip_status", "get_valid_transitions"),
    "Route Planning": lambda svc: _svc_has(
        svc, "route_service", "calculate_route"),
    "Fleet Tracking": lambda svc: _svc_has(
        svc, "fleet_repo", "get_by_tracking_device_id", "get_all"),
    "Driver Management": lambda svc: _svc_has(
        svc, "driver_repo", "create", "update", "get_by_id"),
    "Vehicle/Fleet": lambda svc: _svc_has(
        svc, "fleet_repo", "create", "update", "delete", "get_all"),
    "Maintenance": lambda svc: _svc_has(
        svc, "maintenance_engine", "evaluate_all", "evaluate_truck") and
        _svc_has(svc, "fleet_repo", "add_maintenance_record"),
    "Document Upload": lambda svc: _svc_has(
        svc, "document_service", "upload_document"),
    "Document View": lambda svc: _svc_has(
        svc, "document_service", "get_by_id", "get_documents_for_entity"),
    "OCR Processing": lambda svc: _svc_attr(
        svc, "document_service", "ocr") or _svc_has(
            svc, "ocr_extractor", "extract"),
    "CMR Generation": lambda svc: _svc_has(
        svc, "cmr_generator", "generate", "generate_all_copies"),
    "Invoicing": lambda svc: _svc_has(
        svc, "invoice_service", "create", "finalize", "set_status"),
    "Invoice View": lambda svc: _svc_has(svc, "invoice_service", "get"),
    "Receipt Generation": lambda svc: _svc_has(
        svc, "receipt_generator", "create", "generate_pdf"),
    "Expense Submission": lambda svc: _svc_has(
        svc, "fleet_service", "add_expense", "get_expenses"),
    "Expense Approval": lambda svc: _svc_has(
        svc, "alert_manager", "create_alert", "resolve_alert"),
    "Messaging": lambda svc: _svc_has(
        svc, "event_bus", "publish", "subscribe", "get_history"),
    "Notifications": lambda svc: _svc_has(
        svc, "alert_manager", "create_alert", "get_active_alerts"),
    "Analytics": lambda svc: _svc_has(
        svc, "analytics_service", "get_data", "get_fleet"),
    "Freight Exchange": lambda svc: _svc_has(
        svc, "search_engine_service", "search_loads", "save_search"),
    "Client Management": lambda svc: _svc_has(
        svc, "client_service", "create", "update", "merge_clients"),
    "User/Team Admin": lambda svc: _svc_has(
        svc, "user_service", "create_user", "list_users", "deactivate_user"),
    "Settings": lambda svc: _svc_has(
        svc, "preferences_manager", "get_setting", "save_setting",
        "get_language", "set_language"),
    "ARGO Chat/Actions": lambda svc: _svc_has(
        svc, "copilot_planner", "process_utterance", "compile_execution_plan"),
    "Tachograph": lambda svc: _svc_has(
        svc, "tacho_service", "import_ddd_file", "analyze_driver_hours"),
    "Migration": lambda svc: _svc_has(
        svc, "operations_engine", "migrate_existing_data"),
}


# ── Import-time integrity guards (internal invariants we fully control) ────
def _validate() -> None:
    seen: set[str] = set()
    for row in PARITY_MATRIX:
        if row.feature in seen:
            raise ValueError(f"Duplicate matrix feature: {row.feature!r}")
        seen.add(row.feature)
        if row.sync_requirement not in SYNC_REQUIREMENTS:
            raise ValueError(
                f"{row.feature!r}: bad sync_requirement "
                f"{row.sync_requirement!r} — must be one of "
                f"{sorted(SYNC_REQUIREMENTS)}"
            )
        for column in ("desktop", "mobile_driver", "mobile_dispatcher"):
            value = getattr(row, column)
            if value is not True and value is not False and value != "view":
                raise ValueError(
                    f"{row.feature!r}.{column} has illegal coverage {value!r}"
                )


_validate()
