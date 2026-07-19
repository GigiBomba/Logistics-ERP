"""Schema round-trip tests — prove every data contract serializes losslessly.

Blueprint: §4 (core contracts), §5.2 (reasoning graph).
"""

import json
from datetime import datetime, timezone

import pytest

from backend.copilot.schemas import (
    CoPilotResponse,
    ConfirmationLevel,
    ConversationContext,
    Entity,
    ExecutionPlan,
    ExecutionStep,
    GlobalContext,
    Intent,
    ReasoningGraph,
    ReasoningNode,
    ReasoningNodeType,
    SessionContext,
    ToolContext,
    ToolResult,
)


class TestCoreContracts:
    """§4: Round-trip every core schema."""

    def test_entity_roundtrip(self):
        e = Entity(type="customer", value={"id": 42, "name": "ACME Corp"}, source="extracted", confidence=0.95)
        j = e.model_dump_json()
        restored = Entity.model_validate_json(j)
        assert restored.type == e.type
        assert restored.value == e.value
        assert restored.source == e.source
        assert restored.confidence == pytest.approx(0.95)

    def test_intent_roundtrip(self):
        intent = Intent(
            name="dispatch.create",
            entities=[Entity(type="vehicle", value="Truck 18", source="extracted", confidence=0.9)],
            missing_required_entities=["destination"],
            raw_utterance="Send Truck 18 to Berlin",
        )
        j = intent.model_dump_json()
        restored = Intent.model_validate_json(j)
        assert restored.name == intent.name
        assert len(restored.entities) == 1
        assert restored.missing_required_entities == ["destination"]

    def test_execution_step_roundtrip(self):
        step = ExecutionStep(
            step_id="s1",
            tool_name="vehicle.search",
            tool_version="1.0.0",
            parameters={"location": "Berlin"},
            depends_on=[],
            confirmation_level=ConfirmationLevel.SAFE,
            status="pending",
        )
        j = step.model_dump_json()
        restored = ExecutionStep.model_validate_json(j)
        assert restored.step_id == "s1"
        assert restored.tool_name == "vehicle.search"
        assert restored.status == "pending"

    def test_execution_plan_roundtrip(self):
        step = ExecutionStep(step_id="s1", tool_name="dispatch.create", tool_version="1.0.0",
                             parameters={}, confirmation_level=ConfirmationLevel.BUSINESS, status="pending")
        plan = ExecutionPlan(
            plan_id="p1",
            conversation_id="c1",
            reasoning_graph_id="rg1",
            intent=Intent(name="dispatch.create", raw_utterance="dispatch"),
            steps=[step],
            overall_confidence=0.92,
            requires_confirmation=True,
        )
        j = plan.model_dump_json()
        restored = ExecutionPlan.model_validate_json(j)
        assert restored.plan_id == "p1"
        assert len(restored.steps) == 1
        assert restored.requires_confirmation is True

    def test_tool_result_roundtrip(self):
        tr = ToolResult(status="success", data={"id": 1}, message_key="copilot.step.dispatch_created",
                        message_params={"truck": "MAN TGX"}, undo_token="u1")
        j = tr.model_dump_json()
        restored = ToolResult.model_validate_json(j)
        assert restored.status == "success"
        assert restored.undo_token == "u1"

    def test_copilot_response_roundtrip(self):
        resp = CoPilotResponse(conversation_id="c1", summary_key="copilot.summary.ok")
        j = resp.model_dump_json()
        restored = CoPilotResponse.model_validate_json(j)
        assert restored.conversation_id == "c1"
        assert restored.summary_key == "copilot.summary.ok"

    def test_confirmation_level_values(self):
        assert ConfirmationLevel.SAFE == 0
        assert ConfirmationLevel.INFORMATIONAL == 1
        assert ConfirmationLevel.BUSINESS == 2
        assert ConfirmationLevel.DESTRUCTIVE == 3


class TestReasoningGraphContracts:
    """§5.2: Round-trip reasoning graph models."""

    def test_reasoning_node_roundtrip(self):
        node = ReasoningNode(
            node_id="n1",
            type=ReasoningNodeType.QUERY,
            label="copilot.reasoning.need_destination",
            status="resolved",
            resolved_value="Cluj",
            resolved_source="extracted",
            tool_name="vehicle.search",
            tool_version="1.0.0",
            children=["n2"],
        )
        j = node.model_dump_json()
        restored = ReasoningNode.model_validate_json(j)
        assert restored.node_id == "n1"
        assert restored.type == ReasoningNodeType.QUERY
        assert restored.status == "resolved"
        assert restored.tool_name == "vehicle.search"

    def test_reasoning_graph_roundtrip(self):
        node = ReasoningNode(node_id="root", type=ReasoningNodeType.GOAL, label="dispatch.create", status="resolved")
        graph = ReasoningGraph(
            graph_id="rg1",
            conversation_id="c1",
            root_node_id="root",
            nodes={"root": node},
        )
        j = graph.model_dump_json()
        restored = ReasoningGraph.model_validate_json(j)
        assert restored.graph_id == "rg1"
        assert "root" in restored.nodes
        assert restored.nodes["root"].type == ReasoningNodeType.GOAL

    def test_reasoning_node_type_values(self):
        assert ReasoningNodeType.GOAL == "goal"
        assert ReasoningNodeType.REQUIREMENT == "requirement"
        assert ReasoningNodeType.SUB_GOAL == "sub_goal"
        assert ReasoningNodeType.QUERY == "query"
        assert ReasoningNodeType.COMPARISON == "comparison"
        assert ReasoningNodeType.DECISION == "decision"


class TestContextContracts:
    """§8: Round-trip context models."""

    def test_global_context_roundtrip(self):
        ctx = GlobalContext(company_id=1, user_id=1, role="dispatcher", language="en",
                            timezone="Europe/Bucharest", subscription_tier="business")
        j = ctx.model_dump_json()
        restored = GlobalContext.model_validate_json(j)
        assert restored.company_id == 1
        assert restored.subscription_tier == "business"

    def test_session_context_roundtrip(self):
        ctx = SessionContext(current_customer_id=42, current_trip_id=100, current_module="dispatcher_board")
        j = ctx.model_dump_json()
        restored = SessionContext.model_validate_json(j)
        assert restored.current_customer_id == 42

    def test_conversation_context_roundtrip(self):
        ctx = ConversationContext(conversation_id="c1", pinned_provider_id="google",
                                  pinned_model_id="gemini-2.5-flash", pinned_prompt_version="v1.0")
        j = ctx.model_dump_json()
        restored = ConversationContext.model_validate_json(j)
        assert restored.pinned_provider_id == "google"

    def test_tool_context_roundtrip(self):
        ctx = ToolContext(available_tools=["vehicle.search", "dispatch.create"],
                          tool_parameters_schema={"vehicle.search": {"type": "object"}})
        j = ctx.model_dump_json()
        restored = ToolContext.model_validate_json(j)
        assert "vehicle.search" in restored.available_tools


class TestSupportedLanguages:
    """§3.1: Canonical language list."""

    def test_supported_languages_count(self):
        from backend.copilot.schemas import SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) == 22

    def test_supported_languages_unique(self):
        from backend.copilot.schemas import SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) == len(set(SUPPORTED_LANGUAGES))

    def test_supported_languages_all_two_char(self):
        from backend.copilot.schemas import SUPPORTED_LANGUAGES
        for lang in SUPPORTED_LANGUAGES:
            assert len(lang) == 2, f"{lang} is not a 2-char ISO code"
