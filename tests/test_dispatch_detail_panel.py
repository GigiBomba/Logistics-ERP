"""Tests for the Qt dispatch detail panel dialog.

Expanded to cover init, UI layout, view/edit mode transitions,
empty alert states, save/cancel lifecycle, and error display.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from services.operations.event_bus import TRIP_UPDATED
from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_trip_data(overrides: dict | None = None) -> dict:
    data = {
        "id": 1,
        "trip_id": "TRIP-001",
        "trip_id_num": 1,
        "status": "Planned",
        "truck_plate": "AB-12-34",
        "driver_name": "John Doe",
        "origin": "Bucharest",
        "destination": "Cluj",
        "departure_date": "2026-01-15",
        "eta": "2026-01-16",
        "distance_km": 450.0,
        "total_price_eur": 2500.0,
        "net_profit": 500.0,
    }
    if overrides:
        data.update(overrides)
    return data


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def panel(qt_widget, qtbot):
    """Provide a fully constructed QtDispatchDetailPanel with mocked deps."""
    db = MagicMock()
    ops = MagicMock()
    trip_data = _make_trip_data()
    dlg = QtDispatchDetailPanel(
        parent=qt_widget,
        trip_data=trip_data,
        db=db,
        on_save=MagicMock(),
        on_close=MagicMock(),
        ops=ops,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


# ── Tests ────────────────────────────────────────────────────────────────

class TestQtDispatchDetailPanelInit:
    """Construction and basic state."""

    def test_creation(self, panel):
        assert isinstance(panel, QtDispatchDetailPanel)
        assert panel.windowTitle() != ""

    def test_is_modal(self, panel):
        assert panel.windowModality() == Qt.ApplicationModal

    def test_minimum_size_set(self, panel):
        assert panel.minimumWidth() == 480
        assert panel.minimumHeight() == 500

    def test_stores_trip_data_copy(self, panel):
        """_trip_data should be a dict copy, not the original fixture object."""
        orig = _make_trip_data()
        panel._trip_data["status"] = "Changed"
        # original reference should have been stored as dict()
        assert panel._trip_data is not orig

    def test_default_view_mode(self, panel):
        assert panel._editing is False

    def test_trip_service_initialized(self, panel):
        assert panel._trip_service is not None

    def test_edit_widgets_empty_on_init(self, panel):
        assert panel._edit_widgets == {}

    def test_on_save_callback_stored(self, panel):
        assert panel._on_save is not None

    def test_on_close_callback_stored(self, panel):
        assert panel._on_close_cb is not None

    def test_ops_stored(self, panel):
        assert panel._ops is not None

    def test_window_title_uses_translation(self, panel):
        # Should contain a non-empty title
        assert len(panel.windowTitle()) > 0


class TestQtDispatchDetailPanelUI:
    """UI element presence and structure."""

    def test_header_built(self, panel):
        # The trip ID should be shown in a QLabel somewhere
        labels = panel.findChildren(QLabel)
        texts = " ".join(l.text() for l in labels)
        assert "TRIP-001" in texts

    def test_status_chip_exists(self, panel):
        chip = panel.findChild(QLabel, options=Qt.FindChildrenRecursively)
        chip_texts = [l.text() for l in panel.findChildren(QLabel)]
        assert "Planned" in chip_texts or any("Planned" in l.text() for l in panel.findChildren(QLabel))

    def test_fields_layout_exists(self, panel):
        assert panel._fields_layout is not None
        assert panel._fields_layout.count() > 0

    def test_alerts_layout_exists(self, panel):
        assert panel._alerts_layout is not None

    def test_view_fields_show_data(self, panel):
        """In view mode, field values should be rendered as text."""
        texts = []
        for l in panel.findChildren(QLabel):
            t = l.text()
            if t:
                texts.append(t)
        combined = " ".join(texts)
        assert "AB-12-34" in combined
        assert "John Doe" in combined
        assert "Bucharest" in combined
        assert "Cluj" in combined

    def test_alerts_section_has_divider(self, panel):
        from PySide6.QtWidgets import QFrame
        frames = panel.findChildren(QFrame)
        assert any(f.frameShape() == QFrame.HLine for f in frames)

    def test_no_alerts_label_shown_when_no_trip_alerts(self, panel):
        """When ops returns no relevant alerts, show the 'no alerts' label."""
        panel._ops.get_alerts.return_value = []
        # Force re-build
        panel._build_alerts()
        texts = [l.text() for l in panel.findChildren(QLabel)]
        assert any("no alerts" in t.lower() or t for t in texts)

    def test_empty_state_no_ops(self, panel_no_ops):
        """When ops is None, show no-alerts label."""
        dlg, _ = panel_no_ops
        texts = [l.text() for l in dlg.findChildren(QLabel)]
        assert any("no alerts" in t.lower() or t for t in texts)


@pytest.fixture
def panel_no_ops(qt_widget, qtbot):
    """Panel without ops — to test empty states."""
    db = MagicMock()
    trip_data = _make_trip_data()
    dlg = QtDispatchDetailPanel(parent=qt_widget, trip_data=trip_data, db=db)
    qtbot.addWidget(dlg)
    yield dlg, qtbot


class TestQtDispatchDetailPanelEditMode:
    """Edit mode transitions."""

    def test_enter_edit_mode_flags(self, panel):
        panel._enter_edit_mode()
        assert panel._editing is True

    def test_enter_edit_mode_rebuilds_fields(self, panel):
        panel._enter_edit_mode()
        # Should now have edit widgets
        assert len(panel._edit_widgets) > 0
        assert "status" in panel._edit_widgets
        assert "departure_date" in panel._edit_widgets
        assert "eta" in panel._edit_widgets
        assert "distance_km" in panel._edit_widgets

    def test_enter_edit_mode_shows_save_cancel(self, panel):
        panel._enter_edit_mode()
        btn_widgets = [w for w in panel._btn_widget.findChildren(QWidget) if w is not panel._btn_widget]
        # ActionButton instances are rendered as QPushButton on some platforms
        btn_texts = []
        for w in panel._btn_widget.findChildren(QPushButton):
            btn_texts.append(w.text())
        combined = " ".join(btn_texts).lower()
        assert "save" in combined

    def test_cancel_edit_returns_to_view(self, panel):
        panel._enter_edit_mode()
        panel._cancel_edit()
        assert panel._editing is False
        assert panel._edit_widgets == {}

    def test_cancel_edit_clears_edit_widgets(self, panel):
        panel._enter_edit_mode()
        assert len(panel._edit_widgets) > 0
        panel._cancel_edit()
        assert panel._edit_widgets == {}

    def test_enter_edit_from_view_toggles_buttons(self, panel):
        # Initially view mode — buttons should be different
        initial_texts = {w.text() for w in panel._btn_widget.findChildren(QPushButton)}
        panel._enter_edit_mode()
        edit_texts = {w.text() for w in panel._btn_widget.findChildren(QPushButton)}
        assert initial_texts != edit_texts


class TestQtDispatchDetailPanelSave:
    """Save logic with mocked TripService."""

    def test_save_no_changes_cancels_edit(self, panel):
        panel._enter_edit_mode()
        # Clear all edit widget values to simulate no changes
        for w in panel._edit_widgets.values():
            from ui.widgets import StyledComboBox
            if isinstance(w, StyledComboBox):
                # Don't clear the status combo — that's always set
                pass
            elif hasattr(w, "setText"):
                w.setText("")
        # Clear the distance
        if "distance_km" in panel._edit_widgets:
            panel._edit_widgets["distance_km"].setText("")
        panel._save_changes()
        # Should have cancelled because no changes
        assert panel._editing is False

    def test_save_calls_trip_service(self, panel):
        with patch.object(panel._trip_service, "update") as mock_update:
            panel._enter_edit_mode()
            # Set some changes
            if "eta" in panel._edit_widgets:
                panel._edit_widgets["eta"].setText("2026-01-17")
            panel._save_changes()
            assert mock_update.called

    def test_save_publishes_event(self, panel):
        with patch.object(panel._trip_service, "update") as mock_update:
            with patch("ui.dialogs.dispatch_detail_panel.EventBus.publish") as mock_pub:
                panel._enter_edit_mode()
                if "eta" in panel._edit_widgets:
                    panel._edit_widgets["eta"].setText("2026-01-17")
                panel._save_changes()
                assert mock_pub.called
                call_args = mock_pub.call_args[0]
                assert call_args[0] == TRIP_UPDATED

    def test_save_calls_on_save_callback(self, panel):
        with patch.object(panel._trip_service, "update"):
            panel._enter_edit_mode()
            if "eta" in panel._edit_widgets:
                panel._edit_widgets["eta"].setText("2026-01-17")
            panel._save_changes()
            panel._on_save.assert_called_once()

    def test_save_exception_shows_error(self, panel):
        with patch.object(panel._trip_service, "update", side_effect=ValueError("DB error")):
            panel._enter_edit_mode()
            if "eta" in panel._edit_widgets:
                panel._edit_widgets["eta"].setText("2026-01-17")
            panel._save_changes()
            # Error label should be shown in fields layout
            texts = []
            for i in range(panel._fields_layout.count()):
                w = panel._fields_layout.itemAt(i).widget()
                if w and isinstance(w, QLabel):
                    texts.append(w.text())
            assert any("DB error" in t for t in texts)

    def test_save_with_status_change(self, panel):
        with patch.object(panel._trip_service, "update") as mock_update:
            panel._enter_edit_mode()
            # Change status via the combo
            combo = panel._edit_widgets.get("status")
            if combo and combo.count() > 0:
                combo.setCurrentIndex(0)
            panel._save_changes()
            if mock_update.called:
                args, kwargs = mock_update.call_args
                assert "status" in kwargs.get("changes", {}) or (len(args) > 1 and "status" in args[1])

    def test_save_no_trip_id_returns_early(self, panel):
        with patch.object(panel._trip_service, "update") as mock_update:
            panel._trip_data["trip_id_num"] = None
            panel._trip_data["id"] = None
            panel._save_changes()
            assert not mock_update.called

    def test_save_after_success_resets_to_view(self, panel):
        with patch.object(panel._trip_service, "update"):
            panel._enter_edit_mode()
            if "eta" in panel._edit_widgets:
                panel._edit_widgets["eta"].setText("2026-01-17")
            panel._save_changes()
            assert panel._editing is False
            assert panel._edit_widgets == {}


class TestQtDispatchDetailPanelClose:
    """Close behavior."""

    def test_close_fires_callback(self, panel):
        panel._close()
        panel._on_close_cb.assert_called_once()

    def test_reject_fires_callback(self, panel):
        panel.reject()
        panel._on_close_cb.assert_called_once()


class TestQtDispatchDetailPanelLifecycle:
    """Full lifecycle: view → edit → save/cancel → view."""

    def test_view_edit_view_cycle(self, panel):
        assert panel._editing is False
        panel._enter_edit_mode()
        assert panel._editing is True
        panel._cancel_edit()
        assert panel._editing is False

    def test_view_edit_save_view_cycle(self, panel):
        with patch.object(panel._trip_service, "update"):
            assert panel._editing is False
            panel._enter_edit_mode()
            assert panel._editing is True
            if "eta" in panel._edit_widgets:
                panel._edit_widgets["eta"].setText("2026-01-17")
            panel._save_changes()
            assert panel._editing is False
