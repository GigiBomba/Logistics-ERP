"""Tests for frontend Help Mode modules (non-Qt).

Covers:
- element_registry.py — symbolic ID <-> objectName mappings
- tour_tracker.py — file-based tour completion tracking
- tour_scripts.py — authored walkthrough script data
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest


# =============================================================================
# element_registry
# =============================================================================


class TestElementRegistry:
    """Tests for element_registry — symbolic ID ↔ objectName mapping."""

    def test_resolve_element_known(self):
        from ui.copilot.element_registry import resolve_element, ELEMENT_REGISTRY

        assert resolve_element("nav_overview") == "sidebar-item-overview"
        assert resolve_element("btn_add_driver") == "btn-add-driver"
        assert resolve_element("driver_form_name") == "driver-form-name"

    def test_resolve_element_unknown(self):
        from ui.copilot.element_registry import resolve_element

        assert resolve_element("nonexistent_id") is None

    def test_resolve_element_empty(self):
        from ui.copilot.element_registry import resolve_element

        assert resolve_element("") is None

    def test_resolve_object_name_known(self):
        from ui.copilot.element_registry import resolve_object_name

        result = resolve_object_name("sidebar-item-overview")
        assert result == "nav_overview"
        result = resolve_object_name("btn-add-driver")
        assert result == "btn_add_driver"

    def test_resolve_object_name_unknown(self):
        from ui.copilot.element_registry import resolve_object_name

        assert resolve_object_name("nonexistent-obj-name") is None

    def test_reverse_lookup_is_complete(self):
        """Every entry in ELEMENT_REGISTRY must be reverse-resolvable."""
        from ui.copilot.element_registry import (
            ELEMENT_REGISTRY,
            resolve_object_name,
        )

        for symbolic_id, object_name in ELEMENT_REGISTRY.items():
            assert resolve_object_name(object_name) == symbolic_id

    def test_registry_count(self):
        """Check the expected number of registered elements."""
        from ui.copilot.element_registry import ELEMENT_REGISTRY

        assert len(ELEMENT_REGISTRY) == 42

    def test_register_element(self):
        from ui.copilot.element_registry import (
            ELEMENT_REGISTRY,
            register_element,
            resolve_element,
            resolve_object_name,
        )

        register_element("test_new_id", "test-new-object")
        assert resolve_element("test_new_id") == "test-new-object"
        assert resolve_object_name("test-new-object") == "test_new_id"
        # Cleanup
        del ELEMENT_REGISTRY["test_new_id"]

    def test_all_nav_ids_have_sidebar_prefix(self):
        from ui.copilot.element_registry import ELEMENT_REGISTRY

        nav_ids = {k: v for k, v in ELEMENT_REGISTRY.items() if k.startswith("nav_")}
        for symbolic_id, object_name in nav_ids.items():
            assert object_name.startswith("sidebar-item-"), (
                f"Nav element {symbolic_id} should map to sidebar-item-*"
            )

    def test_all_btn_ids_have_btn_prefix(self):
        from ui.copilot.element_registry import ELEMENT_REGISTRY

        btn_ids = {k: v for k, v in ELEMENT_REGISTRY.items() if k.startswith("btn_")}
        for symbolic_id, object_name in btn_ids.items():
            assert object_name.startswith("btn-"), (
                f"Button element {symbolic_id} should map to btn-*"
            )

    def test_validate_script_targets_all_valid(self):
        from ui.copilot.element_registry import validate_script_targets
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        scripts = list(ALL_SCRIPTS.values())
        missing = validate_script_targets(scripts)
        assert missing == [], f"Missing element targets: {missing}"

    def test_validate_script_targets_reports_missing(self):
        from ui.copilot.element_registry import validate_script_targets

        bad_scripts = [
            {
                "workflow_id": "test",
                "steps": [
                    {"step_id": "s1", "target_element_id": "nav_nonexistent"},
                ],
            },
        ]
        missing = validate_script_targets(bad_scripts)
        assert len(missing) == 1
        assert "nav_nonexistent" in missing[0]

    def test_validate_script_targets_ignores_none_target(self):
        from ui.copilot.element_registry import validate_script_targets

        scripts = [
            {
                "workflow_id": "test",
                "steps": [
                    {"step_id": "s1", "target_element_id": None},
                ],
            },
        ]
        missing = validate_script_targets(scripts)
        assert missing == []


# =============================================================================
# tour_tracker
# =============================================================================


@pytest.fixture
def temp_tour_dir():
    """Create a temporary .operion directory for tour tracking tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("ui.copilot.tour_tracker.APP_DATA_DIR", tmpdir):
            with patch(
                "ui.copilot.tour_tracker.TOUR_COMPLETED_FILE",
                os.path.join(tmpdir, ".tour_completed.json"),
            ):
                yield tmpdir


class TestTourTracker:
    """Tests for tour_tracker — file-based tour completion tracking."""

    def test_is_tour_completed_defaults_false(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        assert tour_tracker.is_tour_completed() is False

    def test_mark_tour_completed(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        tour_tracker.mark_tour_completed()
        assert tour_tracker.is_tour_completed() is True

    def test_mark_tour_completed_specific_workflow(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        assert tour_tracker.is_tour_completed("add_driver") is False
        tour_tracker.mark_tour_completed("add_driver")
        assert tour_tracker.is_tour_completed("add_driver") is True
        # Other workflows should remain incomplete
        assert tour_tracker.is_tour_completed("app_overview") is False

    def test_clear_tour_completed(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        tour_tracker.mark_tour_completed("app_overview")
        assert tour_tracker.is_tour_completed("app_overview") is True
        tour_tracker.clear_tour_completed("app_overview")
        assert tour_tracker.is_tour_completed("app_overview") is False

    def test_clear_all_tours(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        tour_tracker.mark_tour_completed("app_overview")
        tour_tracker.mark_tour_completed("add_driver")
        tour_tracker.clear_all_tours()
        assert tour_tracker.is_tour_completed("app_overview") is False
        assert tour_tracker.is_tour_completed("add_driver") is False

    def test_get_completed_tours(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        tour_tracker.mark_tour_completed("add_driver")
        tour_tracker.mark_tour_completed("generate_invoice")
        completed = tour_tracker.get_completed_tours()
        assert "add_driver" in completed
        assert "generate_invoice" in completed
        assert "app_overview" not in completed

    def test_get_completed_tours_empty(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        assert tour_tracker.get_completed_tours() == []

    def test_increment_completion_count(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        tour_tracker.increment_completion_count("app_overview")
        assert tour_tracker.get_completion_count("app_overview") == 1
        tour_tracker.increment_completion_count("app_overview")
        assert tour_tracker.get_completion_count("app_overview") == 2

    def test_get_completion_count_default(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        assert tour_tracker.get_completion_count("nonexistent") == 0

    def test_tour_completed_sets_timestamp(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        tour_tracker.mark_tour_completed("app_overview")
        data = tour_tracker._read_tour_data()
        assert "completed_at" in data["tours"]["app_overview"]

    def test_read_tour_data_handles_missing_file(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        data = tour_tracker._read_tour_data()
        assert "_version" in data
        assert data["tours"] == {}

    def test_read_tour_data_handles_corrupt_json(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        # Write corrupt JSON
        filepath = os.path.join(temp_tour_dir, ".tour_completed.json")
        with open(filepath, "w") as f:
            f.write("not valid json{{{")
        data = tour_tracker._read_tour_data()
        assert data == {"_version": "1.0", "tours": {}}

    def test_read_tour_data_handles_non_dict(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        filepath = os.path.join(temp_tour_dir, ".tour_completed.json")
        with open(filepath, "w") as f:
            json.dump([1, 2, 3], f)
        data = tour_tracker._read_tour_data()
        assert data == {"_version": "1.0", "tours": {}}

    def test_app_data_dir_created_on_write(self, temp_tour_dir):
        from ui.copilot import tour_tracker

        # The temp dir already exists, but verify the function handles it
        os.rmdir(temp_tour_dir)  # Remove it
        tour_tracker.mark_tour_completed("test")
        assert os.path.isdir(temp_tour_dir)


# =============================================================================
# tour_scripts
# =============================================================================


class TestTourScripts:
    """Tests for tour_scripts — authored walkthrough data integrity."""

    def test_onboarding_tour_has_correct_id(self):
        from ui.copilot.tour_scripts import ONBOARDING_TOUR

        assert ONBOARDING_TOUR["workflow_id"] == "app_overview"
        assert ONBOARDING_TOUR["title_key"] == "tour.app_overview.title"

    def test_onboarding_tour_has_8_steps(self):
        from ui.copilot.tour_scripts import ONBOARDING_TOUR

        steps = ONBOARDING_TOUR["steps"]
        assert len(steps) == 8

    def test_onboarding_tour_first_step_is_dim(self):
        from ui.copilot.tour_scripts import ONBOARDING_TOUR

        assert ONBOARDING_TOUR["steps"][0]["type"] == "dim"
        assert ONBOARDING_TOUR["steps"][0]["tooltip_key"] == "tour.app_overview.welcome"

    def test_onboarding_tour_last_step_is_success(self):
        from ui.copilot.tour_scripts import ONBOARDING_TOUR

        assert ONBOARDING_TOUR["steps"][-1]["type"] == "show_success"
        assert ONBOARDING_TOUR["steps"][-1]["tooltip_key"] == "tour.app_overview.complete"

    def test_add_driver_tour_has_5_steps(self):
        from ui.copilot.tour_scripts import ADD_DRIVER_TOUR

        steps = ADD_DRIVER_TOUR["steps"]
        assert len(steps) == 5
        assert steps[0]["type"] == "navigate"
        assert steps[-1]["type"] == "show_success"

    def test_generate_invoice_tour_has_5_steps(self):
        from ui.copilot.tour_scripts import GENERATE_INVOICE_TOUR

        steps = GENERATE_INVOICE_TOUR["steps"]
        assert len(steps) == 5
        assert steps[0]["type"] == "navigate"
        assert steps[-1]["type"] == "show_success"

    def test_dispatch_trip_tour_has_6_steps(self):
        from ui.copilot.tour_scripts import DISPATCH_TRIP_TOUR

        steps = DISPATCH_TRIP_TOUR["steps"]
        assert len(steps) == 6
        assert steps[0]["type"] == "navigate"
        assert steps[-1]["type"] == "show_success"

    def test_schedule_maintenance_tour_has_4_steps(self):
        from ui.copilot.tour_scripts import SCHEDULE_MAINTENANCE_TOUR

        steps = SCHEDULE_MAINTENANCE_TOUR["steps"]
        assert len(steps) == 4
        assert steps[0]["type"] == "navigate"
        assert steps[-1]["type"] == "show_success"

    def test_all_scripts_contains_5_entries(self):
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        assert len(ALL_SCRIPTS) == 5
        expected = {"app_overview", "add_driver", "generate_invoice", "dispatch_trip", "schedule_maintenance"}
        assert set(ALL_SCRIPTS.keys()) == expected

    def test_all_scripts_have_required_keys(self):
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        required = {"workflow_id", "title_key", "steps"}
        for script_id, script in ALL_SCRIPTS.items():
            assert required.issubset(script.keys()), f"{script_id} missing keys"

    def test_all_steps_have_required_keys(self):
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        step_required = {"step_id", "type", "tooltip_key", "order"}
        for script_id, script in ALL_SCRIPTS.items():
            for i, step in enumerate(script["steps"]):
                missing = step_required - step.keys()
                assert not missing, (
                    f"{script_id} step {i} missing: {missing}"
                )

    def test_all_steps_have_valid_types(self):
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        valid_types = {
            "dim", "highlight", "wait_for_click", "wait_for_input",
            "navigate", "show_success", "arrow", "pulse",
        }
        for script_id, script in ALL_SCRIPTS.items():
            for i, step in enumerate(script["steps"]):
                assert step["type"] in valid_types, (
                    f"{script_id} step {i} invalid type: {step['type']}"
                )

    def test_all_steps_have_increasing_order(self):
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        for script_id, script in ALL_SCRIPTS.items():
            orders = [s["order"] for s in script["steps"]]
            assert orders == sorted(orders), (
                f"{script_id} steps not in order: {orders}"
            )

    def test_all_target_element_ids_resolve(self):
        from ui.copilot.element_registry import resolve_element
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        for script_id, script in ALL_SCRIPTS.items():
            for step in script["steps"]:
                target = step.get("target_element_id")
                if target is not None:
                    assert resolve_element(target) is not None, (
                        f"{script_id} / {step['step_id']}: "
                        f"target_element_id '{target}' not in registry"
                    )

    def test_script_matches_backend_workflow(self):
        """Verify that each tour_scripts entry matches a backend workflow."""
        from backend.services.guided_workflow_service import GuidedWorkflowService
        from ui.copilot.tour_scripts import ALL_SCRIPTS

        service = GuidedWorkflowService()
        backend_ids = set(service.list_available_workflows())
        frontend_ids = set(ALL_SCRIPTS.keys())
        assert frontend_ids == backend_ids, (
            f"Mismatch: frontend={frontend_ids - backend_ids} "
            f"backend={backend_ids - frontend_ids}"
        )
