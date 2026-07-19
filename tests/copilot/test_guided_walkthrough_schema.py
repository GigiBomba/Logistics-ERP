"""Schema round-trip tests for GuidedWalkthrough / GuidedStep.

Blueprint §34.14 test requirement: "GuidedWalkthrough/GuidedStep round-trip
serialization, same pattern as §4's core contract tests."
"""
from __future__ import annotations

import pytest

from backend.copilot.schemas import (
    GuidedStep,
    GuidedStepType,
    GuidedWalkthrough,
)


class TestGuidedWalkthroughSchema:
    """GuidedWalkthrough / GuidedStep round-trip serialization tests."""

    def test_guided_step_defaults(self):
        step = GuidedStep(
            step_id="s1",
            type=GuidedStepType.HIGHLIGHT,
            tooltip_key="tour.test.step1",
            order=1,
        )
        assert step.step_id == "s1"
        assert step.type == GuidedStepType.HIGHLIGHT
        assert step.target_element_id is None
        assert step.tooltip_key == "tour.test.step1"
        assert step.tooltip_params == {}
        assert step.order == 1

    def test_guided_step_with_target(self):
        step = GuidedStep(
            step_id="s2",
            type=GuidedStepType.WAIT_FOR_CLICK,
            target_element_id="btn_add_driver",
            tooltip_key="tour.add_driver.click_add",
            tooltip_params={"name": "John"},
            order=2,
        )
        assert step.target_element_id == "btn_add_driver"
        assert step.tooltip_params == {"name": "John"}

    def test_guided_step_roundtrip_json(self):
        step = GuidedStep(
            step_id="s1",
            type=GuidedStepType.WAIT_FOR_CLICK,
            target_element_id="btn_add_driver",
            tooltip_key="tour.test.click",
            tooltip_params={"field": "name"},
            order=1,
        )
        json_str = step.model_dump_json()
        restored = GuidedStep.model_validate_json(json_str)
        assert restored.step_id == step.step_id
        assert restored.type == step.type
        assert restored.target_element_id == step.target_element_id
        assert restored.tooltip_key == step.tooltip_key
        assert restored.tooltip_params == step.tooltip_params
        assert restored.order == step.order

    def test_guided_step_roundtrip_dict(self):
        step = GuidedStep(
            step_id="s1",
            type=GuidedStepType.DIM,
            tooltip_key="tour.test.dim",
            order=1,
        )
        d = step.model_dump()
        restored = GuidedStep.model_validate(d)
        assert restored.step_id == "s1"
        assert restored.type == GuidedStepType.DIM
        assert restored.tooltip_key == "tour.test.dim"

    def test_guided_step_all_types_serialize(self):
        for step_type in GuidedStepType:
            step = GuidedStep(
                step_id=f"t_{step_type.value}",
                type=step_type,
                tooltip_key=f"tour.test.{step_type.value}",
                order=1,
            )
            json_str = step.model_dump_json()
            restored = GuidedStep.model_validate_json(json_str)
            assert restored.type == step_type

    def test_walkthrough_defaults(self):
        w = GuidedWalkthrough(
            workflow_id="test_workflow",
            title_key="tour.test.title",
            steps=[],
        )
        assert w.workflow_id == "test_workflow"
        assert w.title_key == "tour.test.title"
        assert w.steps == []
        assert w.familiarity_adjusted is False
        assert w.doc_corpus_version == "1.0.0"

    def test_walkthrough_with_steps(self):
        steps = [
            GuidedStep(
                step_id="s1",
                type=GuidedStepType.DIM,
                tooltip_key="tour.test.s1",
                order=1,
            ),
            GuidedStep(
                step_id="s2",
                type=GuidedStepType.HIGHLIGHT,
                target_element_id="nav_overview",
                tooltip_key="tour.test.s2",
                order=2,
            ),
            GuidedStep(
                step_id="s3",
                type=GuidedStepType.SHOW_SUCCESS,
                tooltip_key="tour.test.s3",
                order=3,
            ),
        ]
        w = GuidedWalkthrough(
            workflow_id="multi_step",
            title_key="tour.test.multi",
            steps=steps,
            familiarity_adjusted=True,
            doc_corpus_version="1.0.0",
        )
        assert len(w.steps) == 3
        assert w.familiarity_adjusted is True
        assert w.doc_corpus_version == "1.0.0"
        assert w.steps[0].type == GuidedStepType.DIM
        assert w.steps[1].target_element_id == "nav_overview"
        assert w.steps[2].type == GuidedStepType.SHOW_SUCCESS

    def test_walkthrough_roundtrip_json(self):
        steps = [
            GuidedStep(
                step_id="s1",
                type=GuidedStepType.NAVIGATE,
                target_element_id="nav_drivers",
                tooltip_key="tour.test.nav",
                order=1,
            ),
        ]
        w = GuidedWalkthrough(
            workflow_id="navigate_test",
            title_key="tour.test.nav_title",
            steps=steps,
            familiarity_adjusted=False,
            doc_corpus_version="1.0.0",
        )
        json_str = w.model_dump_json()
        restored = GuidedWalkthrough.model_validate_json(json_str)
        assert restored.workflow_id == w.workflow_id
        assert restored.title_key == w.title_key
        assert restored.familiarity_adjusted == w.familiarity_adjusted
        assert restored.doc_corpus_version == w.doc_corpus_version
        assert len(restored.steps) == len(w.steps)
        assert restored.steps[0].step_id == w.steps[0].step_id
        assert restored.steps[0].type == w.steps[0].type
        assert restored.steps[0].target_element_id == w.steps[0].target_element_id

    def test_walkthrough_empty_steps(self):
        w = GuidedWalkthrough(
            workflow_id="empty",
            title_key="tour.empty",
            steps=[],
        )
        json_str = w.model_dump_json()
        restored = GuidedWalkthrough.model_validate_json(json_str)
        assert restored.steps == []

    def test_walkthrough_with_full_params(self):
        step = GuidedStep(
            step_id="s1",
            type=GuidedStepType.TOOLTIP,
            target_element_id="overview_metrics",
            tooltip_key="tour.test.params",
            tooltip_params={"count": 42, "name": "Revenue"},
            order=1,
        )
        w = GuidedWalkthrough(
            workflow_id="params_test",
            title_key="tour.test.params_title",
            steps=[step],
            familiarity_adjusted=True,
            doc_corpus_version="2.0.0",
        )
        json_str = w.model_dump_json()
        restored = GuidedWalkthrough.model_validate_json(json_str)
        assert restored.steps[0].tooltip_params == {"count": 42, "name": "Revenue"}

    def test_guided_step_type_values(self):
        assert GuidedStepType.HIGHLIGHT.value == "highlight"
        assert GuidedStepType.DIM.value == "dim"
        assert GuidedStepType.TOOLTIP.value == "tooltip"
        assert GuidedStepType.ARROW.value == "arrow"
        assert GuidedStepType.PULSE.value == "pulse"
        assert GuidedStepType.WAIT_FOR_CLICK.value == "wait_for_click"
        assert GuidedStepType.WAIT_FOR_INPUT.value == "wait_for_input"
        assert GuidedStepType.NAVIGATE.value == "navigate"
        assert GuidedStepType.SHOW_SUCCESS.value == "show_success"
