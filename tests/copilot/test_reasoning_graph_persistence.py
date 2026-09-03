"""Reasoning-graph persistence tests — §5.5.

The planner persists the resolved ``ReasoningGraph`` via
``CopilotReasoningGraphRepository.upsert`` after ``resolve_reasoning_graph``
runs (planner.py step 4b).  These tests assert a save + load round-trip
through the repository against a real SQLite DB, both directly and through a
full ``process_utterance`` invocation.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.copilot.schemas import (
    GlobalContext,
    Intent,
    ReasoningGraph,
    ReasoningNode,
    ReasoningNodeType,
)
from tests.test_helpers import InMemoryDB


@pytest.fixture(autouse=True)
def _offline_llm_chat():
    """Force the keyword (offline-fallback) path — a configured provider
    (env API keys like GOOGLE_API_KEY) must never trigger live calls in the
    test suite."""
    from backend.copilot.llm.tool_calling import ToolLoopResult

    with patch("backend.copilot.llm.chat.chat_with_tools", new_callable=AsyncMock) as m:
        m.return_value = ToolLoopResult(attempted=False, provider_failed=False)
        yield m


@pytest.fixture
def db():
    """In-memory DB with the ``copilot_reasoning_graphs`` table.

    ``InMemoryDB`` ships the core ERP schema; the ``copilot_*`` tables are
    created by Alembic migrations rather than the base schema, so the table is
    created here explicitly (mirroring ``test_copilot_repository_cleanup.py``).
    The unique index on ``(company_id, conversation_id)`` mirrors
    database/schema.py (SQLite) / the Alembic migration so the repository's
    ON CONFLICT upsert truly replaces instead of appending.
    """
    from database.tenant_context import clear_context

    d = InMemoryDB()
    d.conn.execute("""CREATE TABLE IF NOT EXISTS copilot_reasoning_graphs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER REFERENCES companies(id),
        conversation_id TEXT,
        plan_id TEXT,
        status TEXT DEFAULT 'building',
        root_node_id TEXT,
        graph TEXT,
        graph_json TEXT,
        created_at TEXT,
        finalized_at TEXT
    )""")
    d.conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_copilot_reasoning_company_conversation "
        "ON copilot_reasoning_graphs(company_id, conversation_id)"
    )
    d.conn.commit()
    yield d
    clear_context()
    d.close()


def _make_graph(graph_id: str = "rg-1", conversation_id: str = "conv-1") -> ReasoningGraph:
    return ReasoningGraph(
        graph_id=graph_id,
        conversation_id=conversation_id,
        root_node_id="root",
        nodes={
            "root": ReasoningNode(
                node_id="root",
                type=ReasoningNodeType.GOAL,
                label="vehicle.search",
                status="resolved",
            ),
            "q1": ReasoningNode(
                node_id="q1",
                type=ReasoningNodeType.QUERY,
                label="trucks.list",
                status="resolved",
                tool_name="vehicle.search",
                resolved_value='[{"id": 1}]',
            ),
        },
    )


class TestReasoningGraphRepositoryRoundTrip:
    """Save + load through CopilotReasoningGraphRepository against a real DB."""

    def test_upsert_then_get_round_trip(self, db):
        from database.tenant_context import set_company_context
        from repositories.copilot_repository import CopilotReasoningGraphRepository

        set_company_context(1)
        graph = _make_graph()
        repo = CopilotReasoningGraphRepository(db)

        repo.upsert(graph.conversation_id, graph.model_dump_json())

        row = repo.get_by_conversation(graph.conversation_id)
        assert row is not None, "get_by_conversation must find the persisted graph"
        assert row["company_id"] == 1
        loaded = ReasoningGraph.model_validate_json(row["graph_json"])
        assert loaded.graph_id == graph.graph_id
        assert loaded.root_node_id == graph.root_node_id
        assert loaded.nodes.keys() == graph.nodes.keys()

    def test_get_by_conversation_tenant_scoped(self, db):
        """Company 2 must not see company 1's persisted graph."""
        from database.tenant_context import set_company_context
        from repositories.copilot_repository import CopilotReasoningGraphRepository

        set_company_context(1)
        repo = CopilotReasoningGraphRepository(db)
        repo.upsert("conv-a", _make_graph(conversation_id="conv-a").model_dump_json())

        # Same DB, different tenant context → row invisible.
        set_company_context(2)
        assert repo.get_by_conversation("conv-a") is None

        set_company_context(1)
        assert repo.get_by_conversation("conv-a") is not None

    def test_repeated_upsert_round_trip_still_readable(self, db):
        """Two upserts for one conversation leave EXACTLY ONE row.

        ``upsert`` uses ``INSERT ... ON CONFLICT (company_id,
        conversation_id) DO UPDATE`` and the schema imposes a unique index on
        that pair, so a second upsert REPLACES the first row instead of
        appending — ``get_by_conversation`` returns the latest graph and the
        table never accumulates duplicates.
        """
        from database.tenant_context import set_company_context
        from repositories.copilot_repository import CopilotReasoningGraphRepository

        set_company_context(1)
        repo = CopilotReasoningGraphRepository(db)
        repo.upsert("conv-b", _make_graph(graph_id="rg-v1", conversation_id="conv-b").model_dump_json())
        repo.upsert("conv-b", _make_graph(graph_id="rg-v2", conversation_id="conv-b").model_dump_json())

        # Round-trip still works: the row resolves to a valid graph.
        row = repo.get_by_conversation("conv-b")
        assert row is not None
        loaded = ReasoningGraph.model_validate_json(row["graph_json"])
        assert loaded.conversation_id == "conv-b"
        # And the upsert was a true replace — exactly one row survives.
        rows = db.rows_to_dicts(
            db.conn.execute(
                "SELECT conversation_id, graph_json FROM copilot_reasoning_graphs "
                "WHERE conversation_id = 'conv-b'"
            ).fetchall()
        )
        assert len(rows) == 1, "repeated upsert must not append duplicate graphs"
        assert json.loads(rows[0]["graph_json"])["graph_id"] == "rg-v2"


class TestPlannerPersistsGraph:
    """A real ``process_utterance`` run persists the graph through services["db"]."""

    @pytest.mark.asyncio
    async def test_process_utterance_writes_reasoning_graph(self, db):
        from database.tenant_context import set_company_context
        from backend.copilot.planner import process_utterance
        from repositories.copilot_repository import CopilotReasoningGraphRepository

        set_company_context(1)
        graph = _make_graph(graph_id="rg-planner", conversation_id="conv-planner")
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="enterprise",
        )
        intent = Intent(
            name="vehicle.search", entities=[],
            missing_required_entities=[], raw_utterance="show trucks",
        )

        with (
            patch("backend.copilot.planner.extract_intent",
                  new=AsyncMock(return_value=intent)),
            patch("backend.copilot.planner.build_reasoning_graph",
                  new=AsyncMock(return_value=graph)),
            patch("backend.copilot.planner.resolve_reasoning_graph",
                  new=AsyncMock(return_value=graph)),
            patch("backend.copilot.planner.compile_execution_plan",
                  new=AsyncMock(return_value=None)),
        ):
            response = await process_utterance(
                utterance="show trucks",
                global_ctx=ctx,
                conversation_id="conv-planner",
                services={"db": db, "role": "dispatcher", "user_id": 1, "company_id": 1},
                permitted_tools=["vehicle.search"],
            )

        assert response is not None

        row = CopilotReasoningGraphRepository(db).get_by_conversation("conv-planner")
        assert row is not None, (
            "process_utterance must persist the resolved reasoning graph (§5.5)"
        )
        loaded = ReasoningGraph.model_validate_json(row["graph_json"])
        assert loaded.graph_id == "rg-planner"
        assert loaded.conversation_id == "conv-planner"
        # Persisted content matches what the planner resolved.
        persisted = json.loads(row["graph_json"])
        assert persisted["root_node_id"] == graph.root_node_id

    @pytest.mark.asyncio
    async def test_planner_without_db_does_not_crash(self, db):
        """services["db"] is None → persistence skipped, pipeline still returns."""
        from backend.copilot.planner import process_utterance

        graph = _make_graph(graph_id="rg-nodb", conversation_id="conv-nodb")
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="enterprise",
        )
        intent = Intent(
            name="vehicle.search", entities=[],
            missing_required_entities=[], raw_utterance="show trucks",
        )

        with (
            patch("backend.copilot.planner.extract_intent",
                  new=AsyncMock(return_value=intent)),
            patch("backend.copilot.planner.build_reasoning_graph",
                  new=AsyncMock(return_value=graph)),
            patch("backend.copilot.planner.resolve_reasoning_graph",
                  new=AsyncMock(return_value=graph)),
            patch("backend.copilot.planner.compile_execution_plan",
                  new=AsyncMock(return_value=None)),
        ):
            response = await process_utterance(
                utterance="show trucks",
                global_ctx=ctx,
                conversation_id="conv-nodb",
                services=None,
                permitted_tools=["vehicle.search"],
            )

        assert response is not None