"""Reasoning Graph — mandatory intermediate layer between Understanding and Execution.

Blueprint: §5 — Reasoning Graph.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.copilot.llm.base import LLMProvider
from backend.copilot.schemas import (
    ConfirmationLevel,
    Intent,
    ReasoningGraph,
    ReasoningNode,
    ReasoningNodeType,
    SessionContext,
    ToolResult,
)
from backend.copilot.tools.registry import get_tool, available_tools

logger = logging.getLogger(__name__)


async def build_reasoning_graph(
    conversation_id: str,
    intent: Intent,
) -> ReasoningGraph:
    """Build a ReasoningGraph from an extracted Intent.

    Phase 1: Simple mapping — each entity becomes a REQUIREMENT node,
    the intent name becomes a GOAL node with children.
    Missing entities become unresolved REQUIREMENT nodes.
    """
    graph_id = str(uuid.uuid4())
    nodes: Dict[str, ReasoningNode] = {}

    # Root: GOAL node
    root_id = f"goal-{intent.name}"
    nodes[root_id] = ReasoningNode(
        node_id=root_id,
        type=ReasoningNodeType.GOAL,
        label=f"copilot.intent.{intent.name}",
        status="resolved",
        children=[],
    )

    # Add REQUIREMENT nodes for each entity (resolved)
    for entity in intent.entities:
        node_id = f"req-{entity.type}"
        nodes[node_id] = ReasoningNode(
            node_id=node_id,
            type=ReasoningNodeType.REQUIREMENT,
            label=f"copilot.reasoning.have_{entity.type}",
            status="resolved",
            resolved_value=entity.value,
            resolved_source=entity.source,
        )
        nodes[root_id].children.append(node_id)

    # Add REQUIREMENT nodes for missing entities (unresolved)
    for missing in intent.missing_required_entities:
        node_id = f"req-{missing}"
        nodes[node_id] = ReasoningNode(
            node_id=node_id,
            type=ReasoningNodeType.REQUIREMENT,
            label=f"copilot.reasoning.need_{missing}",
            status="unresolved",
        )
        nodes[root_id].children.append(node_id)

    graph = ReasoningGraph(
        graph_id=graph_id,
        conversation_id=conversation_id,
        root_node_id=root_id,
        nodes=nodes,
    )

    logger.info("Built reasoning graph %s with %d nodes for intent %s", graph_id, len(nodes), intent.name)
    return graph


async def resolve_reasoning_graph(
    graph: ReasoningGraph,
    company_id: int,
    user_id: int,
    role: str,
    session_context: Optional[SessionContext] = None,
    services: Optional[Dict[str, Any]] = None,
) -> ReasoningGraph:
    """Resolve QUERY nodes by executing Level 0 tool calls.

    Phase 1: This is the simple path — we only handle the case where the graph
    already has resolved REQUIREMENT nodes. QUERY nodes (for e.g. vehicle comparison)
    are built by the LLM during reasoning_graph_resolution in future phases.

    For now, this returns the graph as-is since Phase 1 intent extraction produces
    graphs with REQUIREMENT nodes only (no QUERY nodes needing resolution).
    """
    # Mark any fully-resolved graph as finalized
    all_resolved = all(
        node.status == "resolved"
        for node in graph.nodes.values()
    )
    if all_resolved:
        graph.finalized_at = datetime.utcnow()

    return graph
