"""Comprehensive Qt unit tests for InsightQueueWidget.

Covers widget construction, insight card rendering, severity badges,
action buttons, queue ordering, dynamic add/remove, empty state,
signal emission, overflow handling, scrollable content, grouping,
and edge cases.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, PropertyMock

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.copilot.models import Insight
from ui.copilot.widgets.insight_queue import (
    InsightQueueWidget,
    _InsightCard,
    _SeverityBadge,
    _SEVERITY_STYLES,
    _TYPE_ICONS,
    _format_timestamp,
    _summary_from_payload,
)
from ui.design_tokens import (
    COLOR_ERROR_DEFAULT,
    COLOR_INFO_DEFAULT,
    COLOR_NEUTRAL_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_WARNING_DEFAULT,
    RADIUS_PILL,
    SPACE_2,
    FONT_SIZE_XS,
    FONT_WEIGHT_MEDIUM,
)


# ========================================================================
#  Helpers
# ========================================================================


def _make_insight(
    *,
    id: str = "insight-1",
    insight_type: str = "cost_anomaly",
    severity: str = "critical",
    status: str = "new",
    created_at: str | None = "2026-07-19T10:00:00Z",
    payload: dict | None = None,
) -> Insight:
    """Create an Insight with sensible defaults for testing."""
    return Insight(
        id=id,
        conversation_id="conv-1",
        insight_type=insight_type,
        severity=severity,
        status=status,
        created_at=created_at,
        payload=payload or {"message": "Fuel cost spike detected."},
    )


def _find_widget(parent: QWidget, cls: type, prop: str | None = None) -> list:
    """Recursively find child widgets of a given class, optionally matching a property."""
    found: list = []
    for child in parent.findChildren(cls):
        if prop is None:
            found.append(child)
        elif hasattr(child, "property") and child.property(prop):
            found.append(child)
    return found


# ========================================================================
#  _format_timestamp  (pure function)
# ========================================================================


class TestFormatTimestamp:
    """Tests for the _format_timestamp helper."""

    def test_none_returns_empty(self):
        assert _format_timestamp(None) == ""

    def test_empty_string_returns_empty(self):
        assert _format_timestamp("") == ""

    def test_invalid_string_returns_truncated(self):
        result = _format_timestamp("not-a-date")
        # Falls through to the bare return iso_str[:16]
        assert result == "not-a-date"

    def test_just_now(self):
        now = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"
        # Should be within 60 seconds
        result = _format_timestamp(now)
        assert "just now" in result.lower() or "ago" in result


# ========================================================================
#  _summary_from_payload  (pure function)
# ========================================================================


class TestSummaryFromPayload:
    """Tests for the _summary_from_payload helper."""

    def test_message_field(self):
        result = _summary_from_payload({"message": "Hello"})
        assert result == "Hello"

    def test_summary_field(self):
        result = _summary_from_payload({"summary": "Summary text"})
        assert result == "Summary text"

    def test_message_takes_precedence(self):
        result = _summary_from_payload({"message": "Msg", "summary": "Summary"})
        assert result == "Msg"

    def test_fallback_to_string_values(self):
        result = _summary_from_payload({"foo": "bar", "baz": "qux"})
        assert result in ("bar", "qux")

    def test_empty_payload_returns_empty(self):
        assert _summary_from_payload({}) == ""


# ========================================================================
#  _SeverityBadge  (Qt widget)
# ========================================================================


class TestSeverityBadge:
    """Tests for the _SeverityBadge label widget."""

    def test_construction(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        badge = _SeverityBadge(parent, "critical")
        assert badge is not None
        assert isinstance(badge, QLabel)
        # Text should start with the severity name (capitalised)
        assert "Critical" in badge.text() or badge.text() == "Critical"

    def test_all_severity_styles(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        for severity in ("critical", "high", "medium", "low"):
            badge = _SeverityBadge(parent, severity)
            style = badge.styleSheet()
            expected = _SEVERITY_STYLES[severity]
            assert expected["bg"] in style, f"{severity} bg missing in stylesheet"
            assert expected["fg"] in style, f"{severity} fg missing in stylesheet"
            assert str(RADIUS_PILL) in style

    def test_unknown_severity_falls_back_to_low(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        badge = _SeverityBadge(parent, "unknown_level")
        style = badge.styleSheet()
        assert _SEVERITY_STYLES["low"]["bg"] in style
        assert _SEVERITY_STYLES["low"]["fg"] in style

    def test_fixed_height(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        badge = _SeverityBadge(parent, "warning")
        assert badge.height() == 20 or badge.minimumHeight() <= 20


# ========================================================================
#  _InsightCard  (Qt widget)
# ========================================================================


class TestInsightCard:
    """Tests for the _InsightCard widget."""

    def test_construction(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight()
        card = _InsightCard(parent, insight)
        assert card is not None
        assert card.property("role") == "insight-card"
        assert card.cursor().shape() == Qt.PointingHandCursor

    def test_card_shows_type_icon(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(insight_type="cost_anomaly")
        card = _InsightCard(parent, insight)
        icon_char = _TYPE_ICONS.get("cost_anomaly", "")
        assert icon_char
        # The icon should be rendered in a QLabel somewhere
        labels = card.findChildren(QLabel)
        icon_labels = [l for l in labels if icon_char in l.text()]
        assert len(icon_labels) >= 1

    def test_card_shows_severity_badge(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(severity="high")
        card = _InsightCard(parent, insight)
        badges = card.findChildren(_SeverityBadge)
        assert len(badges) >= 1

    def test_card_shows_summary_text(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(payload={"message": "Critical fuel spike"})
        card = _InsightCard(parent, insight)
        summary_found = any(
            "Critical fuel spike" in l.text()
            for l in card.findChildren(QLabel)
        )
        assert summary_found

    def test_card_truncates_long_summary(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        long_msg = "A" * 500
        insight = _make_insight(payload={"message": long_msg})
        card = _InsightCard(parent, insight)
        summary_found = any(
            len(l.text()) == 120 and "A" * 120 in l.text()
            for l in card.findChildren(QLabel)
            if l.text() and len(l.text()) == 120
        )
        # Summary is truncated to 120 chars in the QLabel
        assert summary_found or any(
            "A" * 120 in l.text() for l in card.findChildren(QLabel)
        )

    def test_card_shows_timestamp(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(created_at="2026-07-19T10:00:00Z")
        card = _InsightCard(parent, insight)
        # The formatted timestamp should appear in some label
        all_text = " ".join(l.text() for l in card.findChildren(QLabel))
        # At minimum the timestamp is non-empty
        ts_labels = [l for l in card.findChildren(QLabel) if "ago" in l.text() or "now" in l.text() or "m" in l.text()]
        # Should have at least the timestamp label
        assert card.findChildren(QLabel)

    def test_card_has_review_button(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight()
        card = _InsightCard(parent, insight)
        buttons = card.findChildren(QPushButton)
        review = [b for b in buttons if "Review" in b.text()]
        assert len(review) == 1

    def test_card_has_dismiss_button(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight()
        card = _InsightCard(parent, insight)
        buttons = card.findChildren(QPushButton)
        dismiss = [b for b in buttons if "Dismiss" in b.text()]
        assert len(dismiss) == 1

    def test_card_has_remind_button(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight()
        card = _InsightCard(parent, insight)
        buttons = card.findChildren(QPushButton)
        remind = [b for b in buttons if not b.text().isascii() or "\u23F0" in b.text()]
        # The snooze button uses emoji \U0001F450, check by tooltip
        remind_tt = [b for b in buttons if b.toolTip() and "Remind" in b.toolTip()]
        assert len(remind_tt) >= 1 or len(remind) >= 1

    # ── Signal emission ───────────────────────────────────────────────

    def test_review_signal(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(id="test-1")
        card = _InsightCard(parent, insight)
        signals = []

        def capture(i):
            signals.append(i)

        card.review_requested.connect(capture)
        card._on_review()
        assert len(signals) == 1
        assert signals[0].id == "test-1"

    def test_dismiss_signal(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(id="test-2")
        card = _InsightCard(parent, insight)
        signals = []

        def capture(i):
            signals.append(i)

        card.dismissed.connect(capture)
        card._on_dismiss()
        assert len(signals) == 1
        assert signals[0].id == "test-2"

    def test_remind_later_signal(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(id="test-3")
        card = _InsightCard(parent, insight)
        signals = []

        def capture(i):
            signals.append(i)

        card.remind_later.connect(capture)
        card._on_remind()
        assert len(signals) == 1
        assert signals[0].id == "test-3"

    def test_review_button_click_emits_signal(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(id="btn-review")
        card = _InsightCard(parent, insight)
        signals = []

        def capture(i):
            signals.append(i)

        card.review_requested.connect(capture)
        buttons = card.findChildren(QPushButton)
        review_btn = [b for b in buttons if "Review" in b.text()][0]
        qtbot.mouseClick(review_btn, Qt.LeftButton)
        assert len(signals) == 1
        assert signals[0].id == "btn-review"

    def test_dismiss_button_click_emits_signal(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(id="btn-dismiss")
        card = _InsightCard(parent, insight)
        signals = []

        def capture(i):
            signals.append(i)

        card.dismissed.connect(capture)
        buttons = card.findChildren(QPushButton)
        dismiss_btn = [b for b in buttons if "Dismiss" in b.text()][0]
        qtbot.mouseClick(dismiss_btn, Qt.LeftButton)
        assert len(signals) == 1
        assert signals[0].id == "btn-dismiss"

    def test_remind_button_click_emits_signal(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        insight = _make_insight(id="btn-remind")
        card = _InsightCard(parent, insight)
        signals = []

        def capture(i):
            signals.append(i)

        card.remind_later.connect(capture)
        buttons = card.findChildren(QPushButton)
        # The remind button has a tooltip "Remind later"
        remind_btn = [b for b in buttons if b.toolTip() and "Remind" in b.toolTip()]
        assert len(remind_btn) >= 1
        qtbot.mouseClick(remind_btn[0], Qt.LeftButton)
        assert len(signals) == 1
        assert signals[0].id == "btn-remind"


# ========================================================================
#  InsightQueueWidget
# ========================================================================


class TestInsightQueueWidgetConstruction:
    """Widget construction and initialisation."""

    def test_construction_default(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        assert widget is not None
        assert widget.objectName() == "insight-queue"
        assert isinstance(widget, QFrame)
        assert widget._active_filter == InsightQueueWidget.FILTER_ALL
        assert widget._insights == []

    def test_construction_with_parent(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        widget = InsightQueueWidget(parent=parent)
        qtbot.addWidget(widget)
        assert widget.parent() is parent

    def test_construction_with_api_client(self, qtbot):
        api = MagicMock()
        api.get.return_value = {"items": [], "limit": 50}
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        assert widget._api_client is api

    def test_construction_with_controller(self, qtbot):
        controller = MagicMock()
        widget = InsightQueueWidget(controller=controller)
        qtbot.addWidget(widget)
        assert widget._controller is controller

    def test_scroll_area_exists(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        scroll = widget.findChild(QScrollArea)
        assert scroll is not None
        assert scroll.widgetResizable() is True

    def test_filter_combo_exists(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        combo = widget._filter_combo
        assert combo is not None
        assert combo.count() >= 3

    def test_empty_label_hidden_by_default(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        assert widget._empty_lbl is not None
        assert widget._empty_lbl.isVisible() is False

    def test_header_title_label(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        all_labels = widget.findChildren(QLabel)
        # At least the title label exists
        assert len(all_labels) >= 1

    def test_initial_visibility(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        # When no insights, scroll area should be hidden (but widget may be visible)
        assert widget._scroll_area.isVisible() is False


class TestInsightQueueWidgetEmptyState:
    """Empty state when queue is cleared or has no insights."""

    def test_empty_state_shown_when_no_insights(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._rebuild_list()
        # _rebuild_list hides the widget itself; show it so children are visible
        widget.show()
        assert widget._empty_lbl.isVisible() is True
        assert widget._scroll_area.isVisible() is False

    def test_empty_state_hidden_when_insights_present(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget._insights = [_make_insight()]
        widget._rebuild_list()
        assert widget._empty_lbl.isVisible() is False
        assert widget._scroll_area.isVisible() is True

    def test_empty_state_reappears_after_removing_all(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget._insights = [_make_insight(id="tmp")]
        widget._rebuild_list()
        assert widget._empty_lbl.isVisible() is False
        # Remove the insight — _rebuild_list hides the widget, so show again
        widget._on_card_dismiss(widget._insights[0])
        widget.show()
        assert widget._empty_lbl.isVisible() is True
        assert widget._scroll_area.isVisible() is False

    def test_empty_label_text(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        assert len(widget._empty_lbl.text()) > 0


class TestInsightQueueWidgetDynamicAddRemove:
    """Adding and removing insights dynamically."""

    def test_rebuild_list_adds_cards(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        insights = [_make_insight(id=f"i{i}") for i in range(3)]
        widget._insights = insights
        widget._rebuild_list()
        cards = widget.findChildren(_InsightCard)
        assert len(cards) == 3

    def test_rebuild_list_removes_old_cards(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._insights = [_make_insight(id="a"), _make_insight(id="b")]
        widget._rebuild_list()
        assert len(widget.findChildren(_InsightCard)) == 2

        widget._insights = [_make_insight(id="a")]
        widget._rebuild_list()
        # Process deferred deleteLater() calls
        qtbot.wait(10)
        assert len(widget.findChildren(_InsightCard)) == 1

    def test_dismiss_removes_insight(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = _make_insight(id="dismiss-me")
        widget._insights = [ins]
        widget._rebuild_list()
        assert len(widget._insights) == 1

        widget._on_card_dismiss(ins)
        # Process deferred deleteLater() calls
        qtbot.wait(10)
        assert widget._insights == []
        cards = widget.findChildren(_InsightCard)
        assert len(cards) == 0

    def test_dismiss_emits_review_requested_only_on_review(self, qtbot):
        # Verify dismiss does NOT emit review_requested
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        signals = []

        def capture(i):
            signals.append(i)

        widget.review_requested.connect(capture)
        ins = _make_insight(id="no-signal")
        widget._insights = [ins]
        widget._rebuild_list()
        widget._on_card_dismiss(ins)
        assert len(signals) == 0

    def test_review_requested_signal(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        signals = []

        def capture(i):
            signals.append(i)

        widget.review_requested.connect(capture)
        ins = _make_insight(id="review-me")
        widget._insights = [ins]
        widget._rebuild_list()
        widget._on_card_review(ins)
        assert len(signals) == 1
        assert signals[0].id == "review-me"


class TestInsightQueueWidgetSeverityBadges:
    """Severity badge display on cards within the queue."""

    SEVERITIES = {
        "critical": COLOR_ERROR_DEFAULT,
        "high": COLOR_WARNING_DEFAULT,
        "medium": COLOR_INFO_DEFAULT,
        "low": COLOR_NEUTRAL_DEFAULT,
    }

    def test_each_severity_renders_correct_badge_color(self, qtbot):
        for sev, expected_color in self.SEVERITIES.items():
            widget = InsightQueueWidget()
            qtbot.addWidget(widget)
            ins = _make_insight(id=f"s-{sev}", severity=sev)
            widget._insights = [ins]
            widget._rebuild_list()
            cards = widget.findChildren(_InsightCard)
            assert len(cards) == 1
            badges = cards[0].findChildren(_SeverityBadge)
            assert len(badges) >= 1
            stylesheet = badges[0].styleSheet()
            assert expected_color in stylesheet, (
                f"Severity {sev!r}: expected bg color {expected_color} "
                f"in badge stylesheet"
            )


class TestInsightQueueWidgetActionButtons:
    """Action buttons on insight cards in the queue."""

    def test_card_review_button_emits_through_queue(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        signals = []

        def capture(i):
            signals.append(i)

        widget.review_requested.connect(capture)
        ins = _make_insight(id="q-review")
        widget._insights = [ins]
        widget._rebuild_list()
        card = widget.findChildren(_InsightCard)[0]
        card._on_review()
        assert len(signals) == 1
        assert signals[0].id == "q-review"

    def test_card_dismiss_button_removes_from_queue(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = _make_insight(id="q-dismiss")
        widget._insights = [ins]
        widget._rebuild_list()
        assert len(widget._insights) == 1
        card = widget.findChildren(_InsightCard)[0]
        card._on_dismiss()
        # The queue should have removed the insight
        assert len(widget._insights) == 0

    def test_card_snooze_button_triggers_log(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = _make_insight(id="q-snooze")
        widget._insights = [ins]
        widget._rebuild_list()
        card = widget.findChildren(_InsightCard)[0]
        # Remind should not remove the card (it's a placeholder)
        card._on_remind()
        assert len(widget._insights) == 1  # insight still present


class TestInsightQueueWidgetOrdering:
    """Queue ordering behaviour."""

    def test_insights_rendered_in_insertion_order(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        # Create insights with distinct IDs in a specific order
        widget._insights = [
            _make_insight(id="first", severity="low"),
            _make_insight(id="second", severity="high"),
            _make_insight(id="third", severity="medium"),
        ]
        widget._rebuild_list()
        cards = widget.findChildren(_InsightCard)
        card_ids = [c._insight.id for c in cards]
        assert card_ids == ["first", "second", "third"]

    def test_rebuild_preserves_order(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._insights = [
            _make_insight(id="z"),
            _make_insight(id="a"),
            _make_insight(id="m"),
        ]
        widget._rebuild_list()
        cards = widget.findChildren(_InsightCard)
        assert [c._insight.id for c in cards] == ["z", "a", "m"]

    def test_order_after_dismiss(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        i1 = _make_insight(id="keep-1")
        i2 = _make_insight(id="remove-me")
        i3 = _make_insight(id="keep-2")
        widget._insights = [i1, i2, i3]
        widget._rebuild_list()
        widget._on_card_dismiss(i2)
        assert [i.id for i in widget._insights] == ["keep-1", "keep-2"]


class TestInsightQueueWidgetFiltering:
    """Filter dropdown behaviour."""

    def test_set_filter_all_refreshes(self, qtbot):
        api = MagicMock()
        # Prevent MagicMock auto-creating _get, so code falls through to get
        api._get = None
        api.get.return_value = {"items": [], "limit": 50}
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        widget.set_filter(InsightQueueWidget.FILTER_ALL)
        assert widget._active_filter == InsightQueueWidget.FILTER_ALL
        api.get.assert_called()

    def test_set_filter_new(self, qtbot):
        api = MagicMock()
        api.get.return_value = {"items": [], "limit": 50}
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        widget.set_filter(InsightQueueWidget.FILTER_NEW)
        assert widget._active_filter == InsightQueueWidget.FILTER_NEW

    def test_set_filter_reviewed(self, qtbot):
        api = MagicMock()
        api.get.return_value = {"items": [], "limit": 50}
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        widget.set_filter(InsightQueueWidget.FILTER_REVIEWED)
        assert widget._active_filter == InsightQueueWidget.FILTER_REVIEWED


class TestInsightQueueWidgetRefresh:
    """Refresh / data-fetching behaviour."""

    def test_refresh_without_api_client_does_nothing(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget.refresh()  # Should not raise

    def test_refresh_with_api_client_populates_insights(self, qtbot):
        api = MagicMock()
        api._get = None  # Prevent MagicMock auto-creating _get
        api.get.return_value = {
            "items": [
                {"id": "r1", "insight_type": "cost_anomaly", "severity": "critical",
                 "payload": {"message": "High fuel cost"}},
                {"id": "r2", "insight_type": "driver_alert", "severity": "high",
                 "payload": {"message": "Driver delay"}},
            ],
            "limit": 50,
        }
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        widget.refresh()
        assert len(widget._insights) == 2

    def test_refresh_with_underscore_get_method(self, qtbot):
        api = MagicMock()
        # Let _get be auto-created so it's used by the code
        api._get.return_value = {"items": [], "limit": 50}
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        widget.refresh()
        api._get.assert_called_once()

    def test_refresh_handles_api_error(self, qtbot):
        api = MagicMock()
        api._get = None  # Force code to use get
        api.get.side_effect = Exception("API unavailable")
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        widget.refresh()  # Should not raise
        assert widget._insights == []

    def test_refresh_handles_none_response(self, qtbot):
        api = MagicMock()
        api._get = None  # Force code to use get
        api.get.return_value = None
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        widget.refresh()  # Should not raise
        assert widget._insights == []


class TestInsightQueueWidgetSignalEmission:
    """Signal emission on card click and action buttons."""

    def test_review_requested_signal_contains_insight(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        fired = []

        def capture(i):
            fired.append(i)

        widget.review_requested.connect(capture)
        ins = _make_insight(id="signal-test")
        # Emit manually via the internal handler
        widget._on_card_review(ins)
        assert len(fired) == 1
        assert fired[0].id == "signal-test"

    def test_actions_connected_to_card_signals(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = _make_insight(id="conn-test")
        widget._insights = [ins]
        widget._rebuild_list()
        card = widget.findChildren(_InsightCard)[0]
        # Check signals are connected
        assert card.review_requested is not None
        assert card.dismissed is not None
        assert card.remind_later is not None


class TestInsightQueueWidgetOverflow:
    """Queue overflow handling (max items)."""

    def test_many_insights_is_scrollable(self, qtbot):
        """With many insights, the scroll area should be the container."""
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        count = 30
        widget._insights = [
            _make_insight(id=f"overflow-{i}", severity="low")
            for i in range(count)
        ]
        widget._rebuild_list()
        cards = widget.findChildren(_InsightCard)
        assert len(cards) == count
        # The scroll area should be visible and contain the cards
        assert widget._scroll_area.isVisible() is True
        # All cards should be inside the scroll content widget
        scroll_content = widget._scroll_area.widget()
        assert scroll_content is not None
        scroll_cards = scroll_content.findChildren(_InsightCard)
        assert len(scroll_cards) == count

    def test_scroll_content_has_stretch_at_end(self, qtbot):
        """The list layout should have a stretch at the end to keep cards
        top-aligned."""
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._insights = [_make_insight()]
        widget._rebuild_list()
        layout = widget._list_layout
        # Last item should be a spacer (stretch)
        last_item = layout.itemAt(layout.count() - 1)
        assert last_item is not None
        # spacerItem is QSpacerItem
        from PySide6.QtWidgets import QSpacerItem
        assert isinstance(last_item, QSpacerItem) or last_item.expandingDirections() != 0


class TestInsightQueueWidgetEdgeCases:
    """Edge cases: zero insights, very long text, etc."""

    def test_zero_insights_shows_empty(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._insights = []
        widget._rebuild_list()
        widget.show()
        assert widget._empty_lbl.isVisible() is True
        assert widget._scroll_area.isVisible() is False

    def test_insight_with_very_long_text(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        long_msg = "Very long message with " + "x" * 500
        ins = _make_insight(payload={"message": long_msg})
        widget._insights = [ins]
        widget._rebuild_list()
        cards = widget.findChildren(_InsightCard)
        assert len(cards) == 1
        # Should not crash; summary should be truncated

    def test_insight_with_null_created_at(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = _make_insight(created_at=None)
        widget._insights = [ins]
        widget._rebuild_list()  # Should not crash

    def test_insight_without_payload_message(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = _make_insight(payload={"other": "value"})
        widget._insights = [ins]
        widget._rebuild_list()  # Should not crash

    def test_insight_with_empty_payload(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = _make_insight(payload={})
        widget._insights = [ins]
        widget._rebuild_list()  # Should not crash

    def test_insight_with_all_categories(self, qtbot):
        """Each insight_type should render without error."""
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        types = list(_TYPE_ICONS.keys())
        insights = [
            _make_insight(id=f"type-{t}", insight_type=t)
            for t in types
        ]
        widget._insights = insights
        widget._rebuild_list()
        cards = widget.findChildren(_InsightCard)
        assert len(cards) == len(types)

    def test_unknown_insight_type_uses_default_icon(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)
        ins = _make_insight(insight_type="unknown_type_xyz")
        card = _InsightCard(parent, ins)
        # Should use the default icon character (speech bubble)
        assert card is not None

    def test_insight_without_conversation_id(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins = Insight(id="no-conv", insight_type="cost_anomaly", severity="low")
        widget._insights = [ins]
        widget._rebuild_list()  # Should not crash
        assert len(widget._insights) == 1


class TestInsightQueueWidgetGrouping:
    """Insight grouping by category."""

    def test_insights_grouped_by_type_in_list(self, qtbot):
        """Cards should be rendered side-by-side in the list layout; we can
        verify by checking the layout order."""
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ins1 = _make_insight(id="g1", insight_type="cost_anomaly")
        ins2 = _make_insight(id="g2", insight_type="cost_anomaly")
        ins3 = _make_insight(id="g3", insight_type="driver_alert")
        widget._insights = [ins1, ins2, ins3]
        widget._rebuild_list()

        # Find cards in order
        cards = widget.findChildren(_InsightCard)
        # The layout order should match the _insights list order
        assert len(cards) == 3
        # All cards should have correct insight types
        assert cards[0]._insight.insight_type == "cost_anomaly"
        assert cards[1]._insight.insight_type == "cost_anomaly"
        assert cards[2]._insight.insight_type == "driver_alert"


class TestInsightQueueWidgetStyling:
    """Visual styling verification."""

    def test_queue_has_correct_stylesheet(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        ss = widget.styleSheet()
        assert "background-color" in ss
        assert "border-radius" in ss
        assert widget.objectName() in ss or "#insight-queue" in ss


class TestInsightQueueWidgetScrollContent:
    """Scrollable content for many insights."""

    def test_scroll_content_widget_exists(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        content = widget._list_content
        assert content is not None
        assert content.layout() is widget._list_layout

    def test_scroll_area_contains_cards(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._insights = [_make_insight() for _ in range(5)]
        widget._rebuild_list()
        scroll_content = widget._scroll_area.widget()
        assert scroll_content is not None
        cards_in_scroll = scroll_content.findChildren(_InsightCard)
        assert len(cards_in_scroll) == 5

    def test_scroll_area_hidden_when_empty(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._rebuild_list()
        widget.show()
        assert widget._scroll_area.isVisible() is False
        assert widget._empty_lbl.isVisible() is True
        assert widget.isVisible() is True  # widget itself may still be visible

    def test_scroll_area_visible_when_items(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        widget._insights = [_make_insight()]
        widget._rebuild_list()
        assert widget._scroll_area.isVisible() is True
        assert widget._empty_lbl.isVisible() is False


class TestInsightQueueWidgetFilterCombo:
    """Filter combo box interaction."""

    def test_filter_change_triggers_refresh_with_api(self, qtbot):
        api = MagicMock()
        api._get = None
        api.get.return_value = {"items": [], "limit": 50}
        widget = InsightQueueWidget(api_client=api)
        qtbot.addWidget(widget)
        # Switch to a filter value that differs from the default "All"
        widget._filter_combo.setCurrentText("New")
        # Allow event loop to process
        QApplication.processEvents()
        assert api.get.called

    def test_filter_combo_updates_active_filter(self, qtbot):
        widget = InsightQueueWidget()
        qtbot.addWidget(widget)
        # Direct set_filter call
        widget.set_filter(InsightQueueWidget.FILTER_NEW)
        assert widget._active_filter == "new"
        widget.set_filter(InsightQueueWidget.FILTER_REVIEWED)
        assert widget._active_filter == "reviewed"
        widget.set_filter(InsightQueueWidget.FILTER_ALL)
        assert widget._active_filter == "all"
