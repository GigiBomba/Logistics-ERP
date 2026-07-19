"""CoPilotTimelineWidget — visual timeline of plan execution steps.

Blueprint: §12.2 — Frontend.

Composes:
  _StepStatusDot     — 8×8px colored status dot with pulse animation
  _StepCard          — Expandable card for one ExecutionStep
  _StepList          — Scrollable list of step cards
  _ReasoningGraphTree — Tree view of ReasoningGraph nodes
  _ConfirmationBar   — Amber warning banner with Confirm/Cancel
  CoPilotTimelineWidget — Top-level widget composing the above
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_BASE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_DEFAULT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    COLOR_WARNING_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_8,
)

from enum import Enum

from ui.copilot.models import ExecutionPlan, ExecutionStep


# ── Local mirrors of backend/copilot/schemas ReasoningGraph types ──────────

class ReasoningNodeType(str, Enum):
    GOAL = "goal"
    REQUIREMENT = "requirement"
    SUB_GOAL = "sub_goal"
    QUERY = "query"
    COMPARISON = "comparison"
    DECISION = "decision"


class ReasoningNode:
    """Lightweight mirror of backend ReasoningNode."""
    def __init__(self, node_id: str, type: ReasoningNodeType, label: str,
                 status: str = "unresolved", children: Optional[List[str]] = None,
                 resolved_value: Any = None, tool_name: Optional[str] = None,
                 label_params: Optional[Dict[str, Any]] = None,
                 resolved_source: Optional[str] = None,
                 tool_version: Optional[str] = None,
                 tool_result_ref: Optional[str] = None,
                 decision_rationale_key: Optional[str] = None,
                 decision_rationale_params: Optional[Dict[str, Any]] = None) -> None:
        self.node_id = node_id
        self.type = type
        self.label = label
        self.label_params = label_params or {}
        self.status = status
        self.resolved_value = resolved_value
        self.resolved_source = resolved_source
        self.tool_name = tool_name
        self.tool_version = tool_version
        self.tool_result_ref = tool_result_ref
        self.decision_rationale_key = decision_rationale_key
        self.decision_rationale_params = decision_rationale_params or {}
        self.children = children or []


class ReasoningGraph:
    """Lightweight mirror of backend ReasoningGraph."""
    def __init__(self, graph_id: str, conversation_id: str, root_node_id: str,
                 nodes: Optional[Dict[str, ReasoningNode]] = None,
                 **kwargs: Any) -> None:
        self.graph_id = graph_id
        self.conversation_id = conversation_id
        self.root_node_id = root_node_id
        self.nodes = nodes or {}


# ── Module-level helpers ────────────────────────────────────────────────────

_STATUS_COLORS: Dict[str, tuple[str, str]] = {
    "pending": (COLOR_NEUTRAL_DEFAULT, COLOR_NEUTRAL_SUBTLE),
    "running": (COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SUBTLE),
    "succeeded": (COLOR_SUCCESS_DEFAULT, COLOR_SUCCESS_SUBTLE),
    "failed": (COLOR_ERROR_DEFAULT, COLOR_ERROR_SUBTLE),
    "skipped": (COLOR_TEXT_TERTIARY, COLOR_NEUTRAL_SUBTLE),
    "awaiting_confirmation": (COLOR_WARNING_DEFAULT, COLOR_WARNING_SUBTLE),
}

_STATUS_LABEL_KEYS: Dict[str, str] = {
    "pending": "copilot.step.status.pending",
    "running": "copilot.step.status.running",
    "succeeded": "copilot.step.status.succeeded",
    "failed": "copilot.step.status.failed",
    "skipped": "copilot.step.status.skipped",
    "awaiting_confirmation": "copilot.step.status.awaiting_confirmation",
}

_SENSITIVE_PARAM_KEYS = {"password", "token", "secret", "key", "auth", "credential"}


def _redact_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Replace sensitive parameter values with asterisks."""
    redacted: Dict[str, Any] = {}
    for k, v in params.items():
        if any(sensitive in k.lower() for sensitive in _SENSITIVE_PARAM_KEYS):
            redacted[k] = t("copilot.step.params_redacted", default="****")
        else:
            redacted[k] = v
    return redacted


def _status_label(status: str) -> str:
    key = _STATUS_LABEL_KEYS.get(status)
    if key:
        return t(key, default=status.replace("_", " ").title())
    return status.replace("_", " ").title()


def _status_badge_style(status: str) -> str:
    """Build inline stylesheet for a status badge label."""
    colors = _STATUS_COLORS.get(
        status, (COLOR_NEUTRAL_DEFAULT, COLOR_NEUTRAL_SUBTLE)
    )
    return (
        f"background-color: {colors[1]};"
        f"color: {colors[0]};"
        f"border: 1px solid {colors[0]};"
        f"border-radius: {RADIUS_SM}px;"
        f"padding: 1px {SPACE_2}px;"
        f"font-size: {FONT_SIZE_XS}px;"
        f"font-weight: {FONT_WEIGHT_BOLD};"
    )


def _format_timing(started_at: datetime | None, finished_at: datetime | None) -> str:
    """Format timing info as a human-readable string."""
    if not started_at:
        return ""
    parts = [f"Started: {started_at.strftime('%H:%M:%S')}"]
    if finished_at:
        parts.append(f"Finished: {finished_at.strftime('%H:%M:%S')}")
        delta = finished_at - started_at
        total_secs = int(delta.total_seconds())
        if total_secs >= 60:
            dur = f"{total_secs // 60}m {total_secs % 60}s"
        else:
            dur = f"{total_secs}s"
        parts.append(t("copilot.step.duration", default="Duration: {dur}", dur=dur))
    return " | ".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# A1: _StepStatusDot
# ═════════════════════════════════════════════════════════════════════════════

class _StepStatusDot(QLabel):
    """8×8 pixel colored status dot with optional pulse animation.

    Call :meth:`set_status` to update appearance.
    Call :meth:`detach` to stop any running pulse timer.
    """

    PULSE_INTERVAL_MS = 600

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._status: str = "pending"
        self._pulse_on: bool = False
        self._timer: QTimer | None = None
        self._update_appearance()

    def set_status(self, status: str) -> None:
        """Set the status and begin/stop pulse animation as needed."""
        self._status = status
        needs_pulse = status in ("running", "awaiting_confirmation")

        if needs_pulse and self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._toggle_pulse)
            self._timer.start(self.PULSE_INTERVAL_MS)
        elif not needs_pulse and self._timer is not None:
            self._timer.stop()
            self._timer = None
            self._pulse_on = False

        self._update_appearance()

    def _toggle_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        self._update_appearance()

    def _update_appearance(self) -> None:
        colors = _STATUS_COLORS.get(self._status, (COLOR_NEUTRAL_DEFAULT, COLOR_NEUTRAL_SUBTLE))

        if self._status == "running":
            bg = COLOR_ACCENT_SUBTLE if self._pulse_on else COLOR_ACCENT_PRIMARY
        elif self._status == "awaiting_confirmation":
            bg = COLOR_WARNING_SUBTLE if self._pulse_on else COLOR_WARNING_DEFAULT
        else:
            bg = colors[0]

        self.setStyleSheet(
            f"background-color: {bg}; border-radius: 4px;"
        )

    def detach(self) -> None:
        """Stop the pulse timer. Call when the dot is no longer needed."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None


# ═════════════════════════════════════════════════════════════════════════════
# B1: _StepCard
# ═════════════════════════════════════════════════════════════════════════════

class _StepCard(QFrame):
    """A single expandable execution step card.

    Shows a header with status dot, step number, tool name, status badge,
    and expand chevron. The expanded detail panel shows parameters
    (with sensitive values redacted), result/error, and timing info.
    """

    def __init__(self, step: ExecutionStep, step_number: int,
                 show_connector: bool = True,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step = step
        self._step_number = step_number
        self._expanded = False

        self.setObjectName(f"step-card-{step.step_id}")
        base_style = (
            f"background-color: {COLOR_BG_ELEVATED};"
            f"border: 1px solid {COLOR_BORDER_SUBTLE};"
            f"border-radius: {RADIUS_MD}px;"
        )
        self.setStyleSheet(f"QFrame#step-card-{step.step_id} {{ {base_style} }}")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        self._layout.setSpacing(SPACE_2)

        # ── Header row ──────────────────────────────────────────
        self._header = QHBoxLayout()
        self._header.setSpacing(SPACE_2)

        # Status dot
        self._dot = _StepStatusDot(self)
        self._dot.set_status(self._step.status)
        self._header.addWidget(self._dot)

        # Step number
        self._num_lbl = QLabel(f"{self._step_number}.")
        self._num_lbl.setFixedWidth(20)
        self._num_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_SM}px;"
            f"background: transparent; border: none;"
        )
        self._header.addWidget(self._num_lbl)

        # Tool name
        self._tool_lbl = QLabel(self._step.tool_name)
        self._tool_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_BASE}px;"
            f"font-weight: {FONT_WEIGHT_MEDIUM};"
            f"background: transparent; border: none;"
        )
        self._header.addWidget(self._tool_lbl, 1)

        # Status badge
        self._badge_lbl = QLabel(_status_label(self._step.status))
        self._badge_lbl.setStyleSheet(
            _status_badge_style(self._step.status)
        )
        self._header.addWidget(self._badge_lbl)

        # Expand chevron
        self._chevron = QLabel("▶")
        self._chevron.setFixedWidth(16)
        self._chevron.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_XS}px;"
            f"background: transparent; border: none;"
        )
        self._chevron.mousePressEvent = lambda _e: self._toggle_expand()
        self._header.addWidget(self._chevron)

        self._layout.addLayout(self._header)

        # ── Detail (collapsible) ────────────────────────────────
        self._detail = QWidget()
        self._detail.setVisible(False)
        self._detail.setStyleSheet("background: transparent; border: none;")
        detail_layout = QVBoxLayout(self._detail)
        detail_layout.setContentsMargins(SPACE_3, 0, SPACE_3, 0)
        detail_layout.setSpacing(SPACE_2)

        # Parameters (redacted)
        params = _redact_params(self._step.parameters)
        if params:
            param_text = ", ".join(f"{k}={v}" for k, v in params.items())
            self._param_lbl = QLabel(param_text)
            self._param_lbl.setWordWrap(True)
            self._param_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;"
                f"background: transparent; border: none;"
            )
            detail_layout.addWidget(self._param_lbl)
        else:
            self._param_lbl = QLabel(
                t("copilot.step.no_result", default="No parameters")
            )
            self._param_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_SM}px;"
                f"font-style: italic; background: transparent; border: none;"
            )
            detail_layout.addWidget(self._param_lbl)

        # Result
        self._result_lbl: QLabel | None = None
        self._error_lbl: QLabel | None = None
        if self._step.result:
            result_text = str(self._step.result)
            self._result_lbl = QLabel(result_text)
            self._result_lbl.setWordWrap(True)
            self._result_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_SM}px;"
                f"background: transparent; border: none;"
            )
            detail_layout.addWidget(self._result_lbl)
        elif self._step.error:
            self._error_lbl = QLabel(f"\u26a0 {self._step.error}")
            self._error_lbl.setWordWrap(True)
            self._error_lbl.setStyleSheet(
                f"color: {COLOR_ERROR_TEXT}; font-size: {FONT_SIZE_SM}px;"
                f"background: transparent; border: none;"
            )
            detail_layout.addWidget(self._error_lbl)
        else:
            self._result_lbl = QLabel(
                t("copilot.step.no_result", default="No result yet")
            )
            self._result_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_SM}px;"
                f"font-style: italic; background: transparent; border: none;"
            )
            detail_layout.addWidget(self._result_lbl)

        # Timing
        timing_str = _format_timing(self._step.started_at, self._step.finished_at)
        self._timing_lbl = QLabel(timing_str)
        self._timing_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_XS}px;"
            f"background: transparent; border: none;"
        )
        if timing_str:
            detail_layout.addWidget(self._timing_lbl)

        self._layout.addWidget(self._detail)

        # Connector line to next step
        self._connector = QFrame()
        self._connector.setFixedHeight(1)
        self._connector.setVisible(show_connector)
        self._connector.setStyleSheet(
            f"background-color: {COLOR_BORDER_SUBTLE}; border: none;"
            f"margin-left: 4px; margin-right: 4px;"
        )
        self._layout.addWidget(self._connector)

    # ── Public API ─────────────────────────────────────────────

    def update_status(self, status: str) -> None:
        """Update the status dot and badge without rebuilding the card."""
        self._step.status = status
        self._dot.set_status(status)
        self._badge_lbl.setText(_status_label(status))
        self._badge_lbl.setStyleSheet(_status_badge_style(status))

    def set_connector_visible(self, visible: bool) -> None:
        """Show or hide the connector line below this card."""
        self._connector.setVisible(visible)

    def detach(self) -> None:
        """Clean up pulse timer resources."""
        self._dot.detach()

    # ── Internals ──────────────────────────────────────────────

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._detail.setVisible(self._expanded)
        self._chevron.setText("▼" if self._expanded else "▶")


# ═════════════════════════════════════════════════════════════════════════════
# B2: _StepList
# ═════════════════════════════════════════════════════════════════════════════

class _StepList(QScrollArea):
    """Scrollable list of _StepCard widgets.

    Maintains a dict[str, _StepCard] keyed by step_id.
    Supports set_steps(), update_step_status(), append_step(), and clear().
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent; border: none;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_3)
        self._layout.addStretch()
        self.setWidget(self._container)

        self._cards: Dict[str, _StepCard] = {}

    # ── Public API ─────────────────────────────────────────────

    def set_steps(self, steps: List[ExecutionStep]) -> None:
        """Replace all step cards with the given list of ExecutionSteps."""
        self.clear()
        for i, step in enumerate(steps):
            is_last = i == len(steps) - 1
            card = _StepCard(
                step, i + 1, show_connector=not is_last, parent=self._container
            )
            self._cards[step.step_id] = card
            self._layout.insertWidget(self._layout.count() - 1, card)
        self._scroll_to_running()

    def update_step_status(self, step_id: str, status: str) -> None:
        """Update the status of a single step card."""
        card = self._cards.get(step_id)
        if card:
            card.update_status(status)
            if status == "running":
                self._scroll_to_card(card)

    def append_step(self, step: ExecutionStep) -> None:
        """Append a new step card at the end."""
        # Hide connector on the previous last card
        if self._cards:
            last_id = list(self._cards.keys())[-1]
            last_card = self._cards[last_id]
            last_card.set_connector_visible(False)

        card = _StepCard(
            step, len(self._cards) + 1, show_connector=False, parent=self._container
        )
        self._cards[step.step_id] = card
        self._layout.insertWidget(self._layout.count() - 1, card)
        if step.status == "running":
            self._scroll_to_card(card)

    def clear(self) -> None:
        """Remove all step cards."""
        for card in self._cards.values():
            card.detach()
            card.deleteLater()
        self._cards.clear()
        # Remove all widgets from layout except the trailing stretch
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

    # ── Internals ──────────────────────────────────────────────

    def _scroll_to_running(self) -> None:
        for card in self._cards.values():
            if card._step.status == "running":
                self._scroll_to_card(card)
                return

    def _scroll_to_card(self, card: _StepCard) -> None:
        self.ensureWidgetVisible(card, 0, 0)


# ═════════════════════════════════════════════════════════════════════════════
# C1: _ReasoningGraphTree
# ═════════════════════════════════════════════════════════════════════════════

class _ReasoningGraphTree(QTreeWidget):
    """Tree widget rendering a ReasoningGraph.

    Node rendering:
      - GOAL nodes: bold + accent color foreground
      - QUERY nodes: italic + tool_name suffix
      - DECISION nodes: bold + resolved_value suffix
      - All nodes colored by status: resolved=green, failed=red, unresolved=grey
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setAnimated(True)
        self.setStyleSheet(
            f"""
            QTreeWidget {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_PRIMARY};
                font-size: {FONT_SIZE_BASE}px;
            }}
            QTreeWidget::item {{
                padding: {SPACE_1}px {SPACE_2}px;
            }}
            """
        )
        self._items: Dict[str, QTreeWidgetItem] = {}

    def set_graph(self, graph: ReasoningGraph) -> None:
        """Populate the tree from a ReasoningGraph object."""
        self.clear()
        self._items.clear()

        # Build all node items
        for node_id, node in graph.nodes.items():
            item = QTreeWidgetItem()
            self._populate_item(item, node)
            self._items[node_id] = item

        # Wire parent/child relationships
        for node_id, node in graph.nodes.items():
            item = self._items[node_id]
            for child_id in node.children:
                child_item = self._items.get(child_id)
                if child_item is not None:
                    item.addChild(child_item)

        # Determine top-level items
        root = self._items.get(graph.root_node_id)
        if root is not None:
            self.addTopLevelItem(root)
            root.setExpanded(True)
        else:
            # Fallback: any node not referenced as a child
            all_children: Set[str] = set()
            for node in graph.nodes.values():
                all_children.update(node.children)
            for node_id in graph.nodes:
                if node_id not in all_children:
                    item = self._items[node_id]
                    self.addTopLevelItem(item)
                    item.setExpanded(True)

    def _populate_item(self, item: QTreeWidgetItem, node: ReasoningNode) -> None:
        """Configure a single tree item based on node type and status."""
        # Foreground colour by status
        if node.status == "resolved":
            fg = COLOR_SUCCESS_TEXT
        elif node.status == "failed":
            fg = COLOR_ERROR_TEXT
        else:
            fg = COLOR_TEXT_TERTIARY

        font = QFont()
        label = node.label

        if node.type == ReasoningNodeType.GOAL:
            font.setBold(True)
            fg = COLOR_ACCENT_PRIMARY
        elif node.type == ReasoningNodeType.QUERY:
            font.setItalic(True)
            tool = node.tool_name or ""
            label = f"{node.label}  ({tool})"
        elif node.type == ReasoningNodeType.DECISION:
            font.setBold(True)
            val = node.resolved_value or ""
            label = f"{node.label}: {val}"
        elif node.type == ReasoningNodeType.SUB_GOAL:
            font.setWeight(QFont.Weight.Medium)
        # REQUIREMENT and COMPARISON use default weight

        item.setText(0, label)
        item.setFont(0, font)
        item.setForeground(0, QColor(fg))


# ═════════════════════════════════════════════════════════════════════════════
# C2: _ConfirmationBar
# ═════════════════════════════════════════════════════════════════════════════

class _ConfirmationBar(QFrame):
    """Amber warning banner requiring user confirmation.

    Emits :attr:`confirmed` or :attr:`cancelled` when the user acts.
    Auto-hides after either signal is emitted.
    """

    confirmed = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("confirmation-bar")
        self.setStyleSheet(
            f"""
            QFrame#confirmation-bar {{
                background-color: {COLOR_WARNING_SUBTLE};
                border: 1px solid {COLOR_WARNING_DEFAULT};
                border-radius: {RADIUS_MD}px;
            }}
            """
        )
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        layout.setSpacing(SPACE_4)

        # Message
        msg = QLabel(
            t(
                "copilot.timeline.confirmation_needed",
                default="\u26a0 This plan requires your confirmation.",
            )
        )
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color: {COLOR_WARNING_TEXT}; font-size: {FONT_SIZE_BASE}px;"
            f"font-weight: {FONT_WEIGHT_MEDIUM}; background: transparent; border: none;"
        )
        layout.addWidget(msg, 1)

        # Confirm button
        confirm_btn = QPushButton(
            t("copilot.timeline.confirm", default="Confirm")
        )
        confirm_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLOR_WARNING_DEFAULT};
                color: {COLOR_TEXT_PRIMARY};
                border: none;
                border-radius: {RADIUS_MD}px;
                padding: {SPACE_2}px {SPACE_5}px;
                font-size: {FONT_SIZE_BASE}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {COLOR_WARNING_TEXT};
            }}
            """
        )
        confirm_btn.clicked.connect(self._on_confirm)
        layout.addWidget(confirm_btn)

        # Cancel button
        cancel_btn = QPushButton(
            t("copilot.timeline.cancel", default="Cancel")
        )
        cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_WARNING_TEXT};
                border: 1px solid {COLOR_WARNING_DEFAULT};
                border-radius: {RADIUS_MD}px;
                padding: {SPACE_2}px {SPACE_5}px;
                font-size: {FONT_SIZE_BASE}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {COLOR_WARNING_SUBTLE};
            }}
            """
        )
        cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(cancel_btn)

    def _on_confirm(self) -> None:
        self.confirmed.emit()
        self.setVisible(False)

    def _on_cancel(self) -> None:
        self.cancelled.emit()
        self.setVisible(False)


# ═════════════════════════════════════════════════════════════════════════════
# D1: CoPilotTimelineWidget
# ═════════════════════════════════════════════════════════════════════════════

class CoPilotTimelineWidget(QFrame):
    """Execution plan timeline — vertical step list with status indicators.

    Composes:
      - Header with title + view toggle (Steps/Reasoning)
      - ConfirmationBar (hidden by default)
      - QStackedWidget showing either _StepList or _ReasoningGraphTree

    Responsive: single-column below 900 px, wider margins above 1280 px.

    Signals
    -------
    plan_confirmed : Signal()
        Emitted when the user confirms via the ConfirmationBar.
    plan_cancelled : Signal()
        Emitted when the user cancels via the ConfirmationBar.
    """

    plan_confirmed = Signal()
    plan_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("copilot-timeline")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._graph: ReasoningGraph | None = None
        self._plan: ExecutionPlan | None = None
        self._view_mode: str = "steps"  # "steps" or "graph"

        self._build_ui()

    def _build_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACE_4, SPACE_5, SPACE_4, SPACE_4)
        self._layout.setSpacing(SPACE_4)

        # ── Header row: title + view toggle ─────────────────────
        header = QHBoxLayout()
        header.setSpacing(SPACE_3)

        self._title = QLabel(
            t("copilot.timeline.title", default="Execution Timeline")
        )
        self._title.setStyleSheet(
            f"font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
            f"color: {COLOR_TEXT_PRIMARY};"
        )
        header.addWidget(self._title)
        header.addStretch()

        self._view_btn = QPushButton(
            t("copilot.timeline.view_reasoning", default="View Reasoning")
        )
        self._view_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_MD}px;
                padding: {SPACE_1}px {SPACE_3}px;
                font-size: {FONT_SIZE_SM}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BG_HOVER};
                color: {COLOR_TEXT_PRIMARY};
            }}
            """
        )
        self._view_btn.clicked.connect(self._toggle_view)
        header.addWidget(self._view_btn)
        self._layout.addLayout(header)

        # ── Confirmation bar ────────────────────────────────────
        self._confirmation_bar = _ConfirmationBar(self)
        self._confirmation_bar.confirmed.connect(self.plan_confirmed.emit)
        self._confirmation_bar.cancelled.connect(self.plan_cancelled.emit)
        self._layout.addWidget(self._confirmation_bar)

        # ── Stacked view (StepList / ReasoningGraphTree) ────────
        self._stack = QStackedWidget()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._stack.setStyleSheet("background: transparent; border: none;")

        self._step_list = _StepList(self)
        self._reasoning_tree = _ReasoningGraphTree(self)

        self._stack.addWidget(self._step_list)       # index 0
        self._stack.addWidget(self._reasoning_tree)   # index 1
        self._layout.addWidget(self._stack, 1)

        # ── Empty placeholder ──────────────────────────────────
        self._empty_lbl = QLabel(
            t(
                "copilot.timeline.empty",
                default="No active plan. Ask the Co-Pilot to do something.",
            )
        )
        self._empty_lbl.setWordWrap(True)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY};")
        self._layout.addWidget(self._empty_lbl)

        self._show_empty()

    # ── Public API ──────────────────────────────────────────────────────────

    def set_plan(self, plan: ExecutionPlan) -> None:
        """Set the execution plan and populate the timeline."""
        self._plan = plan
        self._step_list.set_steps(plan.steps)
        self._stack.setCurrentIndex(0)
        self._view_mode = "steps"
        self._view_btn.setText(
            t("copilot.timeline.view_reasoning", default="View Reasoning")
        )
        self._show_plan()
        if plan.requires_confirmation:
            self.show_confirmation_bar()

    def update_step_status(self, step_id: str, status: str) -> None:
        """Update the status of a single step (real-time feedback)."""
        self._step_list.update_step_status(step_id, status)

    def set_reasoning_graph(self, graph: ReasoningGraph) -> None:
        """Set the reasoning graph for the tree view."""
        self._graph = graph
        self._reasoning_tree.set_graph(graph)
        if self._view_mode == "graph":
            self._stack.setCurrentIndex(1)

    def show_confirmation_bar(self) -> None:
        """Show the confirmation bar at the top of the timeline."""
        self._confirmation_bar.setVisible(True)

    def hide_confirmation_bar(self) -> None:
        """Hide the confirmation bar."""
        self._confirmation_bar.setVisible(False)

    def append_step(self, step: ExecutionStep) -> None:
        """Append a new step to the timeline in real time."""
        self._step_list.append_step(step)

    def clear(self) -> None:
        """Clear everything and return to the empty state."""
        self._plan = None
        self._graph = None
        self._step_list.clear()
        self._reasoning_tree.clear()
        self.hide_confirmation_bar()
        self._show_empty()

    # ── Internals ───────────────────────────────────────────────────────────

    def _toggle_view(self) -> None:
        if self._view_mode == "steps":
            self._view_mode = "graph"
            self._view_btn.setText(
                t("copilot.timeline.view_steps", default="View Steps")
            )
            self._stack.setCurrentIndex(1)
        else:
            self._view_mode = "steps"
            self._view_btn.setText(
                t("copilot.timeline.view_reasoning", default="View Reasoning")
            )
            self._stack.setCurrentIndex(0)

    def _show_plan(self) -> None:
        self._empty_lbl.setVisible(False)
        self._stack.setVisible(True)
        self._view_btn.setVisible(True)

    def _show_empty(self) -> None:
        self._empty_lbl.setVisible(True)
        self._stack.setVisible(False)
        self._view_btn.setVisible(False)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Adjust margins for responsive layout."""
        w = self.width()
        if w < 900:
            self._layout.setContentsMargins(SPACE_3, SPACE_3, SPACE_3, SPACE_3)
        elif w > 1280:
            self._layout.setContentsMargins(SPACE_5, SPACE_6, SPACE_5, SPACE_4)
        else:
            self._layout.setContentsMargins(SPACE_4, SPACE_5, SPACE_4, SPACE_4)
        super().resizeEvent(event)
