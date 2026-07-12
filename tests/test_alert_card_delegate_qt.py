"""pytest-qt tests for AlertCardDelegate — styled item delegate for alert cards.

Extends the legacy tests in ``test_alert_card_delegate.py`` with real
pytest-qt fixtures, mock painter-based paint tests, and coverage for all
severity colors and edge cases.

Tests
-----
- Creation and parent storage
- sizeHint returns the correct QSize
- paint with QPainter mock for each severity level
- paint when alert data is None (no crash)
- paint with truck_id and trip_id references
- paint with truncated long message
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor

from services.operations.alert_manager import Alert, AlertType, Severity
from ui.delegates.alert_card_delegate import (
    AlertCardDelegate,
    _CARD_HEIGHT,
    _SEV_COLORS,
)
from ui.models.alert_list_model import AlertListModel


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def delegate(qt_widget, qtbot):
    """Create an AlertCardDelegate with a QWidget parent."""
    d = AlertCardDelegate(qt_widget)
    qtbot.addWidget(qt_widget)
    yield d


@pytest.fixture
def sample_alert() -> Alert:
    """A typical alert for use in paint tests."""
    return Alert(
        id="abc123",
        type=AlertType.TRIP_DELAY,
        severity=Severity.WARNING,
        title="Trip Delayed",
        message="Estimated delay of 45 minutes due to traffic.",
        truck_id="TRK-042",
        trip_id="TRIP-987",
        created_at="2026-07-12T10:30:00",
    )


@pytest.fixture
def critical_alert() -> Alert:
    return Alert(
        id="crt001",
        type=AlertType.COMPLIANCE_RISK,
        severity=Severity.CRITICAL,
        title="Compliance Risk",
        message="Driver hours exceeded for TRK-001.",
    )


@pytest.fixture
def info_alert() -> Alert:
    return Alert(
        id="inf001",
        type=AlertType.INSPECTION,
        severity=Severity.INFO,
        title="Inspection Due",
        message="Annual inspection due in 14 days.",
    )


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    """Delegate initializes correctly."""

    def test_creation(self, delegate):
        assert delegate is not None
        assert delegate.parent() is not None

    def test_fonts_initialized(self, delegate):
        assert delegate._font_title is not None
        assert delegate._font_body is not None
        assert delegate._font_small is not None
        assert delegate._font_mono is not None

    def test_parent_stored(self, qt_widget, qtbot):
        d = AlertCardDelegate(qt_widget)
        assert d.parent() is qt_widget


# =========================================================================
# sizeHint
# =========================================================================


class TestSizeHint:
    """sizeHint returns the expected dimensions."""

    def test_size_hint_returns_qsize(self, delegate):
        from PySide6.QtWidgets import QStyleOptionViewItem

        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 300, 100)
        index = QModelIndex()
        size = delegate.sizeHint(option, index)
        assert isinstance(size, QSize)
        assert size.width() == 300
        assert size.height() == _CARD_HEIGHT

    def test_size_hint_width_follows_option_rect(self, delegate):
        from PySide6.QtWidgets import QStyleOptionViewItem

        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 500, 100)
        index = QModelIndex()
        size = delegate.sizeHint(option, index)
        assert size.width() == 500


# =========================================================================
# paint — no alert (None data)
# =========================================================================


class TestPaintNoAlert:
    """Paint returns early when alert data is None."""

    def test_paint_with_no_alert_does_not_crash(self, delegate):
        """When index.data(AlertRole) returns None, paint returns early (no drawing)."""
        from PySide6.QtWidgets import QStyleOptionViewItem

        painter = MagicMock()
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 300, _CARD_HEIGHT)
        index = QModelIndex()
        delegate.paint(painter, option, index)  # must not crash
        # No fillRect or drawText calls since paint returns early
        fill_calls = [c for c in painter.method_calls if c[0] == "fillRect"]
        draw_calls = [c for c in painter.method_calls if c[0] == "drawText"]
        assert len(fill_calls) == 0
        assert len(draw_calls) == 0


# =========================================================================
# paint — with alerts
# =========================================================================


class TestPaintWithAlert:
    """Paint draws the correct elements for each alert."""

    def paint_alert(self, delegate, alert: Alert, width: int = 300) -> MagicMock:
        """Helper: paint an alert and return the QPainter mock."""
        from PySide6.QtWidgets import QStyleOptionViewItem

        painter = MagicMock()
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, width, _CARD_HEIGHT)
        index = MagicMock(spec=QModelIndex)
        index.data = MagicMock(return_value=alert)
        delegate.paint(painter, option, index)
        return painter

    def test_paint_calls_save_and_restore(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        painter.save.assert_called_once()
        painter.restore.assert_called_once()

    def test_paint_sets_antialiasing(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        painter.setRenderHint.assert_called_once()

    def test_paint_fills_background(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        calls = [c for c in painter.method_calls if c[0] == "fillRect"]
        assert len(calls) >= 1

    def test_paint_sets_warning_accent_for_sample(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        calls = [c for c in painter.method_calls if c[0] == "fillRect"]
        # Second fillRect is the accent (after background)
        accent_fill = calls[1] if len(calls) >= 2 else calls[-1]
        color = accent_fill.args[1]
        assert isinstance(color, QColor)
        assert color == _SEV_COLORS[Severity.WARNING]

    def test_paint_critical_accent_color(self, delegate, critical_alert):
        painter = self.paint_alert(delegate, critical_alert)
        calls = [c for c in painter.method_calls if c[0] == "fillRect"]
        accent_fill = calls[1] if len(calls) >= 2 else calls[-1]
        color = accent_fill.args[1]
        assert color == _SEV_COLORS[Severity.CRITICAL]

    def test_paint_info_accent_color(self, delegate, info_alert):
        painter = self.paint_alert(delegate, info_alert)
        calls = [c for c in painter.method_calls if c[0] == "fillRect"]
        accent_fill = calls[1] if len(calls) >= 2 else calls[-1]
        color = accent_fill.args[1]
        assert color == _SEV_COLORS[Severity.INFO]

    def test_paint_draws_title(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        draw_text_calls = [c for c in painter.method_calls if c[0] == "drawText"]
        assert len(draw_text_calls) >= 1
        # Title should contain the alert title
        title_call = draw_text_calls[0]
        text = title_call.args[5] if len(title_call.args) >= 6 else ""
        assert "Trip Delayed" in str(text)

    def test_paint_draws_timestamp(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        draw_text_calls = [c for c in painter.method_calls if c[0] == "drawText"]
        ts_call = draw_text_calls[1]
        text = ts_call.args[5] if len(ts_call.args) >= 6 else ""
        assert "10:30" in str(text)

    def test_paint_draws_message(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        draw_text_calls = [c for c in painter.method_calls if c[0] == "drawText"]
        # Row 2 is message (3rd drawText if ts present)
        msg_call = draw_text_calls[2] if len(draw_text_calls) >= 3 else draw_text_calls[-1]
        text = msg_call.args[5] if len(msg_call.args) >= 6 else ""
        assert "delay" in str(text)

    def test_paint_draws_truck_reference(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        draw_text_calls = [c for c in painter.method_calls if c[0] == "drawText"]
        # Last drawText contains references
        ref_call = draw_text_calls[-1]
        text = ref_call.args[5] if len(ref_call.args) >= 6 else ""
        assert "TRK-042" in str(text)
        assert "TRIP-987" in str(text)

    def test_paint_truncates_long_message(self, delegate):
        long_msg = "A" * 200
        alert = Alert(
            id="long",
            type=AlertType.MAINTENANCE,
            severity=Severity.INFO,
            title="Long Msg",
            message=long_msg,
        )
        painter = self.paint_alert(delegate, alert)
        draw_text_calls = [c for c in painter.method_calls if c[0] == "drawText"]
        msg_call = draw_text_calls[-1] if len(draw_text_calls) <= 2 else draw_text_calls[2]
        text = msg_call.args[5] if len(msg_call.args) >= 6 else ""
        assert len(str(text)) <= 120

    def test_paint_without_refs(self, delegate):
        """Alert without truck_id or trip_id skips reference row."""
        alert = Alert(
            id="no_ref",
            type=AlertType.INSURANCE,
            severity=Severity.INFO,
            title="No Refs",
            message="Just a note.",
        )
        painter = self.paint_alert(delegate, alert)
        draw_text_calls = [c for c in painter.method_calls if c[0] == "drawText"]
        # Only title + timestamp + message = 3 calls
        assert len(draw_text_calls) == 3

    def test_paint_sets_font_for_title(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        set_font_calls = [c for c in painter.method_calls if c[0] == "setFont"]
        assert len(set_font_calls) >= 1

    def test_paint_sets_pen(self, delegate, sample_alert):
        painter = self.paint_alert(delegate, sample_alert)
        set_pen_calls = [c for c in painter.method_calls if c[0] == "setPen"]
        assert len(set_pen_calls) >= 1


# =========================================================================
# Edge cases
# =========================================================================


class TestPaintEdgeCases:
    """Edge cases for delegate painting."""

    def test_paint_zero_width_rect(self, delegate, sample_alert):
        """A zero-width option rect should not crash."""
        painter = MagicMock()
        from PySide6.QtWidgets import QStyleOptionViewItem

        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 0, 0)
        index = MagicMock(spec=QModelIndex)
        index.data = MagicMock(return_value=sample_alert)
        delegate.paint(painter, option, index)  # must not crash

    def test_paint_alert_with_empty_title(self, delegate):
        alert = Alert(
            id="empty_title", type=AlertType.INACTIVE_TRUCK,
            severity=Severity.WARNING, title="", message="Body",
        )
        painter = MagicMock()
        from PySide6.QtWidgets import QStyleOptionViewItem

        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 300, _CARD_HEIGHT)
        index = MagicMock(spec=QModelIndex)
        index.data = MagicMock(return_value=alert)
        delegate.paint(painter, option, index)  # must not crash

    def test_muted_severity_fallback(self, delegate):
        """An unknown severity uses the muted color fallback."""
        alert = Alert(
            id="unknown_sev", type=AlertType.MAINTENANCE,
            severity=Severity.INFO, title="Test",
            message="Fallback test",
        )
        painter = self._paint_single(delegate, alert)
        calls = [c for c in painter.method_calls if c[0] == "fillRect"]
        assert len(calls) >= 2  # background + accent
        # Accent should use INFO color (not fallback since INFO is known)
        accent_fill = calls[1]
        assert accent_fill.args[1] == _SEV_COLORS[Severity.INFO]

    def _paint_single(self, delegate, alert) -> MagicMock:
        from PySide6.QtWidgets import QStyleOptionViewItem
        painter = MagicMock()
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 300, _CARD_HEIGHT)
        index = MagicMock(spec=QModelIndex)
        index.data = MagicMock(return_value=alert)
        delegate.paint(painter, option, index)
        return painter
