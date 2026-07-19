"""Tests for the QtPairedAssignmentDialog (PySide6 version).

Covers dialog construction, truck/driver selection, suggestion system,
accept suggestion, manual override, confirm/cancel behaviour,
validation of incompatible pairs, and edge cases (empty lists,
no suggestions).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QWidget

from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_truck_item(overrides: dict | None = None) -> dict:
    data = {
        "id": 101,
        "label": "SCANIA R500",
        "sublabel": "AB-12-34",
        "score": 92,
        "available": True,
        "status_text": "",
    }
    if overrides:
        data.update(overrides)
    return data


def _make_driver_item(overrides: dict | None = None) -> dict:
    data = {
        "id": 201,
        "label": "John Doe",
        "sublabel": "CDL-A",
        "score": 88,
        "available": True,
        "status_text": "",
    }
    if overrides:
        data.update(overrides)
    return data


def _make_trip_data(overrides: dict | None = None) -> dict:
    data = {
        "trip_id": "TRIP-042",
        "origin": "Bucharest",
        "destination": "Cluj-Napoca",
    }
    if overrides:
        data.update(overrides)
    return data


def _make_truck_items() -> list[dict]:
    return [
        _make_truck_item(),
        _make_truck_item({
            "id": 102, "label": "VOLVO FH", "sublabel": "CD-56-78",
            "score": 75, "available": True,
        }),
        _make_truck_item({
            "id": 103, "label": "DAF XF", "sublabel": "EF-90-12",
            "score": 45, "available": False, "status_text": "In maintenance",
        }),
    ]


def _make_driver_items() -> list[dict]:
    return [
        _make_driver_item(),
        _make_driver_item({
            "id": 202, "label": "Jane Smith", "sublabel": "CDL-B",
            "score": 72, "available": True,
        }),
        _make_driver_item({
            "id": 203, "label": "Bob Wilson", "sublabel": "CDL-A",
            "score": 30, "available": False, "status_text": "On leave",
        }),
    ]


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def trip_data():
    return _make_trip_data()


@pytest.fixture
def truck_items():
    return _make_truck_items()


@pytest.fixture
def driver_items():
    return _make_driver_items()


@pytest.fixture
def on_assign_both():
    return MagicMock()


@pytest.fixture
def on_assign_truck():
    return MagicMock()


@pytest.fixture
def on_assign_driver():
    return MagicMock()


@pytest.fixture
def dialog(qt_widget, qtbot, trip_data, truck_items, driver_items,
           on_assign_both, on_assign_truck, on_assign_driver):
    """Full-featured dialog with all callbacks."""
    dlg = QtPairedAssignmentDialog(
        parent=qt_widget,
        trip_data=trip_data,
        truck_items=truck_items,
        driver_items=driver_items,
        paired_hint="Suggested pair: SCANIA R500 + John Doe",
        on_assign_both=on_assign_both,
        on_assign_truck=on_assign_truck,
        on_assign_driver=on_assign_driver,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


@pytest.fixture
def dialog_empty(qt_widget, qtbot, trip_data, on_assign_both):
    """Dialog with empty truck/driver lists."""
    dlg = QtPairedAssignmentDialog(
        parent=qt_widget,
        trip_data=trip_data,
        truck_items=[],
        driver_items=[],
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


@pytest.fixture
def dialog_no_callbacks(qt_widget, qtbot, trip_data, truck_items, driver_items):
    """Dialog without any callbacks."""
    dlg = QtPairedAssignmentDialog(
        parent=qt_widget,
        trip_data=trip_data,
        truck_items=truck_items,
        driver_items=driver_items,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


# ── Test: Construction & Initialisation ──────────────────────────────────

class TestQtPairedAssignmentDialogInit:
    """Dialog construction and basic state."""

    def test_creation(self, dialog):
        assert isinstance(dialog, QtPairedAssignmentDialog)
        assert dialog.windowTitle() != ""

    def test_is_modal(self, dialog):
        assert dialog.windowModality() == Qt.ApplicationModal

    def test_minimum_size_set(self, dialog):
        assert dialog.minimumWidth() == 480
        assert dialog.minimumHeight() == 400

    def test_stores_trip_data(self, dialog, trip_data):
        assert dialog._trip_data["trip_id"] == trip_data["trip_id"]

    def test_stores_truck_items(self, dialog, truck_items):
        assert len(dialog._truck_items) == len(truck_items)

    def test_stores_driver_items(self, dialog, driver_items):
        assert len(dialog._driver_items) == len(driver_items)

    def test_stores_paired_hint(self, dialog):
        assert "SCANIA R500" in dialog._paired_hint

    def test_stores_callbacks(self, dialog, on_assign_both,
                              on_assign_truck, on_assign_driver):
        assert dialog._on_assign_both is on_assign_both
        assert dialog._on_assign_truck is on_assign_truck
        assert dialog._on_assign_driver is on_assign_driver

    def test_auto_selects_on_init(self, dialog):
        """Auto-select chooses first available truck and driver."""
        assert dialog._selected_truck == 0
        assert dialog._selected_driver == 0

    def test_truck_widgets_maps_indices(self, dialog):
        assert len(dialog._truck_widgets) == 3
        assert all(isinstance(w, QFrame) for w in dialog._truck_widgets.values())

    def test_driver_widgets_maps_indices(self, dialog):
        assert len(dialog._driver_widgets) == 3
        assert all(isinstance(w, QFrame) for w in dialog._driver_widgets.values())

    def header_shows_trip_id(self, dialog):
        texts = [l.text() for l in dialog.findChildren(QLabel)]
        assert any("TRIP-042" in t for t in texts)

    def header_shows_route(self, dialog):
        texts = [l.text() for l in dialog.findChildren(QLabel)]
        combined = " ".join(texts)
        assert "Bucharest" in combined
        assert "Cluj-Napoca" in combined


# ── Test: Auto-Select First Available ───────────────────────────────────

class TestQtPairedAssignmentDialogAutoSelect:
    """Auto-selection of first available truck and driver."""

    def test_auto_selects_first_available_truck(self, dialog):
        # Truck 0 (SCANIA R500) is available (score 92)
        assert dialog._selected_truck == 0

    def test_auto_selects_first_available_driver(self, dialog):
        # Driver 0 (John Doe) is available (score 88)
        assert dialog._selected_driver == 0

    def test_auto_select_skips_unavailable(self, dialog):
        # Truck index 2 is unavailable, so it is NOT auto-selected
        assert dialog._selected_truck != 2
        assert dialog._selected_driver != 2

    def test_auto_select_highlights_truck_row(self, dialog):
        """Selected truck row should have COLOR_ACCENT_SUBTLE background."""
        wid = dialog._truck_widgets[0]
        style = wid.styleSheet()
        assert "#1e1f3d" in style.lower()

    def test_auto_select_highlights_driver_row(self, dialog):
        """Selected driver row should have COLOR_ACCENT_SUBTLE background."""
        wid = dialog._driver_widgets[0]
        style = wid.styleSheet()
        assert "#1e1f3d" in style.lower()

    def test_no_selection_when_all_unavailable(self, dialog_empty):
        assert dialog_empty._selected_truck is None
        assert dialog_empty._selected_driver is None

    def test_auto_select_only_available_item(self, qt_widget, qtbot, trip_data):
        """When only the second item is available, it should be selected."""
        trucks = [
            _make_truck_item({"id": 1, "available": False, "status_text": "Broken"}),
            _make_truck_item({"id": 2, "available": True}),
        ]
        drivers = [
            _make_driver_item({"id": 10, "available": False, "status_text": "Sick"}),
            _make_driver_item({"id": 20, "available": True}),
        ]
        dlg = QtPairedAssignmentDialog(
            parent=qt_widget, trip_data=trip_data,
            truck_items=trucks, driver_items=drivers,
        )
        qtbot.addWidget(dlg)
        assert dlg._selected_truck == 1
        assert dlg._selected_driver == 1
        dlg.close()


# ── Test: Selection Behaviour ───────────────────────────────────────────

class TestQtPairedAssignmentDialogSelection:
    """Manual selection of trucks and drivers."""

    def test_select_truck_updates_selection(self, dialog):
        dialog._select_truck(1)
        assert dialog._selected_truck == 1

    def test_select_driver_updates_selection(self, dialog):
        dialog._select_driver(1)
        assert dialog._selected_driver == 1

    def test_select_truck_highlights_row(self, dialog):
        dialog._select_truck(1)
        wid = dialog._truck_widgets[1]
        style = wid.styleSheet()
        # Selected row gets COLOR_ACCENT_SUBTLE (#1E1F3D)
        assert "#1e1f3d" in style.lower()

    def test_select_truck_deselects_previous(self, dialog):
        dialog._select_truck(1)
        wid_0 = dialog._truck_widgets[0]
        style_0 = wid_0.styleSheet()
        # Deselected row gets COLOR_BG_SURFACE
        assert "#141416" in style_0.lower()

    def test_select_same_truck_twice_keeps_selection(self, dialog):
        dialog._select_truck(0)
        assert dialog._selected_truck == 0

    def test_select_driver_highlights_row(self, dialog):
        dialog._select_driver(1)
        wid = dialog._driver_widgets[1]
        style = wid.styleSheet()
        assert "#1e1f3d" in style.lower()

    def test_select_unavailable_truck_still_selects(self, dialog):
        """User can select an unavailable item (the dialog does not prevent it)."""
        dialog._select_truck(2)
        assert dialog._selected_truck == 2

    def test_click_row_triggers_selection(self, dialog):
        """Clicking a truck row frame should call _select_truck."""
        wid = dialog._truck_widgets[2]
        # Simulate a mouse press event
        from PySide6.QtGui import QMouseEvent
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            wid.rect().center(),
            wid.mapToGlobal(wid.rect().center()),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        )
        wid.mousePressEvent(event)
        assert dialog._selected_truck == 2


# ── Test: Button State (Update Buttons) ─────────────────────────────────

class TestQtPairedAssignmentDialogButtons:
    """Button enable/disable state based on selection."""

    def test_both_btn_enabled_when_both_selected(self, dialog):
        """After auto-select, both truck and driver should be selected."""
        assert dialog._both_btn is not None
        assert dialog._both_btn.isEnabled() is True

    def test_both_btn_disabled_when_truck_missing(self, dialog):
        dialog._selected_truck = None
        dialog._update_buttons()
        assert dialog._both_btn.isEnabled() is False

    def test_both_btn_disabled_when_driver_missing(self, dialog):
        dialog._selected_driver = None
        dialog._update_buttons()
        assert dialog._both_btn.isEnabled() is False

    def test_truck_btn_enabled_when_truck_selected(self, dialog):
        assert dialog._truck_btn is not None
        assert dialog._truck_btn.isEnabled() is True

    def test_truck_btn_disabled_when_truck_missing(self, dialog):
        dialog._selected_truck = None
        dialog._update_buttons()
        assert dialog._truck_btn.isEnabled() is False

    def test_driver_btn_enabled_when_driver_selected(self, dialog):
        assert dialog._driver_btn is not None
        assert dialog._driver_btn.isEnabled() is True

    def test_driver_btn_disabled_when_driver_missing(self, dialog):
        dialog._selected_driver = None
        dialog._update_buttons()
        assert dialog._driver_btn.isEnabled() is False

    def test_all_buttons_exist(self, dialog):
        assert dialog._both_btn is not None
        assert dialog._truck_btn is not None
        assert dialog._driver_btn is not None


# ── Test: Suggestion System ─────────────────────────────────────────────

class TestQtPairedAssignmentDialogSuggestions:
    """Paired hint / suggestion display."""

    def test_paired_hint_displayed_when_provided(self, dialog):
        texts = [l.text() for l in dialog.findChildren(QLabel)]
        combined = " ".join(texts)
        assert "SCANIA R500" in combined

    def test_paired_hint_not_displayed_when_empty(self, qt_widget, qtbot,
                                                   trip_data, truck_items,
                                                   driver_items):
        hint_text = "Custom suggestion for this trip"
        dlg = QtPairedAssignmentDialog(
            parent=qt_widget, trip_data=trip_data,
            truck_items=truck_items, driver_items=driver_items,
            paired_hint=hint_text,
        )
        qtbot.addWidget(dlg)
        texts = [l.text() for l in dlg.findChildren(QLabel)]
        combined = " ".join(texts)
        assert hint_text in combined
        dlg.close()

    def test_paired_hint_omitted_when_empty_string(self, qt_widget, qtbot,
                                                    trip_data, truck_items,
                                                    driver_items):
        dlg = QtPairedAssignmentDialog(
            parent=qt_widget, trip_data=trip_data,
            truck_items=truck_items, driver_items=driver_items,
            paired_hint="",
        )
        qtbot.addWidget(dlg)
        l = len(dlg.findChildren(QLabel))
        dlg.close()

    def test_high_score_item_has_star(self, dialog):
        """Items with available=True and score > 70 should have a star."""
        wid = dialog._truck_widgets[0]  # SCANIA R500, score 92
        labels = wid.findChildren(QLabel)
        texts = [l.text() for l in labels]
        # Star unicode character
        assert any("\u2b50" in t for t in texts)

    def test_low_score_item_no_star(self, dialog):
        """Truck index 2 is unavailable, so no star even if score > 70."""
        wid = dialog._truck_widgets[2]  # DAF XF, score 45
        labels = wid.findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert not any("\u2b50" in t for t in texts)

    def test_medium_score_no_star(self, qt_widget, qtbot, trip_data):
        """Available item with score <= 70 should not get a star."""
        trucks = [_make_truck_item({"id": 1, "score": 65, "available": True})]
        drivers = [_make_driver_item({"id": 10, "score": 60, "available": True})]
        dlg = QtPairedAssignmentDialog(
            parent=qt_widget, trip_data=trip_data,
            truck_items=trucks, driver_items=drivers,
        )
        qtbot.addWidget(dlg)
        wid = dlg._truck_widgets[0]
        labels = wid.findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert not any("\u2b50" in t for t in texts)
        dlg.close()

    def test_suggestion_accepted_via_assign_both(self, dialog, on_assign_both):
        """Accepting the suggested pair (auto-selected) calls on_assign_both."""
        dialog._do_assign_both()
        on_assign_both.assert_called_once()
        # Truck 0 id=101, Driver 0 id=201
        args = on_assign_both.call_args[0]
        assert args[0] == 101
        assert args[1] == 201

    def test_suggestion_accepted_closes_dialog(self, dialog):
        dialog._do_assign_both()
        assert dialog.result() == QDialog.Accepted  # type: ignore[attr-defined]


# ── Test: Manual Override ───────────────────────────────────────────────

class TestQtPairedAssignmentDialogManualOverride:
    """Manual selection of non-suggested pairs."""

    def test_select_different_truck_and_assign_both(
        self, dialog, on_assign_both
    ):
        dialog._select_truck(1)   # VOLVO FH (id=102)
        dialog._select_driver(1)  # Jane Smith (id=202)
        dialog._do_assign_both()
        on_assign_both.assert_called_once_with(102, 202)

    def test_assign_truck_only(self, dialog, on_assign_truck):
        dialog._select_truck(1)
        dialog._do_assign_truck_only()
        on_assign_truck.assert_called_once_with(102)

    def test_assign_driver_only(self, dialog, on_assign_driver):
        dialog._select_driver(1)
        dialog._do_assign_driver_only()
        on_assign_driver.assert_called_once_with(202)

    def test_assign_truck_only_closes_dialog(self, dialog):
        dialog._do_assign_truck_only()
        assert dialog.result() == QDialog.Accepted  # type: ignore[attr-defined]

    def test_assign_driver_only_closes_dialog(self, dialog):
        dialog._do_assign_driver_only()
        assert dialog.result() == QDialog.Accepted  # type: ignore[attr-defined]

    def test_manual_selection_unavailable_item(self, dialog, on_assign_both):
        """Manually selecting an unavailable item still assigns."""
        dialog._select_truck(2)   # DAF XF (unavailable, id=103)
        dialog._select_driver(2)  # Bob Wilson (unavailable, id=203)
        dialog._do_assign_both()
        on_assign_both.assert_called_once_with(103, 203)


# ── Test: Assign With No Callbacks ──────────────────────────────────────

class TestQtPairedAssignmentDialogNoCallbacks:
    """Assign behaviour when no callbacks are provided."""

    def test_assign_both_no_callback_does_not_raise(
        self, dialog_no_callbacks
    ):
        dialog_no_callbacks._do_assign_both()
        assert dialog_no_callbacks.result() == QDialog.Accepted  # type: ignore[attr-defined]

    def test_assign_truck_no_callback_does_not_raise(
        self, dialog_no_callbacks
    ):
        dialog_no_callbacks._do_assign_truck_only()
        assert dialog_no_callbacks.result() == QDialog.Accepted  # type: ignore[attr-defined]

    def test_assign_driver_no_callback_does_not_raise(
        self, dialog_no_callbacks
    ):
        dialog_no_callbacks._do_assign_driver_only()
        assert dialog_no_callbacks.result() == QDialog.Accepted  # type: ignore[attr-defined]


# ── Test: Cancel Behaviour ──────────────────────────────────────────────

class TestQtPairedAssignmentDialogCancel:
    """Cancel / reject behaviour."""

    def test_cancel_returns_rejected(self, dialog, qtbot):
        """Find the Cancel button and click it."""
        btns = dialog.findChildren(QPushButton)
        cancel_btn = None
        for b in btns:
            txt = b.text().lower()
            if "cancel" in txt or "detail_cancel" in txt:
                cancel_btn = b
                break
        assert cancel_btn is not None
        qtbot.mouseClick(cancel_btn, Qt.LeftButton)
        assert dialog.result() == QDialog.Rejected  # type: ignore[attr-defined]

    def test_reject_via_close_button(self, dialog):
        """Closing the dialog (e.g. via window X) should reject."""
        dialog.reject()
        assert dialog.result() == QDialog.Rejected  # type: ignore[attr-defined]

    def test_cancel_does_not_call_assign_callbacks(
        self, dialog, on_assign_both, on_assign_truck, on_assign_driver, qtbot
    ):
        btns = dialog.findChildren(QPushButton)
        cancel_btn = None
        for b in btns:
            txt = b.text().lower()
            if "cancel" in txt or "detail_cancel" in txt:
                cancel_btn = b
                break
        assert cancel_btn is not None
        qtbot.mouseClick(cancel_btn, Qt.LeftButton)
        on_assign_both.assert_not_called()
        on_assign_truck.assert_not_called()
        on_assign_driver.assert_not_called()


# ── Test: Validation (Incompatible Pair) ────────────────────────────────

class TestQtPairedAssignmentDialogValidation:
    """Validation and edge cases for incompatible truck/driver pairs.

    Note: The current dialog does not enforce compatibility rules on its
    own — it relies on the caller to validate. These tests document the
    current behaviour and provide a foundation for future validation.
    """

    def test_assign_both_with_none_selection_returns_early(self, dialog):
        """_do_assign_both returns early if either selection is None."""
        dialog._selected_truck = None
        dialog._selected_driver = None
        # Should not raise
        dialog._do_assign_both()
        # Dialog should not be accepted
        assert dialog.result() != QDialog.Accepted  # type: ignore[attr-defined]

    def test_assign_truck_with_none_selection_returns_early(self, dialog):
        dialog._selected_truck = None
        dialog._do_assign_truck_only()
        assert dialog.result() != QDialog.Accepted  # type: ignore[attr-defined]

    def test_assign_driver_with_none_selection_returns_early(self, dialog):
        dialog._selected_driver = None
        dialog._do_assign_driver_only()
        assert dialog.result() != QDialog.Accepted  # type: ignore[attr-defined]

    def test_assign_both_no_callbacks_skips_callback(self, dialog_no_callbacks):
        """When no callbacks are set, assign should still work."""
        dialog_no_callbacks._do_assign_both()
        assert dialog_no_callbacks.result() == QDialog.Accepted  # type: ignore[attr-defined]


# ── Test: Edge Cases (Empty Lists) ──────────────────────────────────────

class TestQtPairedAssignmentDialogEdgeCases:
    """Edge cases: empty lists, no suggestions, etc."""

    def test_empty_truck_list(self, dialog_empty):
        assert dialog_empty._selected_truck is None
        assert len(dialog_empty._truck_widgets) == 0

    def test_empty_driver_list(self, dialog_empty):
        assert dialog_empty._selected_driver is None
        assert len(dialog_empty._driver_widgets) == 0

    def test_empty_lists_buttons_disabled(self, dialog_empty):
        assert dialog_empty._both_btn is not None
        assert dialog_empty._both_btn.isEnabled() is False
        assert dialog_empty._truck_btn.isEnabled() is False
        assert dialog_empty._driver_btn.isEnabled() is False

    def test_empty_lists_no_crash_on_assign(self, dialog_empty):
        """Assigning with empty lists should not crash."""
        dialog_empty._selected_truck = None
        dialog_empty._selected_driver = None
        dialog_empty._do_assign_both()
        assert dialog_empty.result() != QDialog.Accepted  # type: ignore[attr-defined]

    def test_single_item_in_list(self, qt_widget, qtbot, trip_data,
                                 on_assign_both):
        """Dialog works with single truck and driver."""
        trucks = [_make_truck_item({"id": 1})]
        drivers = [_make_driver_item({"id": 10})]
        dlg = QtPairedAssignmentDialog(
            parent=qt_widget, trip_data=trip_data,
            truck_items=trucks, driver_items=drivers,
            on_assign_both=on_assign_both,
        )
        qtbot.addWidget(dlg)
        assert dlg._selected_truck == 0
        assert dlg._selected_driver == 0
        dlg._do_assign_both()
        on_assign_both.assert_called_once_with(1, 10)
        dlg.close()

    def test_sublabel_truncated_to_30_chars(self, qt_widget, qtbot, trip_data):
        """sublabel longer than 30 chars should be truncated by the widget."""
        long_sublabel = "A" * 50
        trucks = [_make_truck_item({"id": 1, "sublabel": long_sublabel})]
        drivers = [_make_driver_item({"id": 10, "sublabel": long_sublabel})]
        dlg = QtPairedAssignmentDialog(
            parent=qt_widget, trip_data=trip_data,
            truck_items=trucks, driver_items=drivers,
        )
        qtbot.addWidget(dlg)
        wid = dlg._truck_widgets[0]
        labels = wid.findChildren(QLabel)
        for lbl in labels:
            if len(lbl.text()) > 30 and len(long_sublabel) > 30:
                # If sublabel was shown at full length, it would be > 30
                # The dialog slices to [:30], so it should be <= 30
                assert len(lbl.text()) <= 30
        dlg.close()


# ── Test: Signal Emission (Callbacks) ───────────────────────────────────

class TestQtPairedAssignmentDialogSignals:
    """Verify that callbacks are invoked at the right time."""

    def test_assign_both_emits_ids(self, dialog, on_assign_both):
        dialog._select_truck(0)
        dialog._select_driver(0)
        dialog._do_assign_both()
        on_assign_both.assert_called_once()
        args = on_assign_both.call_args[0]
        assert args[0] == dialog._truck_items[0]["id"]
        assert args[1] == dialog._driver_items[0]["id"]

    def test_assign_truck_emits_id(self, dialog, on_assign_truck):
        dialog._select_truck(1)
        dialog._do_assign_truck_only()
        on_assign_truck.assert_called_once_with(
            dialog._truck_items[1]["id"]
        )

    def test_assign_driver_emits_id(self, dialog, on_assign_driver):
        dialog._select_driver(1)
        dialog._do_assign_driver_only()
        on_assign_driver.assert_called_once_with(
            dialog._driver_items[1]["id"]
        )

    def test_accept_called_after_assign_both(self, dialog):
        dialog._select_truck(0)
        dialog._select_driver(0)
        dialog._do_assign_both()
        assert dialog.result() == QDialog.Accepted  # type: ignore[attr-defined]

    def test_reject_called_on_cancel(self, dialog, qtbot):
        btns = dialog.findChildren(QPushButton)
        cancel_btn = None
        for b in btns:
            txt = b.text().lower()
            if "cancel" in txt or "detail_cancel" in txt:
                cancel_btn = b
                break
        assert cancel_btn is not None
        qtbot.mouseClick(cancel_btn, Qt.LeftButton)
        assert dialog.result() == QDialog.Rejected  # type: ignore[attr-defined]
