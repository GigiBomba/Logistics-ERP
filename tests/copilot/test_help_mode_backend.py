"""Tests for backend Help Mode services and tools.

Covers:
- DocumentationService (documentation_service.py)
- GuidedWorkflowService (guided_workflow_service.py)
- HelpAnswerQuestionTool / GuideWorkflowTool (help_tools.py)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.copilot.schemas import (
    GuideWorkflowParams,
    GuidedStep,
    GuidedStepType,
    GuidedWalkthrough,
    HelpAnswer,
    HelpAnswerParams,
)
from backend.copilot.tools.help_tools import GuideWorkflowTool, HelpAnswerQuestionTool


def _make_tool_ctx() -> MagicMock:
    """Create a minimal mock ToolExecutionContext."""
    ctx = MagicMock()
    ctx.session_context = MagicMock()
    ctx.session_context.current_module = "en"
    ctx.user_id = 1
    ctx.company_id = 1
    return ctx


# =============================================================================
# DocumentationService
# =============================================================================


class TestDocumentationService:
    """Tests for DocumentationService — keyword search + answer building."""

    def test_search_returns_relevant_articles(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        results = service.search("how do I manage my fleet vehicles")
        assert len(results) >= 1
        article_ids = [r["article_id"] for r in results]
        assert "fleet_management" in article_ids

    def test_search_top_k_defaults_to_3(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        results = service.search("document")
        assert len(results) <= 3

    def test_search_top_k_custom(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        results = service.search("document", top_k=5)
        assert 1 <= len(results) <= 5

    def test_search_sorted_by_relevance(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        results = service.search("driver tachograph hours")
        assert len(results) >= 1
        # The most relevant should be driver_management
        assert results[0]["article_id"] == "driver_management"

    def test_search_returns_romanian_content(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        # Search for a word present in Romanian content but not English content
        # "toate" appears in Romanian overrides: "toate vehiculele", "toate informațiile"
        results = service.search("toate", language="ro")
        assert len(results) >= 1
        # The Romanian content should contain Romanian words, not English defaults
        content = results[0]["content"]
        assert "toate" in content

    def test_search_falls_back_to_english_for_unknown_language(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        results = service.search("fleet", language="xx")
        assert len(results) >= 1

    def test_search_unknown_query_returns_empty(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        results = service.search("xyznonexistent12345")
        assert results == []

    def test_search_and_answer_returns_help_answer(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        answer = service.search_and_answer("how do I manage drivers")
        assert isinstance(answer, HelpAnswer)
        assert len(answer.sources) >= 1
        assert answer.sources[0].article_id is not None

    def test_search_and_answer_no_results_returns_empty_sources(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        answer = service.search_and_answer("xyznonexistent12345")
        assert isinstance(answer, HelpAnswer)
        assert answer.sources == []

    def test_search_and_answer_filters_by_active_screen(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        answer = service.search_and_answer(
            "how do I manage invoices and billing",
            active_screen="invoices",
        )
        assert len(answer.sources) >= 1
        assert answer.sources[0].article_id == "invoices"

    def test_search_and_answer_with_unmatched_screen_returns_results(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        answer = service.search_and_answer(
            "driver tachograph",
            active_screen="billing",
        )
        assert len(answer.sources) >= 1

    def test_doc_source_excerpt_is_truncated(self):
        from backend.services.documentation_service import DocumentationService

        service = DocumentationService()
        answer = service.search_and_answer("fleet")
        for source in answer.sources:
            assert len(source.excerpt) <= 203  # 200 chars + optional "..."

    def test_singleton_returns_same_instance(self):
        from backend.services.documentation_service import (
            DocumentationService,
            get_documentation_service,
        )

        s1 = get_documentation_service()
        s2 = get_documentation_service()
        assert s1 is s2
        assert isinstance(s1, DocumentationService)


# =============================================================================
# GuidedWorkflowService
# =============================================================================


class TestGuidedWorkflowService:
    """Tests for GuidedWorkflowService — walkthrough scripts + familiarity."""

    def test_get_script_app_overview(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("app_overview")
        assert script is not None
        assert isinstance(script, GuidedWalkthrough)
        assert script.workflow_id == "app_overview"
        assert len(script.steps) == 8

    def test_get_script_add_driver(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("add_driver")
        assert script is not None
        assert script.workflow_id == "add_driver"
        assert len(script.steps) == 5

    def test_get_script_generate_invoice(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("generate_invoice")
        assert script is not None
        assert script.workflow_id == "generate_invoice"
        assert len(script.steps) == 5

    def test_get_script_dispatch_trip(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("dispatch_trip")
        assert script is not None
        assert script.workflow_id == "dispatch_trip"
        assert len(script.steps) == 6

    def test_get_script_schedule_maintenance(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("schedule_maintenance")
        assert script is not None
        assert script.workflow_id == "schedule_maintenance"
        assert len(script.steps) == 4

    def test_get_script_unknown_returns_none(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        assert service.get_script("nonexistent") is None

    def test_list_available_workflows(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        workflows = service.list_available_workflows()
        expected = {"app_overview", "add_driver", "generate_invoice", "dispatch_trip", "schedule_maintenance"}
        assert set(workflows) == expected

    def test_adjust_for_familiarity_new(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("app_overview")
        assert script is not None
        adjusted = service.adjust_for_familiarity(script, familiarity_level="new")
        # "new" returns the same object unchanged
        assert adjusted is script or not adjusted.familiarity_adjusted

    def test_adjust_for_familiarity_familiar_adds_short_suffix(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("add_driver")
        assert script is not None
        adjusted = service.adjust_for_familiarity(script, familiarity_level="familiar")
        assert adjusted.familiarity_adjusted is True
        for step in adjusted.steps:
            if step.tooltip_key:
                assert step.tooltip_key.endswith(".short")

    def test_adjust_for_familiarity_expert_keeps_two_steps(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("dispatch_trip")
        assert script is not None
        adjusted = service.adjust_for_familiarity(script, familiarity_level="expert")
        assert adjusted.familiarity_adjusted is True
        assert len(adjusted.steps) == 2
        assert adjusted.steps[0].step_id == "start"
        assert adjusted.steps[-1].step_id == "quick_complete"

    def test_adjust_for_familiarity_expert_single_step_script(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        single = GuidedWalkthrough(
            workflow_id="test",
            title_key="test.title",
            steps=[
                GuidedStep(step_id="only", type=GuidedStepType.DIM, tooltip_key="test.only", order=1),
            ],
        )
        adjusted = service.adjust_for_familiarity(single, familiarity_level="expert")
        assert len(adjusted.steps) == 2
        assert adjusted.steps[0].step_id == "only"
        assert adjusted.steps[-1].step_id == "quick_complete"

    def test_adjust_for_familiarity_unknown_level_returns_as_is(self):
        from backend.services.guided_workflow_service import GuidedWorkflowService

        service = GuidedWorkflowService()
        script = service.get_script("app_overview")
        assert script is not None
        adjusted = service.adjust_for_familiarity(script, familiarity_level="bogus")
        assert adjusted is script

    def test_singleton_returns_same_instance(self):
        from backend.services.guided_workflow_service import (
            GuidedWorkflowService,
            get_guided_workflow_service,
        )

        s1 = get_guided_workflow_service()
        s2 = get_guided_workflow_service()
        assert s1 is s2
        assert isinstance(s1, GuidedWorkflowService)


# =============================================================================
# HelpAnswerQuestionTool
# =============================================================================


class TestHelpAnswerQuestionTool:
    """Tests for help.answer_question tool."""

    @pytest.mark.asyncio
    async def test_validate_rejects_empty_question(self):
        tool = HelpAnswerQuestionTool()
        params = HelpAnswerParams(question="")
        ctx = _make_tool_ctx()
        errors = await tool.validate(params, ctx)
        assert any("empty_question" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_rejects_whitespace_only(self):
        tool = HelpAnswerQuestionTool()
        params = HelpAnswerParams(question="   ")
        ctx = _make_tool_ctx()
        errors = await tool.validate(params, ctx)
        assert any("empty_question" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_rejects_question_too_long(self):
        tool = HelpAnswerQuestionTool()
        params = HelpAnswerParams(question="x" * 2001)
        ctx = _make_tool_ctx()
        errors = await tool.validate(params, ctx)
        assert any("question_too_long" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_accepts_valid_question(self):
        tool = HelpAnswerQuestionTool()
        params = HelpAnswerParams(question="How do I manage my fleet?")
        ctx = _make_tool_ctx()
        errors = await tool.validate(params, ctx)
        assert errors == []

    @pytest.mark.asyncio
    async def test_execute_returns_success_with_answer(self):
        tool = HelpAnswerQuestionTool()
        params = HelpAnswerParams(question="How do I manage my fleet?")
        ctx = _make_tool_ctx()
        result = await tool.execute(params, ctx)
        assert result.status == "success"
        assert isinstance(result.data, dict)
        assert "answer" in result.data
        assert len(result.data["answer"]["sources"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_returns_no_answer_for_unknown_question(self):
        tool = HelpAnswerQuestionTool()
        params = HelpAnswerParams(question="xyznonexistent12345")
        ctx = _make_tool_ctx()
        result = await tool.execute(params, ctx)
        assert result.status == "success"
        assert isinstance(result.data, dict)
        assert len(result.data["answer"]["sources"]) == 0

    @pytest.mark.asyncio
    async def test_execute_handles_exception_gracefully(self):
        tool = HelpAnswerQuestionTool()
        params = HelpAnswerParams(question="How do I manage my fleet?")
        ctx = _make_tool_ctx()
        with patch(
            "backend.copilot.tools.help_tools.get_documentation_service",
            side_effect=RuntimeError("boom"),
        ):
            result = await tool.execute(params, ctx)
        assert result.status == "failed"


# =============================================================================
# GuideWorkflowTool
# =============================================================================


class TestGuideWorkflowTool:
    """Tests for help.guide_workflow tool."""

    @pytest.mark.asyncio
    async def test_validate_rejects_empty_workflow_id(self):
        tool = GuideWorkflowTool()
        params = GuideWorkflowParams(workflow_id="")
        ctx = _make_tool_ctx()
        errors = await tool.validate(params, ctx)
        assert any("empty_workflow" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_rejects_unknown_workflow(self):
        tool = GuideWorkflowTool()
        params = GuideWorkflowParams(workflow_id="nonexistent")
        ctx = _make_tool_ctx()
        errors = await tool.validate(params, ctx)
        assert any("workflow_not_found" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_accepts_valid_workflow(self):
        tool = GuideWorkflowTool()
        params = GuideWorkflowParams(workflow_id="app_overview")
        ctx = _make_tool_ctx()
        errors = await tool.validate(params, ctx)
        assert errors == []

    @pytest.mark.asyncio
    async def test_execute_returns_success_with_walkthrough(self):
        tool = GuideWorkflowTool()
        params = GuideWorkflowParams(workflow_id="app_overview")
        ctx = _make_tool_ctx()
        result = await tool.execute(params, ctx)
        assert result.status == "success"
        assert isinstance(result.data, dict)
        assert "walkthrough" in result.data
        assert result.data["walkthrough"]["workflow_id"] == "app_overview"
        assert len(result.data["walkthrough"]["steps"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_returns_failed_for_unknown_workflow(self):
        tool = GuideWorkflowTool()
        params = GuideWorkflowParams(workflow_id="nonexistent")
        ctx = _make_tool_ctx()
        result = await tool.execute(params, ctx)
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_handles_exception_gracefully(self):
        tool = GuideWorkflowTool()
        params = GuideWorkflowParams(workflow_id="app_overview")
        ctx = _make_tool_ctx()
        with patch(
            "backend.copilot.tools.help_tools.get_guided_workflow_service",
            side_effect=RuntimeError("boom"),
        ):
            result = await tool.execute(params, ctx)
        assert result.status == "failed"
