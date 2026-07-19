"""Authored walkthrough scripts for the Guided UI Mentor System.

Blueprint: §34.2 — GuidedWalkthrough data contract.
§34.7 — Onboarding Tour (first launch).

These are hardcoded Python data structures. In production, they are served
by the backend's guided_workflow_service. This local copy is used by the
desktop client's TourController for offline-capable tour playback.

Each script follows the GuidedWalkthrough/GuidedStep schema from schemas.py.

Step types:
- DIM: dim everything, show tooltip (no specific target)
- HIGHLIGHT: highlight a specific element + show tooltip
- WAIT_FOR_CLICK: blocks until the target element is clicked
- WAIT_FOR_INPUT: blocks until the target field receives input
- NAVIGATE: brief instruction, then moves to next step (user navigates)
- SHOW_SUCCESS: terminal step, overlay clears with success message
- ARROW: arrow pointer from tooltip to highlighted element
- PULSE: animated pulse on highlighted element
"""

from __future__ import annotations

from typing import Any

# ── Onboarding Tour ───────────────────────────────────────────────────────

ONBOARDING_TOUR: dict[str, Any] = {
    "workflow_id": "app_overview",
    "title_key": "tour.app_overview.title",
    "steps": [
        {
            "step_id": "welcome",
            "type": "dim",
            "target_element_id": None,
            "tooltip_key": "tour.app_overview.welcome",
            "order": 1,
        },
        {
            "step_id": "sidebar",
            "type": "highlight",
            "target_element_id": "nav_overview",
            "tooltip_key": "tour.app_overview.sidebar",
            "order": 2,
        },
        {
            "step_id": "fleet",
            "type": "highlight",
            "target_element_id": "nav_fleet",
            "tooltip_key": "tour.app_overview.fleet",
            "order": 3,
        },
        {
            "step_id": "drivers",
            "type": "highlight",
            "target_element_id": "nav_drivers",
            "tooltip_key": "tour.app_overview.drivers",
            "order": 4,
        },
        {
            "step_id": "trips",
            "type": "highlight",
            "target_element_id": "nav_trips",
            "tooltip_key": "tour.app_overview.trips",
            "order": 5,
        },
        {
            "step_id": "dispatch",
            "type": "highlight",
            "target_element_id": "nav_dispatch_board",
            "tooltip_key": "tour.app_overview.dispatch",
            "order": 6,
        },
        {
            "step_id": "copilot",
            "type": "highlight",
            "target_element_id": "nav_copilot",
            "tooltip_key": "tour.app_overview.copilot",
            "order": 7,
        },
        {
            "step_id": "complete",
            "type": "show_success",
            "target_element_id": None,
            "tooltip_key": "tour.app_overview.complete",
            "order": 8,
        },
    ],
}

# ── Workflow tours ────────────────────────────────────────────────────────

ADD_DRIVER_TOUR: dict[str, Any] = {
    "workflow_id": "add_driver",
    "title_key": "tour.add_driver.title",
    "steps": [
        {
            "step_id": "navigate",
            "type": "navigate",
            "target_element_id": "nav_drivers",
            "tooltip_key": "tour.add_driver.navigate",
            "order": 1,
        },
        {
            "step_id": "click_add",
            "type": "wait_for_click",
            "target_element_id": "btn_add_driver",
            "tooltip_key": "tour.add_driver.click_add",
            "order": 2,
        },
        {
            "step_id": "fill_form",
            "type": "wait_for_input",
            "target_element_id": "driver_form_name",
            "tooltip_key": "tour.add_driver.fill_form",
            "order": 3,
        },
        {
            "step_id": "save",
            "type": "wait_for_click",
            "target_element_id": "btn_save_driver",
            "tooltip_key": "tour.add_driver.save",
            "order": 4,
        },
        {
            "step_id": "complete",
            "type": "show_success",
            "target_element_id": None,
            "tooltip_key": "tour.add_driver.complete",
            "order": 5,
        },
    ],
}

GENERATE_INVOICE_TOUR: dict[str, Any] = {
    "workflow_id": "generate_invoice",
    "title_key": "tour.generate_invoice.title",
    "steps": [
        {
            "step_id": "navigate",
            "type": "navigate",
            "target_element_id": "nav_invoices",
            "tooltip_key": "tour.generate_invoice.navigate",
            "order": 1,
        },
        {
            "step_id": "click_new",
            "type": "wait_for_click",
            "target_element_id": "btn_new_invoice",
            "tooltip_key": "tour.generate_invoice.click_new",
            "order": 2,
        },
        {
            "step_id": "fill_client",
            "type": "wait_for_input",
            "target_element_id": "invoice_client_field",
            "tooltip_key": "tour.generate_invoice.fill_client",
            "order": 3,
        },
        {
            "step_id": "add_items",
            "type": "wait_for_click",
            "target_element_id": "btn_add_invoice_item",
            "tooltip_key": "tour.generate_invoice.add_items",
            "order": 4,
        },
        {
            "step_id": "complete",
            "type": "show_success",
            "target_element_id": None,
            "tooltip_key": "tour.generate_invoice.complete",
            "order": 5,
        },
    ],
}

DISPATCH_TRIP_TOUR: dict[str, Any] = {
    "workflow_id": "dispatch_trip",
    "title_key": "tour.dispatch_trip.title",
    "steps": [
        {
            "step_id": "navigate",
            "type": "navigate",
            "target_element_id": "nav_dispatch_board",
            "tooltip_key": "tour.dispatch_trip.navigate",
            "order": 1,
        },
        {
            "step_id": "select_trip",
            "type": "wait_for_click",
            "target_element_id": "dispatch_trip_card",
            "tooltip_key": "tour.dispatch_trip.select_trip",
            "order": 2,
        },
        {
            "step_id": "assign_truck",
            "type": "wait_for_click",
            "target_element_id": "btn_assign_truck",
            "tooltip_key": "tour.dispatch_trip.assign_truck",
            "order": 3,
        },
        {
            "step_id": "assign_driver",
            "type": "wait_for_click",
            "target_element_id": "btn_assign_driver",
            "tooltip_key": "tour.dispatch_trip.assign_driver",
            "order": 4,
        },
        {
            "step_id": "confirm",
            "type": "wait_for_click",
            "target_element_id": "btn_confirm_dispatch",
            "tooltip_key": "tour.dispatch_trip.confirm",
            "order": 5,
        },
        {
            "step_id": "complete",
            "type": "show_success",
            "target_element_id": None,
            "tooltip_key": "tour.dispatch_trip.complete",
            "order": 6,
        },
    ],
}

SCHEDULE_MAINTENANCE_TOUR: dict[str, Any] = {
    "workflow_id": "schedule_maintenance",
    "title_key": "tour.schedule_maintenance.title",
    "steps": [
        {
            "step_id": "navigate",
            "type": "navigate",
            "target_element_id": "nav_maintenance",
            "tooltip_key": "tour.schedule_maintenance.navigate",
            "order": 1,
        },
        {
            "step_id": "click_schedule",
            "type": "wait_for_click",
            "target_element_id": "btn_schedule_maintenance",
            "tooltip_key": "tour.schedule_maintenance.click_schedule",
            "order": 2,
        },
        {
            "step_id": "fill_details",
            "type": "wait_for_input",
            "target_element_id": "maintenance_description_field",
            "tooltip_key": "tour.schedule_maintenance.fill_details",
            "order": 3,
        },
        {
            "step_id": "complete",
            "type": "show_success",
            "target_element_id": None,
            "tooltip_key": "tour.schedule_maintenance.complete",
            "order": 4,
        },
    ],
}

# ── All scripts lookup ────────────────────────────────────────────────────

ALL_SCRIPTS: dict[str, dict[str, Any]] = {
    "app_overview": ONBOARDING_TOUR,
    "add_driver": ADD_DRIVER_TOUR,
    "generate_invoice": GENERATE_INVOICE_TOUR,
    "dispatch_trip": DISPATCH_TRIP_TOUR,
    "schedule_maintenance": SCHEDULE_MAINTENANCE_TOUR,
}
