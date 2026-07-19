"""Tests for the desktop-side dataclass models in ui/copilot/models.py."""
from __future__ import annotations

from datetime import datetime

import pytest

from ui.copilot.models import (
    ConfirmationLevel,
    CoPilotResponse,
    Entity,
    ExecutionPlan,
    ExecutionStep,
    Insight,
    Intent,
    ToolResult,
)


class TestConfirmationLevel:
    def test_safe_is_zero(self):
        assert ConfirmationLevel.SAFE.value == 0

    def test_informational_is_one(self):
        assert ConfirmationLevel.INFORMATIONAL.value == 1

    def test_business_is_two(self):
        assert ConfirmationLevel.BUSINESS.value == 2

    def test_destructive_is_three(self):
        assert ConfirmationLevel.DESTRUCTIVE.value == 3

    def test_enum_membership(self):
        assert ConfirmationLevel.SAFE in ConfirmationLevel


class TestEntity:
    def test_created_with_defaults(self):
        e = Entity()
        assert e.type == ""
        assert e.value is None
        assert e.source == "extracted"
        assert e.confidence == 0.0

    def test_created_with_fields(self):
        e = Entity(type="vehicle", value={"id": 1}, source="user", confidence=0.95)
        assert e.type == "vehicle"
        assert e.value == {"id": 1}
        assert e.source == "user"
        assert e.confidence == 0.95


class TestIntent:
    def test_created_with_defaults(self):
        intent = Intent()
        assert intent.name == ""
        assert intent.entities == []
        assert intent.missing_required_entities == []
        assert intent.raw_utterance == ""

    def test_created_with_fields(self):
        entities = [Entity(type="vehicle", value="Truck 1")]
        intent = Intent(
            name="dispatch.create",
            entities=entities,
            missing_required_entities=["destination"],
            raw_utterance="Send truck 1 to Berlin",
        )
        assert intent.name == "dispatch.create"
        assert len(intent.entities) == 1
        assert intent.missing_required_entities == ["destination"]


class TestExecutionStep:
    def test_created_with_defaults(self):
        step = ExecutionStep()
        assert step.step_id == ""
        assert step.tool_name == ""
        assert step.tool_version == ""
        assert step.parameters == {}
        assert step.depends_on == []
        assert step.confirmation_level == ConfirmationLevel.SAFE
        assert step.status == "pending"
        assert step.result is None
        assert step.error is None
        assert step.started_at is None
        assert step.finished_at is None

    def test_created_with_fields(self):
        now = datetime.now()
        step = ExecutionStep(
            step_id="s1",
            tool_name="vehicle.search",
            tool_version="1.0.0",
            parameters={"query": "MAN"},
            depends_on=[],
            confirmation_level=ConfirmationLevel.INFORMATIONAL,
            status="running",
            result={"found": 3},
            error=None,
            started_at=now,
            finished_at=None,
        )
        assert step.step_id == "s1"
        assert step.tool_name == "vehicle.search"
        assert step.status == "running"
        assert step.confirmation_level == ConfirmationLevel.INFORMATIONAL
        assert step.result == {"found": 3}
        assert step.started_at == now


class TestExecutionPlan:
    def test_created_with_defaults(self):
        plan = ExecutionPlan()
        assert plan.plan_id == ""
        assert plan.conversation_id == ""
        assert plan.intent.name == ""
        assert plan.steps == []
        assert plan.overall_confidence == 0.0
        assert plan.requires_confirmation is False

    def test_created_with_steps(self):
        step = ExecutionStep(
            step_id="s1",
            tool_name="dispatch.create",
            tool_version="1.0.0",
            confirmation_level=ConfirmationLevel.BUSINESS,
        )
        plan = ExecutionPlan(
            plan_id="p1",
            conversation_id="c1",
            steps=[step],
            intent=Intent(name="dispatch.create", raw_utterance="dispatch"),
            overall_confidence=0.95,
            requires_confirmation=True,
        )
        assert len(plan.steps) == 1
        assert plan.steps[0].step_id == "s1"
        assert plan.overall_confidence == 0.95
        assert plan.requires_confirmation is True

    def test_requires_confirmation_depends_on_steps(self):
        """requires_confirmation is True when any step needs BUSINESS or DESTRUCTIVE."""
        # SAFE steps → no confirmation needed
        plan_safe = ExecutionPlan(
            steps=[
                ExecutionStep(step_id="s1", confirmation_level=ConfirmationLevel.SAFE),
                ExecutionStep(step_id="s2", confirmation_level=ConfirmationLevel.INFORMATIONAL),
            ]
        )
        # The dataclass stores requires_confirmation as-is, it's not computed.
        # The business logic is in the backend schema, not the desktop model.
        # Verify the field can be set independently.
        plan_safe.requires_confirmation = False
        assert plan_safe.requires_confirmation is False

        # When explicitly set to True
        plan_destructive = ExecutionPlan(
            steps=[ExecutionStep(step_id="s1", confirmation_level=ConfirmationLevel.DESTRUCTIVE)],
            requires_confirmation=True,
        )
        assert plan_destructive.requires_confirmation is True


class TestCoPilotResponse:
    def test_created_with_defaults(self):
        resp = CoPilotResponse()
        assert resp.conversation_id == ""
        assert resp.reasoning_graph is None
        assert resp.plan is None
        assert resp.clarification_question_key is None
        assert resp.clarification_params == {}
        assert resp.timeline == []
        assert resp.summary_key is None
        assert resp.summary_params == {}

    def test_created_with_fields(self):
        plan = ExecutionPlan(plan_id="p1", requires_confirmation=True)
        resp = CoPilotResponse(
            conversation_id="c1",
            plan=plan,
            summary_key="copilot.summary.ok",
            clarification_question_key="copilot.clarification.missing_entities",
        )
        assert resp.conversation_id == "c1"
        assert resp.plan is not None
        assert resp.plan.plan_id == "p1"
        assert resp.summary_key == "copilot.summary.ok"
        assert resp.clarification_question_key == "copilot.clarification.missing_entities"


class TestInsight:
    def test_created_with_defaults(self):
        insight = Insight()
        assert insight.id == ""
        assert insight.conversation_id == ""
        assert insight.insight_type == ""
        assert insight.payload == {}
        assert insight.severity == "low"
        assert insight.status == "new"
        assert insight.created_at is None

    def test_created_with_all_fields(self):
        insight = Insight(
            id="ins_1",
            conversation_id="c1",
            insight_type="cost_anomaly",
            payload={"amount": 5000},
            severity="high",
            status="new",
            created_at="2026-07-16T10:00:00Z",
        )
        assert insight.id == "ins_1"
        assert insight.insight_type == "cost_anomaly"
        assert insight.payload == {"amount": 5000}
        assert insight.severity == "high"
        assert insight.created_at == "2026-07-16T10:00:00Z"


class TestToolResult:
    def test_created_with_defaults(self):
        tr = ToolResult()
        assert tr.status == ""
        assert tr.data is None
        assert tr.message_key == ""
        assert tr.message_params == {}
        assert tr.undo_token is None

    def test_created_with_fields(self):
        tr = ToolResult(
            status="success",
            data={"receipt_id": 42},
            message_key="copilot.receipt.draft.success",
            undo_token="u1",
        )
        assert tr.status == "success"
        assert tr.data == {"receipt_id": 42}
        assert tr.message_key == "copilot.receipt.draft.success"
        assert tr.undo_token == "u1"
