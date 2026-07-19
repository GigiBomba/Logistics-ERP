"""Guided walkthrough service for step-by-step UI tours.

Blueprint: §34 — Guided UI Mentor System.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.copilot.schemas import GuidedStep, GuidedStepType, GuidedWalkthrough

logger = logging.getLogger(__name__)

# ── Walkthrough Scripts ────────────────────────────────────────────────────

_SCRIPTS: dict[str, dict[str, Any]] = {
    "app_overview": {
        "workflow_id": "app_overview",
        "title_key": "tour.app_overview.title",
        "steps": [
            {
                "step_id": "welcome",
                "type": GuidedStepType.DIM,
                "target_element_id": None,
                "tooltip_key": "tour.app_overview.welcome",
                "order": 1,
            },
            {
                "step_id": "sidebar",
                "type": GuidedStepType.HIGHLIGHT,
                "target_element_id": "nav_overview",
                "tooltip_key": "tour.app_overview.sidebar",
                "order": 2,
            },
            {
                "step_id": "fleet",
                "type": GuidedStepType.HIGHLIGHT,
                "target_element_id": "nav_fleet",
                "tooltip_key": "tour.app_overview.fleet",
                "order": 3,
            },
            {
                "step_id": "drivers",
                "type": GuidedStepType.HIGHLIGHT,
                "target_element_id": "nav_drivers",
                "tooltip_key": "tour.app_overview.drivers",
                "order": 4,
            },
            {
                "step_id": "trips",
                "type": GuidedStepType.HIGHLIGHT,
                "target_element_id": "nav_trips",
                "tooltip_key": "tour.app_overview.trips",
                "order": 5,
            },
            {
                "step_id": "dispatch",
                "type": GuidedStepType.HIGHLIGHT,
                "target_element_id": "nav_dispatch_board",
                "tooltip_key": "tour.app_overview.dispatch",
                "order": 6,
            },
            {
                "step_id": "copilot",
                "type": GuidedStepType.HIGHLIGHT,
                "target_element_id": "nav_copilot",
                "tooltip_key": "tour.app_overview.copilot",
                "order": 7,
            },
            {
                "step_id": "complete",
                "type": GuidedStepType.SHOW_SUCCESS,
                "target_element_id": None,
                "tooltip_key": "tour.app_overview.complete",
                "order": 8,
            },
        ],
    },
    "add_driver": {
        "workflow_id": "add_driver",
        "title_key": "tour.add_driver.title",
        "steps": [
            {
                "step_id": "start",
                "type": GuidedStepType.NAVIGATE,
                "target_element_id": "nav_drivers",
                "tooltip_key": "tour.add_driver.start",
                "order": 1,
            },
            {
                "step_id": "click_add",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_add_driver",
                "tooltip_key": "tour.add_driver.click_add",
                "order": 2,
            },
            {
                "step_id": "fill_form",
                "type": GuidedStepType.WAIT_FOR_INPUT,
                "target_element_id": "driver_form_name",
                "tooltip_key": "tour.add_driver.fill_form",
                "order": 3,
            },
            {
                "step_id": "save",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_save_driver",
                "tooltip_key": "tour.add_driver.save",
                "order": 4,
            },
            {
                "step_id": "complete",
                "type": GuidedStepType.SHOW_SUCCESS,
                "target_element_id": None,
                "tooltip_key": "tour.add_driver.complete",
                "order": 5,
            },
        ],
    },
    "generate_invoice": {
        "workflow_id": "generate_invoice",
        "title_key": "tour.generate_invoice.title",
        "steps": [
            {
                "step_id": "start",
                "type": GuidedStepType.NAVIGATE,
                "target_element_id": "nav_invoices",
                "tooltip_key": "tour.generate_invoice.start",
                "order": 1,
            },
            {
                "step_id": "click_new",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_new_invoice",
                "tooltip_key": "tour.generate_invoice.click_new",
                "order": 2,
            },
            {
                "step_id": "fill_client",
                "type": GuidedStepType.WAIT_FOR_INPUT,
                "target_element_id": "invoice_client_field",
                "tooltip_key": "tour.generate_invoice.fill_client",
                "order": 3,
            },
            {
                "step_id": "add_items",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_add_invoice_item",
                "tooltip_key": "tour.generate_invoice.add_items",
                "order": 4,
            },
            {
                "step_id": "complete",
                "type": GuidedStepType.SHOW_SUCCESS,
                "target_element_id": None,
                "tooltip_key": "tour.generate_invoice.complete",
                "order": 5,
            },
        ],
    },
    "dispatch_trip": {
        "workflow_id": "dispatch_trip",
        "title_key": "tour.dispatch_trip.title",
        "steps": [
            {
                "step_id": "start",
                "type": GuidedStepType.NAVIGATE,
                "target_element_id": "nav_dispatch_board",
                "tooltip_key": "tour.dispatch_trip.start",
                "order": 1,
            },
            {
                "step_id": "select_trip",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "dispatch_trip_card",
                "tooltip_key": "tour.dispatch_trip.select_trip",
                "order": 2,
            },
            {
                "step_id": "assign_truck",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_assign_truck",
                "tooltip_key": "tour.dispatch_trip.assign_truck",
                "order": 3,
            },
            {
                "step_id": "assign_driver",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_assign_driver",
                "tooltip_key": "tour.dispatch_trip.assign_driver",
                "order": 4,
            },
            {
                "step_id": "confirm",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_confirm_dispatch",
                "tooltip_key": "tour.dispatch_trip.confirm",
                "order": 5,
            },
            {
                "step_id": "complete",
                "type": GuidedStepType.SHOW_SUCCESS,
                "target_element_id": None,
                "tooltip_key": "tour.dispatch_trip.complete",
                "order": 6,
            },
        ],
    },
    "schedule_maintenance": {
        "workflow_id": "schedule_maintenance",
        "title_key": "tour.schedule_maintenance.title",
        "steps": [
            {
                "step_id": "start",
                "type": GuidedStepType.NAVIGATE,
                "target_element_id": "nav_maintenance",
                "tooltip_key": "tour.schedule_maintenance.start",
                "order": 1,
            },
            {
                "step_id": "click_schedule",
                "type": GuidedStepType.WAIT_FOR_CLICK,
                "target_element_id": "btn_schedule_maintenance",
                "tooltip_key": "tour.schedule_maintenance.click_schedule",
                "order": 2,
            },
            {
                "step_id": "fill_details",
                "type": GuidedStepType.WAIT_FOR_INPUT,
                "target_element_id": "maintenance_description_field",
                "tooltip_key": "tour.schedule_maintenance.fill_details",
                "order": 3,
            },
            {
                "step_id": "complete",
                "type": GuidedStepType.SHOW_SUCCESS,
                "target_element_id": None,
                "tooltip_key": "tour.schedule_maintenance.complete",
                "order": 4,
            },
        ],
    },
}


class GuidedWorkflowService:
    """Service for guided walkthrough scripts and familiarity tracking."""

    def get_script(self, workflow_id: str) -> GuidedWalkthrough | None:
        """Look up a walkthrough script by workflow_id."""
        script_data = _SCRIPTS.get(workflow_id)
        if not script_data:
            return None

        return GuidedWalkthrough(
            workflow_id=script_data["workflow_id"],
            title_key=script_data["title_key"],
            steps=[GuidedStep(**s) for s in script_data["steps"]],
        )

    def list_available_workflows(self) -> list[str]:
        """Return list of all available workflow IDs."""
        return list(_SCRIPTS.keys())

    def adjust_for_familiarity(
        self,
        script: GuidedWalkthrough,
        user_id: str = "",
        company_id: str = "",
        familiarity_level: str = "new",
    ) -> GuidedWalkthrough:
        """Adjust walkthrough verbosity based on user familiarity.

        Levels:
        - new (0-1 completions): full walkthrough
        - familiar (2-5): condensed tooltips
        - expert (6+): minimal summary
        """
        if familiarity_level == "new":
            return script  # Full walkthrough as-is

        if familiarity_level == "familiar":
            # Condensed: fewer tooltip details but same steps
            condensed = script.model_copy(deep=True)
            condensed.familiarity_adjusted = True
            for step in condensed.steps:
                if step.tooltip_key and not step.tooltip_key.endswith(".short"):
                    step.tooltip_key += ".short"
            return condensed

        if familiarity_level == "expert":
            # Minimal: just title and a "quick version" note
            brief = script.model_copy(deep=True)
            brief.familiarity_adjusted = True
            # Keep only first and last step
            brief.steps = [script.steps[0]] if script.steps else []
            if script.steps:
                brief.steps.append(
                    GuidedStep(
                        step_id="quick_complete",
                        type=GuidedStepType.SHOW_SUCCESS,
                        tooltip_key="tour.expert.quick_complete",
                        order=999,
                    )
                )
            return brief

        return script


# Singleton
_guided_workflow_service: GuidedWorkflowService | None = None


def get_guided_workflow_service() -> GuidedWorkflowService:
    global _guided_workflow_service
    if _guided_workflow_service is None:
        _guided_workflow_service = GuidedWorkflowService()
    return _guided_workflow_service
