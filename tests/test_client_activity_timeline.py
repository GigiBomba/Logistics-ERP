"""Tests for the client activity timeline widget."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QLabel

from ui.widgets.client_activity_timeline import QtClientActivityTimeline


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.get_client_trips.return_value = []
    svc.get_client_invoices.return_value = []
    return svc


SAMPLE_TRIPS = [
    {"start_date": "2026-07-01T10:00:00", "truck_number": "AB-01", "status": "completed", "client_name": "Acme", "distance_km": 500},
    {"start_date": "2026-06-28T14:00:00", "truck_number": "AB-02", "status": "planned", "client_name": "Acme", "distance_km": 300},
]
SAMPLE_INVOICES = [
    {"issue_date": "2026-07-02", "invoice_number": "INV-001", "status": "Paid", "total_amount": 2500, "trip_status": "completed"},
    {"issue_date": "2026-07-03", "invoice_number": "INV-002", "status": "Overdue", "total_amount": 1800, "trip_status": "in transit"},
]


class TestQtClientActivityTimelineInit:
    """Construction and basic initialisation."""

    def test_creation_with_service(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        assert widget.layout() is not None
        # _build() is called from __init__, verify service methods were invoked
        mock_service.get_client_trips.assert_called_once_with(1, limit=50)
        mock_service.get_client_invoices.assert_called_once_with(1, limit=50)

    def test_creation_without_service(self, qt_widget, qtbot):
        widget = QtClientActivityTimeline(qt_widget, service=None)
        qtbot.addWidget(widget)
        assert widget.layout() is not None


class TestQtClientActivityTimelineData:
    """Data collection & rendering."""

    def test_collect_events_aggregates_trips_and_invoices(self, qt_widget, qtbot, mock_service):
        mock_service.get_client_trips.return_value = SAMPLE_TRIPS
        mock_service.get_client_invoices.return_value = SAMPLE_INVOICES
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        events = widget._collect_events()
        assert len(events) == 4

    def test_collect_events_no_service(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        widget.service = None
        events = widget._collect_events()
        assert events == []

    def test_collect_events_trips_only(self, qt_widget, qtbot, mock_service):
        mock_service.get_client_trips.return_value = SAMPLE_TRIPS
        mock_service.get_client_invoices.return_value = []
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        events = widget._collect_events()
        assert len(events) == 2
        assert all("Trip:" in e["label"] for e in events)

    def test_collect_events_sorts_by_date_desc(self, qt_widget, qtbot, mock_service):
        mock_service.get_client_trips.return_value = SAMPLE_TRIPS
        mock_service.get_client_invoices.return_value = SAMPLE_INVOICES
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        # Already built in __init__ — verify row order (ts labels descending)
        dates = []
        for i in range(widget.layout().count()):
            row = widget.layout().itemAt(i).widget()
            if row and row.layout():
                ts_label = row.layout().itemAt(2).widget()
                if isinstance(ts_label, QLabel):
                    dates.append(ts_label.text())
        assert dates == sorted(dates, reverse=True), "rows must be sorted ts descending"

    def test_collect_events_limits_to_50_each(self, qt_widget, qtbot, mock_service):
        QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        mock_service.get_client_trips.assert_called_once_with(1, limit=50)
        mock_service.get_client_invoices.assert_called_once_with(1, limit=50)

    def test_build_renders_events(self, qt_widget, qtbot, mock_service):
        mock_service.get_client_trips.return_value = SAMPLE_TRIPS
        mock_service.get_client_invoices.return_value = SAMPLE_INVOICES
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        assert widget.layout().count() == 4

    def test_build_empty_shows_empty_state(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        assert widget.layout().count() == 1
        label = widget.layout().itemAt(0).widget()
        assert isinstance(label, QLabel)
        assert label.text() == "common.no_activity"

    def test_build_limits_to_30_rows(self, qt_widget, qtbot, mock_service):
        many_trips = [
            {"start_date": f"2026-07-{d:02d}T10:00:00", "truck_number": f"T-{d}", "status": "completed", "client_name": "Acme", "distance_km": 100}
            for d in range(1, 41)
        ]
        mock_service.get_client_trips.return_value = many_trips
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        assert widget.layout().count() == 30

    def test_add_event_row_has_dot_and_label_and_date(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        widget._clear_layout()

        ev = {"ts": "2026-07-15T12:00:00", "label": "Test event", "color": "accent"}
        widget._add_event_row(ev)

        row = widget.layout().itemAt(0).widget()
        assert row is not None
        assert row.layout() is not None

        dot = row.layout().itemAt(0).widget()
        assert isinstance(dot, QLabel)
        assert dot.text() == "\u25cf"

        label = row.layout().itemAt(1).widget()
        assert isinstance(label, QLabel)
        assert label.text() == "Test event"

        ts = row.layout().itemAt(2).widget()
        assert isinstance(ts, QLabel)
        assert ts.text() == "2026-07-15"

    def test_clear_layout_removes_all_widgets(self, qt_widget, qtbot, mock_service):
        mock_service.get_client_trips.return_value = SAMPLE_TRIPS
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        # _build() was called during init, so there should be rows
        widget._build()
        assert widget.layout().count() > 0
        widget._clear_layout()
        assert widget.layout().count() == 0


class TestQtClientActivityTimelineHelpers:
    """Static helper methods (_status_color, _resolve_dot_role)."""

    @staticmethod
    def test_status_color_completed():
        assert QtClientActivityTimeline._status_color("completed") == "success"

    @staticmethod
    def test_status_color_in_transit():
        assert QtClientActivityTimeline._status_color("in transit") == "accent"

    @staticmethod
    def test_status_color_loading():
        assert QtClientActivityTimeline._status_color("loading") == "warning"

    @staticmethod
    def test_status_color_cancelled():
        assert QtClientActivityTimeline._status_color("cancelled") == "muted"

    @staticmethod
    def test_status_color_unknown():
        assert QtClientActivityTimeline._status_color("bogus") == "accent"

    @staticmethod
    def test_status_color_empty():
        assert QtClientActivityTimeline._status_color("") == "accent"

    @staticmethod
    def test_status_color_case_insensitive():
        assert QtClientActivityTimeline._status_color("COMPLETED") == "success"

    @staticmethod
    def test_resolve_dot_role_info():
        assert QtClientActivityTimeline._resolve_dot_role("info") == "accent"

    @staticmethod
    def test_resolve_dot_role_passthrough():
        assert QtClientActivityTimeline._resolve_dot_role("success") == "success"
        assert QtClientActivityTimeline._resolve_dot_role("warning") == "warning"


class TestQtClientActivityTimelineLifecycle:
    """refresh / cleanup / destroy lifecycle."""

    def test_refresh_switches_client(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        mock_service.reset_mock()
        mock_service.get_client_trips.return_value = []
        mock_service.get_client_invoices.return_value = []

        widget.refresh(client_id=2)

        assert widget.client_id == 2
        mock_service.get_client_trips.assert_called_once_with(2, limit=50)
        mock_service.get_client_invoices.assert_called_once_with(2, limit=50)

    def test_refresh_no_arg_reuses_client_id(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        mock_service.reset_mock()
        mock_service.get_client_trips.return_value = []
        mock_service.get_client_invoices.return_value = []

        widget.refresh()

        assert widget.client_id == 1
        mock_service.get_client_trips.assert_called_once_with(1, limit=50)

    def test_cleanup_nulls_service(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        widget.cleanup()
        assert widget.service is None

    def test_destroy_calls_cleanup_and_delete(self, qt_widget, qtbot, mock_service):
        widget = QtClientActivityTimeline(qt_widget, service=mock_service, client_id=1)
        qtbot.addWidget(widget)
        widget._destroy()
        assert widget.service is None
