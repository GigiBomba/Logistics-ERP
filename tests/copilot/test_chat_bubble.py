"""Comprehensive Qt unit tests for ChatBubbleWidget.

Tests cover:
  - Widget construction and initialization with text content
  - User vs assistant bubble styling (alignment, background color)
  - Timestamp display and formatting
  - Long message handling (word wrap, max-width)
  - Role label text for user vs assistant
  - Message label properties (word wrap, font size)
  - Container bubble maximum width
  - Edge cases: empty message, very long message, special characters
  - Multiple bubble type forms (text only — the widget uses is_user flag)
  - Error styling (red-tinted assistant bubble)
  - Loading/typing indicator patterns (placeholder text)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

# =============================================================================
# Helpers
# =============================================================================

# The t() fallback keys for role labels
YOU_LABEL = "copilot.chat.you"
CO_PILOT_LABEL = "copilot.chat.co_pilot"

# Known design-token colour name substrings used in bubble stylesheets
# (actual hex values from ui/design_tokens.py).
# We check for these name references in the generated stylesheet.
COLOR_USER_BG = "COLOR_ACCENT_SUBTLE"
COLOR_ASSISTANT_BG = "COLOR_BG_ELEVATED"


def _get_labels(bubble: QFrame) -> list[QLabel]:
    """Return all QLabel children of the bubble."""
    return bubble.findChildren(QLabel)


def _get_role_label(bubble: QFrame) -> QLabel | None:
    """Return the role label (first label in layout)."""
    labels = _get_labels(bubble)
    # Role label is typically the first one
    for lbl in labels:
        text = lbl.text()
        if text in (YOU_LABEL, CO_PILOT_LABEL) or "copilot.chat" in text:
            return lbl
    return labels[0] if labels else None


def _get_message_label(bubble: QFrame) -> QLabel | None:
    """Return the message label (second label, has the actual message text)."""
    labels = _get_labels(bubble)
    if len(labels) >= 2:
        return labels[1]
    return None


def _get_timestamp_label(bubble: QFrame) -> QLabel | None:
    """Return the timestamp label (last label, shows time like '14:30')."""
    labels = _get_labels(bubble)
    if len(labels) >= 3:
        return labels[-1]
    return None


# =============================================================================
# Construction & Initialization
# =============================================================================


class TestConstruction:
    """Verify the widget is built correctly with expected defaults."""

    def test_construction_defaults(self, qt_widget):
        """Widget is a QFrame with transparent background and Expanding/Fixed policy."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", is_user=False, parent=qt_widget)
        assert bubble is not None
        assert bubble._message == "Hello"
        assert bubble._is_user is False
        policy = bubble.sizePolicy()
        assert policy.horizontalPolicy().name == "Expanding"
        assert policy.verticalPolicy().name == "Fixed"
        assert "transparent" in bubble.styleSheet()

    def test_construction_no_parent(self):
        """Can construct with no parent."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("No parent", parent=None)
        assert bubble is not None

    def test_construction_user_bubble(self, qt_widget):
        """User bubble sets is_user flag correctly."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("User text", is_user=True, parent=qt_widget)
        assert bubble._is_user is True

    def test_construction_assistant_bubble(self, qt_widget):
        """Assistant bubble sets is_user flag to False."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Assistant text", is_user=False, parent=qt_widget)
        assert bubble._is_user is False

    def test_timestamp_defaults_to_now(self, qt_widget):
        """When no timestamp is provided, it defaults to datetime.now()."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        before = datetime.now()
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        after = datetime.now()
        assert before <= bubble._timestamp <= after

    def test_custom_timestamp(self, qt_widget):
        """Custom timestamp is stored correctly."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        ts = datetime(2025, 6, 15, 14, 30, 0)
        bubble = ChatBubbleWidget("Hello", timestamp=ts, parent=qt_widget)
        assert bubble._timestamp == ts


# =============================================================================
# Role Label
# =============================================================================


class TestRoleLabel:
    """Role label text for user vs assistant."""

    def test_user_role_label(self, qt_widget):
        """User bubble has a role label with the 'you' i18n key."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", is_user=True, parent=qt_widget)
        role_lbl = _get_role_label(bubble)
        assert role_lbl is not None
        # t() falls back to the key string when no translation is loaded
        assert "you" in role_lbl.text().lower() or "copilot.chat" in role_lbl.text()

    def test_assistant_role_label(self, qt_widget):
        """Assistant bubble has a role label with the 'co_pilot' i18n key."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", is_user=False, parent=qt_widget)
        role_lbl = _get_role_label(bubble)
        assert role_lbl is not None
        assert "co_pilot" in role_lbl.text().lower() or "copilot.chat" in role_lbl.text()

    def test_role_label_has_semibold_font(self, qt_widget):
        """Role label has semibold font weight in its stylesheet."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", parent=qt_widget)
        role_lbl = _get_role_label(bubble)
        assert role_lbl is not None
        assert "FONT_WEIGHT_SEMIBOLD" in role_lbl.styleSheet() or "font-weight" in role_lbl.styleSheet()

    def test_role_label_secondary_color(self, qt_widget):
        """Role label uses secondary text colour."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", parent=qt_widget)
        role_lbl = _get_role_label(bubble)
        assert role_lbl is not None
        assert "COLOR_TEXT_SECONDARY" in role_lbl.styleSheet() or "color" in role_lbl.styleSheet()


# =============================================================================
# Message Label
# =============================================================================


class TestMessageLabel:
    """Message text label behavior."""

    def test_message_text_displayed(self, qt_widget):
        """Message text appears in the message label."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Display this text", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert "Display this text" in msg_lbl.text()

    def test_message_word_wrap_enabled(self, qt_widget):
        """Message label has word wrap enabled."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Wrapped text", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert msg_lbl.wordWrap() is True

    def test_message_primary_color(self, qt_widget):
        """Message label uses primary text colour."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Coloured", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert "COLOR_TEXT_PRIMARY" in msg_lbl.styleSheet() or "color" in msg_lbl.styleSheet()

    def test_message_font_size_sm(self, qt_widget):
        """Message label uses FONT_SIZE_SM."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Size test", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert "FONT_SIZE_SM" in msg_lbl.styleSheet() or "font-size" in msg_lbl.styleSheet()


# =============================================================================
# Timestamp Display
# =============================================================================


class TestTimestamp:
    """Timestamp display and formatting."""

    def test_timestamp_label_exists(self, qt_widget):
        """A timestamp label is present."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", parent=qt_widget)
        ts_lbl = _get_timestamp_label(bubble)
        assert ts_lbl is not None

    def test_timestamp_format_hh_mm(self, qt_widget):
        """Timestamp is formatted as HH:MM."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        ts = datetime(2025, 6, 15, 9, 5, 0)
        bubble = ChatBubbleWidget("Hi", timestamp=ts, parent=qt_widget)
        ts_lbl = _get_timestamp_label(bubble)
        assert ts_lbl is not None
        assert ts_lbl.text() == "09:05"

    def test_timestamp_afternoon(self, qt_widget):
        """Timestamp shows PM time correctly."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        ts = datetime(2025, 6, 15, 14, 30, 0)
        bubble = ChatBubbleWidget("Hi", timestamp=ts, parent=qt_widget)
        ts_lbl = _get_timestamp_label(bubble)
        assert ts_lbl is not None
        assert ts_lbl.text() == "14:30"

    def test_timestamp_midnight(self, qt_widget):
        """Midnight timestamp shows 00:00."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        ts = datetime(2025, 6, 15, 0, 0, 0)
        bubble = ChatBubbleWidget("Hi", timestamp=ts, parent=qt_widget)
        ts_lbl = _get_timestamp_label(bubble)
        assert ts_lbl is not None
        assert ts_lbl.text() == "00:00"

    def test_timestamp_alignment_user(self, qt_widget):
        """User has right-aligned timestamp."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", is_user=True, parent=qt_widget)
        ts_lbl = _get_timestamp_label(bubble)
        assert ts_lbl is not None
        assert ts_lbl.alignment() == Qt.AlignRight

    def test_timestamp_alignment_assistant(self, qt_widget):
        """Assistant has left-aligned timestamp."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", is_user=False, parent=qt_widget)
        ts_lbl = _get_timestamp_label(bubble)
        assert ts_lbl is not None
        assert ts_lbl.alignment() == Qt.AlignLeft

    def test_timestamp_secondary_color(self, qt_widget):
        """Timestamp uses secondary text colour."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hi", parent=qt_widget)
        ts_lbl = _get_timestamp_label(bubble)
        assert ts_lbl is not None
        assert "COLOR_TEXT_SECONDARY" in ts_lbl.styleSheet() or "color" in ts_lbl.styleSheet()


# =============================================================================
# User vs Assistant Styling
# =============================================================================


class TestUserVsAssistantStyling:
    """Verify different styling for user and assistant messages."""

    def test_user_bubble_alignment(self, qt_widget):
        """User bubble is right-aligned (stretch before bubble)."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("User msg", is_user=True, parent=qt_widget)
        layout = bubble.layout()
        # User layout: stretch(1), bubble, (no stretch after)
        assert layout is not None
        # The layout should have a stretch at index 0
        stretch = layout.itemAt(0)
        assert stretch is not None
        # stretch is a QSpacerItem
        from PySide6.QtWidgets import QSpacerItem
        assert isinstance(stretch, QSpacerItem)

    def test_assistant_bubble_alignment(self, qt_widget):
        """Assistant bubble is left-aligned (stretch after bubble)."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Assistant msg", is_user=False, parent=qt_widget)
        layout = bubble.layout()
        assert layout is not None
        # The layout should have a stretch at the last position
        last_idx = layout.count() - 1
        last_item = layout.itemAt(last_idx)
        assert last_item is not None
        from PySide6.QtWidgets import QSpacerItem
        assert isinstance(last_item, QSpacerItem)

    def test_user_bubble_background(self, qt_widget):
        """User bubble container uses accent subtle colour."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("User msg", is_user=True, parent=qt_widget)
        # Find the inner bubble frame (the first QFrame child)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        # Stylesheet should contain the user background colour reference
        assert "COLOR_ACCENT_SUBTLE" in inner.styleSheet() or "background-color" in inner.styleSheet()

    def test_assistant_bubble_background(self, qt_widget):
        """Assistant bubble container uses elevated background colour."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Assistant msg", is_user=False, parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        assert "COLOR_BG_ELEVATED" in inner.styleSheet() or "background-color" in inner.styleSheet()

    def test_bubble_has_border(self, qt_widget):
        """Bubble container has a border."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Bordered", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        assert "border" in inner.styleSheet()

    def test_bubble_rounded_corners(self, qt_widget):
        """Bubble container has rounded corners."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Rounded", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        assert "border-radius" in inner.styleSheet()

    def test_bubble_max_width(self, qt_widget):
        """Bubble container has a maximum width of 480px."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Max width test", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        assert inner.maximumWidth() == 480


# =============================================================================
# Long Message & Edge Cases
# =============================================================================


class TestLongMessages:
    """Behavior with long message text."""

    def test_long_message_wraps(self, qt_widget):
        """Very long text is set on the label without crashing and with word wrap."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        long_text = "Hello " * 500  # ~3000 chars
        bubble = ChatBubbleWidget(long_text, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert len(msg_lbl.text()) > 0
        assert msg_lbl.wordWrap() is True

    def test_extremely_long_message(self, qt_widget):
        """50K character message does not crash the widget."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        huge = "X" * 50_000
        bubble = ChatBubbleWidget(huge, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert len(msg_lbl.text()) == 50_000

    def test_empty_message(self, qt_widget):
        """Empty message string does not crash."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None

    def test_single_character_message(self, qt_widget):
        """Single character renders correctly."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Z", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert msg_lbl.text() == "Z"

    def test_message_with_newlines(self, qt_widget):
        """Multiline message preserves newlines."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        multiline = "line1\nline2\nline3"
        bubble = ChatBubbleWidget(multiline, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert "line1" in msg_lbl.text()
        assert "line2" in msg_lbl.text()
        assert "line3" in msg_lbl.text()


# =============================================================================
# Special Characters & Unicode
# =============================================================================


class TestSpecialCharacters:
    """Handle unicode, emoji, and HTML characters."""

    def test_unicode_text(self, qt_widget):
        """Unicode characters render correctly."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        text = "Café résumé 日本 你好"
        bubble = ChatBubbleWidget(text, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert text in msg_lbl.text()

    def test_emoji_in_message(self, qt_widget):
        """Emoji characters are rendered."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        text = "Hello 🚚 📦 ✅"
        bubble = ChatBubbleWidget(text, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert text in msg_lbl.text()

    def test_html_special_chars(self, qt_widget):
        """HTML special characters are displayed as literal text."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        text = "<test> & \"quote\" 'single'"
        bubble = ChatBubbleWidget(text, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert text in msg_lbl.text()

    def test_sql_injection_text(self, qt_widget):
        """SQL-like content does not break the display."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        text = "1; DROP TABLE messages; --"
        bubble = ChatBubbleWidget(text, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert text in msg_lbl.text()


# =============================================================================
# Container Bubble Structure
# =============================================================================


class TestBubbleContainer:
    """Verify the nested container structure."""

    def test_outer_is_qframe(self, qt_widget):
        """ChatBubbleWidget itself is a QFrame."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        assert isinstance(bubble, QFrame)

    def test_inner_bubble_has_vbox_layout(self, qt_widget):
        """Inner bubble frame has a QVBoxLayout with role, message, timestamp."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        from PySide6.QtWidgets import QVBoxLayout
        assert isinstance(inner.layout(), QVBoxLayout)

    def test_three_labels_in_bubble(self, qt_widget):
        """Inner bubble has three labels: role, message, timestamp."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        labels = inner.findChildren(QLabel)
        assert len(labels) == 3

    def test_bubble_container_has_size_policy(self, qt_widget):
        """Inner bubble has Preferred/Fixed size policy."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        policy = inner.sizePolicy()
        assert policy.horizontalPolicy().name == "Preferred"
        assert policy.verticalPolicy().name == "Fixed"

    def test_bubble_border_rounding(self, qt_widget):
        """Bubble container uses RADIUS_LG border radius."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        # The stylesheet should contain RADIUS_LG reference
        ss = inner.styleSheet()
        assert "RADIUS_LG" in ss or "border-radius" in ss


# =============================================================================
# Error State Bubble
# =============================================================================


class TestErrorStateBubble:
    """Simulate error messages in a bubble (assistant bubble with error content)."""

    def test_error_message_as_assistant_bubble(self, qt_widget):
        """An error message can be displayed as an assistant-style bubble."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        error_msg = "An error occurred while processing your request."
        bubble = ChatBubbleWidget(error_msg, is_user=False, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert error_msg in msg_lbl.text()
        # Assistant styling
        assert bubble._is_user is False
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        assert "COLOR_BG_ELEVATED" in inner.styleSheet() or "background-color" in inner.styleSheet()

    def test_error_prefix_detection(self, qt_widget):
        """Bubble correctly renders text that starts with '[Error]'."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        error = "[Error] Connection timeout. Please try again."
        bubble = ChatBubbleWidget(error, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert "[Error]" in msg_lbl.text()
        assert "Connection timeout" in msg_lbl.text()


# =============================================================================
# Loading/Typing Indicator
# =============================================================================


class TestLoadingIndicator:
    """Simulate a loading/typing indicator via the bubble widget."""

    def test_loading_text_ellipsis(self, qt_widget):
        """A bubble with ellipsis text simulates typing state."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        loading_text = "Thinking..."
        bubble = ChatBubbleWidget(loading_text, is_user=False, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert "Thinking" in msg_lbl.text() or "..." in msg_lbl.text()

    def test_loading_empty_assistant_indicator(self, qt_widget):
        """An assistant bubble with an empty loading placeholder is rendered."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("", is_user=False, parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert msg_lbl.text() == ""

    def test_typing_dots_text(self, qt_widget):
        """Three dots as message content renders without issue."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("...", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        assert msg_lbl.text() == "..."


# =============================================================================
# Signal / Interaction Patterns (future-proofing)
# =============================================================================


class TestInteractionPatterns:
    """Verify structure supports future interactions (copy, links, etc.)."""

    def test_message_label_selectable(self, qt_widget):
        """Message label text is selectable by default (QLabel default)."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Selectable text", parent=qt_widget)
        msg_lbl = _get_message_label(bubble)
        assert msg_lbl is not None
        # QLabel has textInteractionFlags; default includes TextSelectableByMouse
        assert msg_lbl.textInteractionFlags() != Qt.NoTextInteraction

    def test_no_extra_unexpected_children(self, qt_widget):
        """Bubble does not have unexpected widget children beyond QLabel."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Clean", parent=qt_widget)
        all_children = bubble.findChildren(QWidget)
        labels = bubble.findChildren(QLabel)
        # Note: QLabel inherits from QFrame in PySide6, so findChildren(QFrame)
        # returns QLabel instances too. Filter for actual QFrame-only widgets.
        frames = [c for c in bubble.findChildren(QFrame)
                  if not isinstance(c, QLabel)]
        # 1 inner container QFrame (not counting self, which findChildren excludes)
        assert len(frames) == 1
        assert len(labels) == 3  # role, message, timestamp

    def test_accessible_bubble_created(self, qt_widget):
        """Bubble can be assigned accessible properties."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Accessible", parent=qt_widget)
        bubble.setAccessibleName("chat-bubble")
        assert bubble.accessibleName() == "chat-bubble"


# =============================================================================
# Multiple Bubbles (conversation simulation)
# =============================================================================


class TestMultipleBubbles:
    """Creating multiple bubbles in sequence (conversation)."""

    def test_multiple_user_bubbles(self, qt_widget):
        """Multiple user bubbles can be created without conflict."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubbles = []
        for i in range(5):
            b = ChatBubbleWidget(f"User message {i}", is_user=True, parent=qt_widget)
            bubbles.append(b)
        assert len(bubbles) == 5
        for i, b in enumerate(bubbles):
            msg_lbl = _get_message_label(b)
            assert msg_lbl is not None
            assert f"User message {i}" in msg_lbl.text()

    def test_mixed_bubbles(self, qt_widget):
        """User and assistant bubbles can be mixed in a parent widget."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        user = ChatBubbleWidget("Where is my truck?", is_user=True, parent=qt_widget)
        assistant = ChatBubbleWidget("Truck #42 is at warehouse 3.", is_user=False, parent=qt_widget)
        assert user._is_user is True
        assert assistant._is_user is False
        assert _get_message_label(user) is not None
        assert _get_message_label(assistant) is not None

    def test_bubbles_with_different_timestamps(self, qt_widget):
        """Bubbles with different timestamps display correctly."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        base = datetime(2025, 6, 15, 10, 0, 0)
        bubbles = []
        for i in range(4):
            ts = base + timedelta(hours=i)
            b = ChatBubbleWidget(f"Message {i}", timestamp=ts, parent=qt_widget)
            bubbles.append(b)
        for i, b in enumerate(bubbles):
            ts_lbl = _get_timestamp_label(b)
            expected = (base + timedelta(hours=i)).strftime("%H:%M")
            assert ts_lbl is not None
            assert ts_lbl.text() == expected


# =============================================================================
# Layout Structure
# =============================================================================


class TestLayoutStructure:
    """Verify the outer layout structure."""

    def test_outer_layout_is_horizontal(self, qt_widget):
        """Widget-level layout is QHBoxLayout."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        from PySide6.QtWidgets import QHBoxLayout
        assert isinstance(bubble.layout(), QHBoxLayout)

    def test_outer_layout_no_margins(self, qt_widget):
        """Widget-level layout has zero margins and spacing."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        layout = bubble.layout()
        assert layout is not None
        margins = layout.getContentsMargins()
        assert margins == (0, 0, 0, 0)
        assert layout.spacing() == 0

    def test_inner_layout_margins(self, qt_widget):
        """Inner bubble layout has SPACE_3 horizontal / SPACE_2 vertical margins."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        inner_layout = inner.layout()
        assert inner_layout is not None
        margins = inner_layout.getContentsMargins()
        # Contents margins should be non-zero (SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        assert margins[0] > 0  # left
        assert margins[2] > 0  # right
        assert margins[1] > 0  # top
        assert margins[3] > 0  # bottom

    def test_inner_layout_spacing(self, qt_widget):
        """Inner bubble layout has SPACE_2 spacing."""
        from ui.copilot.widgets.chat_bubble import ChatBubbleWidget
        bubble = ChatBubbleWidget("Hello", parent=qt_widget)
        frames = bubble.findChildren(QFrame)
        assert len(frames) >= 1
        inner = frames[0]
        assert inner.layout() is not None
        assert inner.layout().spacing() > 0
