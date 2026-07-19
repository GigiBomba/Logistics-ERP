"""Element registry — maps symbolic IDs to widget objectNames for the Guided UI.

Blueprint: §34.3 — Stable UI Element IDs.

Each entry maps a symbolic target_element_id (used in walkthrough scripts)
to the actual widget's objectName on the PySide6 desktop client.

Whenever a UI refactor renames or removes a widget, this registry must be
updated — a CI check asserts every scripted target_element_id resolves.
"""

from __future__ import annotations

from typing import Optional

# ── Symbolic ID → widget objectName mapping ───────────────────────────────

ELEMENT_REGISTRY: dict[str, str] = {
    # ── Sidebar navigation ───────────────────────────────────────────────
    "nav_overview": "sidebar-item-overview",
    "nav_analytics": "sidebar-item-analytics",
    "nav_routes": "sidebar-item-routes",
    "nav_calculator": "sidebar-item-calculator",
    "nav_dispatch_board": "sidebar-item-dispatch-board",
    "nav_fleet": "sidebar-item-fleet",
    "nav_drivers": "sidebar-item-drivers",
    "nav_trips": "sidebar-item-trips",
    "nav_clients": "sidebar-item-clients",
    "nav_invoices": "sidebar-item-invoices",
    "nav_receipts": "sidebar-item-receipts",
    "nav_cmr": "sidebar-item-cmr",
    "nav_documents": "sidebar-item-documents",
    "nav_tracking": "sidebar-item-tracking",
    "nav_maintenance": "sidebar-item-maintenance",
    "nav_copilot": "sidebar-item-copilot",
    "nav_settings": "sidebar-item-settings",

    # ── View containers ──────────────────────────────────────────────────
    "workspace_overview": "view-overview",
    "workspace_fleet": "view-fleet",
    "workspace_drivers": "view-drivers",
    "workspace_trips": "view-trips",
    "workspace_dispatch": "view-dispatch-board",
    "workspace_copilot": "view-copilot",
    "workspace_invoices": "view-invoices",
    "workspace_maintenance": "view-maintenance",

    # ── Action buttons ───────────────────────────────────────────────────
    "btn_add_driver": "btn-add-driver",
    "btn_save_driver": "btn-save-driver",
    "btn_create_trip": "btn-create-trip",
    "btn_generate_invoice": "btn-generate-invoice",
    "btn_new_invoice": "btn-new-invoice",
    "btn_add_invoice_item": "btn-add-invoice-item",
    "btn_dispatch_assign": "btn-dispatch-assign",
    "btn_assign_truck": "btn-assign-truck",
    "btn_assign_driver": "btn-assign-driver",
    "btn_confirm_dispatch": "btn-confirm-dispatch",
    "btn_schedule_maintenance": "btn-schedule-maintenance",

    # ── Form fields ──────────────────────────────────────────────────────
    "driver_form_name": "driver-form-name",
    "invoice_client_field": "invoice-client-field",
    "maintenance_description_field": "maintenance-description-field",

    # ── Data display ─────────────────────────────────────────────────────
    "dispatch_trip_card": "dispatch-trip-card",
    "overview_metrics": "overview-metrics",
    "fleet_health_panel": "fleet-health-panel",
}

# ── Reverse lookup: objectName → symbolic ID ─────────────────────────────

_OBJECT_NAME_TO_SYMBOLIC: dict[str, str] = {
    v: k for k, v in ELEMENT_REGISTRY.items()
}


def resolve_element(element_id: str) -> Optional[str]:
    """Resolve a symbolic element ID to a widget objectName.

    Returns None if the ID is not in the registry.
    """
    return ELEMENT_REGISTRY.get(element_id)


def resolve_object_name(object_name: str) -> Optional[str]:
    """Reverse-resolve a widget objectName to a symbolic element ID."""
    return _OBJECT_NAME_TO_SYMBOLIC.get(object_name)


def register_element(symbolic_id: str, object_name: str) -> None:
    """Register a new element mapping (for dynamic widgets)."""
    ELEMENT_REGISTRY[symbolic_id] = object_name
    _OBJECT_NAME_TO_SYMBOLIC[object_name] = symbolic_id


def validate_script_targets(workflow_scripts: list[dict]) -> list[str]:
    """Validate that every target_element_id in scripts resolves.

    Returns a list of missing IDs (empty = all valid).
    Used by CI checks to catch UI refactors that break walkthroughs.
    """
    missing: list[str] = []
    for script in workflow_scripts:
        for step in script.get("steps", []):
            target = step.get("target_element_id")
            if target and target not in ELEMENT_REGISTRY:
                missing.append(f"{script.get('workflow_id')}:{step.get('step_id')} -> {target}")
    return missing
