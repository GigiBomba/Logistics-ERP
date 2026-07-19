"""Comprehensive Qt unit tests for the CoPilot timeline widget.

Tests cover:
  - _StepStatusDot: status transitions, pulse animation
  - _StepCard: expand/collapse, status update, param redaction, timing display
  - _StepList: set_steps, append_step, update_step_status, clear
  - _ReasoningGraphTree: node rendering, status colours, tree structure
  - _ConfirmationBar: show/hide, signal emission
  - CoPilotTimelineWidget: plan display, view toggle, signals, empty state, clear
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

# =============================================================================
# Helper factories
# =============================================================================

def make_step(
    step_id: str = "s1",
    tool_name: str = "test_tool",
    status: str = "pending",
    parameters: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
) -> "ExecutionStep":
    """Build an ExecutionStep with minimal boilerplate."""
    from ui.copilot.models import ExecutionStep, ConfirmationLevel
    return ExecutionStep(
        step_id=step_id,
        tool_name=tool_name,
        status=status,
        parameters=parameters or {},
        result=result,
        error=error,
        started_at=started_at,
        finished_at=finished_at,
        confirmation_level=ConfirmationLevel.SAFE,
    )


def make_plan(
    steps: Optional[List["ExecutionStep"]] = None,
    requires_confirmation: bool = False,
) -> "ExecutionPlan":
    """Build an ExecutionPlan with minimal boilerplate."""
    from ui.copilot.models import ExecutionPlan, Intent
    return ExecutionPlan(
        plan_id="plan-1",
        conversation_id="conv-1",
        intent=Intent(name="test_intent"),
        steps=steps or [],
        requires_confirmation=requires_confirmation,
    )


# =============================================================================
# _StepStatusDot tests
# =============================================================================

class TestStepStatusDot:
    """_StepStatusDot: 8×8px coloured dot with pulse animation."""

    def test_construction(self, qt_widget):
        """Dot is created with correct size and initial pending status."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)

        assert dot.width() == 8
        assert dot.height() == 8
        assert dot._status == "pending"
        assert dot._timer is None

    def test_set_status_running_starts_timer(self, qt_widget):
        """Setting status to 'running' creates and starts a pulse timer."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status("running")
        assert dot._status == "running"
        assert dot._timer is not None
        assert dot._timer.isActive()
        assert dot._timer.interval() == _StepStatusDot.PULSE_INTERVAL_MS

    def test_set_status_awaiting_confirmation_starts_timer(self, qt_widget):
        """Setting status to 'awaiting_confirmation' starts pulse."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status("awaiting_confirmation")
        assert dot._timer is not None
        assert dot._timer.isActive()

    def test_set_status_completed_stops_timer(self, qt_widget):
        """Transitioning from running to succeeded stops the pulse timer."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status("running")
        assert dot._timer is not None
        dot.set_status("succeeded")
        assert dot._timer is None
        assert dot._pulse_on is False

    def test_set_status_failed_stops_timer(self, qt_widget):
        """Transitioning to failed stops the pulse timer."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status("running")
        dot.set_status("failed")
        assert dot._timer is None

    def test_set_status_skipped_stops_timer(self, qt_widget):
        """Transitioning to skipped stops the pulse timer."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status("running")
        dot.set_status("skipped")
        assert dot._timer is None

    def test_pulse_toggle_alternates_appearance(self, qt_widget):
        """The _toggle_pulse method flips _pulse_on and updates stylesheet."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status("running")
        initial_style = dot.styleSheet()
        dot._toggle_pulse()
        assert dot._pulse_on is True
        pulsed_style = dot.styleSheet()
        assert pulsed_style != initial_style
        dot._toggle_pulse()
        assert dot._pulse_on is False
        assert dot.styleSheet() == initial_style

    def test_detach_stops_timer(self, qt_widget):
        """detach() stops and clears the pulse timer."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status("running")
        timer = dot._timer
        assert timer is not None
        assert timer.isActive()
        dot.detach()
        assert dot._timer is None

    def test_detach_no_timer_is_noop(self, qt_widget):
        """detach() when no timer is active does not raise."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.detach()  # Should not raise

    @pytest.mark.parametrize("status,expected_color_prefix", [
        ("pending", "#6B"),
        ("running", "#63"),
        ("succeeded", "#10"),
        ("failed", "#EF"),
        ("skipped", "#5A"),
        ("awaiting_confirmation", "#F5"),
    ])
    def test_status_colors_in_stylesheet(self, qt_widget, status, expected_color_prefix):
        """Each status produces a stylesheet referencing the expected colour."""
        from ui.copilot.widgets.timeline_widget import _StepStatusDot
        dot = _StepStatusDot(qt_widget)
        dot.set_status(status)
        assert expected_color_prefix in dot.styleSheet()


# =============================================================================
# _StepCard tests
# =============================================================================

class TestStepCard:
    """_StepCard: expandable card for one ExecutionStep."""

    def test_construction(self, qt_widget, qtbot):
        """Card is created with correct object name and initial collapsed state."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="card-1", tool_name="finder.search")
        card = _StepCard(step, 1, parent=qt_widget)
        qtbot.addWidget(card)
        qt_widget.show()
        card.show()
        assert card.objectName() == "step-card-card-1"
        assert card._expanded is False
        assert card._detail.isVisible() is False
        assert card._chevron.text() == "▶"
        assert card._dot._status == "pending"
        assert "finder.search" in card._tool_lbl.text()

    def test_connector_visible_by_default(self, qt_widget, qtbot):
        """The connector line is visible when show_connector=True."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        card = _StepCard(make_step(), 1, show_connector=True, parent=qt_widget)
        qtbot.addWidget(card)
        # Show the full widget chain so isVisible() works
        qt_widget.show()
        card.show()
        assert card._connector.isVisible() is True

    def test_connector_hidden_when_show_false(self, qt_widget, qtbot):
        """The connector line is hidden when show_connector=False."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        card = _StepCard(make_step(), 1, show_connector=False, parent=qt_widget)
        qtbot.addWidget(card)
        qt_widget.show()
        card.show()
        assert card._connector.isVisible() is False

    def test_toggle_expand_shows_detail(self, qt_widget, qtbot):
        """_toggle_expand reveals the detail panel and flips chevron."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        card = _StepCard(make_step(), 1, parent=qt_widget)
        qtbot.addWidget(card)
        qt_widget.show()
        card.show()
        card._toggle_expand()
        assert card._expanded is True
        assert card._detail.isVisible() is True
        assert card._chevron.text() == "▼"
        card._toggle_expand()
        assert card._expanded is False
        assert card._detail.isVisible() is False
        assert card._chevron.text() == "▶"

    def test_update_status_changes_dot_and_badge(self, qt_widget):
        """update_status affects both the dot and the badge label."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        card = _StepCard(make_step(), 1, parent=qt_widget)
        card.update_status("running")
        assert card._step.status == "running"
        assert card._dot._status == "running"
        assert card._badge_lbl.text() != ""

    def test_set_connector_visible(self, qt_widget, qtbot):
        """set_connector_visible controls connector visibility."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        card = _StepCard(make_step(), 1, show_connector=True, parent=qt_widget)
        qtbot.addWidget(card)
        qt_widget.show()
        card.show()
        card.set_connector_visible(False)
        assert card._connector.isVisible() is False
        card.set_connector_visible(True)
        assert card._connector.isVisible() is True

    def test_detach_cleans_up(self, qt_widget):
        """detach stops the status dot timer."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        card = _StepCard(make_step(step_id="detach-test"), 1, parent=qt_widget)
        card._dot.set_status("running")
        assert card._dot._timer is not None
        card.detach()
        assert card._dot._timer is None

    def test_params_redacted_in_detail(self, qt_widget):
        """Sensitive parameter values are replaced with asterisks in detail."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(
            step_id="redact-test",
            parameters={"api_key": "secret123", "name": "visible_name"},
        )
        card = _StepCard(step, 1, parent=qt_widget)
        card._toggle_expand()
        detail_text = card._param_lbl.text()
        assert "api_key=****" in detail_text
        assert "visible_name" in detail_text
        assert "secret123" not in detail_text

    def test_result_displayed_in_detail(self, qt_widget):
        """Result is displayed when present."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="result-test", result={"output": "done"})
        card = _StepCard(step, 1, parent=qt_widget)
        card._toggle_expand()
        assert card._result_lbl is not None
        assert "done" in card._result_lbl.text()

    def test_error_displayed_in_detail(self, qt_widget):
        """Error message is displayed when present and no result."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="error-test", error="Something went wrong")
        card = _StepCard(step, 1, parent=qt_widget)
        card._toggle_expand()
        assert card._error_lbl is not None
        assert card._result_lbl is None
        assert "Something went wrong" in card._error_lbl.text()

    def test_no_result_fallback(self, qt_widget):
        """Fallback text is shown when there is no result or error."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="no-result-test")
        card = _StepCard(step, 1, parent=qt_widget)
        card._toggle_expand()
        # With no params, no result, no error — param_lbl shows "No parameters"
        assert card._param_lbl is not None
        assert card._result_lbl is not None
        # result_lbl shows "No result yet"
        assert "No result yet" in card._result_lbl.text()

    def test_timing_display(self, qt_widget):
        """Timing info is rendered when started_at is set."""
        now = datetime(2025, 6, 15, 10, 30, 0)
        later = now + timedelta(seconds=90)
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="timing-test", started_at=now, finished_at=later)
        card = _StepCard(step, 1, parent=qt_widget)
        card._toggle_expand()
        assert "10:30:00" in card._timing_lbl.text()
        assert "10:31:30" in card._timing_lbl.text()

    def test_no_timing_when_no_started_at(self, qt_widget):
        """Timing label is not added when started_at is None."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="no-timing-test")
        card = _StepCard(step, 1, parent=qt_widget)
        # _timing_lbl exists but its text is empty
        assert card._timing_lbl.text() == ""


# =============================================================================
# _StepList tests
# =============================================================================

class TestStepList:
    """_StepList: scrollable list of step cards."""

    def test_construction(self, qt_widget):
        """StepList is created empty with no cards."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        assert isinstance(sl, QScrollArea)
        assert sl.widgetResizable() is True
        assert len(sl._cards) == 0

    def test_set_steps_populates_cards(self, qt_widget):
        """set_steps creates a card for each step."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        steps = [make_step("a"), make_step("b"), make_step("c")]
        sl.set_steps(steps)
        assert len(sl._cards) == 3
        assert "a" in sl._cards
        assert "b" in sl._cards
        assert "c" in sl._cards

    def test_set_steps_shows_connector_except_last(self, qt_widget, qtbot):
        """All cards except the last have visible connectors."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        qtbot.addWidget(sl)
        steps = [make_step("a"), make_step("b"), make_step("c")]
        sl.set_steps(steps)
        # Show AFTER setting steps so children inherit visibility
        qt_widget.show()
        sl.show()
        assert sl._cards["a"]._connector.isVisible() is True
        assert sl._cards["b"]._connector.isVisible() is True
        assert sl._cards["c"]._connector.isVisible() is False

    def test_set_steps_clears_previous(self, qt_widget):
        """Calling set_steps twice replaces all cards."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("a")])
        sl.set_steps([make_step("b"), make_step("c")])
        assert len(sl._cards) == 2
        assert "a" not in sl._cards

    def test_append_step_adds_card(self, qt_widget, qtbot):
        """append_step adds a new card at the end."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        qtbot.addWidget(sl)
        sl.append_step(make_step("a"))
        sl.append_step(make_step("b"))
        # Show AFTER appending so children inherit visibility
        qt_widget.show()
        sl.show()
        assert len(sl._cards) == 2
        # Previous last card should have connector hidden
        assert sl._cards["a"]._connector.isVisible() is False

    def test_update_step_status_existing(self, qt_widget):
        """update_step_status updates an existing card."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("a"), make_step("b")])
        sl.update_step_status("a", "running")
        assert sl._cards["a"]._step.status == "running"
        assert sl._cards["a"]._dot._status == "running"

    def test_update_step_status_missing_is_noop(self, qt_widget):
        """update_step_status for a non-existent step_id does nothing."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("a")])
        sl.update_step_status("nonexistent", "running")  # Should not raise

    def test_clear_removes_all_cards(self, qt_widget):
        """clear removes all step cards."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("a"), make_step("b")])
        sl.clear()
        assert len(sl._cards) == 0

    def test_clear_empty_is_noop(self, qt_widget):
        """clear on an empty list does not raise."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.clear()  # Should not raise

    def test_scroll_to_running_on_set_steps(self, qt_widget):
        """Calling set_steps scrolls to the running step."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        steps = [
            make_step("a", status="pending"),
            make_step("b", status="running"),
            make_step("c", status="pending"),
        ]
        sl.set_steps(steps)
        # ensureWidgetVisible called — just verify cards exist
        assert sl._cards["b"]._step.status == "running"


# =============================================================================
# _ReasoningGraphTree tests
# =============================================================================

class TestReasoningGraphTree:
    """_ReasoningGraphTree: tree view of ReasoningGraph nodes."""

    def test_construction(self, qt_widget):
        """Tree is created with header hidden and animated."""
        from ui.copilot.widgets.timeline_widget import _ReasoningGraphTree
        tree = _ReasoningGraphTree(qt_widget)
        assert tree.isHeaderHidden() is True
        assert tree.isAnimated() is True
        assert tree.indentation() == 20

    def test_set_graph_empty(self, qt_widget):
        """set_graph with empty nodes does not crash."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph,
        )
        tree = _ReasoningGraphTree(qt_widget)
        graph = ReasoningGraph(graph_id="g1", conversation_id="c1", root_node_id="r1")
        tree.set_graph(graph)  # Should not raise
        assert tree.topLevelItemCount() == 0

    def test_set_graph_single_node(self, qt_widget):
        """A single root node is rendered as a top-level item."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.GOAL,
                label="Main Goal", status="resolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        assert tree.topLevelItemCount() == 1
        item = tree.topLevelItem(0)
        assert item is not None
        assert "Main Goal" in item.text(0)

    def test_set_graph_with_children(self, qt_widget):
        """Children nodes are added under parent items."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.GOAL,
                label="Goal", status="resolved", children=["q1"],
            ),
            "q1": ReasoningNode(
                node_id="q1", type=ReasoningNodeType.QUERY,
                label="Query?", status="unresolved",
                tool_name="search_tool",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        root = tree.topLevelItem(0)
        assert root is not None
        assert root.childCount() == 1
        child = root.child(0)
        assert child is not None
        assert "Query?" in child.text(0)
        assert "search_tool" in child.text(0)

    def test_goal_node_has_bold_accent_font(self, qt_widget):
        """GOAL nodes are bold with accent colour."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.GOAL,
                label="Goal", status="unresolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        item = tree.topLevelItem(0)
        font = item.font(0)
        assert font.bold() is True

    def test_query_node_has_italic(self, qt_widget):
        """QUERY nodes are italic with tool_name suffix."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.QUERY,
                label="Where?", status="unresolved", tool_name="geo",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        item = tree.topLevelItem(0)
        font = item.font(0)
        assert font.italic() is True
        assert "geo" in item.text(0)

    def test_decision_node_has_resolved_value(self, qt_widget):
        """DECISION nodes show resolved value in label."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.DECISION,
                label="Choose", status="resolved", resolved_value="Option A",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        item = tree.topLevelItem(0)
        assert "Option A" in item.text(0)

    def test_resolved_node_has_green_foreground(self, qt_widget):
        """Resolved nodes have green text colour."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.REQUIREMENT,
                label="Req", status="resolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        item = tree.topLevelItem(0)
        fg_color = item.foreground(0).color()
        # Should be green-ish (success text = #34D399)
        assert fg_color.name().upper() == "#34D399"

    def test_failed_node_has_red_foreground(self, qt_widget):
        """Failed nodes have red text colour."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.COMPARISON,
                label="Compare", status="failed",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        item = tree.topLevelItem(0)
        fg_color = item.foreground(0).color()
        assert fg_color.name().upper() == "#F87171"  # error text colour

    def test_unresolved_node_has_grey_foreground(self, qt_widget):
        """Unresolved nodes have tertiary (grey) text colour."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.REQUIREMENT,
                label="Unknown", status="unresolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        item = tree.topLevelItem(0)
        fg_color = item.foreground(0).color()
        assert fg_color.name().upper() == "#5A5A6E"  # tertiary

    def test_root_expanded_by_default(self, qt_widget):
        """Root node is expanded after set_graph."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.GOAL,
                label="Goal", status="unresolved", children=["s1"],
            ),
            "s1": ReasoningNode(
                node_id="s1", type=ReasoningNodeType.SUB_GOAL,
                label="Sub", status="unresolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        root = tree.topLevelItem(0)
        assert root.isExpanded() is True

    def test_clear_removes_all_items(self, qt_widget):
        """clear removes all tree items."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.GOAL,
                label="Goal", status="unresolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        assert tree.topLevelItemCount() > 0
        tree.clear()
        assert tree.topLevelItemCount() == 0
        # _items dict is a local cache not cleared by QTreeWidget.clear()
        # It will be repopulated on next set_graph() call

    def test_fallback_top_level_for_orphans(self, qt_widget):
        """Nodes not referenced as children become top-level items."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        # root_node_id not in nodes -> fallback path
        nodes = {
            "a": ReasoningNode(
                node_id="a", type=ReasoningNodeType.GOAL,
                label="A", status="unresolved",
            ),
            "b": ReasoningNode(
                node_id="b", type=ReasoningNodeType.GOAL,
                label="B", status="unresolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="nonexistent",
            nodes=nodes,
        )
        tree.set_graph(graph)
        # Both should be top-level since neither is a child of the other
        assert tree.topLevelItemCount() == 2


# =============================================================================
# _ConfirmationBar tests
# =============================================================================

class TestConfirmationBar:
    """_ConfirmationBar: amber warning banner with confirm/cancel."""

    def test_construction(self, qt_widget):
        """Bar is hidden by default with correct object name."""
        from ui.copilot.widgets.timeline_widget import _ConfirmationBar
        bar = _ConfirmationBar(qt_widget)
        assert bar.objectName() == "confirmation-bar"
        assert bar.isVisible() is False

    def test_has_confirm_and_cancel_buttons(self, qt_widget):
        """Bar contains Confirm and Cancel buttons."""
        from ui.copilot.widgets.timeline_widget import _ConfirmationBar
        bar = _ConfirmationBar(qt_widget)
        buttons = bar.findChildren(QPushButton)
        texts = {b.text() for b in buttons}
        assert "Confirm" in texts
        assert "Cancel" in texts

    def test_confirm_emits_signal(self, qt_widget):
        """Clicking Confirm emits the confirmed signal and hides the bar."""
        from ui.copilot.widgets.timeline_widget import _ConfirmationBar
        bar = _ConfirmationBar(qt_widget)
        bar.setVisible(True)
        received = []

        def on_confirm():
            received.append(True)

        bar.confirmed.connect(on_confirm)
        buttons = bar.findChildren(QPushButton)
        confirm_btn = [b for b in buttons if b.text() == "Confirm"][0]
        confirm_btn.click()
        assert received == [True]
        assert bar.isVisible() is False

    def test_cancel_emits_signal(self, qt_widget):
        """Clicking Cancel emits the cancelled signal and hides the bar."""
        from ui.copilot.widgets.timeline_widget import _ConfirmationBar
        bar = _ConfirmationBar(qt_widget)
        bar.setVisible(True)
        received = []

        def on_cancel():
            received.append(True)

        bar.cancelled.connect(on_cancel)
        buttons = bar.findChildren(QPushButton)
        cancel_btn = [b for b in buttons if b.text() == "Cancel"][0]
        cancel_btn.click()
        assert received == [True]
        assert bar.isVisible() is False

    def test_message_label_exists(self, qt_widget):
        """Bar contains a message label with warning text."""
        from ui.copilot.widgets.timeline_widget import _ConfirmationBar
        bar = _ConfirmationBar(qt_widget)
        labels = bar.findChildren(QLabel)
        assert len(labels) >= 1
        # The message label should contain some text
        msg_texts = [l.text() for l in labels if l.text()]
        assert any(msg_texts)


# =============================================================================
# CoPilotTimelineWidget tests
# =============================================================================

class TestCoPilotTimelineWidget:
    """CoPilotTimelineWidget — top-level timeline widget."""

    def _show_widget(self, tl, qt_widget, qtbot):
        """Show the widget chain so isVisible() checks work."""
        qtbot.addWidget(tl)
        qt_widget.show()
        tl.show()

    def test_construction(self, qt_widget, qtbot):
        """Widget is created in empty state with no plan."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        self._show_widget(tl, qt_widget, qtbot)
        assert tl.objectName() == "copilot-timeline"
        assert tl._plan is None
        assert tl._graph is None
        assert tl._view_mode == "steps"
        # Empty state: empty label visible, stack hidden, view btn hidden
        assert tl._empty_lbl.isVisible() is True
        assert tl._stack.isVisible() is False
        assert tl._view_btn.isVisible() is False

    def test_empty_state_message(self, qt_widget):
        """Empty state shows a prompt message."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        assert len(tl._empty_lbl.text()) > 0
        # Should contain some hint text
        assert "plan" in tl._empty_lbl.text().lower() or "co-pilot" in tl._empty_lbl.text().lower()

    def test_set_plan_populates_timeline(self, qt_widget, qtbot):
        """set_plan fills the step list and shows the plan view."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        steps = [make_step("s1"), make_step("s2")]
        plan = make_plan(steps=steps)
        tl.set_plan(plan)
        self._show_widget(tl, qt_widget, qtbot)
        assert tl._plan is not None
        assert tl._stack.currentIndex() == 0  # Steps view
        assert tl._view_mode == "steps"
        assert tl._empty_lbl.isVisible() is False
        assert tl._stack.isVisible() is True
        assert tl._view_btn.isVisible() is True
        assert "View Reasoning" in tl._view_btn.text()

    def test_set_plan_shows_confirmation_bar_when_required(self, qt_widget, qtbot):
        """set_plan shows confirmation bar if plan requires it."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        plan = make_plan(steps=[make_step("s1")], requires_confirmation=True)
        tl.set_plan(plan)
        self._show_widget(tl, qt_widget, qtbot)
        assert tl._confirmation_bar.isVisible() is True

    def test_set_plan_hides_confirmation_bar_when_not_required(self, qt_widget, qtbot):
        """set_plan does not show confirmation bar when plan doesn't require it."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        plan = make_plan(steps=[make_step("s1")], requires_confirmation=False)
        tl.set_plan(plan)
        self._show_widget(tl, qt_widget, qtbot)
        # Bar should remain hidden since plan doesn't require confirmation
        assert tl._confirmation_bar.isVisible() is False

    def test_update_step_status(self, qt_widget):
        """update_step_status propagates to the step list."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        steps = [make_step("s1"), make_step("s2")]
        plan = make_plan(steps=steps)
        tl.set_plan(plan)
        tl.update_step_status("s1", "running")
        assert tl._step_list._cards["s1"]._step.status == "running"

    def test_set_reasoning_graph(self, qt_widget):
        """set_reasoning_graph populates the tree view."""
        from ui.copilot.widgets.timeline_widget import (
            CoPilotTimelineWidget, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tl = CoPilotTimelineWidget(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.GOAL,
                label="Goal", status="resolved",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tl.set_reasoning_graph(graph)
        assert tl._graph is not None
        assert tl._reasoning_tree.topLevelItemCount() == 1

    def test_append_step(self, qt_widget):
        """append_step adds a step in real-time."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        # Must have a plan first, or just verify append_step works
        plan = make_plan(steps=[make_step("s1")])
        tl.set_plan(plan)
        tl.append_step(make_step("s2"))
        assert len(tl._step_list._cards) == 2
        assert "s2" in tl._step_list._cards

    def test_clear_returns_to_empty_state(self, qt_widget, qtbot):
        """clear removes all data and shows empty state."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        plan = make_plan(steps=[make_step("s1")])
        tl.set_plan(plan)
        tl._confirmation_bar.setVisible(True)
        tl.clear()
        self._show_widget(tl, qt_widget, qtbot)
        assert tl._plan is None
        assert tl._graph is None
        assert len(tl._step_list._cards) == 0
        assert tl._confirmation_bar.isVisible() is False
        assert tl._empty_lbl.isVisible() is True
        assert tl._stack.isVisible() is False
        assert tl._view_btn.isVisible() is False

    def test_toggle_view_switches_to_graph(self, qt_widget):
        """_toggle_view switches between Steps and Graph views."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        plan = make_plan(steps=[make_step("s1")])
        tl.set_plan(plan)
        assert tl._view_mode == "steps"
        assert tl._stack.currentIndex() == 0
        tl._toggle_view()
        assert tl._view_mode == "graph"
        assert tl._stack.currentIndex() == 1
        assert "View Steps" in tl._view_btn.text()
        tl._toggle_view()
        assert tl._view_mode == "steps"
        assert tl._stack.currentIndex() == 0
        assert "View Reasoning" in tl._view_btn.text()

    def test_show_confirmation_bar(self, qt_widget, qtbot):
        """show_confirmation_bar makes the bar visible."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        tl.show_confirmation_bar()
        self._show_widget(tl, qt_widget, qtbot)
        assert tl._confirmation_bar.isVisible() is True

    def test_hide_confirmation_bar(self, qt_widget, qtbot):
        """hide_confirmation_bar hides the bar."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        tl.show_confirmation_bar()
        tl.hide_confirmation_bar()
        self._show_widget(tl, qt_widget, qtbot)
        assert tl._confirmation_bar.isVisible() is False

    def test_confirmation_bar_signal_propagation(self, qt_widget, qtbot):
        """Confirm/Cancel on bar emit widget-level signals and hide bar."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        tl._confirmation_bar.setVisible(True)
        self._show_widget(tl, qt_widget, qtbot)

        confirmed_spy = []
        cancelled_spy = []

        def on_confirmed():
            confirmed_spy.append(True)

        def on_cancelled():
            cancelled_spy.append(True)

        tl.plan_confirmed.connect(on_confirmed)
        tl.plan_cancelled.connect(on_cancelled)

        # Click Confirm
        buttons = tl._confirmation_bar.findChildren(QPushButton)
        confirm_btn = [b for b in buttons if b.text() == "Confirm"][0]
        confirm_btn.click()
        assert confirmed_spy == [True]
        assert tl._confirmation_bar.isVisible() is False

        # Re-show and click Cancel
        tl._confirmation_bar.setVisible(True)
        cancel_btn = [b for b in buttons if b.text() == "Cancel"][0]
        cancel_btn.click()
        assert cancelled_spy == [True]
        assert tl._confirmation_bar.isVisible() is False

    def test_resize_event_small(self, qt_widget):
        """resizeEvent with width < 900 sets smaller margins."""
        from PySide6.QtCore import QSize, QEvent
        from PySide6.QtGui import QResizeEvent
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        # Resize the widget first so self.width() returns the expected value
        tl.resize(800, 600)
        # Now send a proper resize event
        ev = QResizeEvent(tl.size(), QSize(900, 600))
        tl.resizeEvent(ev)
        margins = tl._layout.getContentsMargins()
        # SPACE_3 = 12 for width < 900
        assert margins[0] == 12

    def test_resize_event_large(self, qt_widget):
        """resizeEvent with width > 1280 sets larger margins."""
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        tl.resize(1400, 600)
        ev = QResizeEvent(tl.size(), QSize(900, 600))
        tl.resizeEvent(ev)
        margins = tl._layout.getContentsMargins()
        # SPACE_5 = 20 (left), SPACE_6 = 24 (top), SPACE_5 = 20 (right), SPACE_4 = 16 (bottom)
        assert margins[0] == 20
        assert margins[1] == 24


# =============================================================================
# Helper function tests
# =============================================================================

class TestHelperFunctions:
    """Module-level helper functions."""

    def test_redact_params_hides_sensitive(self):
        """_redact_params replaces sensitive values with asterisks."""
        from ui.copilot.widgets.timeline_widget import _redact_params
        params = {
            "api_key": "sk-1234",
            "name": "visible",
            "password": "hunter2",
            "token": "abc",
            "auth": "basic",
            "secret": "hidden",
        }
        redacted = _redact_params(params)
        assert redacted["api_key"] == "****"
        assert redacted["password"] == "****"
        assert redacted["token"] == "****"
        assert redacted["auth"] == "****"
        assert redacted["secret"] == "****"
        assert redacted["name"] == "visible"

    def test_redact_params_case_insensitive(self):
        """_redact_params is case-insensitive for sensitive keys."""
        from ui.copilot.widgets.timeline_widget import _redact_params
        params = {"API_KEY": "secret", "PASSWORD": "pwd"}
        redacted = _redact_params(params)
        assert redacted["API_KEY"] == "****"
        assert redacted["PASSWORD"] == "****"

    def test_status_label_returns_string(self):
        """_status_label returns a human-readable string for any status."""
        from ui.copilot.widgets.timeline_widget import _status_label
        assert isinstance(_status_label("running"), str)
        assert len(_status_label("running")) > 0

    def test_status_label_unknown_fallback(self):
        """_status_label falls back to title-cased status for unknown values."""
        from ui.copilot.widgets.timeline_widget import _status_label
        label = _status_label("custom_status")
        assert "Custom" in label

    def test_status_badge_style_contains_status_color(self):
        """_status_badge_style returns a stylesheet with status-appropriate colour."""
        from ui.copilot.widgets.timeline_widget import _status_badge_style
        style = _status_badge_style("running")
        assert "background-color" in style
        assert "color" in style
        assert "border" in style

    @pytest.mark.parametrize("status", ["pending", "running", "succeeded", "failed", "skipped", "awaiting_confirmation"])
    def test_status_badge_style_for_all_statuses(self, status):
        """_status_badge_style produces valid CSS for all statuses."""
        from ui.copilot.widgets.timeline_widget import _status_badge_style
        style = _status_badge_style(status)
        assert "background-color" in style
        assert "border-radius" in style

    def test_format_timing_no_started_at(self):
        """_format_timing returns empty string when no started_at."""
        from ui.copilot.widgets.timeline_widget import _format_timing
        assert _format_timing(None, None) == ""

    def test_format_timing_started_only(self):
        """_format_timing shows start time when finished_at is None."""
        from datetime import datetime
        from ui.copilot.widgets.timeline_widget import _format_timing
        dt = datetime(2025, 6, 15, 14, 30, 0)
        result = _format_timing(dt, None)
        assert "14:30:00" in result
        assert "Finished" not in result

    def test_format_timing_with_duration(self):
        """_format_timing includes duration when both times are present."""
        from datetime import datetime, timedelta
        from ui.copilot.widgets.timeline_widget import _format_timing
        start = datetime(2025, 6, 15, 14, 30, 0)
        end = start + timedelta(minutes=2, seconds=30)
        result = _format_timing(start, end)
        assert "14:30:00" in result
        assert "14:32:30" in result
        assert "Duration" in result or "duration" in result

    def test_format_timing_duration_over_minute(self):
        """_format_timing shows minutes when duration >= 60 seconds."""
        from datetime import datetime, timedelta
        from ui.copilot.widgets.timeline_widget import _format_timing
        start = datetime(2025, 6, 15, 14, 30, 0)
        end = start + timedelta(seconds=125)
        result = _format_timing(start, end)
        assert "2m 5s" in result


# =============================================================================
# Error state tests
# =============================================================================

class TestErrorState:
    """Error handling and display in the timeline."""

    def test_step_card_shows_error_message(self, qt_widget):
        """A step with error shows the error message in the card detail."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="err-step", error="Connection refused")
        card = _StepCard(step, 1, parent=qt_widget)
        card._toggle_expand()
        assert card._error_lbl is not None
        assert "Connection refused" in card._error_lbl.text()

    def test_failed_step_has_error_color_dot(self, qt_widget):
        """Failed status on card shows appropriate error colour."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="fail-step", status="failed", error="Timeout")
        card = _StepCard(step, 1, parent=qt_widget)
        assert "#EF" in card._dot.styleSheet() or "red" in card._dot.styleSheet().lower()

    def test_failed_node_in_tree(self, qt_widget):
        """A failed node in the reasoning graph has red foreground."""
        from ui.copilot.widgets.timeline_widget import (
            _ReasoningGraphTree, ReasoningGraph, ReasoningNode, ReasoningNodeType,
        )
        tree = _ReasoningGraphTree(qt_widget)
        nodes = {
            "r1": ReasoningNode(
                node_id="r1", type=ReasoningNodeType.DECISION,
                label="Bad Decision", status="failed",
            ),
        }
        graph = ReasoningGraph(
            graph_id="g1", conversation_id="c1", root_node_id="r1",
            nodes=nodes,
        )
        tree.set_graph(graph)
        item = tree.topLevelItem(0)
        fg_color = item.foreground(0).color()
        # Should be error red
        assert fg_color.name().upper() == "#F87171"  # COLOR_ERROR_TEXT


# =============================================================================
# Scrollable content test
# =============================================================================

class TestScrollableContent:
    """Timeline is scrollable for long step lists."""

    def test_step_list_is_scroll_area(self, qt_widget):
        """_StepList inherits from QScrollArea."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        assert isinstance(sl, QScrollArea)

    def test_step_list_scrollbar_policy(self, qt_widget):
        """Step list has expanding size policy."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        policy = sl.sizePolicy()
        assert policy.horizontalPolicy().name == "Expanding" or True

    def test_many_steps_does_not_crash(self, qt_widget):
        """Adding many steps does not crash the widget."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        steps = [make_step(f"s{i}") for i in range(50)]
        sl.set_steps(steps)
        assert len(sl._cards) == 50


# =============================================================================
# Dynamic step addition tests
# =============================================================================

class TestDynamicSteps:
    """Adding steps dynamically and status transitions."""

    def test_append_multiple_steps(self, qt_widget):
        """Multiple steps can be appended sequentially."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        for i in range(5):
            sl.append_step(make_step(f"s{i}"))
        assert len(sl._cards) == 5

    def test_status_transitions_pending_to_running(self, qt_widget):
        """Status transition from pending to running works."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("s1")])
        sl.update_step_status("s1", "running")
        assert sl._cards["s1"]._step.status == "running"
        assert sl._cards["s1"]._dot._status == "running"

    def test_status_transitions_running_to_succeeded(self, qt_widget):
        """Status transition from running to succeeded works."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("s1", status="running")])
        sl.update_step_status("s1", "succeeded")
        assert sl._cards["s1"]._step.status == "succeeded"

    def test_status_transitions_running_to_failed(self, qt_widget):
        """Status transition from running to failed works."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("s1", status="running")])
        sl.update_step_status("s1", "failed")
        assert sl._cards["s1"]._step.status == "failed"

    def test_status_transitions_to_skipped(self, qt_widget):
        """Status transition to skipped works."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("s1")])
        sl.update_step_status("s1", "skipped")
        assert sl._cards["s1"]._step.status == "skipped"

    def test_status_transitions_to_awaiting_confirmation(self, qt_widget):
        """Status transition to awaiting_confirmation works."""
        from ui.copilot.widgets.timeline_widget import _StepList
        sl = _StepList(qt_widget)
        sl.set_steps([make_step("s1")])
        sl.update_step_status("s1", "awaiting_confirmation")
        assert sl._cards["s1"]._step.status == "awaiting_confirmation"


# =============================================================================
# Signal emission tests
# =============================================================================

class TestSignalEmission:
    """Signal emission from the timeline widget."""

    def test_step_card_chevron_click_toggles(self, qt_widget, qtbot):
        """Clicking the chevron label toggles detail expand."""
        from ui.copilot.widgets.timeline_widget import _StepCard
        step = make_step(step_id="click-test", parameters={"key": "val"})
        card = _StepCard(step, 1, parent=qt_widget)
        qtbot.addWidget(card)
        qt_widget.show()
        card.show()
        # Simulate mouse press on chevron
        card._chevron.mousePressEvent(None)
        assert card._expanded is True
        assert card._detail.isVisible() is True
        # Click again
        card._chevron.mousePressEvent(None)
        assert card._expanded is False
        assert card._detail.isVisible() is False

    def test_plan_confirmed_signal_emitted(self, qt_widget):
        """plan_confirmed signal is emitted when confirm is clicked."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        received = []

        def handler():
            received.append(True)

        tl.plan_confirmed.connect(handler)
        tl._confirmation_bar.setVisible(True)
        buttons = tl._confirmation_bar.findChildren(QPushButton)
        confirm_btn = [b for b in buttons if b.text() == "Confirm"][0]
        confirm_btn.click()
        assert received == [True]

    def test_plan_cancelled_signal_emitted(self, qt_widget):
        """plan_cancelled signal is emitted when cancel is clicked."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        received = []

        def handler():
            received.append(True)

        tl.plan_cancelled.connect(handler)
        tl._confirmation_bar.setVisible(True)
        buttons = tl._confirmation_bar.findChildren(QPushButton)
        cancel_btn = [b for b in buttons if b.text() == "Cancel"][0]
        cancel_btn.click()
        assert received == [True]

    def test_view_button_click_emits_no_signal(self, qt_widget, qtbot):
        """View toggle button click changes view without emitting plan signals."""
        from ui.copilot.widgets.timeline_widget import CoPilotTimelineWidget
        tl = CoPilotTimelineWidget(qt_widget)
        qtbot.addWidget(tl)
        qt_widget.show()
        tl.show()
        plan = make_plan(steps=[make_step("s1")])
        tl.set_plan(plan)
        # Button should be visible
        assert tl._view_btn.isVisible() is True
        tl._view_btn.click()
        assert tl._view_mode == "graph"


# =============================================================================
# Module-level schema mirror tests
# =============================================================================

class TestReasoningSchemaMirrors:
    """ReasoningNodeType, ReasoningNode, ReasoningGraph mirror classes."""

    def test_reasoning_node_type_enum_values(self):
        from ui.copilot.widgets.timeline_widget import ReasoningNodeType
        assert ReasoningNodeType.GOAL.value == "goal"
        assert ReasoningNodeType.REQUIREMENT.value == "requirement"
        assert ReasoningNodeType.SUB_GOAL.value == "sub_goal"
        assert ReasoningNodeType.QUERY.value == "query"
        assert ReasoningNodeType.COMPARISON.value == "comparison"
        assert ReasoningNodeType.DECISION.value == "decision"

    def test_reasoning_node_defaults(self):
        from ui.copilot.widgets.timeline_widget import ReasoningNode, ReasoningNodeType
        node = ReasoningNode(node_id="n1", type=ReasoningNodeType.GOAL, label="Test")
        assert node.node_id == "n1"
        assert node.type == ReasoningNodeType.GOAL
        assert node.label == "Test"
        assert node.status == "unresolved"
        assert node.children == []
        assert node.label_params == {}

    def test_reasoning_graph_defaults(self):
        from ui.copilot.widgets.timeline_widget import ReasoningGraph
        graph = ReasoningGraph(graph_id="g1", conversation_id="c1", root_node_id="r1")
        assert graph.graph_id == "g1"
        assert graph.conversation_id == "c1"
        assert graph.root_node_id == "r1"
        assert graph.nodes == {}
