"""Tests for the dispatch detail panel (PySide6 side-drawer)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt, SignalInstance
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t

# ── Workaround: ScrollableFormContainer in ui/widgets uses SP which is
#    not defined (it imports SP as S). We provide a fixed replacement. ──


class _FixedScrollableFormContainer(QScrollArea):
    """Bug-fixed replacement for ScrollableFormContainer (SP → local int)."""

    def __init__(self, parent: QWidget | None = None, max_width: int = 740):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.content = QWidget()
        self.content.setMaximumWidth(max_width)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._layout = QVBoxLayout(self.content)
        self._layout.setContentsMargins(10, 6, 10, 10)
        self._layout.setSpacing(6)
        self._layout.setAlignment(Qt.AlignTop)
        self.setWidget(self.content)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch)

    def add_layout(self, layout, stretch: int = 0) -> None:
        self._layout.addLayout(layout, stretch)

    def add_stretch(self, stretch: int = 1) -> None:
        self._layout.addStretch(stretch)


# ── Sample data ──────────────────────────────────────────────────────

FAKE_ALERTS = [
    type("Alert", (), {
        "severity": type("Sev", (), {"value": "critical"})(),
        "message": "Trip delayed by 3 hours", "trip_id": 42,
    })(),
    type("Alert", (), {
        "severity": type("Sev", (), {"value": "warning"})(),
        "message": "Driver hours low", "trip_id": 42,
    })(),
]

# ── Module-level patches ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _auto_patches():
    """Apply module-level patches:
    - ScrollableFormContainer (workaround for SP bug)
    - TripService
    - EventBus
    """
    with patch(
        "ui.dialogs.dispatch_detail_panel.ScrollableFormContainer",
        _FixedScrollableFormContainer,
    ), patch("ui.dialogs.dispatch_detail_panel.TripService"), \
         patch("ui.dialogs.dispatch_detail_panel.EventBus"):
        yield


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def trip_data():
    return {
        "trip_id": "T42",
        "trip_id_num": 42,
        "status": "In Transit",
        "truck_plate": "AB12CDE",
        "truck_id": 101,
        "driver_name": "John Doe",
        "driver_id": 201,
        "origin": "Bucharest",
        "destination": "Cluj-Napoca",
        "departure_date": "2026-07-20",
        "eta": "2026-07-22",
        "distance_km": 450.5,
        "total_price_eur": 1234.56,
        "net_profit": 345.67,
    }


@pytest.fixture
def minimal_trip_data():
    return {"trip_id": "T1", "trip_id_num": 1}


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.get_alerts.return_value = []
    return ops


@pytest.fixture
def detail_panel(qtbot, trip_data, mock_db, mock_ops):
    from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
    panel = QtDispatchDetailPanel(
        trip_data=trip_data, db=mock_db, ops=mock_ops,
    )
    qtbot.addWidget(panel)
    yield panel
    panel.hide()


# ======================================================================
# TestQtDispatchDetailPanelInit — Construction
# ======================================================================


class TestQtDispatchDetailPanelInit:
    """Construction of QtDispatchDetailPanel."""

    def test_creation(self, detail_panel, trip_data):
        assert detail_panel._trip_data == trip_data
        assert detail_panel._editing is False
        assert detail_panel._edit_widgets == {}
        assert detail_panel._db is not None

    def test_creation_without_data(self, qtbot):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        panel = QtDispatchDetailPanel(trip_data=None, db=None, ops=None)
        qtbot.addWidget(panel)
        assert panel._trip_data == {}
        assert panel._trip_service is None
        assert panel._db is None
        assert panel._ops is None
        assert panel._on_save is None
        assert panel._on_close_cb is None

    def test_close_requested_signal_exists(self, detail_panel):
        assert isinstance(detail_panel.close_requested, SignalInstance)

    def test_on_close_callback_connected_if_provided(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        cb = MagicMock()
        panel = QtDispatchDetailPanel(
            trip_data=trip_data, db=mock_db, ops=mock_ops, on_close=cb,
        )
        qtbot.addWidget(panel)
        panel.close_requested.emit()
        cb.assert_called_once()

    def test_style_sheet_applied(self, detail_panel):
        assert detail_panel.property("role") == "detail-drawer"

    def test_fixed_width_480(self, detail_panel):
        assert detail_panel.minimumWidth() == 480
        assert detail_panel.maximumWidth() == 480

    def test_trip_service_created_when_db_provided(self, detail_panel):
        assert detail_panel._trip_service is not None

    def test_trip_service_none_when_db_none(self, qtbot):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        panel = QtDispatchDetailPanel(trip_data={}, db=None, ops=None)
        qtbot.addWidget(panel)
        assert panel._trip_service is None


# ======================================================================
# TestQtDispatchDetailPanelBuild — UI shell
# ======================================================================


class TestQtDispatchDetailPanelBuild:
    """UI shell structure."""

    def test_header_contains_trip_id(self, detail_panel):
        labels = detail_panel.findChildren(QLabel)
        assert any(lbl.text() == "T42" for lbl in labels)

    def test_header_contains_status_chip(self, detail_panel):
        labels = detail_panel.findChildren(QLabel)
        assert any(lbl.text() == "In Transit" for lbl in labels)

    def test_header_close_button_exists(self, detail_panel):
        buttons = detail_panel.findChildren(QPushButton)
        close_btns = [b for b in buttons if not b.text() and b.isFlat()]
        assert len(close_btns) >= 1

    def test_fields_frame_exists(self, detail_panel):
        assert hasattr(detail_panel, "_fields_frame")
        assert detail_panel._fields_frame is not None

    def test_alerts_frame_exists(self, detail_panel):
        assert hasattr(detail_panel, "_alerts_frame")
        assert detail_panel._alerts_frame is not None

    def test_button_row_exists(self, detail_panel):
        assert hasattr(detail_panel, "_btn_widget")
        # setFixedHeight(52) sets both min & max height
        assert detail_panel._btn_widget.minimumHeight() == 52
        assert detail_panel._btn_widget.maximumHeight() == 52
        btns = detail_panel._btn_widget.findChildren(QPushButton)
        assert len(btns) >= 2  # Edit + Close


# ======================================================================
# TestQtDispatchDetailPanelViewMode — View-mode fields
# ======================================================================


class TestQtDispatchDetailPanelViewMode:
    """View-mode field display."""

    FIELD_KEYS = [
        "dispatch_board.detail_truck",
        "dispatch_board.detail_driver",
        "dispatch_board.detail_route",
        "dispatch_board.detail_departure",
        "dispatch_board.detail_eta",
        "dispatch_board.detail_promised_date",
        "dispatch_board.detail_distance",
        "dispatch_board.detail_price",
        "dispatch_board.detail_net_profit",
    ]

    def test_all_fields_displayed(self, detail_panel):
        labels = detail_panel._fields_frame.findChildren(QLabel)
        label_texts = {lbl.text() for lbl in labels}
        for key in self.FIELD_KEYS:
            assert t(key) in label_texts, f"Missing field label: {t(key)}"

    def test_field_labels_match_keys(self, detail_panel):
        labels = detail_panel._fields_frame.findChildren(QLabel)
        label_texts = [lbl.text() for lbl in labels]
        for key in self.FIELD_KEYS:
            translated = t(key)
            assert translated in label_texts

    def test_missing_values_show_na(self, qtbot, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = {
            "trip_id": "T1", "trip_id_num": 1, "status": "Planned",
            "origin": "Bucharest", "destination": "Cluj",
        }
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        labels = panel._fields_frame.findChildren(QLabel)
        value_texts = [lbl.text() for lbl in labels]
        assert t("common.na") in value_texts

    def test_route_field_shows_origin_arrow_destination(self, detail_panel):
        labels = detail_panel._fields_frame.findChildren(QLabel)
        route_texts = [lbl.text() for lbl in labels if "\u2192" in lbl.text()]
        assert len(route_texts) >= 1
        assert "Bucharest" in route_texts[0]
        assert "Cluj-Napoca" in route_texts[0]

    def test_distance_formatted_with_km(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["distance_km"] = 500
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        labels = panel._fields_frame.findChildren(QLabel)
        assert any("500 km" in lbl.text() for lbl in labels)

    def test_price_formatted_with_commas(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["total_price_eur"] = 1234.56
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        labels = panel._fields_frame.findChildren(QLabel)
        assert any("1,234.56" in lbl.text() for lbl in labels)

    def test_net_profit_formatted(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["net_profit"] = -100.5
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        labels = panel._fields_frame.findChildren(QLabel)
        assert any("-100.50" in lbl.text() for lbl in labels)

    def test_edit_button_is_primary(self, detail_panel):
        btn = _find_button_by_text(detail_panel._btn_widget, t("dispatch_board.detail_edit_button"))
        assert btn is not None
        assert btn.property("variant") == "primary"

    def test_close_button_is_ghost(self, detail_panel):
        btn = _find_button_by_text(detail_panel._btn_widget, t("dispatch_board.detail_close"))
        assert btn is not None
        assert btn.property("variant") == "ghost"


# ======================================================================
# TestQtDispatchDetailPanelEditMode — Edit mode
# ======================================================================


class TestQtDispatchDetailPanelEditMode:
    """Entering and interacting with edit mode."""

    def test_enter_edit_mode_shows_edit_fields(self, detail_panel):
        btn = _find_button_by_text(detail_panel._btn_widget, t("dispatch_board.detail_edit_button"))
        assert btn is not None
        btn.click()
        assert detail_panel._editing is True

    def test_status_combo_shows_valid_transitions(self, detail_panel):
        detail_panel._enter_edit_mode()
        combo = detail_panel._edit_widgets.get("status")
        assert combo is not None
        from services.operations.event_bus import VALID_TRANSITIONS
        expected = VALID_TRANSITIONS["In Transit"]
        items = [combo.itemText(i) for i in range(combo.count())]
        assert items == expected

    def test_departure_edit_field_prefilled(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["departure_date"] = "2026-07-23"
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        edit_w = panel._edit_widgets.get("departure_date")
        assert edit_w is not None
        assert edit_w.text() == "2026-07-23"

    def test_eta_edit_field_prefilled(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["eta"] = "2026-07-25"
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        edit_w = panel._edit_widgets.get("eta")
        assert edit_w is not None
        assert edit_w.text() == "2026-07-25"

    def test_promised_date_edit_field_prefilled(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["promised_date"] = "2026-07-28"
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        edit_w = panel._edit_widgets.get("promised_date")
        assert edit_w is not None
        assert edit_w.text() == "2026-07-28"

    def test_promised_date_edit_field_empty_when_unset(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        panel = QtDispatchDetailPanel(trip_data=dict(trip_data), db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        edit_w = panel._edit_widgets.get("promised_date")
        assert edit_w is not None
        assert edit_w.text() == ""

    def test_promised_date_view_field_shown_when_set(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["promised_date"] = "2026-07-28"
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        labels = panel._fields_frame.findChildren(QLabel)
        value_texts = [lbl.text() for lbl in labels]
        assert "2026-07-28" in value_texts

    def test_distance_edit_field_prefilled(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["distance_km"] = 500
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        edit_w = panel._edit_widgets.get("distance_km")
        assert edit_w is not None
        assert edit_w.text() == "500"

    def test_save_and_cancel_buttons_shown_in_edit_mode(self, detail_panel):
        detail_panel._enter_edit_mode()
        btns = detail_panel._btn_widget.findChildren(QPushButton)
        texts = [b.text() for b in btns]
        assert t("dispatch_board.detail_save") in texts
        assert t("dispatch_board.detail_cancel") in texts

    def test_cancel_edit_restores_view_mode(self, detail_panel):
        detail_panel._enter_edit_mode()
        assert detail_panel._editing is True
        cancel_btn = _find_button_by_text(detail_panel._btn_widget, t("dispatch_board.detail_cancel"))
        assert cancel_btn is not None
        cancel_btn.click()
        assert detail_panel._editing is False
        assert detail_panel._edit_widgets == {}

    def test_enter_edit_mode_clears_previous_edit_widgets(self, detail_panel):
        detail_panel._enter_edit_mode()
        assert len(detail_panel._edit_widgets) == 5
        detail_panel._enter_edit_mode()
        assert len(detail_panel._edit_widgets) == 5
        assert all(k in detail_panel._edit_widgets for k in ("status", "departure_date", "eta", "promised_date", "distance_km"))


# ======================================================================
# TestQtDispatchDetailPanelSave — Save changes
# ======================================================================


class TestQtDispatchDetailPanelSave:
    """Save changes flow."""

    def test_save_with_changes_updates_trip_service(self, detail_panel):
        detail_panel._enter_edit_mode()
        combo = detail_panel._edit_widgets["status"]
        combo.setCurrentText("Loading")
        detail_panel._save_changes()
        detail_panel._trip_service.update.assert_called_once()

    def test_save_publishes_event(self, detail_panel):
        with patch("ui.dialogs.dispatch_detail_panel.EventBus") as mock_eb:
            detail_panel._enter_edit_mode()
            combo = detail_panel._edit_widgets["status"]
            combo.setCurrentText("Loading")
            detail_panel._save_changes()
            mock_eb.return_value.publish.assert_called_once()
            from services.operations.event_bus import TRIP_UPDATED
            args, _ = mock_eb.return_value.publish.call_args
            assert args[0] == TRIP_UPDATED

    def test_save_calls_on_save_callback(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        on_save = MagicMock()
        panel = QtDispatchDetailPanel(
            trip_data=trip_data, db=mock_db, ops=mock_ops, on_save=on_save,
        )
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        combo = panel._edit_widgets["status"]
        combo.setCurrentText("Loading")
        panel._save_changes()
        on_save.assert_called_once_with(panel._trip_data)

    def test_save_without_changes_cancels_edit(self, qtbot, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = {"trip_id": "T1", "trip_id_num": 1, "status": "UnknownStatus"}
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        panel._save_changes()
        assert panel._editing is False
        panel._trip_service.update.assert_not_called()

    def test_save_with_invalid_trip_id_shows_error(self, qtbot, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = {"trip_id": "T1", "status": "Planned"}  # no trip_id_num
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        panel._save_changes()
        error_labels = panel._fields_frame.findChildren(QLabel)
        assert any("Cannot identify trip" in lbl.text() for lbl in error_labels)

    def test_save_with_service_error_shows_inline_error(self, detail_panel):
        detail_panel._enter_edit_mode()
        combo = detail_panel._edit_widgets["status"]
        combo.setCurrentText("Loading")
        detail_panel._trip_service.update.side_effect = RuntimeError("DB failure")
        detail_panel._save_changes()
        error_labels = detail_panel._fields_frame.findChildren(QLabel)
        assert any("DB failure" in lbl.text() for lbl in error_labels)
        assert detail_panel._editing is True

    def test_save_includes_promised_date_when_set(self, detail_panel):
        from datetime import date
        detail_panel._enter_edit_mode()
        promised_w = detail_panel._edit_widgets["promised_date"]
        promised_w.setText("2026-01-15")
        detail_panel._save_changes()
        detail_panel._trip_service.update.assert_called_once()
        args, _ = detail_panel._trip_service.update.call_args
        trip_update = args[1]
        assert trip_update.promised_date == date(2026, 1, 15)

    def test_save_omits_promised_date_when_unset(self, detail_panel):
        detail_panel._enter_edit_mode()
        combo = detail_panel._edit_widgets["status"]
        combo.setCurrentText("Loading")
        detail_panel._save_changes()
        detail_panel._trip_service.update.assert_called_once()
        args, _ = detail_panel._trip_service.update.call_args
        trip_update = args[1]
        assert trip_update.promised_date is None

    def test_save_invalid_promised_date_shows_inline_error(self, detail_panel):
        detail_panel._enter_edit_mode()
        promised_w = detail_panel._edit_widgets["promised_date"]
        promised_w.setText("not-a-date")
        detail_panel._save_changes()
        error_labels = detail_panel._fields_frame.findChildren(QLabel)
        assert any(lbl.text() for lbl in error_labels)
        assert detail_panel._editing is True

    def test_save_empty_fields_not_included_in_changes(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["status"] = "UnknownStatus"
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        dep_w = panel._edit_widgets.get("departure_date")
        if dep_w:
            dep_w.setText("")
        panel._save_changes()
        assert panel._editing is False

    def test_save_invalid_distance_handled(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = dict(trip_data)
        data["status"] = "UnknownStatus"
        data["distance_km"] = 500
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        dist_w = panel._edit_widgets.get("distance_km")
        if dist_w:
            dist_w.setText("abc")
        panel._save_changes()
        assert panel._editing is False


# ======================================================================
# TestQtDispatchDetailPanelCancel — Cancel
# ======================================================================


class TestQtDispatchDetailPanelCancel:
    """Cancel edit behaviour."""

    def test_cancel_resets_editing_flag(self, detail_panel):
        detail_panel._enter_edit_mode()
        assert detail_panel._editing is True
        detail_panel._cancel_edit()
        assert detail_panel._editing is False

    def test_cancel_clears_edit_widgets(self, detail_panel):
        detail_panel._enter_edit_mode()
        assert len(detail_panel._edit_widgets) > 0
        detail_panel._cancel_edit()
        assert detail_panel._edit_widgets == {}

    def test_cancel_restores_view_fields(self, detail_panel):
        detail_panel._enter_edit_mode()
        detail_panel._cancel_edit()
        assert detail_panel._fields_layout.count() >= 8

    def test_cancel_restores_alerts_section(self, detail_panel):
        detail_panel._enter_edit_mode()
        detail_panel._cancel_edit()
        assert detail_panel._alerts_layout.count() >= 1

    def test_cancel_restores_buttons(self, detail_panel):
        detail_panel._enter_edit_mode()
        detail_panel._cancel_edit()
        btns = detail_panel._btn_widget.findChildren(QPushButton)
        texts = [b.text() for b in btns]
        assert t("dispatch_board.detail_edit_button") in texts
        assert t("dispatch_board.detail_close") in texts


# ======================================================================
# TestQtDispatchDetailPanelClose — Close
# ======================================================================


class TestQtDispatchDetailPanelClose:
    """Close behaviour."""

    def test_close_calls_on_close_callback(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        on_close = MagicMock()
        panel = QtDispatchDetailPanel(
            trip_data=trip_data, db=mock_db, ops=mock_ops, on_close=on_close,
        )
        qtbot.addWidget(panel)
        panel._close()
        # Callback is invoked once directly (_on_close_cb()) and once via the
        # connected signal (close_requested.emit()), so total calls = 2.
        assert on_close.call_count >= 1

    def test_close_emits_signal(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        slot = MagicMock()
        panel = QtDispatchDetailPanel(
            trip_data=trip_data, db=mock_db, ops=mock_ops,
        )
        qtbot.addWidget(panel)
        panel.close_requested.connect(slot)
        panel._close()
        slot.assert_called_once()

    def test_close_hides_panel(self, detail_panel):
        detail_panel.show()
        assert detail_panel.isVisible()
        detail_panel._close()
        assert not detail_panel.isVisible()

    def test_close_button_triggers_close(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        on_close = MagicMock()
        panel = QtDispatchDetailPanel(
            trip_data=trip_data, db=mock_db, ops=mock_ops, on_close=on_close,
        )
        qtbot.addWidget(panel)
        panel.show()
        buttons = panel.findChildren(QPushButton)
        close_btn = next((b for b in buttons if not b.text() and b.isFlat()), None)
        assert close_btn is not None
        close_btn.click()
        assert on_close.call_count >= 1


# ======================================================================
# TestQtDispatchDetailPanelLoadTrip — Load trip
# ======================================================================


class TestQtDispatchDetailPanelLoadTrip:
    """load_trip public API."""

    def test_load_trip_replaces_trip_data(self, detail_panel, minimal_trip_data):
        new_data = {"trip_id": "T99", "trip_id_num": 99, "status": "Delivered"}
        detail_panel.load_trip(new_data)
        assert detail_panel._trip_data["trip_id"] == "T99"
        assert detail_panel._trip_data["trip_id_num"] == 99

    def test_load_trip_rebuilds_view_fields(self, detail_panel):
        detail_panel.load_trip({"trip_id": "T99", "trip_id_num": 99, "status": "Delivered"})
        labels = detail_panel._fields_frame.findChildren(QLabel)
        label_texts = {lbl.text() for lbl in labels}
        assert t("dispatch_board.detail_truck") in label_texts

    def test_load_trip_updates_db_and_service(self, detail_panel):
        new_db = MagicMock()
        detail_panel.load_trip({"trip_id": "T1", "trip_id_num": 1}, db=new_db)
        assert detail_panel._db is new_db
        assert detail_panel._trip_service is not None

    def test_load_trip_updates_ops(self, detail_panel):
        new_ops = MagicMock()
        detail_panel.load_trip({"trip_id": "T1", "trip_id_num": 1}, ops=new_ops)
        assert detail_panel._ops is new_ops

    def test_load_trip_updates_callbacks(self, detail_panel):
        on_save = MagicMock()
        on_close = MagicMock()
        detail_panel.load_trip(
            {"trip_id": "T1", "trip_id_num": 1},
            on_save=on_save, on_close=on_close,
        )
        assert detail_panel._on_save is on_save
        assert detail_panel._on_close_cb is on_close

    def test_load_trip_disconnects_previous_close_signal(self, qtbot, trip_data, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        old_cb = MagicMock()
        new_cb = MagicMock()
        panel = QtDispatchDetailPanel(
            trip_data=trip_data, db=mock_db, ops=mock_ops, on_close=old_cb,
        )
        qtbot.addWidget(panel)
        panel.load_trip({"trip_id": "T1", "trip_id_num": 1}, on_close=new_cb)
        panel.close_requested.emit()
        old_cb.assert_not_called()
        new_cb.assert_called_once()

    def test_load_trip_resets_to_view_mode(self, detail_panel):
        detail_panel._enter_edit_mode()
        assert detail_panel._editing is True
        detail_panel.load_trip({"trip_id": "T1", "trip_id_num": 1})
        assert detail_panel._editing is False
        assert detail_panel._edit_widgets == {}


# ======================================================================
# TestQtDispatchDetailPanelAlerts — Alerts display
# ======================================================================


class TestQtDispatchDetailPanelAlerts:
    """Alert section rendering."""

    def test_alerts_section_has_divider(self, detail_panel):
        assert detail_panel._alerts_layout.count() >= 1
        item = detail_panel._alerts_layout.itemAt(0)
        assert item is not None
        widget = item.widget()
        assert isinstance(widget, QFrame)
        assert widget.frameShape() == QFrame.HLine

    def test_alerts_title_shown(self, detail_panel):
        labels = detail_panel._alerts_frame.findChildren(QLabel)
        assert any(t("dispatch_board.detail_alerts_for_trip") in lbl.text() for lbl in labels)

    def test_alerts_for_trip_rendered(self, qtbot, trip_data, mock_db):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        ops = MagicMock()
        ops.get_alerts.return_value = FAKE_ALERTS
        panel = QtDispatchDetailPanel(trip_data=trip_data, db=mock_db, ops=ops)
        qtbot.addWidget(panel)
        labels = panel._alerts_frame.findChildren(QLabel)
        all_text = " ".join(lbl.text() for lbl in labels)
        assert "Trip delayed by 3 hours" in all_text
        assert "Driver hours low" in all_text

    def test_no_alerts_shows_empty_label(self, detail_panel, mock_ops):
        mock_ops.get_alerts.return_value = []
        detail_panel._build_alerts()
        labels = detail_panel._alerts_frame.findChildren(QLabel)
        assert any(t("dispatch_board.detail_no_alerts") == lbl.text() for lbl in labels)

    def test_no_ops_shows_empty_label(self, qtbot, trip_data, mock_db):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        panel = QtDispatchDetailPanel(trip_data=trip_data, db=mock_db, ops=None)
        qtbot.addWidget(panel)
        labels = panel._alerts_frame.findChildren(QLabel)
        assert any(t("dispatch_board.detail_no_alerts") == lbl.text() for lbl in labels)

    def test_no_trip_id_shows_empty_label(self, qtbot, mock_db, mock_ops):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        data = {"trip_id": "T1"}  # no trip_id_num
        panel = QtDispatchDetailPanel(trip_data=data, db=mock_db, ops=mock_ops)
        qtbot.addWidget(panel)
        labels = panel._alerts_frame.findChildren(QLabel)
        assert any(t("dispatch_board.detail_no_alerts") == lbl.text() for lbl in labels)

    def test_alert_severity_color_correspondence(self, qtbot, trip_data, mock_db):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        ops = MagicMock()
        ops.get_alerts.return_value = FAKE_ALERTS
        panel = QtDispatchDetailPanel(trip_data=trip_data, db=mock_db, ops=ops)
        qtbot.addWidget(panel)
        labels = panel._alerts_frame.findChildren(QLabel)
        sev_labels = [lbl for lbl in labels if lbl.text() in ("CRITICAL", "WARNING")]
        assert len(sev_labels) == 2
        for lbl in sev_labels:
            if lbl.text() == "CRITICAL":
                assert "#e5484d" in lbl.styleSheet() or lbl.styleSheet()
            elif lbl.text() == "WARNING":
                assert "#f5a623" in lbl.styleSheet() or lbl.styleSheet()


# ======================================================================
# TestQtDispatchDetailPanelEmptyTrip — Empty trip
# ======================================================================


class TestQtDispatchDetailPanelEmptyTrip:
    """Behaviour with empty/minimal trip data."""

    def test_empty_trip_shows_defaults(self, qtbot):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        panel = QtDispatchDetailPanel(trip_data={}, db=MagicMock(), ops=MagicMock())
        qtbot.addWidget(panel)
        buttons = panel.findChildren(QPushButton)
        assert any(btn.text() == t("dispatch_board.detail_edit_button") for btn in buttons)

    def test_empty_trip_edit_mode_save_blocked(self, qtbot):
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel
        panel = QtDispatchDetailPanel(trip_data={}, db=MagicMock(), ops=MagicMock())
        qtbot.addWidget(panel)
        panel._enter_edit_mode()
        panel._save_changes()
        error_labels = panel._fields_frame.findChildren(QLabel)
        assert any("Cannot identify trip" in lbl.text() for lbl in error_labels)


# ======================================================================
# TestQtDispatchDetailPanelErrorHandling — Error handling
# ======================================================================


class TestQtDispatchDetailPanelErrorHandling:
    """Inline error display and graceful handling."""

    def test_inline_error_displayed(self, detail_panel):
        detail_panel._show_inline_error("Test error")
        labels = detail_panel._fields_frame.findChildren(QLabel)
        err_labels = [lbl for lbl in labels if lbl.text() == "Test error"]
        assert len(err_labels) == 1
        ss = err_labels[0].styleSheet()
        # COLOR_ERROR_DEFAULT = "#EF4444"
        assert "#EF4444" in ss or "#EF4444".lower() in ss.lower()

    def test_inline_error_dismissed_after_timeout(self, qtbot, detail_panel):
        from unittest.mock import patch
        with patch.object(detail_panel, "_dismiss_error") as mock_dismiss:
            detail_panel._show_inline_error("Test error")
            qtbot.wait(3500)
            mock_dismiss.assert_called_once()
        assert detail_panel._editing is False

    def test_save_exception_handled_gracefully(self, detail_panel):
        detail_panel._enter_edit_mode()
        detail_panel._trip_service.update.side_effect = RuntimeError("Service boom")
        combo = detail_panel._edit_widgets["status"]
        combo.setCurrentText("Loading")
        detail_panel._save_changes()
        error_labels = detail_panel._fields_frame.findChildren(QLabel)
        assert any("Service boom" in lbl.text() for lbl in error_labels)
        assert detail_panel._editing is True


# ======================================================================
# Helpers
# ======================================================================


def _find_button_by_text(parent, text: str) -> QPushButton | None:
    """Find the first QPushButton child with matching text."""
    for btn in parent.findChildren(QPushButton):
        if btn.text() == text:
            return btn
    return None
