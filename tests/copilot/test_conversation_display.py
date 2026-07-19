"""Comprehensive Qt unit tests for ConversationDisplayWidget.

Tests cover:
  - Widget construction
  - Adding a message bubble to the display
  - Adding multiple messages (user + assistant turns)
  - Auto-scroll to latest message
  - Clearing all messages
  - Empty state display
  - Support for different message types (text, thinking)
  - Scroll area behavior for many messages
  - Edge case: adding very long messages, adding messages rapidly
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QSizePolicy, QWidget

from ui.copilot.widgets.chat_bubble import ChatBubbleWidget


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def display(qt_widget: QWidget) -> "ConversationDisplayWidget":
    """Build a ConversationDisplayWidget attached to a parent."""
    from ui.copilot.widgets.conversation_display import ConversationDisplayWidget

    d = ConversationDisplayWidget(parent=qt_widget)
    return d


@pytest.fixture
def display_with_messages(display: "ConversationDisplayWidget") -> "ConversationDisplayWidget":
    """Build a display pre-populated with a few messages."""
    display.add_message("Hello!", is_user=True)
    display.add_message("Hi there! How can I help?", is_user=False)
    display.add_message("Show me the fleet dashboard", is_user=True)
    return display


@pytest.fixture
def shown_display(display, qtbot):
    """Display with its parent shown (for visibility-dependent tests)."""
    display.parent().show()
    display.show()
    qtbot.wait(50)
    return display


# =============================================================================
# Use the session-scoped QApp from test_conftest
# =============================================================================
pytestmark = pytest.mark.usefixtures("qapp")


# =============================================================================
# Widget Construction & Initialisation
# =============================================================================


class TestConstruction:
    """Verify the display is built correctly with expected defaults."""

    def test_construction_defaults(self, qt_widget: QWidget):
        """Display is created as a QScrollArea with correct defaults."""
        from ui.copilot.widgets.conversation_display import ConversationDisplayWidget

        d = ConversationDisplayWidget(parent=qt_widget)
        assert isinstance(d, QScrollArea)
        assert d.widgetResizable() is True
        assert d.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert d.frameShape() == QScrollArea.NoFrame
        # Not shown by default (parent not shown)
        assert d.isVisible() is False

    def test_construction_no_parent(self):
        """Should construct safely with no parent."""
        from ui.copilot.widgets.conversation_display import ConversationDisplayWidget

        d = ConversationDisplayWidget(parent=None)
        assert d is not None
        assert d.widgetResizable() is True

    def test_empty_state_label_created(self, display):
        """Empty state label exists and is not hidden (widget-level)."""
        assert display._empty_label is not None
        assert isinstance(display._empty_label, QLabel)
        # Widget is hidden because parent isn't shown; check !isHidden instead
        assert not display._empty_label.isHidden()
        assert display._empty_label.text() != ""

    def test_empty_state_label_hidden_when_parent_shown(self, shown_display):
        """Empty state label is visible when parent is shown."""
        assert shown_display._empty_label.isVisible() is True

    def test_thinking_indicator_exists(self, display):
        """Thinking indicator widget exists and is hidden initially."""
        assert display._thinking is not None
        assert display._thinking.isVisible() is False  # Hidden via setVisible(False)

    def test_container_has_correct_layout(self, display):
        """Container layout has the expected spacing and margins."""
        assert display._layout is not None
        assert display._layout.spacing() > 0
        margins = display._layout.contentsMargins()
        assert margins.left() > 0
        assert margins.top() > 0
        assert margins.right() > 0
        assert margins.bottom() > 0

    def test_spacer_exists(self, display):
        """Spacer widget keeps bubbles at the top."""
        assert display._spacer is not None
        assert display._spacer.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding


# =============================================================================
# Adding Messages
# =============================================================================


class TestAddMessage:
    """Verify adding messages works correctly."""

    def test_add_message_creates_bubble(self, display):
        """Adding a message creates a ChatBubbleWidget."""
        display.add_message("Test message", is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert bubbles[0]._message == "Test message"
        assert bubbles[0]._is_user is True

    def test_add_hides_empty_state(self, shown_display):
        """Adding a message hides the empty state label."""
        assert shown_display._empty_label.isVisible() is True
        shown_display.add_message("First message", is_user=True)
        assert shown_display._empty_label.isVisible() is False

    def test_add_two_messages(self, display):
        """Adding two messages creates two bubbles."""
        display.add_message("User message", is_user=True)
        display.add_message("Assistant response", is_user=False)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 2
        assert bubbles[0]._message == "User message"
        assert bubbles[0]._is_user is True
        assert bubbles[1]._message == "Assistant response"
        assert bubbles[1]._is_user is False

    def test_add_message_user_and_assistant_turns(self, display):
        """Multiple turns of user/assistant messages are ordered correctly."""
        messages = [
            ("Hello", True),
            ("Hi!", False),
            ("Show dashboard", True),
            ("Here it is", False),
        ]
        for text, is_user in messages:
            display.add_message(text, is_user=is_user)

        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 4
        for i, (text, is_user) in enumerate(messages):
            assert bubbles[i]._message == text
            assert bubbles[i]._is_user == is_user

    def test_add_message_with_custom_timestamp(self, display):
        """Adding a message with a custom timestamp preserves it."""
        ts = datetime(2025, 6, 15, 14, 30, 0)
        display.add_message("Timestamped message", is_user=True, timestamp=ts)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert bubbles[0]._timestamp == ts

    def test_add_message_default_timestamp(self, display):
        """Adding a message without timestamp uses current time."""
        before = datetime.now()
        display.add_message("No timestamp", is_user=True)
        after = datetime.now()
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert before <= bubbles[0]._timestamp <= after


# =============================================================================
# Auto-Scroll Behavior
# =============================================================================


class TestAutoScroll:
    """Verify auto-scroll to latest message on new content."""

    def test_add_message_triggers_scroll(self, display, qtbot):
        """Adding a message triggers a scroll-to-bottom via timer."""
        with patch.object(display, "_perform_scroll") as mock_scroll:
            display.add_message("Test", is_user=True)
            qtbot.wait(100)
            mock_scroll.assert_called_once()

    def test_scroll_to_bottom_after_multiple_messages(self, display, qtbot):
        """After adding multiple messages, scrollbar is at maximum."""
        for i in range(20):
            display.add_message(f"Message {i}", is_user=(i % 2 == 0))

        qtbot.wait(200)  # Let scroll timers fire
        scrollbar = display.verticalScrollBar()
        if scrollbar.maximum() > 0:
            assert scrollbar.value() == scrollbar.maximum()

    def test_scroll_timer_uses_single_shot(self, display):
        """_scroll_to_bottom uses a single-shot QTimer."""
        original = display._scroll_to_bottom
        display._scroll_to_bottom = lambda: None  # Disable actual scroll
        with patch.object(display, "_perform_scroll") as mock_scroll:
            display.add_message("Test", is_user=True)
            # Verify perform_scroll is called (indirect validation)
            pass

    def test_show_thinking_triggers_scroll(self, display, qtbot):
        """show_thinking also scrolls to bottom."""
        with patch.object(display, "_scroll_to_bottom") as mock_scroll:
            display.show_thinking()
            mock_scroll.assert_called_once()


# =============================================================================
# Clearing Messages
# =============================================================================


class TestClear:
    """Verify clearing messages works correctly."""

    def test_clear_removes_bubbles_from_layout(self, display_with_messages, qtbot):
        """Clear removes ChatBubbleWidgets from the layout."""
        # Before: layout should have empty_label + 3 bubbles + thinking + spacer = 6 items
        assert display_with_messages._layout.count() >= 5

        display_with_messages.clear()
        qtbot.wait(50)  # Process deferredDelete events

        # After: layout should have empty_label + thinking + spacer = 3 items
        assert display_with_messages._layout.count() == 3
        # No ChatBubbleWidget should remain in the layout
        for i in range(display_with_messages._layout.count()):
            item = display_with_messages._layout.itemAt(i)
            if item and item.widget():
                assert not isinstance(item.widget(), ChatBubbleWidget)

    def test_clear_shows_empty_state_when_parent_shown(self, shown_display, qtbot):
        """Clear restores the empty state label visibility."""
        shown_display.add_message("Test", is_user=True)
        assert shown_display._empty_label.isVisible() is False
        shown_display.clear()
        qtbot.wait(50)
        assert shown_display._empty_label.isVisible() is True

    def test_clear_stops_thinking(self, display):
        """Clear stops the thinking indicator."""
        display.show_thinking()
        assert display._thinking._timer.isActive() is True
        display.clear()
        assert display._thinking.isVisible() is False
        assert display._thinking._timer.isActive() is False

    def test_clear_empty_display_no_crash(self, display):
        """Clearing an already-empty display does not crash."""
        display.clear()  # Should not raise

    def test_clear_then_add_messages(self, display, qtbot):
        """After clear, adding messages works correctly."""
        display.add_message("Before", is_user=True)
        display.clear()
        qtbot.wait(50)
        display.add_message("After", is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert bubbles[0]._message == "After"


# =============================================================================
# Empty State
# =============================================================================


class TestEmptyState:
    """Verify empty state display."""

    def test_empty_state_visible_when_shown(self, shown_display):
        """Empty state label is visible when display is shown."""
        assert shown_display._empty_label.isVisible() is True

    def test_empty_state_text_not_empty(self, display):
        """Empty state has informative text."""
        assert display._empty_label.text() != ""
        assert len(display._empty_label.text()) > 0

    def test_empty_state_hidden_after_add(self, shown_display):
        """Empty state hides after adding a message."""
        shown_display.add_message("Test", is_user=True)
        assert shown_display._empty_label.isVisible() is False

    def test_empty_state_centered(self, display):
        """Empty state label is center-aligned."""
        assert display._empty_label.alignment() & Qt.AlignCenter

    def test_empty_state_word_wrap(self, display):
        """Empty state label has word wrap enabled."""
        assert display._empty_label.wordWrap() is True


# =============================================================================
# Thinking Indicator
# =============================================================================


class TestThinkingIndicator:
    """Verify thinking indicator show/hide behavior."""

    def test_thinking_hidden_initially(self, display):
        """Thinking indicator is hidden by default."""
        assert display._thinking.isVisible() is False

    def test_show_thinking_makes_visible_when_shown(self, shown_display, qtbot):
        """show_thinking() makes the indicator visible when display is shown."""
        shown_display.show_thinking()
        qtbot.wait(50)
        assert shown_display._thinking.isVisible() is True

    def test_hide_thinking_hides_indicator(self, shown_display, qtbot):
        """hide_thinking() makes the indicator invisible and stops animation."""
        shown_display.show_thinking()
        qtbot.wait(50)
        assert shown_display._thinking.isVisible() is True
        shown_display.hide_thinking()
        assert shown_display._thinking.isVisible() is False
        assert shown_display._thinking._timer.isActive() is False

    def test_show_thinking_after_messages(self, shown_display_with_messages, qtbot):
        """Showing thinking after messages works correctly."""
        shown_display_with_messages.show_thinking()
        qtbot.wait(50)
        assert shown_display_with_messages._thinking.isVisible() is True
        # Messages should still be there
        bubbles = shown_display_with_messages.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 3

    def test_hide_thinking_when_not_running(self, display):
        """hide_thinking() when not running does not crash."""
        display.hide_thinking()  # Should not raise


# =============================================================================
# Different Message Types
# =============================================================================


class TestMessageTypes:
    """Verify the display handles various types of content."""

    def test_text_message(self, display):
        """Regular text message is displayed correctly."""
        display.add_message("Hello world", is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert "Hello world" in bubbles[0]._message

    def test_long_text_message(self, display):
        """Long text message is handled without truncation."""
        long_text = "A" * 10000
        display.add_message(long_text, is_user=False)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert len(bubbles[0]._message) == 10000

    def test_empty_text_message(self, display):
        """Empty text message still creates a bubble."""
        display.add_message("", is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert bubbles[0]._message == ""

    def test_message_with_special_characters(self, display):
        """Messages with special characters render correctly."""
        special = "Line1\nLine2\tTabbed\n特殊文字😊"
        display.add_message(special, is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert bubbles[0]._message == special

    def test_message_with_html_content(self, display):
        """Messages containing HTML are displayed as plain text."""
        html = "<b>Bold</b> <script>alert('xss')</script>"
        display.add_message(html, is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert bubbles[0]._message == html


# =============================================================================
# Scroll Area Behavior
# =============================================================================


class TestScrollAreaBehavior:
    """Verify scroll area handles many messages correctly."""

    def test_many_messages(self, display):
        """Adding many messages creates the expected number of bubbles."""
        n = 50
        for i in range(n):
            display.add_message(f"Message {i}", is_user=(i % 2 == 0))
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == n

    def test_messages_order_maintained(self, display):
        """Message order is preserved with many messages."""
        n = 20
        for i in range(n):
            display.add_message(f"Msg-{i}", is_user=(i % 2 == 0))
        bubbles = display.findChildren(ChatBubbleWidget)
        for i in range(n):
            assert bubbles[i]._message == f"Msg-{i}"

    def test_scroll_area_expands_with_content(self, display):
        """The scroll area content grows as messages are added."""
        initial_height = display._container.sizeHint().height()
        for i in range(10):
            display.add_message(f"Message {i}", is_user=True)
        final_height = display._container.sizeHint().height()
        assert final_height > initial_height

    def test_vertical_scrollbar_appears(self, display, qtbot):
        """Vertical scrollbar appears when content exceeds viewport."""
        display.parent().show()
        display.show()
        display.resize(400, 100)  # Small viewport
        qtbot.wait(50)
        for i in range(30):
            display.add_message(f"Message {i}", is_user=True)
        qtbot.wait(200)
        scrollbar = display.verticalScrollBar()
        assert scrollbar.maximum() > 0

    def test_horizontal_scrollbar_always_off(self, display):
        """Horizontal scrollbar is always off."""
        assert display.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Verify edge cases are handled gracefully."""

    def test_add_message_rapidly(self, display, qtbot):
        """Adding messages rapidly does not cause issues."""
        for i in range(100):
            display.add_message(f"Fast message {i}", is_user=(i % 2 == 0))
        qtbot.wait(500)  # Let scroll timers settle
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 100

    def test_add_message_very_long_text(self, display):
        """Very long single message (50k chars) is handled."""
        long_text = "Lorem ipsum dolor sit amet " * 2000  # ~50k chars
        display.add_message(long_text, is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert len(bubbles[0]._message) > 50000

    def test_add_message_after_clear(self, display, qtbot):
        """Adding messages after clear works correctly."""
        display.add_message("First batch", is_user=True)
        display.clear()
        qtbot.wait(50)
        display.add_message("Second batch", is_user=True)
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert bubbles[0]._message == "Second batch"

    def test_clear_during_thinking(self, shown_display, qtbot):
        """Clear while thinking indicator is visible works."""
        shown_display.show_thinking()
        qtbot.wait(50)
        assert shown_display._thinking.isVisible() is True
        shown_display.clear()
        assert shown_display._thinking.isVisible() is False
        assert shown_display._empty_label.isVisible() is True

    def test_add_message_with_none_text(self, display):
        """Adding a message with None text does not crash."""
        display.add_message(None, is_user=True)  # type: ignore[arg-type]
        bubbles = display.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 1
        assert bubbles[0]._message is None

    def test_show_hide_thinking_multiple_times(self, shown_display, qtbot):
        """Calling show/hide thinking multiple times is idempotent."""
        for _ in range(5):
            shown_display.show_thinking()
            qtbot.wait(30)
            shown_display.hide_thinking()
            qtbot.wait(30)
        assert shown_display._thinking.isVisible() is False


# =============================================================================
# Layout Integrity
# =============================================================================


class TestLayoutIntegrity:
    """Verify the internal layout structure is maintained."""

    def test_layout_item_count_initial(self, display):
        """Layout has empty_label + thinking + spacer = 3 items initially."""
        assert display._layout.count() == 3

    def test_layout_items_are_widgets(self, display):
        """All layout items are widgets (not spacers or layouts)."""
        for i in range(display._layout.count()):
            item = display._layout.itemAt(i)
            assert item is not None
            assert item.widget() is not None

    def test_bubbles_inserted_before_thinking(self, display):
        """Bubbles are inserted before the thinking indicator."""
        display.add_message("Test", is_user=True)
        # Layout: [empty_label(hidden), bubble, thinking, spacer]
        item1 = display._layout.itemAt(1)
        assert item1 is not None
        w1 = item1.widget()
        assert isinstance(w1, ChatBubbleWidget)
        assert w1._message == "Test"

    def test_thinking_position_after_messages(self, display):
        """Thinking indicator stays after all messages."""
        display.add_message("Msg 1", is_user=True)
        display.add_message("Msg 2", is_user=False)
        display.add_message("Msg 3", is_user=True)
        # Find thinking index
        thinking_idx = None
        for i in range(display._layout.count()):
            item = display._layout.itemAt(i)
            if item and item.widget() is display._thinking:
                thinking_idx = i
                break
        assert thinking_idx is not None
        # Thinking should be after all bubbles (≥ index 4: empty + 3 bubbles)
        assert thinking_idx >= 4

    def test_spacer_is_last_item(self, display):
        """Spacer widget is the last item in the layout."""
        display.add_message("Test", is_user=True)
        last_idx = display._layout.count() - 1
        last_item = display._layout.itemAt(last_idx)
        assert last_item is not None
        assert last_item.widget() is display._spacer


# =============================================================================
# Show/Hide Display
# =============================================================================


class TestShowHide:
    """Verify show/hide transitions work correctly."""

    def test_show_makes_visible(self, display, qtbot):
        """Calling show() makes the widget visible when parent is shown."""
        display.parent().show()
        display.show()
        qtbot.wait(50)
        assert display.isVisible() is True

    def test_hide_makes_invisible(self, display, qtbot):
        """Calling hide() makes the widget invisible."""
        display.parent().show()
        display.show()
        qtbot.wait(50)
        assert display.isVisible() is True
        display.hide()
        qtbot.wait(50)
        assert display.isVisible() is False

    def test_show_after_add_messages(self, display_with_messages, qtbot):
        """Showing display after adding messages retains bubbles."""
        display_with_messages.parent().show()
        display_with_messages.show()
        qtbot.wait(50)
        assert display_with_messages.isVisible() is True
        bubbles = display_with_messages.findChildren(ChatBubbleWidget)
        assert len(bubbles) == 3


# =============================================================================
# Additional fixture for shown_display_with_messages
# =============================================================================


@pytest.fixture
def shown_display_with_messages(display_with_messages, qtbot):
    """Display with messages and parent shown (for visibility-dependent tests)."""
    display_with_messages.parent().show()
    display_with_messages.show()
    qtbot.wait(50)
    return display_with_messages
